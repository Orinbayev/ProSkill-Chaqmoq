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
from core.services.center_ai_context import (
    build_center_ai_context,
    build_center_ai_prompt_context,
    generate_center_alerts,
    get_category_revenue_context,
    get_daily_revenue_for_date,
    get_debt_aging_context,
    get_monthly_stats,
    get_student_full_info,
    get_teacher_full_info,
)
from core.services.center_ai_security import can_view_private_details, guard_cross_center_question, privacy_mode_label
from education.models import Attendance, Enrollment, Payment, PaymentAllocation, StudentGroupHistory, TuitionMonth

try:
    from google import genai as google_genai
except Exception:  # pragma: no cover - optional dependency at runtime
    google_genai = None

try:
    legacy_genai = None
    if google_genai is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import google.generativeai as legacy_genai
except Exception:  # pragma: no cover - optional dependency at runtime
    legacy_genai = None


logger = logging.getLogger(__name__)

INSIGHT_CACHE_TTL = 60 * 30
ANSWER_CACHE_TTL = 60 * 5
FORECAST_CACHE_TTL = 60 * 30
CHURN_CACHE_TTL = 60 * 10
ANSWER_ENGINE_VERSION = "2026-04-09-v4"

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

STRICT_SYSTEM_PROMPT = """
SEN O'QUV MARKAZINING DO'STONA AI YORDAMCHISISAN.

JAVOB STILI (juda muhim):
- QISQA bo'l. Maksimal 3-4 jumla. Foydalanuvchi keyingi savol berib aniqlashtira oladi.
- Sodda, kundalik o'zbek tilida yoz. "Hisoblanadi", "qayd etilgan", "tashkil etmoqda" kabi rasmiy
  iboralarni ishlatma. O'rniga: "bor", "yetakchi", "edi", "ko'ryapman".
- Mos joyda emojidan foydalan: 💰 daromad, 👨‍🏫 ustoz, 👥 guruh, 📊 davomat, ⚠️ ogohlantirish,
  ✅ yaxshi, 🔴 yomon, 📞 telefon, 📚 kurs, 🎯 reja. Ortiqcha emoji qo'yma — javobiga 1-3 ta yetadi.
- Markdown va ro'yxat ishlatma (* yoki - belgilarisiz). Oddiy matn yoki "1) 2)" raqamli ro'yxat ok.
- Agar profil ma'lumoti so'ralsa (telefon, qarz, davomat) — barcha kerakli ma'lumotni 2-3 jumlada
  jamlab ber, kerak bo'lmagan tafsilotni qo'shma.

MA'LUMOT QOIDALARI:
- Faqat CONTEXT asosida javob ber. Tashqi ma'lumot o'ylab topma.
- Multi-tenant: faqat joriy markaz ma'lumotidan foydalan, boshqa markazlarni aralashtirma.
- Taqqoslash savollari ("eng yaxshi ustoz/guruh") uchun CONTEXT dagi raqamlardan foydalanib sortla
  va aniq nom + 1-2 ta asosiy raqamni ber.
- Agar CONTEXT da QIDIRILGAN PROFIL bo'limi bo'lsa, foydalanuvchi shu odam haqida so'rayapti —
  unga aynan shu odam haqida zich javob ber (ism, telefon, kurs, ustoz, qarz, davomat, holat).
- "Yopilishi kerak guruhlar" — kam o'quvchili / 0 daromadli guruhlardan top 3-5 tasini ayt, izoh berma.
- Faqat hech qanday tegishli ma'lumot bo'lmasagina: "Bu haqida ma'lumot topilmadi" deb qisqa ayt.
""".strip()


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


class _GoogleGenAIModel:
    def __init__(self, *, client, candidates: list[str], cache_key: str):
        self.client = client
        self.candidates = candidates
        self.cache_key = cache_key

    def generate_content(self, prompt: str):
        cached = cache.get(self.cache_key)
        candidates = [cached] if cached else []
        candidates.extend([name for name in self.candidates if name and name not in candidates])

        last_exc: Exception | None = None
        for model_name in candidates:
            try:
                response = self.client.models.generate_content(model=model_name, contents=prompt)
                cache.set(self.cache_key, model_name, 60 * 60)
                return response
            except Exception as exc:
                last_exc = exc
                logger.warning("Gemini model failed: provider=google-genai model=%s error=%s", model_name, exc)
        if last_exc:
            raise last_exc
        raise RuntimeError("No Gemini model candidates configured")


class _LegacyGeminiModel:
    def __init__(self, *, candidates: list[str], cache_key: str):
        self.candidates = candidates
        self.cache_key = cache_key

    def generate_content(self, prompt: str):
        cached = cache.get(self.cache_key)
        candidates = [cached] if cached else []
        candidates.extend([name for name in self.candidates if name and name not in candidates])

        last_exc: Exception | None = None
        for model_name in candidates:
            try:
                response = legacy_genai.GenerativeModel(model_name).generate_content(prompt)
                cache.set(self.cache_key, model_name, 60 * 60)
                return response
            except Exception as exc:
                last_exc = exc
                logger.warning("Gemini model failed: provider=legacy model=%s error=%s", model_name, exc)
        if last_exc:
            raise last_exc
        raise RuntimeError("No Gemini model candidates configured")


def _gemini_candidates(*, legacy: bool) -> list[str]:
    raw_candidates = [
        os.environ.get("GEMINI_MODEL", "").strip(),
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-flash-latest",
    ]
    normalized = []
    for candidate in raw_candidates:
        if not candidate:
            continue
        name = candidate.strip()
        if legacy and not name.startswith("models/"):
            name = f"models/{name}"
        if not legacy and name.startswith("models/"):
            name = name.removeprefix("models/")
        if name not in normalized:
            normalized.append(name)
    return normalized


def _gemini_model():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        if google_genai is not None:
            client = google_genai.Client(api_key=api_key)
            return _GoogleGenAIModel(
                client=client,
                candidates=_gemini_candidates(legacy=False),
                cache_key="director-ai-gemini-model-google-genai",
            )

        if legacy_genai is not None:
            legacy_genai.configure(api_key=api_key)
            return _LegacyGeminiModel(
                candidates=_gemini_candidates(legacy=True),
                cache_key="director-ai-gemini-model-legacy",
            )
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
        # Quota / rate limit holatlarida foydalanuvchiga aniq xabar
        msg = str(exc)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            return (
                "⏳ AI hozirda band (kunlik so'rov limiti tugagan). "
                "Bir necha daqiqadan keyin qayta urinib ko'ring yoki Gemini bilingini yoqing.",
                "rate-limited",
            )
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


SEARCH_STOPWORDS = {
    "haqida",
    "malumot",
    "ma'lumot",
    "ber",
    "ayt",
    "ko'rsat",
    "kursi",
    "kurs",
    "telefon",
    "telefoni",
    "raqam",
    "raqami",
    "holati",
    "holat",
    "to'lov",
    "tolov",
    "qarz",
    "qarzi",
    "kim",
    "qaysi",
    "qanaqa",
    "bor",
    "top",
    "topib",
    "menga",
    "shu",
    "bu",
    "o'quvchi",
    "oquvchi",
    "student",
    "ustoz",
    "o'qituvchi",
    "oqituvchi",
    "teacher",
    "markaz",
    "markazda",
    "bizning",
    "bizda",
    "nechta",
    "qancha",
    "jami",
    "soni",
    "bor",
    "ha",
    "bormi",
    "nima",
    "saytim",
    "saytimda",
    "eng",
    "faol",
    "platforma",
    "tizim",
    "modul",
    "modullar",
    "bo'lim",
    "bolim",
}


def _extract_search_query(question: str) -> str:
    raw = str(question or "").strip()
    if not raw:
        return ""

    phone_match = re.search(r"\+?\d[\d\s()\-]{6,}", raw)
    if phone_match:
        return phone_match.group(0).strip()

    normalized = _normalize_question(raw)
    tokens = [token for token in re.split(r"[^a-z0-9']+", normalized) if token]
    filtered = [token for token in tokens if token not in SEARCH_STOPWORDS and len(token) >= 2]
    return " ".join(filtered[:3]).strip()


def _format_student_answer(item: dict) -> str:
    attendance = item.get("attendance") or {}
    course = item.get("course") or "biriktirilmagan"
    teacher_name = item.get("teacher_name") or "biriktirilmagan"
    phone = item.get("phone") or "yo'q"
    student_name = item.get("full_name") or "O'quvchi"
    status_label = item.get("status_label") or "Noma'lum"
    return (
        f"{student_name} haqida ma'lumot: telefon {phone}, kurs {course}, "
        f"ustoz {teacher_name}, jami to'lov {_compact_money(item.get('total_payment') or 0)}, "
        f"qarzi {_compact_money(item.get('debt') or 0)}, holati {status_label}. "
        f"Davomat {attendance.get('rate') or 0}% ({attendance.get('present') or 0} ta kelgan, "
        f"{attendance.get('absent') or 0} ta kelmagan)."
    )


def _format_teacher_answer(item: dict) -> str:
    phone = item.get("phone") or "yo'q"
    teacher_name = item.get("teacher_name") or "Ustoz"
    status_label = item.get("status_label") or "Noma'lum"
    return (
        f"{teacher_name} haqida ma'lumot: telefon {phone}, guruhlari {item.get('groups_count') or 0} ta, "
        f"faol guruhlari {item.get('active_groups') or 0} ta, o'quvchilari {item.get('students_count') or 0} ta, "
        f"to'lovlardan tushgan jami daromad {_compact_money(item.get('total_income') or 0)}, holati {status_label}."
    )


def _advanced_rule_bundle(center: Center, viewer, question: str) -> dict | None:
    q = _normalize_question(question)
    search_query = _extract_search_query(question)

    if _question_has(q, "o'sish", "osish", "growth"):
        stats = get_monthly_stats(center.id)
        answer = (
            f"Bu oy {stats['this_month_students']} ta yangi o'quvchi qo'shilgan. "
            f"O'tgan oy {stats['last_month_students']} ta edi. "
            f"O'sish {stats['growth_percentage']}% ni tashkil qildi."
        )
        return {
            "answer": answer,
            "data": {"type": "monthly_stats", **stats},
        }

    if _question_has(q, "muammo", "problem", "ogohlantirish", "alert", "xavf", "risk", "yopilish xavfi"):
        alerts = generate_center_alerts(center.id)
        if not alerts:
            return {
                "answer": "Hozircha jiddiy ogohlantirish topilmadi.",
                "data": {"type": "alerts", "items": []},
            }

        if _question_has(q, "guruh", "group", "yopilish"):
            group_alerts = [item for item in alerts if item.get("code") == "group_at_risk"]
            if group_alerts:
                answer = "Yopilish xavfidagi guruhlar: " + "; ".join(item["message"] for item in group_alerts[:3])
                return {
                    "answer": answer,
                    "data": {"type": "alerts", "items": group_alerts},
                }

        answer = "Asosiy ogohlantirishlar: " + "; ".join(item["message"] for item in alerts[:3])
        return {
            "answer": answer,
            "data": {"type": "alerts", "items": alerts},
        }

    if _question_has(q, "qarzdor", "qarzi bor") and _question_has(q, "o'quvchi", "oquvchi", "student"):
        # Agar "diagramma", "aging", "yoshiga" so'zlari bo'lsa — aging tahlil
        if _question_has(q, "diagramma", "aging", "yoshiga", "qancha kun", "necha kun"):
            aging = get_debt_aging_context(center)
            buckets = aging.get("buckets") or []
            total_debt = aging.get("total_debt") or 0
            total_debtors = aging.get("total_debtors") or 0
            top_debtors = aging.get("top_debtors") or []

            if not buckets:
                return {
                    "answer": "Hozircha qarzdorlik ma'lumoti topilmadi.",
                    "data": {"type": "debt_aging", **aging},
                }

            bucket_text = " | ".join(
                f"{b['label']}: {_compact_money(b['amount'])} ({b['debtor_count']} o'quvchi)"
                for b in buckets
            )
            top_text = ""
            if top_debtors:
                top_text = " Eng katta qarzdorlar: " + "; ".join(
                    f"{d['full_name']} — {_compact_money(d['total_debt'])}"
                    for d in top_debtors[:5]
                )
            answer = (
                f"Qarzdorlik tahlili (jami {total_debtors} o'quvchi, "
                f"{_compact_money(total_debt)} qarz): {bucket_text}.{top_text}"
            )
            return {
                "answer": answer,
                "data": {"type": "debt_aging", **aging},
            }

        # Oddiy qarzdor ro'yxat
        ctx = build_center_ai_context(center, viewer=viewer, question=question, limit=5)
        risky_students = ((ctx.get("students") or {}).get("risky_students") or [])[:10]
        if not risky_students:
            return {
                "answer": "Hozircha qarzdor o'quvchilar ro'yxati topilmadi.",
                "data": {"type": "risky_students", "items": []},
            }
        answer = "Qarzdor o'quvchilar: " + "; ".join(
            f"{item['full_name']} — qarzi {_compact_money(item.get('debt') or 0)}"
            for item in risky_students
        )
        return {
            "answer": answer,
            "data": {"type": "risky_students", "items": risky_students},
        }

    # ── Muayyan sanaga to'lovlar ("25 martda qancha daromad?") ─────────────
    specific_date = _extract_specific_date(question)
    if specific_date and _question_has(q, "daromad", "tolov", "to'lov", "tushum", "pul", "qancha"):
        daily = get_daily_revenue_for_date(center, specific_date)
        total = daily.get("total") or 0
        cnt = daily.get("payments_count") or 0
        cash = daily.get("cash") or 0
        card = daily.get("card") or 0
        prev = daily.get("prev_day_total") or 0
        change = daily.get("change_vs_prev_day_pct")

        date_label = specific_date.strftime(f"{specific_date.day}-{MONTH_NAMES[specific_date.month - 1]} {specific_date.year}")
        change_text = ""
        if change is not None:
            change_text = f" (oldingi kunga nisbatan {_signed_pct(change)})"

        if total == 0:
            answer = f"{date_label} kunda hech qanday to'lov qabul qilinmagan."
        else:
            answer = (
                f"{date_label} kunda jami {_compact_money(total)} daromad tushdi "
                f"({cnt} ta to'lov{change_text}). "
            )
            if cash and card:
                answer += f"Naqd: {_compact_money(cash)}, Karta: {_compact_money(card)}."
            elif cash:
                answer += f"Barchasi naqd pul."
            elif card:
                answer += f"Barchasi karta orqali."

        return {
            "answer": answer,
            "data": {"type": "daily_revenue", **daily},
        }

    # ── Kurs/bo'lim daromadi reytingi ────────────────────────────────────────
    if _question_has(q, "kurs", "bo'lim", "bolim", "kategoriya", "yo'nalish") and _question_has(
        q, "daromad", "eng kam", "eng ko'p", "ko'proq", "kamoq", "past", "yuqori", "reyting"
    ):
        cat_rev = get_category_revenue_context(center)
        categories = cat_rev.get("by_category") or []

        if not categories:
            return {
                "answer": "Kurs daromadi ma'lumoti topilmadi.",
                "data": {"type": "category_revenue", **cat_rev},
            }

        is_lowest = _question_has(q, "eng kam", "eng past", "kamoq", "zaif", "past")

        if is_lowest:
            target = sorted(categories, key=lambda c: c["revenue"])
            label = "Eng kam daromad keltiruvchi bo'limlar"
        else:
            target = sorted(categories, key=lambda c: -c["revenue"])
            label = "Eng ko'p daromad keltiruvchi bo'limlar"

        lines = []
        for i, cat in enumerate(target[:5], 1):
            lines.append(
                f"{i}. {cat['category']}: {_compact_money(cat['revenue'])} "
                f"({cat['students']} o'quvchi)"
            )

        answer = f"{label}:\n" + "\n".join(lines)

        # Guruh darajasidagi tafsilot
        if _question_has(q, "guruh", "group", "batafsil"):
            worst_group = (cat_rev.get("lowest_groups") or [{}])[0]
            if worst_group:
                answer += f"\n\nEng kam daromadli guruh: {worst_group.get('name')} — {_compact_money(worst_group.get('revenue', 0))}"

        return {
            "answer": answer,
            "data": {"type": "category_revenue", **cat_rev},
        }

    # ── Oy daromadi (O'tgan oy / Bu oy / Mart daromadi) ─────────────────────
    if _question_has(q, "daromad", "tushum", "qancha pul") and not specific_date:
        month_year = _extract_month_year(question)
        if month_year:
            month_num, year = month_year
            from datetime import date as _date
            import calendar
            _, last_day = calendar.monthrange(year, month_num)
            m_start = _date(year, month_num, 1)
            m_end = _date(year, month_num, last_day)

            from core.services.center_ai_context import get_center_finance_context
            fin = get_center_finance_context(center, m_start, m_end)
            rev = fin["summary"]["revenue"]
            profit = fin["summary"]["profit"]
            expenses = fin["summary"]["expenses"]
            teacher_payout = fin["summary"]["teacher_payout"]
            cnt = fin["summary"]["payments_count"]

            month_label_text = f"{MONTH_NAMES[month_num - 1].capitalize()} {year}"
            answer = (
                f"{month_label_text} oyi moliyaviy natijasi: "
                f"daromad {_compact_money(rev)}, "
                f"xarajat {_compact_money(expenses)}, "
                f"ustoz ulushi {_compact_money(teacher_payout)}, "
                f"sof foyda {_compact_money(profit)}. "
                f"Jami {cnt} ta to'lov qabul qilindi."
            )
            return {
                "answer": answer,
                "data": {"type": "month_revenue", "month": f"{year}-{month_num:02d}", **fin["summary"]},
            }

    search_requested = bool(search_query) and (
        _question_has(q, "haqida", "telefon", "raqam", "kurs", "holat", "to'lov", "tolov", "qarz", "qarzi", "kim")
        or bool(re.search(r"\d{4,}", search_query))
        or (
            len(search_query.split()) <= 2
            and not _question_has(
                q,
                "nechta",
                "qancha",
                "jami",
                "soni",
                "daromad",
                "foyda",
                "o'sish",
                "growth",
                "muammo",
                "problem",
                "alert",
                "guruh",
                "lead",
                "mahsulot",
                "do'kon",
                "dokon",
                "saytim",
                "nima bor",
                "platforma",
                "tizim",
                "modul",
            )
        )
    )
    if not search_requested:
        return None

    # Eslatma: ism qidiruvi natijalari endi Gemini ga `_profile_lookup_block`
    # orqali yuboriladi. Bu yerda rule-based formatdan voz kechib, har doim
    # Gemini'ga o'tkazamiz — natijada javob qisqa va tabiiy bo'ladi.
    return None


def _extract_specific_date(question: str) -> date | None:
    """
    Savoldan aniq sana ajratib oladi.
    Qo'llab-quvvatlanadigan formatlar:
      - "25 mart", "25 martda", "25-mart"
      - "25.03", "25.03.2026", "2026-03-25"
      - "25/03/2026"
    """
    q = question.lower()
    today = timezone.localdate()

    # ISO format: 2026-03-25
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", q)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # dd.mm.yyyy yoki dd.mm
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{4}))?", q)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            return date(year, month, day)
        except ValueError:
            pass

    # "25 mart", "25-mart", "25 martda"
    month_map_uz = {
        "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4,
        "may": 5, "iyun": 6, "iyul": 7, "avgust": 8,
        "sentyabr": 9, "oktyabr": 10, "noyabr": 11, "dekabr": 12,
    }
    for month_name, month_num in month_map_uz.items():
        m = re.search(rf"(\d{{1,2}})\s*[.\-]?\s*{month_name}", q)
        if m:
            day = int(m.group(1))
            year = today.year
            # Agar oy o'tib ketgan bo'lsa, o'tgan yilni ishlatamiz
            try:
                candidate = date(year, month_num, day)
                if candidate > today:
                    candidate = date(year - 1, month_num, day)
                return candidate
            except ValueError:
                pass

    return None


def _extract_month_year(question: str) -> tuple[int, int] | None:
    """
    Savoldan oy va yilni ajratib oladi.
    Masalan: "mart 2026", "o'tgan oy", "bu oy", "fevral"
    """
    q = question.lower()
    today = timezone.localdate()

    if any(k in q for k in ("bu oy", "joriy oy", "hozirgi oy")):
        return today.month, today.year
    if any(k in q for k in ("o'tgan oy", "otgan oy", "oldingi oy")):
        prev = today.replace(day=1) - timedelta(days=1)
        return prev.month, prev.year

    month_map_uz = {
        "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4,
        "may": 5, "iyun": 6, "iyul": 7, "avgust": 8,
        "sentyabr": 9, "oktyabr": 10, "noyabr": 11, "dekabr": 12,
    }
    for month_name, month_num in month_map_uz.items():
        if month_name in q:
            year_m = re.search(r"\b(202\d|20[3-9]\d)\b", q)
            year = int(year_m.group(1)) if year_m else today.year
            return month_num, year

    return None


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


def _profile_lookup_block(center: Center, question: str, *, viewer=None) -> str:
    """
    Savolda biror ism/familiya uchrasa — shu o'quvchi yoki ustozning to'liq
    profilini prompt uchun matn shaklida qaytaradi. Hech narsa topilmasa "" qaytadi.
    """
    search_query = _extract_search_query(question)
    if not search_query:
        return ""

    # Ism qidiruvini faqat 2-3 ta so'zli, raqamsiz so'rovlarda yoqamiz.
    # "guruhlar yopilishi kerak" kabi savollarni o'tkazib yuboramiz.
    q_norm = _normalize_question(question)
    if any(token in q_norm for token in ("nechta", "qancha", "jami", "soni", "yopilish", "eng yaxshi", "eng kuchli")):
        return ""

    try:
        student_info = get_student_full_info(center.id, search_query, viewer=viewer, limit=3)
        teacher_info = get_teacher_full_info(center.id, search_query, viewer=viewer, limit=3)
    except Exception:  # pragma: no cover
        return ""

    students = (student_info.get("items") or [])[:3]
    teachers = (teacher_info.get("items") or [])[:3]
    if not students and not teachers:
        return ""

    lines: list[str] = []

    NA = "yo'q"

    if students:
        lines.append(
            f"QIDIRILGAN O'QUVCHI PROFIL(LARI) — so'rov: {search_query!r}, topildi: {len(students)} ta"
        )
        for s in students:
            att = s.get("attendance") or {}
            phone = s.get("phone") or NA
            course = s.get("course") or NA
            teacher = s.get("teacher_name") or NA
            status = s.get("status_label") or "—"
            full_name = s.get("full_name") or "—"
            fields = [
                f"Ism: {full_name}",
                f"📞 Telefon: {phone}",
                f"📚 Kurs(lar): {course}",
                f"👨‍🏫 Ustoz(lar): {teacher}",
                f"Faol guruhlar: {int(s.get('groups_count') or 0)} ta",
                f"💰 Jami to'lov: {_compact_money(s.get('total_payment') or 0)}",
                f"Davr to'lovi: {_compact_money(s.get('paid_in_period') or 0)}",
                f"⚠️ Qarz: {_compact_money(s.get('debt') or 0)}",
                f"O'tib ketgan oylar: {int(s.get('overdue_months') or 0)}",
                f"Oylik narx: {_compact_money(s.get('monthly_fee') or 0)}",
                f"Holat: {status}",
                f"📊 Davomat: {att.get('rate') or 0}% ({att.get('present') or 0} kelgan / {att.get('absent') or 0} kelmagan)",
                f"⚡ Chaqmoq ballari: {int(s.get('chaqmoq') or 0)}",
            ]
            lines.append("  • " + ", ".join(fields))

    if teachers:
        lines.append(
            f"\nQIDIRILGAN USTOZ PROFIL(LARI) — so'rov: {search_query!r}, topildi: {len(teachers)} ta"
        )
        for t in teachers:
            phone = t.get("phone") or NA
            tname = t.get("teacher_name") or "—"
            status = t.get("status_label") or "—"
            group_names = t.get("group_names") or []
            groups_str = ", ".join(group_names[:6]) or NA
            fields = [
                f"Ism: {tname}",
                f"📞 Telefon: {phone}",
                f"O'quvchi: {int(t.get('students_count') or 0)} ta",
                f"Faol guruh: {int(t.get('active_groups') or t.get('groups_count') or 0)} ta",
                f"Guruhlar: {groups_str}",
                f"💰 Daromad: {_compact_money(t.get('total_income') or 0)}",
                f"Ustoz ulushi: {_compact_money(t.get('teacher_payout') or 0)} ({int(t.get('share_percent') or 0)}%)",
                f"Holat: {status}",
            ]
            lines.append("  • " + ", ".join(fields))

    return "\n".join(lines)


def _full_center_context(center: Center, stats: dict, question: str, *, viewer=None, limit: int = 12) -> tuple[dict, str]:
    compact = _compact_context(stats)
    period = compact.get("period") or {}
    date_from = period.get("date_from") or None
    date_to = period.get("date_to") or None
    privacy_mode = privacy_mode_label(viewer)
    cache_key = (
        f"director-ai-full-context:{center.id}:{date_from or 'na'}:{date_to or 'na'}:"
        f"{privacy_mode}:{md5((question or '').encode('utf-8')).hexdigest()}:{limit}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached.get("context") or {}, cached.get("prompt") or ""

    try:
        context = build_center_ai_context(
            center,
            viewer=viewer,
            question=question,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        prompt_context = build_center_ai_prompt_context(
            center,
            viewer=viewer,
            question=question,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    except Exception as exc:
        logger.warning("Center AI context build failed: %s", exc)
        context = {}
        prompt_context = ""

    # Savolda ism uchragan bo'lsa — shu o'quvchi/ustozning to'liq profilini
    # prompt ga qo'shamiz. Shunda Gemini "Abdulla qaysi guruhda?" kabi savollarga
    # to'liq profil asosida tabiiy javob bera oladi.
    try:
        profile_block = _profile_lookup_block(center, question, viewer=viewer)
        if profile_block:
            prompt_context = (prompt_context or "") + "\n\n" + profile_block
            context["profile_match"] = True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Profile lookup failed: %s", exc)

    cache.set(
        cache_key,
        {"context": context, "prompt": prompt_context},
        ANSWER_CACHE_TTL,
    )
    return context, prompt_context


def _pick_forecast_item(question: str, items: list[dict]) -> dict:
    q = _normalize_question(question)
    forecast_items = [item for item in items if item.get("is_forecast")]
    if not forecast_items:
        return {}

    for item in forecast_items:
        month_value = str(item.get("month") or "")
        label_value = _normalize_question(item.get("label") or "")
        if month_value and month_value in q:
            return item
        if label_value and label_value in q:
            return item

    for idx, month_name in enumerate(MONTH_NAMES, start=1):
        if month_name in q:
            for item in forecast_items:
                if str(item.get("month") or "").endswith(f"-{idx:02d}"):
                    return item

    return forecast_items[0]


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


def _fallback_answer(center: Center, viewer, question: str, stats: dict, history: list[dict] | None = None) -> str:
    privacy_block = guard_cross_center_question(center, question)
    if privacy_block:
        return privacy_block

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

    advanced_rule = _advanced_rule_bundle(center, viewer, q)
    if advanced_rule:
        return advanced_rule["answer"]

    raw_finance = stats.get("finance") or {}
    raw_students = stats.get("students") or {}
    raw_teachers = stats.get("teachers") or {}
    raw_groups = stats.get("groups") or {}
    raw_marketing = stats.get("marketing") or {}
    raw_requests = stats.get("requests") or {}
    raw_managers = stats.get("managers") or {}
    raw_roster = raw_students.get("roster") or []
    full_ctx, _ = _full_center_context(center, stats, question, viewer=viewer)
    full_finance = ((full_ctx.get("finance") or {}).get("summary") or {})
    full_students = ((full_ctx.get("students") or {}).get("summary") or {})
    full_teachers = ((full_ctx.get("teachers") or {}).get("summary") or {})
    full_groups = ((full_ctx.get("groups") or {}).get("summary") or {})
    full_leads = ((full_ctx.get("leads") or {}).get("summary") or {})
    full_store = ((full_ctx.get("store") or {}).get("summary") or {})
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
    privacy_mode = privacy_mode_label(viewer)
    private_access = can_view_private_details(viewer)
    total_students = int(full_students.get("total_students") or raw_students.get("total") or 0)
    active_students = int(full_students.get("active_students") or raw_students.get("active_students") or students["active_students"] or 0)
    total_teachers = int(full_teachers.get("total_teachers") or raw_teachers.get("total_count") or 0)
    total_groups = int(full_groups.get("total_groups") or raw_groups.get("total_count") or 0)
    total_leads = int(full_leads.get("total_leads") or raw_marketing.get("all_time_leads") or 0)
    period_leads = int(full_leads.get("period_leads") or raw_marketing.get("total_leads") or marketing["new_leads"] or 0)
    total_products = int(full_store.get("products_count") or raw_requests.get("products_count") or 0)
    total_requests = int(full_store.get("requests_count") or raw_requests.get("total_count") or 0)
    finance_revenue = int(full_finance.get("revenue") or raw_finance.get("income") or finance["income"] or 0)
    finance_expenses = int(full_finance.get("expenses") or raw_finance.get("expense") or raw_finance.get("operating_expense") or 0)
    finance_profit = int(full_finance.get("profit") or raw_finance.get("profit") or 0)
    finance_teacher_payout = int(full_finance.get("teacher_payout") or raw_finance.get("teacher_shares") or 0)
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
            f"{period_label} oralig'ida ChaqmoqApp markazingizda daromad {_compact_money(finance_revenue)}, "
            f"foyda {_compact_money(finance_profit)}, ochiq qarz {_compact_money(raw_finance.get('open_debt') or finance['open_debt'])}. "
            f"Jami o'quvchilar {total_students} ta, faol o'quvchilar {active_students} ta, ustozlar {total_teachers} ta, "
            f"guruhlar {total_groups} ta, leadlar {total_leads} ta va shu davr leadi {period_leads} ta. "
            f"Eng kuchli ustoz {teachers['best_teacher']['name'] or 'aniqlanmadi'}, eng samarali lead manbasi {marketing['best_source']['name'] or 'aniqlanmadi'}, "
            f"do'kon bo'limida esa {total_products} ta mahsulot va {total_requests} ta so'rov bor."
        )

    if _question_has(q, "telefon", "raqam", "contact", "aloqa"):
        if not private_access:
            return (
                "Telefon va shaxsiy aloqa ma'lumotlari maxfiy. Bu akkaunt uchun detail cheklangan. "
                "Direktor rolida kirsangiz to'liq ko'rish mumkin."
            )
        return (
            "Telefon raqamlarini aytib bera olaman, lekin aniq odamni topish uchun ism yoki familyani ham yozing. "
            f"Hozir chat {privacy_mode} rejimda ishlayapti va faqat {center.name} ichidagi ma'lumotlarni ko'radi."
        )

    if _question_has(q, "daromad", "tushum", "kirim") and _question_has(q, "prognoz", "taxmin", "bashorat", "kelasi oy", "keyingi oy", "kutilmoqda"):
        forecast_items, forecast_summary = forecast_revenue_bundle(
            center,
            months_ahead=3,
            anchor_date=_parse_period_day(period.get("date_to")) or timezone.localdate(),
        )
        selected_item = _pick_forecast_item(q, forecast_items)
        if selected_item:
            tail = [
                f"{item['label']} {_compact_money(item['amount'])}"
                for item in forecast_items
                if item.get("is_forecast")
            ]
            return (
                f"{selected_item.get('label') or 'Kelasi oy'} uchun daromad prognozi taxminan "
                f"{_compact_money(selected_item.get('amount') or 0)}. "
                f"Weighted moving average asosida keyingi oylar: {', '.join(tail)}."
            )
        return "Daromad prognozi uchun yetarli tarixiy ma'lumot topilmadi."

    if _question_has(q, "o'quvchi", "oquvchi", "student") and _question_has(q, "nechta", "qancha", "jami", "soni", "bor"):
        if _question_has(q, "faol", "aktiv"):
            return (
                f"{period_intro} faol o'quvchilar soni {active_students} ta. "
                f"Markaz bazasidagi jami o'quvchilar esa {total_students} ta."
            )
        return (
            f"Markazda jami {total_students} ta o'quvchi bor. "
            f"{period_intro} faol o'quvchilar {active_students} ta."
        )

    if _question_has(q, "ustoz", "o'qituvchi", "oqituvchi", "teacher") and _question_has(q, "nechta", "qancha", "jami", "soni", "bor"):
        return (
            f"Markazda jami {total_teachers} ta ustoz bor. "
            f"{period_intro} ishlayotgan guruhlar soni {total_groups} ta."
        )

    if _question_has(q, "guruh") and _question_has(q, "nechta", "qancha", "jami", "soni", "bor"):
        return f"Markazda jami {total_groups} ta guruh bor."

    if _question_has(q, "lead") and _question_has(q, "nechta", "qancha", "jami", "soni", "bor"):
        return (
            f"Markaz bazasida jami {total_leads} ta lead bor. "
            f"{period_intro} qo'shilgan leadlar {period_leads} ta."
        )

    if _question_has(q, "mahsulot", "do'kon", "dokon") and _question_has(q, "nechta", "qancha", "jami", "soni", "bor"):
        return (
            f"Do'kon bo'limida jami {total_products} ta mahsulot bor. "
            f"{period_intro} xarid so'rovlari {total_requests} ta."
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
            f"{period_intro} daromad {_compact_money(finance_revenue)}. "
            f"Oldingi davrga nisbatan {_signed_pct(raw_finance.get('income_growth') or finance['income_growth'])} "
            f"o'zgarish bor."
        )

    if _question_has(q, "foyda", "marja"):
        return (
            f"{period_intro} sof foyda {_compact_money(finance_profit)}. "
            f"Marja {_pct(raw_finance.get('profit_margin') or 0)} darajada."
        )

    if _question_has(q, "xarajat", "chiqim"):
        return (
            f"{period_intro} xarajat {_compact_money(finance_expenses)}. "
            f"O'qituvchi ulushi {_compact_money(finance_teacher_payout)} ni tashkil qilgan."
        )

    if _question_has(q, "davomatdan pul", "ustoz puli", "o'qituvchi ulushi", "davomat puli", "davomatga yarasha"):
        return (
            "ChaqmoqAppda ustoz ulushi davomat yozilganda TeacherIncome orqali hisoblanadi. "
            f"{period_intro} jami o'qituvchi ulushi {_compact_money(finance_teacher_payout)} bo'lgan. "
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
            f"{period_intro} faol o'quvchilar soni {active_students} ta. "
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

    return "Ma'lumot yetarli emas"


def _answer_bundle(center: Center, viewer, question: str, stats: dict, history: list[dict] | None = None) -> tuple[str, str]:
    cleaned_question = (question or "").strip()
    if not cleaned_question:
        return "Savol matni bo'sh bo'lmasligi kerak.", "fallback"

    privacy_block = guard_cross_center_question(center, cleaned_question)
    if privacy_block:
        return privacy_block, "privacy"

    compact = _compact_context(stats)
    site_ctx = _site_context(center, stats)
    full_ctx, full_prompt_ctx = _full_center_context(center, stats, cleaned_question, viewer=viewer)
    history_tail = (history or [])[-8:]
    cache_key = (
        f"director-ai-answer:{ANSWER_ENGINE_VERSION}:{center.id}:{privacy_mode_label(viewer)}:{_stats_digest({'compact': compact, 'site': site_ctx})}:"
        f"{md5((full_prompt_ctx or '').encode('utf-8')).hexdigest()}:{_history_digest(history_tail)}:"
        f"{md5(cleaned_question.encode('utf-8')).hexdigest()}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, "cache"

    fallback = _fallback_answer(center, viewer, cleaned_question, stats, history=history_tail)
    history_text = _history_context(history_tail)
    prompt = f"""
{STRICT_SYSTEM_PROMPT}

Qo'shimcha qoidalar:
- Shaxsiy ma'lumotlarni faqat privacy_mode=full bo'lsa ochiq ayt.
- Savol platforma yoki sayt modullari haqida bo'lsa, platform_knowledge bo'yicha tushuntir.
- Savol raqam yoki holat haqida bo'lsa, current_site_snapshot bo'yicha aniq son va nomlarni ayt.
- ChaqmoqApp ichidagi ish jarayonlari savol qilinsa workflows va metric_glossary bo'yicha tushuntir.
- Hech qanday markdown yoki ro'yxat yozma.

Savol: {cleaned_question}

Oxirgi chat konteksti:
{history_text or "Yo'q"}

Platform knowledge:
{json.dumps(site_ctx, ensure_ascii=False, default=str)}

Current site snapshot:
{json.dumps(compact, ensure_ascii=False, default=str)}

Full center context:
{full_prompt_ctx or json.dumps(full_ctx, ensure_ascii=False, default=str)}
"""
    answer, source = _prompt_text(prompt, default=fallback, cache_key=None)
    cache.set(cache_key, answer, ANSWER_CACHE_TTL)
    return answer, source


def answer_question(center, question: str, stats: dict, history: list[dict] | None = None) -> str:
    answer, _ = _answer_bundle(center, None, question, stats, history=history)
    return answer


def answer_question_bundle(center, question: str, stats: dict, history: list[dict] | None = None, viewer=None) -> tuple[str, str]:
    return _answer_bundle(center, viewer, question, stats, history=history)


def answer_question_structured_bundle(
    center,
    question: str,
    stats: dict,
    history: list[dict] | None = None,
    viewer=None,
) -> tuple[str, str, dict | None]:
    privacy_block = guard_cross_center_question(center, question)
    if privacy_block:
        return privacy_block, "privacy", {"type": "privacy", "blocked": True}

    advanced_rule = _advanced_rule_bundle(center, viewer, question)
    if advanced_rule:
        return advanced_rule["answer"], "rule-based", advanced_rule.get("data")

    answer, source = _answer_bundle(center, viewer, question, stats, history=history)
    compact = _compact_context(stats)
    return answer, source, {
        "type": "snapshot",
        "period": compact.get("period") or {},
        "finance": compact.get("finance") or {},
        "students": compact.get("students") or {},
        "teachers": compact.get("teachers") or {},
    }
