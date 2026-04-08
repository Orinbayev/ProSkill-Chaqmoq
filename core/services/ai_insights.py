from __future__ import annotations

import json
import logging
import os
import re
import warnings
from collections import defaultdict
from datetime import date, timedelta
from difflib import SequenceMatcher
from hashlib import md5

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import Center, User
from chaqmoq.models import Ledger
from education.models import Attendance, Enrollment, Payment, PaymentAllocation, StudentGroupHistory, TuitionMonth

try:
    warnings.filterwarnings("ignore", category=FutureWarning, message=".*google\\.generativeai.*")
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional dependency at runtime
    genai = None


logger = logging.getLogger(__name__)

INSIGHT_CACHE_TTL = 60 * 30
ANSWER_CACHE_TTL = 60 * 5
FORECAST_CACHE_TTL = 60 * 30
CHURN_CACHE_TTL = 60 * 10
ANSWER_ENGINE_VERSION = "2026-04-08-v2"

MONTH_NAMES = [
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentyabr",
    "oktyabr",
    "noyabr",
    "dekabr",
]

PLATFORM_MODULES = [
    {
        "name": "Direktor dashboard",
        "description": "Umumiy KPI, moliya, o'qituvchi, o'quvchi, lead, guruh va do'kon ko'rsatkichlarini jamlaydi.",
    },
    {
        "name": "Moliya",
        "description": "Daromad, foyda, xarajat, qarzdorlik, to'lov intizomi va pul oqimini ko'rsatadi.",
    },
    {
        "name": "O'quvchilar",
        "description": "Faol o'quvchilar, davomat, risk, qarzdorlik va roster ma'lumotlarini beradi.",
    },
    {
        "name": "O'qituvchilar",
        "description": "Ustozlar reytingi, health score, daromad va xavf holatini tahlil qiladi.",
    },
    {
        "name": "Guruhlar",
        "description": "Guruhlarning foydasi, qarzi, yopilish tavsiyasi va o'sish potensialini ko'rsatadi.",
    },
    {
        "name": "Leadlar va marketing",
        "description": "Lead manbalari, yo'nalishlar, konversiya va funnel ma'lumotlarini jamlaydi.",
    },
    {
        "name": "Managerlar",
        "description": "Managerlar ishlagan leadlar, konversiya va so'rov natijalarini ko'rsatadi.",
    },
    {
        "name": "Do'kon",
        "description": "Mahsulotlar, xarid so'rovlari, top mahsulotlar va do'kon faolligini ko'rsatadi.",
    },
]

PLATFORM_WORKFLOWS = [
    {
        "name": "Lead dan o'quvchiga aylanish",
        "description": "Lead manba va yo'nalish bilan yaratiladi, managerga biriktiriladi, keyin o'quvchiga aylantirilsa marketing konversiyasi va dashboard statistikasi yangilanadi.",
    },
    {
        "name": "Davomat va o'qituvchi ulushi",
        "description": "Davomat qo'yilganda TeacherIncome yozuvi hisoblanadi. Shu sabab ustozning ulushi davomat sanasi va guruh narxiga qarab real vaqtda moliya ko'rsatkichlariga ta'sir qiladi.",
    },
    {
        "name": "To'lov va qarzdorlik",
        "description": "To'lovlar enrollment va tuition oylariga ulanadi, shundan daromad, to'lov bajarilishi va qarzdorlik ko'rsatkichlari hisoblanadi.",
    },
    {
        "name": "Guruh health score",
        "description": "Guruhlar daromad, foyda, qarz, davomad va yopilish tavsiyasi bo'yicha reyting qilinadi.",
    },
    {
        "name": "Do'kon va so'rovlar",
        "description": "Mahsulotlar katalogi, purchase request va xarajatlar do'kon faolligi bilan birga kuzatiladi.",
    },
]

METRIC_GLOSSARY = [
    {"name": "Daromad", "description": "Tanlangan davrdagi kirimlar summasi."},
    {"name": "Foyda", "description": "Daromaddan xarajat va ulushlar ayrilgandan keyingi sof natija."},
    {"name": "Qarz", "description": "To'lanmagan oyliklar va ochiq qarzdorlik summasi."},
    {"name": "Faol o'quvchi", "description": "Hozir o'qishni davom ettirayotgan, aktiv enrollmentga ega o'quvchi."},
    {"name": "Lead konversiya", "description": "Leadlarning o'quvchiga aylanish ulushi."},
    {"name": "Teacher health score", "description": "Ustoz daromadi, o'quvchi oqimi va risk ko'rsatkichlari asosidagi umumiy baho."},
]


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _shift_month(day: date, delta: int) -> date:
    month_index = (day.year * 12 + day.month - 1) + delta
    year, month_index = divmod(month_index, 12)
    return date(year, month_index + 1, 1)


def _month_label(day: date) -> str:
    return f"{MONTH_NAMES[day.month - 1]} {day.year}"


def _compact_money(value: int | float) -> str:
    amount = int(value or 0)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 1_000_000_000:
        return f"{sign}{amount / 1_000_000_000:.1f} mlrd so'm"
    if amount >= 1_000_000:
        return f"{sign}{amount / 1_000_000:.1f} mln so'm"
    if amount >= 1_000:
        return f"{sign}{round(amount / 1_000)} ming so'm"
    return f"{sign}{amount} so'm"


def _pct(value) -> str:
    return f"{float(value or 0):.1f}%"


def _signed_pct(value) -> str:
    numeric = float(value or 0)
    prefix = "+" if numeric > 0 else ""
    return f"{prefix}{numeric:.1f}%"


def _extract_json_block(text: str, default):
    raw = (text or "").strip()
    if not raw:
        return default

    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    if fenced:
        raw = fenced.group(1).strip()

    for pattern in (r"\[[\s\S]*\]", r"\{[\s\S]*\}"):
        match = re.search(pattern, raw)
        if not match:
            continue
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
    return default


def _gemini_model():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or genai is None:
        return None
    try:
        genai.configure(api_key=api_key)
        cached_name = cache.get("director-ai-gemini-model")
        if cached_name:
            return genai.GenerativeModel(cached_name)

        available_models = []
        try:
            available_models = [
                model.name
                for model in genai.list_models()
                if "generateContent" in (getattr(model, "supported_generation_methods", []) or [])
            ]
        except Exception:
            logger.warning("Gemini model list could not be loaded", exc_info=True)

        candidates = [
            os.environ.get("GEMINI_MODEL", "").strip(),
            "models/gemini-2.0-flash",
            "models/gemini-2.5-flash",
            "models/gemini-flash-latest",
        ]
        for candidate in candidates:
            if not candidate:
                continue
            normalized = candidate if candidate.startswith("models/") else f"models/{candidate}"
            if available_models and normalized not in available_models:
                continue
            cache.set("director-ai-gemini-model", normalized, 60 * 60)
            return genai.GenerativeModel(normalized)
        if available_models:
            selected = available_models[0]
            cache.set("director-ai-gemini-model", selected, 60 * 60)
            return genai.GenerativeModel(selected)
        return None
    except Exception:
        logger.warning("Gemini model configuration failed", exc_info=True)
        return None


def _prompt_json(prompt: str, *, default, cache_key: str | None = None, ttl: int = INSIGHT_CACHE_TTL):
    if cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, "cache"

    model = _gemini_model()
    if not model:
        return default, "fallback"

    try:
        response = model.generate_content(prompt)
        parsed = _extract_json_block(getattr(response, "text", ""), default)
        if cache_key:
            cache.set(cache_key, parsed, ttl)
        return parsed, "gemini"
    except Exception as exc:
        logger.warning("Gemini prompt failed: %s", exc)
        return default, "fallback"


def _prompt_text(prompt: str, *, default: str, cache_key: str | None = None, ttl: int = ANSWER_CACHE_TTL):
    if cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, "cache"

    model = _gemini_model()
    if not model:
        return default, "fallback"

    try:
        response = model.generate_content(prompt)
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            return default, "fallback"
        if cache_key:
            cache.set(cache_key, text, ttl)
        return text, "gemini"
    except Exception as exc:
        logger.warning("Gemini answer request failed: %s", exc)
        return default, "fallback"


def _stats_digest(stats: dict) -> str:
    try:
        payload = json.dumps(stats, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        payload = str(stats)
    return md5(payload.encode("utf-8")).hexdigest()


def _history_digest(history: list[dict] | None) -> str:
    try:
        payload = json.dumps(history or [], ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        payload = str(history or [])
    return md5(payload.encode("utf-8")).hexdigest()


def _normalize_question(text: str) -> str:
    normalized = (
        str(text or "")
        .strip()
        .lower()
        .replace("’", "'")
        .replace("`", "'")
        .replace("yoʻ", "yo'")
        .replace("oʻ", "o'")
        .replace("gʻ", "g'")
    )
    replacements = (
        (r"\bo['']?tkan\b", "o'tgan"),
        (r"\botkan\b", "o'tgan"),
        (r"\bfodya\b", "foyda"),
        (r"\bfoda\b", "foyda"),
        (r"\bfoida\b", "foyda"),
        (r"\boquvchi\b", "o'quvchi"),
        (r"\boqtuvchi\b", "o'qituvchi"),
        (r"\bqarzdorli[kq]\b", "qarzdorlik"),
        (r"\bdaromat\b", "daromad"),
    )
    for pattern, repl in replacements:
        normalized = re.sub(pattern, repl, normalized)
    return normalized


def _question_tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9']+", _normalize_question(text)) if token]


def _token_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _question_has(text: str, *variants: str, threshold: float = 0.78) -> bool:
    normalized_text = _normalize_question(text)
    tokens = _question_tokens(normalized_text)

    for variant in variants:
        norm_variant = _normalize_question(variant)
        if not norm_variant:
            continue
        if norm_variant in normalized_text:
            return True
        variant_tokens = _question_tokens(norm_variant)
        if not variant_tokens:
            continue
        matched = True
        for variant_token in variant_tokens:
            if not any(
                token == variant_token
                or (
                    abs(len(token) - len(variant_token)) <= 2
                    and _token_similarity(token, variant_token) >= threshold
                )
                for token in tokens
            ):
                matched = False
                break
        if matched:
            return True
    return False


def _is_social_prompt(text: str) -> bool:
    return _question_has(
        text,
        "salom",
        "assalomu alaykum",
        "hello",
        "rahmat",
        "thanks",
        "ok",
        "yaxshi",
        "qalesan",
        "qandaysan",
        "nima qilyapsan",
    )


def _should_link_history(text: str) -> bool:
    if _is_social_prompt(text):
        return False
    return _question_has(
        text,
        "chi",
        "unda",
        "u",
        "shu",
        "keyinchi",
        "keyin",
        "qancha",
        "qaysi",
        "kim",
        "nechi",
        "nima",
    )


def _history_context(history: list[dict] | None, *, limit: int = 8) -> str:
    rows = []
    for item in (history or [])[-limit:]:
        role = "Foydalanuvchi" if item.get("role") == "user" else "AI"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        rows.append(f"{role}: {content}")
    return "\n".join(rows)


def _top_student_by_activity(roster: list[dict]) -> dict:
    if not roster:
        return {}
    ordered = sorted(
        roster,
        key=lambda item: (
            0 if item.get("status_label") == "Faol" else 1,
            -(float(item.get("attendance_value") or -1)),
            float(item.get("risk_score") or 999),
            float(item.get("debt") or 0),
            str(item.get("name") or ""),
        ),
    )
    return ordered[0] if ordered else {}


def _site_context(center: Center, stats: dict) -> dict:
    system = stats.get("system") or {}
    filters = (stats.get("filters") or {}).get("applied") or {}
    finance = stats.get("finance") or {}
    students = stats.get("students") or {}
    teachers = stats.get("teachers") or {}
    groups = stats.get("groups") or {}
    managers = stats.get("managers") or {}
    requests = stats.get("requests") or {}
    marketing = stats.get("marketing") or {}
    executive = stats.get("executive") or {}

    roster = students.get("roster") or []
    top_active_student = _top_student_by_activity(roster)

    return {
        "center": {
            "name": getattr(center, "name", "") or "",
            "slug": getattr(center, "slug", "") or "",
        },
        "period": {
            "date_from": system.get("start_date") or "",
            "date_to": system.get("end_date") or "",
            "last_updated": system.get("last_updated") or "",
        },
        "filters": {
            "branch_ids": filters.get("branch_ids") or [],
            "teacher_ids": filters.get("teacher_ids") or [],
            "category_ids": filters.get("category_ids") or [],
            "group_ids": filters.get("group_ids") or [],
            "source_ids": filters.get("source_ids") or [],
            "payment_types": filters.get("payment_types") or [],
            "debt_status": filters.get("debt_status") or "all",
        },
        "modules": PLATFORM_MODULES,
        "workflows": PLATFORM_WORKFLOWS,
        "metric_glossary": METRIC_GLOSSARY,
        "snapshot": {
            "active_students": int(students.get("active_students") or 0),
            "total_students": int(students.get("total") or 0),
            "teachers_count": int(teachers.get("total_count") or 0),
            "groups_count": int(groups.get("total_count") or 0),
            "managers_count": int(managers.get("total_count") or 0),
            "period_leads": int(marketing.get("total_leads") or 0),
            "all_time_leads": int(marketing.get("all_time_leads") or 0),
            "products_count": int(requests.get("products_count") or 0),
            "requests_count": int(requests.get("total_count") or 0),
            "income": int(finance.get("income") or 0),
            "profit": int(finance.get("profit") or 0),
            "expense": int(finance.get("expense") or finance.get("operating_expense") or 0),
            "open_debt": int(finance.get("open_debt") or 0),
        },
        "top_items": {
            "active_student": {
                "name": top_active_student.get("name") or "",
                "attendance_value": float(top_active_student.get("attendance_value") or 0),
                "risk_score": float(top_active_student.get("risk_score") or 0),
                "course": top_active_student.get("course") or "",
            },
            "teachers": [
                {
                    "name": row.get("teacher_name") or row.get("name") or "",
                    "revenue": int(row.get("revenue") or 0),
                    "health_score": float(row.get("health_score") or 0),
                    "students": int(row.get("students") or 0),
                }
                for row in (teachers.get("ranking") or [])[:5]
            ],
            "groups": [
                {
                    "name": row.get("group_name") or "",
                    "revenue": int(row.get("revenue") or 0),
                    "soft_profit": int(row.get("soft_profit") or 0),
                    "open_debt": int(row.get("open_debt") or 0),
                    "health_score": float(row.get("health_score") or 0),
                }
                for row in (groups.get("profitability") or [])[:5]
            ],
            "sources": [
                {
                    "name": row.get("name") or "",
                    "count": int(row.get("count") or 0),
                    "conversion": float(row.get("conversion") or row.get("student_conversion") or 0),
                    "revenue": int(row.get("revenue") or 0),
                }
                for row in (marketing.get("sources") or [])[:5]
            ],
            "directions": [
                {
                    "name": row.get("name") or "",
                    "count": int(row.get("count") or 0),
                    "active_students": int(row.get("active_students") or 0),
                    "conversion": float(row.get("conversion") or row.get("student_conversion") or 0),
                }
                for row in (marketing.get("directions") or [])[:5]
            ],
            "managers": [
                {
                    "name": row.get("manager_name") or "",
                    "leads": int(row.get("leads") or 0),
                    "converted": int(row.get("converted") or 0),
                    "productivity_score": float(row.get("productivity_score") or 0),
                }
                for row in (managers.get("ranking") or [])[:5]
            ],
            "products": [
                {
                    "name": row.get("name") or "",
                    "count": int(row.get("count") or 0),
                    "qty": int(row.get("qty") or 0),
                }
                for row in (requests.get("top_products") or [])[:5]
            ],
        },
        "focus_items": executive.get("focus_items") or [],
    }


def _compact_context(stats: dict) -> dict:
    finance = stats.get("finance", {})
    students = stats.get("students", {})
    teachers = stats.get("teachers", {})
    groups = stats.get("groups", {})
    marketing = stats.get("marketing", {})
    plans = stats.get("plans", {})
    executive = stats.get("executive", {})
    top_teacher = (teachers.get("ranking") or [{}])[0]
    weak_teacher = sorted(teachers.get("ranking") or [], key=lambda item: item.get("health_score", 0))[:1]
    top_risk = (students.get("risk_students") or [{}])[0]
    best_source = marketing.get("best_source") or {}
    close_candidate = (groups.get("close_candidates") or [{}])[:1]

    return {
        "finance": {
            "income": int(finance.get("income") or 0),
            "income_previous": int(finance.get("income_previous") or 0),
            "income_growth": float(finance.get("income_growth") or 0),
            "profit": int(finance.get("profit") or 0),
            "profit_margin": float(finance.get("profit_margin") or 0),
            "open_debt": int(finance.get("open_debt") or 0),
            "debtors_count": int(finance.get("debtors_count") or 0),
            "payment_completion_rate": float(finance.get("payment_completion_rate") or 0),
        },
        "students": {
            "active_students": int(students.get("active_students") or 0),
            "new_count": int(students.get("new_count") or 0),
            "risk_count": len([item for item in students.get("risk_students") or [] if float(item.get("risk_score") or 0) >= 60]),
            "top_risk_student": {
                "name": top_risk.get("name") or "",
                "risk_score": float(top_risk.get("risk_score") or 0),
                "debt": int(top_risk.get("debt") or 0),
                "reason": top_risk.get("reason") or "",
            },
        },
        "teachers": {
            "best_teacher": {
                "name": top_teacher.get("teacher_name") or "",
                "revenue": int(top_teacher.get("revenue") or 0),
                "health_score": float(top_teacher.get("health_score") or 0),
            },
            "weak_teacher": {
                "name": (weak_teacher[0].get("teacher_name") if weak_teacher else "") or "",
                "revenue": int((weak_teacher[0].get("revenue") if weak_teacher else 0) or 0),
                "health_score": float((weak_teacher[0].get("health_score") if weak_teacher else 0) or 0),
            },
        },
        "marketing": {
            "new_leads": int(marketing.get("total_leads") or 0),
            "conversion_rate": float(marketing.get("conversion_rate") or 0),
            "best_source": {
                "name": best_source.get("name") or "",
                "conversion": float(best_source.get("conversion") or 0),
                "revenue": int(best_source.get("revenue") or 0),
            },
        },
        "plans": {
            "finance_pct": float((plans.get("finance") or {}).get("pct") or 0),
            "students_pct": float((plans.get("students") or {}).get("pct") or 0),
            "marketing_pct": float((plans.get("marketing") or {}).get("pct") or 0),
        },
        "groups": {
            "close_candidate": {
                "group_name": (close_candidate[0].get("group_name") if close_candidate else "") or "",
                "health_score": float((close_candidate[0].get("health_score") if close_candidate else 0) or 0),
                "primary_action": (close_candidate[0].get("primary_action") if close_candidate else "") or "",
            },
        },
        "trend_signal": executive.get("trend_signal") or {},
        "period": {
            "date_from": (stats.get("system") or {}).get("start_date") or "",
            "date_to": (stats.get("system") or {}).get("end_date") or "",
        },
    }


def _parse_period_day(raw) -> date | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _period_phrase(question: str, period: dict) -> str:
    q = _normalize_question(question)
    date_from = _parse_period_day(period.get("date_from"))
    date_to = _parse_period_day(period.get("date_to"))
    today = timezone.localdate()

    if date_from and date_to and date_from == date_to:
        if "kecha" in q or "kechagi" in q:
            return "Kecha"
        if any(token in q for token in ["bugun", "bugungi"]) or date_from == today:
            return "Bugun"
        return f"{date_from.isoformat()} kuni"

    if any(token in q for token in ["o'tgan oy", "otgan oy", "oldingi oy"]):
        return "O'tgan oyda"
    if any(token in q for token in ["shu oy", "joriy oy", "bu oy"]):
        return "Joriy oyda"
    if any(token in q for token in ["shu hafta", "joriy hafta", "bu hafta"]):
        return "Joriy haftada"

    start = period.get("date_from") or ""
    end = period.get("date_to") or ""
    if start and end:
        return f"{start} dan {end} gacha oralig'ida"
    return "Tanlangan davrda"


def _fallback_insights(stats: dict) -> list[dict]:
    ctx = _compact_context(stats)
    finance = ctx["finance"]
    students = ctx["students"]
    teachers = ctx["teachers"]
    marketing = ctx["marketing"]
    plans = ctx["plans"]
    groups = ctx["groups"]

    insights: list[dict] = []
    income_growth = finance["income_growth"]
    if income_growth >= 10:
        insights.append(
            {
                "type": "success",
                "title": "Daromad ijobiy o'smoqda",
                "text": f"Daromad oldingi davrga nisbatan {_signed_pct(income_growth)} ga oshgan. Joriy tushum {_compact_money(finance['income'])}.",
            }
        )
    elif income_growth < 0:
        insights.append(
            {
                "type": "warning",
                "title": "Daromad pasaygan",
                "text": f"Daromad {_signed_pct(income_growth)} ga pasaygan. Ochiq qarz {_compact_money(finance['open_debt'])} bo'lib turibdi.",
            }
        )
    else:
        insights.append(
            {
                "type": "info",
                "title": "Daromad barqaror",
                "text": f"Daromad keskin o'zgarmagan, joriy ko'rsatkich {_compact_money(finance['income'])}.",
            }
        )

    if students["top_risk_student"]["name"]:
        insights.append(
            {
                "type": "warning" if students["top_risk_student"]["risk_score"] >= 60 else "info",
                "title": "Xavfli o'quvchi kuzatuvda",
                "text": f"{students['top_risk_student']['name']} uchun risk balli {int(students['top_risk_student']['risk_score'])}. Sabab: {students['top_risk_student']['reason'] or 'davomat va to‘lov signallari'}.",
            }
        )

    if teachers["best_teacher"]["name"]:
        insights.append(
            {
                "type": "success",
                "title": "Eng kuchli ustoz",
                "text": f"{teachers['best_teacher']['name']} hozir yetakchi: {_compact_money(teachers['best_teacher']['revenue'])} daromad va {int(teachers['best_teacher']['health_score'])} ball.",
            }
        )
    if teachers["weak_teacher"]["name"] and teachers["weak_teacher"]["name"] != teachers["best_teacher"]["name"]:
        insights.append(
            {
                "type": "warning",
                "title": "E'tibor talab qiladigan ustoz",
                "text": f"{teachers['weak_teacher']['name']} health score bo'yicha pastroqda. Holat bahosi {int(teachers['weak_teacher']['health_score'])} ball.",
            }
        )

    plan_pct = plans["finance_pct"]
    insights.append(
        {
            "type": "success" if plan_pct >= 85 else "warning" if plan_pct < 60 else "info",
            "title": "Oy maqsadi holati",
            "text": f"Daromad rejasi {_pct(plan_pct)} bajarilgan. O'quvchi rejasi {_pct(plans['students_pct'])}, lead rejasi {_pct(plans['marketing_pct'])}.",
        }
    )

    if marketing["best_source"]["name"]:
        insights.append(
            {
                "type": "info",
                "title": "Eng yaxshi manba",
                "text": f"{marketing['best_source']['name']} manbasi yetakchi. Konversiya {_pct(marketing['best_source']['conversion'])} va shu kanaldan {_compact_money(marketing['best_source']['revenue'])} tushum kelgan.",
            }
        )

    if groups["close_candidate"]["group_name"]:
        action_text = groups["close_candidate"]["primary_action"] or "qo'shimcha tekshiruv"
        insights.append(
            {
                "type": "warning",
                "title": "Kuzatuvdagi guruh",
                "text": f"{groups['close_candidate']['group_name']} guruhi nazoratda. Tavsiya: {action_text}.",
            }
        )

    return insights[:5]


def _generate_insights_bundle(center: Center, stats: dict) -> tuple[list[dict], str]:
    ctx = _compact_context(stats)
    cache_key = f"director-ai-insights:{center.id}:{_stats_digest(ctx)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, "cache"

    fallback = _fallback_insights(stats)
    prompt = f"""
Sen o'quv markazi direktori uchun qisqa AI tahlilchi ekansan.
Javob faqat JSON massiv bo'lsin.
Har bir element formati:
{{"type":"warning|info|success","title":"...","text":"..."}}

Qoidalar:
- Faqat o'zbek tilida yoz.
- 4 ta insight yoz.
- Har insight 1-2 jumladan oshmasin.
- Raqamlarni o'zgartirma, faqat berilgan contextdan foydalan.
- Keraksiz kirish yoki xulosa yozma.

Context:
{json.dumps(ctx, ensure_ascii=False, default=str)}
"""
    result, source = _prompt_json(prompt, default=fallback, cache_key=None)
    cleaned: list[dict] = []
    if isinstance(result, list):
        for item in result:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            cleaned.append(
                {
                    "type": item.get("type") if item.get("type") in {"warning", "info", "success"} else "info",
                    "title": str(item.get("title") or "AI xulosa").strip(),
                    "text": text,
                }
            )
    if not cleaned:
        cleaned = fallback
        source = "fallback"
    cache.set(cache_key, cleaned, INSIGHT_CACHE_TTL)
    return cleaned, source


def generate_insights(center, stats: dict) -> list[dict]:
    insights, _ = _generate_insights_bundle(center, stats)
    return insights


def generate_insights_bundle(center, stats: dict) -> tuple[list[dict], str]:
    return _generate_insights_bundle(center, stats)


def _tuition_debt_map(center: Center, *, as_of: date, student_ids: list[int]) -> dict[int, int]:
    active_enrollments = list(
        Enrollment.objects.filter(
            center=center,
            student_id__in=student_ids,
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
        ).values("id", "student_id")
    )
    if not active_enrollments:
        return {}

    enrollment_ids = [row["id"] for row in active_enrollments]
    tuition_rows = list(
        TuitionMonth.objects.filter(
            enrollment_id__in=enrollment_ids,
            month__lte=_month_start(as_of),
        )
        .order_by("enrollment_id", "month")
        .values("id", "enrollment_id", "month", "fee_amount")
    )
    if not tuition_rows:
        return {}

    tuition_ids = [row["id"] for row in tuition_rows]
    allocations = dict(
        PaymentAllocation.objects.filter(
            tuition_month_id__in=tuition_ids,
            payment__paid_date__lte=as_of,
        )
        .values("tuition_month_id")
        .annotate(total=Sum("amount"))
        .values_list("tuition_month_id", "total")
    )
    student_open_months = defaultdict(int)
    enrollment_student = {row["id"]: row["student_id"] for row in active_enrollments}
    for row in tuition_rows:
        paid = int(allocations.get(row["id"]) or 0)
        fee = int(row["fee_amount"] or 0)
        if max(fee - paid, 0) > 0:
            student_open_months[enrollment_student[row["enrollment_id"]]] += 1
    return dict(student_open_months)


def _status_from_score(score: int) -> tuple[str, str]:
    if score >= 60:
        return "Xavfli", "rose"
    if score >= 30:
        return "Kuzatuv", "amber"
    return "Yaxshi", "emerald"


def _calculate_churn_risk_bundle(
    center: Center,
    *,
    as_of: date | None = None,
    limit: int = 5,
    student_ids: list[int] | None = None,
) -> tuple[list[dict], dict]:
    as_of = as_of or timezone.localdate()
    student_signature = ",".join(str(student_id) for student_id in sorted(student_ids or [])) or "all"
    cache_key = f"director-ai-churn:{center.id}:{as_of.isoformat()}:{limit}:{md5(student_signature.encode('utf-8')).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached["items"], cached["summary"]

    students_qs = User.objects.filter(center=center, role="student", is_archived=False)
    if student_ids:
        students_qs = students_qs.filter(id__in=student_ids)
    students = list(students_qs.only("id", "ism", "familya", "email", "telefon1", "telefon2"))
    if not students:
        summary = {"total": 0, "danger": 0, "watch": 0, "good": 0, "average_score": 0}
        cache.set(cache_key, {"items": [], "summary": summary}, CHURN_CACHE_TTL)
        return [], summary

    student_ids = [student.id for student in students]
    range_start = as_of - timedelta(days=30)
    previous_start = as_of - timedelta(days=60)
    previous_end = as_of - timedelta(days=31)

    absences = dict(
        Attendance.objects.filter(
            center=center,
            student_id__in=student_ids,
            date__range=(range_start, as_of),
        )
        .filter(Q(status="absent_unexcused") | (Q(present=False) & Q(forced=False)))
        .values("student_id")
        .annotate(total=Count("id"))
        .values_list("student_id", "total")
    )
    open_months = _tuition_debt_map(center, as_of=as_of, student_ids=student_ids)
    recent_lightning = dict(
        Ledger.objects.filter(student_id__in=student_ids, sana__date__range=(range_start, as_of))
        .values("student_id")
        .annotate(total=Sum("ball"))
        .values_list("student_id", "total")
    )
    previous_lightning = dict(
        Ledger.objects.filter(student_id__in=student_ids, sana__date__range=(previous_start, previous_end))
        .values("student_id")
        .annotate(total=Sum("ball"))
        .values_list("student_id", "total")
    )
    exit_signals = set(
        StudentGroupHistory.objects.filter(
            center=center,
            student_id__in=student_ids,
            end_date__isnull=False,
            end_date__gte=as_of - timedelta(days=30),
        ).values_list("student_id", flat=True)
    )

    group_names = defaultdict(list)
    for row in Enrollment.objects.filter(
        center=center,
        student_id__in=student_ids,
        is_active=True,
        student__is_archived=False,
        group__is_archived=False,
    ).select_related("group"):
        group_names[row.student_id].append(row.group.nom)

    items: list[dict] = []
    scores: list[int] = []
    for student in students:
        score = 0
        reasons: list[str] = []
        absent_days = int(absences.get(student.id) or 0)
        overdue_months = int(open_months.get(student.id) or 0)
        recent_delta = int(recent_lightning.get(student.id) or 0)
        previous_delta = int(previous_lightning.get(student.id) or 0)

        if absent_days >= 3:
            score += 40
            reasons.append(f"So'nggi 30 kunda {absent_days} marta kelmagan")
        if overdue_months >= 2:
            score += 35
            reasons.append(f"{overdue_months} oylik to'lov yopilmagan")
        if recent_delta < 0 or recent_delta < previous_delta:
            score += 15
            reasons.append("Chaqmoq balansi pasaygan")
        if student.id in exit_signals:
            score += 10
            reasons.append("Guruhdan chiqish signali bor")

        score = max(0, min(100, score))
        status, tone = _status_from_score(score)
        scores.append(score)
        phone = (student.telefon1 or student.telefon2 or "").strip()
        items.append(
            {
                "student_id": student.id,
                "student_name": student.get_full_name() or student.email,
                "phone": phone,
                "call_url": f"tel:{phone}" if phone else "",
                "groups": group_names.get(student.id, []),
                "score": score,
                "status": status,
                "tone": tone,
                "reasons": reasons or ["Holat barqaror"],
                "absent_days": absent_days,
                "overdue_months": overdue_months,
                "lightning_delta": recent_delta,
            }
        )

    items.sort(key=lambda item: (-item["score"], -item["overdue_months"], -item["absent_days"], item["student_name"]))
    top_items = items[:limit]
    summary = {
        "total": len(items),
        "danger": len([item for item in items if item["score"] >= 60]),
        "watch": len([item for item in items if 30 <= item["score"] < 60]),
        "good": len([item for item in items if item["score"] < 30]),
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
    }
    cache.set(cache_key, {"items": top_items, "summary": summary}, CHURN_CACHE_TTL)
    return top_items, summary


def calculate_churn_risk(center) -> list[dict]:
    items, _ = _calculate_churn_risk_bundle(center)
    return items


def calculate_churn_risk_bundle(
    center,
    *,
    as_of: date | None = None,
    limit: int = 5,
    student_ids: list[int] | None = None,
) -> tuple[list[dict], dict]:
    return _calculate_churn_risk_bundle(center, as_of=as_of, limit=limit, student_ids=student_ids)


def _wma(values: list[int]) -> int:
    clean = [int(value or 0) for value in values][-3:]
    if not clean:
        return 0
    weights = list(range(1, len(clean) + 1))
    total_weight = sum(weights)
    weighted_sum = sum(value * weight for value, weight in zip(clean, weights))
    return round(weighted_sum / total_weight)


def _forecast_bundle(center: Center, *, months_ahead: int = 3, anchor_date: date | None = None) -> tuple[list[dict], dict]:
    anchor_date = _month_start(anchor_date or timezone.localdate())
    cache_key = f"director-ai-forecast:{center.id}:{anchor_date.isoformat()}:{months_ahead}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached["items"], cached["summary"]

    first_actual_month = _shift_month(anchor_date, -5)
    last_actual_month = anchor_date
    first_after_anchor = _shift_month(anchor_date, 1)
    last_needed_month = _shift_month(anchor_date, months_ahead)

    payment_rows = list(
        Payment.objects.filter(
            center=center,
            paid_date__gte=first_actual_month,
            paid_date__lt=_shift_month(last_needed_month, 1),
        )
        .annotate(bucket=TruncMonth("paid_date"))
        .values("bucket")
        .annotate(total=Sum("summa"))
        .order_by("bucket")
    )
    payment_map = {row["bucket"].date() if hasattr(row["bucket"], "date") else row["bucket"]: int(row["total"] or 0) for row in payment_rows}

    items: list[dict] = []
    actual_values: list[int] = []
    cursor = first_actual_month
    while cursor <= last_actual_month:
        amount = int(payment_map.get(cursor, 0))
        actual_values.append(amount)
        items.append(
            {
                "month": cursor.strftime("%Y-%m"),
                "label": _month_label(cursor),
                "amount": amount,
                "is_forecast": False,
            }
        )
        cursor = _shift_month(cursor, 1)

    seed_values = actual_values[-3:] if actual_values else [0, 0, 0]
    cursor = first_after_anchor
    forecast_values: list[int] = []
    while len(forecast_values) < months_ahead:
        next_amount = _wma(seed_values)
        forecast_values.append(next_amount)
        items.append(
            {
                "month": cursor.strftime("%Y-%m"),
                "label": _month_label(cursor),
                "amount": int(next_amount),
                "is_forecast": True,
            }
        )
        seed_values = [*seed_values[-2:], next_amount]
        cursor = _shift_month(cursor, 1)

    summary = {
        "next_month_amount": int(forecast_values[0] if forecast_values else 0),
        "anchor_label": _month_label(anchor_date),
        "actual_total": int(sum(actual_values)),
        "forecast_total": int(sum(forecast_values)),
    }
    cache.set(cache_key, {"items": items, "summary": summary}, FORECAST_CACHE_TTL)
    return items, summary


def forecast_revenue(center, months_ahead=3) -> list[dict]:
    items, _ = _forecast_bundle(center, months_ahead=months_ahead)
    return items


def forecast_revenue_bundle(center, *, months_ahead=3, anchor_date: date | None = None) -> tuple[list[dict], dict]:
    return _forecast_bundle(center, months_ahead=months_ahead, anchor_date=anchor_date)


def _fallback_answer(question: str, stats: dict, history: list[dict] | None = None) -> str:
    q = _normalize_question(question)
    if _question_has(q, "salom", "assalomu alaykum", "hello"):
        return (
            "Salom. Men ChaqmoqApp direktori uchun AI yordamchiman. Daromad, foyda, qarz, ustoz, guruh, "
            "o'quvchi, lead va do'kon bo'yicha aniq savol bersangiz darhol javob beraman."
        )

    if _question_has(q, "rahmat", "thanks", "rakhmat"):
        return "Marhamat. Yana savol bo'lsa yozavering, men dashboard bo'yicha aniq javob beraman."

    if len(q.split()) <= 3 and history and _should_link_history(q):
        previous_user = next(
            (
                _normalize_question(item.get("content"))
                for item in reversed(history)
                if item.get("role") == "user" and _normalize_question(item.get("content")) != q
            ),
            "",
        )
        if previous_user:
            q = f"{previous_user} {q}".strip()

    raw_finance = stats.get("finance") or {}
    raw_students = stats.get("students") or {}
    raw_teachers = stats.get("teachers") or {}
    raw_groups = stats.get("groups") or {}
    raw_marketing = stats.get("marketing") or {}
    raw_requests = stats.get("requests") or {}
    raw_managers = stats.get("managers") or {}
    raw_roster = raw_students.get("roster") or []
    ctx = _compact_context(stats)
    finance = ctx["finance"]
    students = ctx["students"]
    teachers = ctx["teachers"]
    marketing = ctx["marketing"]
    groups = ctx["groups"]
    plans = ctx["plans"]
    period = ctx["period"]
    period_label = f"{period['date_from']} dan {period['date_to']} gacha"
    period_intro = _period_phrase(q, period)

    teacher_ranking = raw_teachers.get("ranking") or []
    best_teacher_row = teacher_ranking[0] if teacher_ranking else {}
    weak_teacher_row = sorted(
        teacher_ranking,
        key=lambda item: (float(item.get("health_score") or 0), float(item.get("revenue") or 0)),
    )[0] if teacher_ranking else {}

    group_profitability = raw_groups.get("profitability") or []
    most_indebted_group = raw_groups.get("most_indebted") or {}
    top_profitable_group = (raw_groups.get("top_profitable") or [{}])[0]
    weak_group = sorted(
        group_profitability,
        key=lambda item: (float(item.get("health_score") or 0), float(item.get("soft_profit") or 0)),
    )[0] if group_profitability else {}

    best_source = raw_marketing.get("best_source") or {}
    worst_source = raw_marketing.get("worst_source") or {}
    best_direction = (raw_marketing.get("directions") or [{}])[0]
    top_risk_student = (raw_students.get("risk_students") or [{}])[0]
    top_manager = (raw_managers.get("ranking") or [{}])[0]
    top_product = (raw_requests.get("top_products") or [{}])[0]
    top_active_student = _top_student_by_activity(raw_roster)
    site_scope_requested = any(
        phrase in q
        for phrase in [
            "saytim",
            "chaqmoqapp",
            "platforma",
            "tizim",
            "nima bor",
            "modullar",
            "qaysi bo'lim",
            "qanday bo'lim",
            "hamma narsa",
            "hammasi",
        ]
    )

    if _question_has(q, "yordam", "nima so'rasam bo'ladi", "nimalarni bilasan") and len(q.split()) <= 6:
        return (
            "Savol berishingiz mumkin. Men joriy dashboard filtrlari asosida daromad, qarz, ustoz, guruh, "
            "lead, mahsulot va o'quvchilar bo'yicha aniq javob beraman."
        )

    if site_scope_requested and not any(
        _question_has(q, keyword)
        for keyword in ["daromad", "qarz", "ustoz", "guruh", "lead", "manba", "mahsulot", "o'quvchi"]
    ):
        return (
            f"ChaqmoqApp direktor panelida moliya, o'quvchilar, o'qituvchilar, guruhlar, leadlar, managerlar va do'kon bo'limlari bor. "
            f"{period_label} oralig'ida faol o'quvchilar {int(raw_students.get('active_students') or students['active_students'])} ta, "
            f"ustozlar {int(raw_teachers.get('total_count') or 0)} ta, guruhlar {int(raw_groups.get('total_count') or 0)} ta, "
            f"leadlar {int(raw_marketing.get('total_leads') or marketing['new_leads'])} ta va do'kon so'rovlari {int(raw_requests.get('total_count') or 0)} ta. "
            f"Moliya bo'limida daromad {_compact_money(raw_finance.get('income') or finance['income'])}, foyda {_compact_money(raw_finance.get('profit') or 0)} va ochiq qarz {_compact_money(raw_finance.get('open_debt') or finance['open_debt'])}. "
            "Davomat qo'yilganda ustoz ulushi ham hisoblanadi, leadlar esa manba va yo'nalish kesimida kuzatiladi. "
            "Qaysi bo'lim kerak bo'lsa, alohida aniq raqam bilan ham aytib beraman."
        )

    if _question_has(q, "saytim haqida", "to'liq tahlil", "to'liq ma'lumot", "hammasini ayt", "umumiy holat"):
        return (
            f"{period_label} oralig'ida ChaqmoqApp markazingizda daromad {_compact_money(raw_finance.get('income') or finance['income'])}, "
            f"foyda {_compact_money(raw_finance.get('profit') or 0)}, ochiq qarz {_compact_money(raw_finance.get('open_debt') or finance['open_debt'])}. "
            f"Faol o'quvchilar {int(raw_students.get('active_students') or students['active_students'])} ta, ustozlar {int(raw_teachers.get('total_count') or 0)} ta, "
            f"guruhlar {int(raw_groups.get('total_count') or 0)} ta, leadlar {int(raw_marketing.get('all_time_leads') or 0)} ta va shu davr leadi {int(raw_marketing.get('total_leads') or marketing['new_leads'])} ta. "
            f"Eng kuchli ustoz {teachers['best_teacher']['name'] or 'aniqlanmadi'}, eng samarali lead manbasi {marketing['best_source']['name'] or 'aniqlanmadi'}, "
            f"do'kon bo'limida esa {int(raw_requests.get('products_count') or 0)} ta mahsulot va {int(raw_requests.get('total_count') or 0)} ta so'rov bor."
        )

    if (_question_has(q, "eng faol") and _question_has(q, "o'quvchi")) or (_question_has(q, "eng faol") and _question_has(q, "student")):
        if top_active_student.get("name"):
            course_name = top_active_student.get("course") or "ko'rsatilmagan"
            return (
                f"{period_label} oralig'ida eng faol o'quvchi {top_active_student['name']}. "
                f"Davomati {_pct(top_active_student.get('attendance_value') or 0)}, risk balli {round(float(top_active_student.get('risk_score') or 0), 1)} "
                f"va guruhi {course_name}."
            )
        return "Faollik bo'yicha yetarli o'quvchi ma'lumoti topilmadi."

    if _question_has(q, "eng qarzdor guruh") or (_question_has(q, "qarz", "qarzdor") and _question_has(q, "guruh")):
        if most_indebted_group.get("group_name"):
            return (
                f"{period_label} oralig'ida eng qarzdor guruh {most_indebted_group['group_name']}. "
                f"Ochiq qarzi {_compact_money(most_indebted_group.get('open_debt') or 0)} va qarzdorlik ulushi "
                f"{_pct(most_indebted_group.get('debt_ratio') or 0)}."
            )
        return "Guruhlar bo'yicha qarzdorlik ma'lumoti topilmadi."

    if _question_has(q, "qarz", "qarzdor", "qarzdorlik"):
        return (
            f"{period_intro} ochiq qarz {_compact_money(finance['open_debt'])}. "
            f"Qarzdor o'quvchilar soni {finance['debtors_count']} ta."
        )

    if _question_has(q, "daromad", "tushum", "kirim") and not _question_has(q, "prognoz", "taxmin"):
        return (
            f"{period_intro} daromad {_compact_money(raw_finance.get('income') or finance['income'])}. "
            f"Oldingi davrga nisbatan {_signed_pct(raw_finance.get('income_growth') or finance['income_growth'])} "
            f"o'zgarish bor."
        )

    if _question_has(q, "foyda", "marja"):
        return (
            f"{period_intro} sof foyda {_compact_money(raw_finance.get('profit') or 0)}. "
            f"Marja {_pct(raw_finance.get('profit_margin') or 0)} darajada."
        )

    if _question_has(q, "xarajat", "chiqim"):
        expense_amount = raw_finance.get("expense") or raw_finance.get("operating_expense") or 0
        return (
            f"{period_intro} xarajat {_compact_money(expense_amount)}. "
            f"O'qituvchi ulushi {_compact_money(raw_finance.get('teacher_shares') or 0)} ni tashkil qilgan."
        )

    if _question_has(q, "davomatdan pul", "ustoz puli", "o'qituvchi ulushi", "davomat puli", "davomatga yarasha"):
        return (
            "ChaqmoqAppda ustoz ulushi davomat yozilganda TeacherIncome orqali hisoblanadi. "
            f"{period_intro} jami o'qituvchi ulushi {_compact_money(raw_finance.get('teacher_shares') or 0)} bo'lgan. "
            "Agar kelasi oy sanasiga davomat qo'yilsa, pul ham aynan o'sha oy sanasi bo'yicha yoziladi."
        )

    if _question_has(q, "ustoz", "o'qituvchi", "oqituvchi"):
        if _question_has(q, "yomon", "zaif", "past", "kuchsiz", "eng yomon"):
            if weak_teacher_row.get("teacher_name"):
                return (
                    f"{period_label} oralig'ida eng past ko'rsatkichdagi ustoz {weak_teacher_row['teacher_name']}. "
                    f"Health score {int(weak_teacher_row.get('health_score') or 0)}, daromadi "
                    f"{_compact_money(weak_teacher_row.get('revenue') or 0)}."
                )
            return "Ustozlar bo'yicha past ko'rsatkichli ma'lumot topilmadi."
        if teachers["best_teacher"]["name"]:
            return (
                f"{period_intro} eng kuchli ustoz {teachers['best_teacher']['name']}. "
                f"U {_compact_money(best_teacher_row.get('revenue') or teachers['best_teacher']['revenue'])} daromad olib kelgan, "
                f"health score {int(best_teacher_row.get('health_score') or teachers['best_teacher']['health_score'])}."
            )
        return "Ustozlar bo'yicha yetarli ma'lumot topilmadi."

    if _question_has(q, "yo'nalish", "yonalish"):
        if best_direction.get("name"):
            return (
                f"{period_intro} eng samarali yo'nalish {best_direction['name']}. "
                f"Leadlar soni {int(best_direction.get('count') or 0)} ta, faolga aylangani "
                f"{int(best_direction.get('active_students') or 0)} ta."
            )
        return "Yo'nalishlar bo'yicha ma'lumot yetarli emas."

    if _question_has(q, "lead", "manba", "source"):
        if _question_has(q, "yomon", "past", "eng yomon", "kuchsiz") and worst_source.get("name"):
            return (
                f"{period_intro} eng sust manba {worst_source['name']}. "
                f"Konversiya {_pct(worst_source.get('conversion') or 0)} va tushum {_compact_money(worst_source.get('revenue') or 0)}."
            )
        if marketing["best_source"]["name"]:
            return (
                f"{period_intro} eng samarali manba {marketing['best_source']['name']}. "
                f"Konversiya {_pct(best_source.get('conversion') or marketing['best_source']['conversion'])}, "
                f"tushum {_compact_money(best_source.get('revenue') or marketing['best_source']['revenue'])}."
            )
        return "Lead manbalari bo'yicha yetarli ma'lumot topilmadi."

    if _question_has(q, "guruh"):
        if _question_has(q, "foyda", "daromad", "eng yaxshi", "kuchli") and top_profitable_group.get("group_name"):
            return (
                f"{period_intro} eng kuchli guruh {top_profitable_group['group_name']}. "
                f"Sof foydasi {_compact_money(top_profitable_group.get('soft_profit') or 0)} va daromadi "
                f"{_compact_money(top_profitable_group.get('revenue') or 0)}."
            )
        if groups["close_candidate"]["group_name"] or weak_group.get("group_name"):
            close_group = groups["close_candidate"]["group_name"] and (raw_groups.get("close_candidates") or [{}])[0] or weak_group
            action_text = close_group.get("primary_action") or groups["close_candidate"]["primary_action"] or "qo'shimcha tekshiruv"
            return (
                f"Eng ko'p e'tibor talab qilayotgan guruh {close_group.get('group_name') or groups['close_candidate']['group_name']}. "
                f"Tavsiya: {action_text}."
            )
        return "Guruhlar bo'yicha savol uchun yetarli signal topilmadi."

    if _question_has(q, "xavf", "davomat", "risk"):
        if students["top_risk_student"]["name"] or top_risk_student.get("name"):
            return (
                f"{period_intro} eng xavfli o'quvchi "
                f"{top_risk_student.get('name') or students['top_risk_student']['name']}. "
                f"Risk balli {int(top_risk_student.get('risk_score') or students['top_risk_student']['risk_score'])}, "
                f"qarzi {_compact_money(top_risk_student.get('debt') or students['top_risk_student']['debt'])}."
            )
        return "Xavf bo'yicha alohida signal topilmadi."

    if _question_has(q, "faol o'quvchi", "o'quvchi soni", "student"):
        return (
            f"{period_intro} faol o'quvchilar soni {int(raw_students.get('active_students') or students['active_students'])} ta. "
            f"Yangi qo'shilgan o'quvchilar {int(raw_students.get('new_count') or students['new_count'])} ta."
        )

    if _question_has(q, "maqsad", "reja", "plan"):
        return (
            f"Reja bajarilishi bo'yicha daromad {_pct(plans['finance_pct'])}, faol o'quvchi {_pct(plans['students_pct'])} "
            f"va lead {_pct(plans['marketing_pct'])} darajada."
        )

    if _question_has(q, "mahsulot", "so'rov", "do'kon", "dokon"):
        if _question_has(q, "eng ko'p", "top", "yetakchi", "mashhur") and top_product.get("name"):
            return (
                f"{period_intro} eng ko'p so'ralgan mahsulot {top_product['name']}. "
                f"So'rovlar soni {int(top_product.get('count') or 0)} ta va jami birlik {int(top_product.get('qty') or 0)} ta."
            )
        if _question_has(q, "qanday", "nima bor", "modul", "bo'lim"):
            return (
                "Do'kon bo'limida mahsulotlar katalogi, xarid so'rovlari va xarajatlar nazorati mavjud. "
                f"{period_intro} mahsulotlar soni {int(raw_requests.get('products_count') or 0)} ta, "
                f"so'rovlar soni {int(raw_requests.get('total_count') or 0)} ta."
            )
        return (
            f"{period_intro} do'kon bo'limida {int(raw_requests.get('total_count') or 0)} ta so'rov bor. "
            f"Katalogdagi mahsulotlar soni {int(raw_requests.get('products_count') or 0)} ta."
        )

    if _question_has(q, "manager", "sotuv"):
        if top_manager.get("manager_name"):
            return (
                f"{period_intro} eng faol manager {top_manager['manager_name']}. "
                f"U {int(top_manager.get('leads') or 0)} lead bilan ishlab, {int(top_manager.get('converted') or 0)} tasini konvert qilgan."
            )
        return "Managerlar bo'yicha yetarli ma'lumot topilmadi."

    return (
        f"{period_intro} daromad {_compact_money(finance['income'])}, faol o'quvchilar {students['active_students']} ta, "
        f"yangi leadlar {marketing['new_leads']} ta va daromad rejasi {_pct(plans['finance_pct'])} bajarilgan."
    )


def _answer_bundle(center: Center, question: str, stats: dict, history: list[dict] | None = None) -> tuple[str, str]:
    cleaned_question = (question or "").strip()
    if not cleaned_question:
        return "Savol matni bo'sh bo'lmasligi kerak.", "fallback"

    compact = _compact_context(stats)
    site_ctx = _site_context(center, stats)
    history_tail = (history or [])[-8:]
    cache_key = (
        f"director-ai-answer:{ANSWER_ENGINE_VERSION}:{center.id}:{_stats_digest({'compact': compact, 'site': site_ctx})}:"
        f"{_history_digest(history_tail)}:{md5(cleaned_question.encode('utf-8')).hexdigest()}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, "cache"

    fallback = _fallback_answer(cleaned_question, stats, history=history_tail)
    history_text = _history_context(history_tail)
    prompt = f"""
Sen o'quv markazi direktori yordamchisisan.
Sen ChaqmoqApp platformasini yaxshi biladigan direktor AI yordamchisisan.
Faqat berilgan context asosida javob ber.
Javob o'zbek tilida, sodda, aniq va amaliy bo'lsin.
Javobni eng muhim natija yoki son bilan boshlashga harakat qil.
Savol platforma yoki sayt modullari haqida bo'lsa, platform_knowledge bo'yicha tushuntir.
Savol raqam yoki holat haqida bo'lsa, current_site_snapshot bo'yicha aniq son va nomlarni ayt.
ChaqmoqApp ichidagi ish jarayonlari savol qilinsa workflows va metric_glossary bo'yicha tushuntir.
Ma'lumot yetmasa buni ochiq ayt.
Hech qanday markdown yoki ro'yxat yozma.

Savol: {cleaned_question}

Oxirgi chat konteksti:
{history_text or "Yo'q"}

Platform knowledge:
{json.dumps(site_ctx, ensure_ascii=False, default=str)}

Current site snapshot:
{json.dumps(compact, ensure_ascii=False, default=str)}
"""
    answer, source = _prompt_text(prompt, default=fallback, cache_key=None)
    cache.set(cache_key, answer, ANSWER_CACHE_TTL)
    return answer, source


def answer_question(center, question: str, stats: dict, history: list[dict] | None = None) -> str:
    answer, _ = _answer_bundle(center, question, stats, history=history)
    return answer


def answer_question_bundle(center, question: str, stats: dict, history: list[dict] | None = None) -> tuple[str, str]:
    return _answer_bundle(center, question, stats, history=history)
