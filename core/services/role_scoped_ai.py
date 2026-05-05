"""
Role-scoped AI yordamchi.

Har bir foydalanuvchi (teacher / student / parent) AI dan faqat O'ZIGA TEGISHLI
ma'lumotlarni so'raydi va boshqa odamlarning ma'lumoti hech qachon prompt ga
o'tmaydi. Bu xavfsizlik ichkidan ta'minlangan — biz oldindan rolga ko'ra
filter qilingan ma'lumotnigina Gemini ga yuboramiz.

Director/manager uchun esa keng kontekstli `ai_insights.answer_question_structured_bundle`
ishlatiladi (alohida fayl).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from hashlib import md5

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import User
from core.services.center_ai_security import visible_phone
from education.models import Attendance, Enrollment, Group, Payment

logger = logging.getLogger(__name__)

ANSWER_CACHE_TTL = 60 * 5  # 5 daqiqa
HISTORY_TAIL = 8


def _present_filter() -> Q:
    return Q(status="present") | Q(present=True) | Q(forced=True)


def _compact_money(value) -> str:
    v = int(value or 0)
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f} mln so'm"
    if abs(v) >= 1_000:
        return f"{v/1_000:.0f} ming so'm"
    return f"{v} so'm"


def _full_name(u) -> str:
    parts = [getattr(u, "ism", "") or "", getattr(u, "familya", "") or ""]
    return " ".join(p for p in parts if p).strip() or u.get_username() or "—"


def _age_from_birth(b) -> str:
    if not b:
        return "—"
    today = timezone.localdate()
    years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    return f"{years} yosh"


# ─────────────────────────── TEACHER ────────────────────────────

def build_teacher_context(teacher: User) -> str:
    today = timezone.localdate()
    period_from = today - timedelta(days=30)

    groups = (
        Group.objects.filter(oqituvchi=teacher, is_archived=False, center=teacher.center)
        .order_by("-id")
    )
    group_ids = list(groups.values_list("id", flat=True))

    enrollments_qs = (
        Enrollment.objects.filter(group__in=group_ids, is_active=True)
        .select_related("student", "group")
    )
    student_ids = list(enrollments_qs.values_list("student_id", flat=True).distinct())

    # Davomat statistikasi (oxirgi 30 kun)
    att_qs = Attendance.objects.filter(group__in=group_ids, date__range=(period_from, today))
    att_total = att_qs.count()
    att_present = att_qs.filter(_present_filter()).count()
    att_pct = round(att_present / att_total * 100, 1) if att_total else 0.0

    # Bu oy ustoz daromadi (taxminiy)
    pay_qs = Payment.objects.filter(group__in=group_ids, paid_date__range=(period_from, today))
    period_revenue = int(pay_qs.aggregate(s=Sum("summa"))["s"] or 0)

    # Guruhlar batafsil
    group_lines = []
    for g in groups[:10]:
        g_enrolls = enrollments_qs.filter(group_id=g.id)
        st_count = g_enrolls.count()
        g_att = att_qs.filter(group_id=g.id)
        g_total = g_att.count()
        g_present = g_att.filter(_present_filter()).count()
        g_pct = round(g_present / g_total * 100, 1) if g_total else 0.0
        group_lines.append(
            f"  • {g.nom}: {st_count} o'quvchi, {_compact_money(g.kurs_narxi)}/oy, "
            f"davomat {g_pct}% ({g_present}/{g_total})"
        )

    # Qarzdor o'quvchilar (faqat ustoz guruhlaridagilar)
    debtors = []
    for e in enrollments_qs.select_related("student").order_by("-id")[:50]:
        monthly = int(e.kurs_narxi_actual or e.group.kurs_narxi or 0) if hasattr(e, "kurs_narxi_actual") else int(e.group.kurs_narxi or 0)
        paid = int(e.jami_tolangan or 0)
        debt = max(monthly - paid, 0) if monthly else 0
        if debt > 0:
            debtors.append((e.student, debt, e.group.nom))
    debtor_lines = [
        f"  • {_full_name(s)} ({grp}): qarz {_compact_money(d)}"
        for s, d, grp in debtors[:8]
    ]

    teacher_phone = teacher.telefon1 or teacher.phone_number or ""
    parts = [
        f"USTOZ PROFIL: {_full_name(teacher)}, 📞 {teacher_phone or "yo'q"}",
        f"DAVR: {period_from} dan {today} gacha (oxirgi 30 kun)",
        f"GURUHLAR: {groups.count()} ta faol",
        f"O'QUVCHILAR: {len(student_ids)} ta faol",
        f"DAVOMAT (umumiy): {att_pct}% ({att_present}/{att_total})",
        f"GURUHLARDAN TUSHUM: {_compact_money(period_revenue)}",
        "",
        f"GURUHLAR RO'YXATI ({min(groups.count(), 10)} ta ko'rsatildi):",
        "\n".join(group_lines) if group_lines else "  (yo'q)",
        "",
        f"QARZDOR O'QUVCHILAR ({len(debtor_lines)} ta):",
        "\n".join(debtor_lines) if debtor_lines else "  (yo'q)",
    ]
    return "\n".join(parts)


# ─────────────────────────── STUDENT ────────────────────────────

def build_student_context(student: User) -> str:
    today = timezone.localdate()
    period_from = today - timedelta(days=30)

    enrollments = (
        Enrollment.objects.filter(student=student, is_active=True)
        .select_related("group", "group__oqituvchi")
    )
    group_ids = list(enrollments.values_list("group_id", flat=True))

    # Davomat (oxirgi 30 kun)
    att_qs = Attendance.objects.filter(student=student, date__range=(period_from, today))
    att_total = att_qs.count()
    att_present = att_qs.filter(_present_filter()).count()
    att_pct = round(att_present / att_total * 100, 1) if att_total else 0.0

    # To'lovlar
    pay_total = int(
        Payment.objects.filter(student=student).aggregate(s=Sum("summa"))["s"] or 0
    )
    pay_period = int(
        Payment.objects.filter(student=student, paid_date__range=(period_from, today))
        .aggregate(s=Sum("summa"))["s"] or 0
    )

    # Qarz hisoblash (oddiy: enrollment monthly_fee - jami_tolangan)
    debt_total = 0
    monthly_fee_total = 0
    for e in enrollments:
        monthly = int(e.group.kurs_narxi or 0)
        paid = int(e.jami_tolangan or 0)
        monthly_fee_total += monthly
        debt_total += max(monthly - paid, 0)

    # Guruhlar batafsil
    group_lines = []
    for e in enrollments[:8]:
        g = e.group
        g_att = att_qs.filter(group_id=g.id)
        g_total = g_att.count()
        g_present = g_att.filter(_present_filter()).count()
        g_pct = round(g_present / g_total * 100, 1) if g_total else 0.0
        teacher_name = _full_name(g.oqituvchi) if g.oqituvchi_id else "biriktirilmagan"
        group_lines.append(
            f"  • {g.nom} (👨‍🏫 {teacher_name}): {_compact_money(g.kurs_narxi)}/oy, "
            f"davomat {g_pct}% ({g_present}/{g_total})"
        )

    phone = student.telefon1 or student.phone_number or ""
    parts = [
        f"O'QUVCHI PROFIL: {_full_name(student)}",
        f"📞 Telefon: {phone or "yo'q"}",
        f"🎂 Yosh: {_age_from_birth(student.birth_date)} (tug'ilgan: {student.birth_date or 'kiritilmagan'})",
        f"⚡ Chaqmoq ballari: {int(getattr(student, 'chaqmoq', 0) or 0)}",
        f"DAVR: {period_from} dan {today} gacha",
        "",
        f"GURUHLARIM ({enrollments.count()} ta):",
        "\n".join(group_lines) if group_lines else "  (hozircha yo'q)",
        "",
        "DAVOMAT (oxirgi 30 kun):",
        f"  Foiz: {att_pct}%, kelgan {att_present} ta, kelmagan {att_total - att_present} ta",
        "",
        "MOLIYA:",
        f"  💰 Jami to'langan (umumiy): {_compact_money(pay_total)}",
        f"  Bu davrda to'langan: {_compact_money(pay_period)}",
        f"  Oylik narx (jami): {_compact_money(monthly_fee_total)}",
        f"  ⚠️ Qarz: {_compact_money(debt_total)}",
    ]
    return "\n".join(parts)


# ─────────────────────────── PARENT ─────────────────────────────

def build_parent_context(parent: User) -> str:
    children = parent.children.filter(is_archived=False).select_related("center")[:6]
    if not children:
        return f"OTA-ONA PROFIL: {_full_name(parent)}\nFARZAND(LAR): hali biriktirilmagan"

    today = timezone.localdate()
    period_from = today - timedelta(days=30)

    parent_phone = parent.telefon1 or parent.phone_number or "(telefon yo'q)"
    parts = [
        f"OTA-ONA PROFIL: {_full_name(parent)}",
        f"📞 {parent_phone}",
        f"FARZAND(LAR): {len(children)} ta",
        f"DAVR: {period_from} dan {today} gacha",
        "",
    ]

    for idx, ch in enumerate(children, 1):
        enrollments = (
            Enrollment.objects.filter(student=ch, is_active=True)
            .select_related("group", "group__oqituvchi")
        )
        groups_str = ", ".join(
            f"{e.group.nom} (👨‍🏫 {_full_name(e.group.oqituvchi) if e.group.oqituvchi_id else '—'})"
            for e in enrollments[:5]
        ) or "yo'q"

        att_qs = Attendance.objects.filter(student=ch, date__range=(period_from, today))
        att_total = att_qs.count()
        att_present = att_qs.filter(_present_filter()).count()
        att_pct = round(att_present / att_total * 100, 1) if att_total else 0.0

        pay_period = int(
            Payment.objects.filter(student=ch, paid_date__range=(period_from, today))
            .aggregate(s=Sum("summa"))["s"] or 0
        )
        debt = 0
        for e in enrollments:
            paid = int(e.jami_tolangan or 0)
            monthly = int(e.group.kurs_narxi or 0)
            debt += max(monthly - paid, 0)

        ch_phone = visible_phone(ch.telefon1 or ch.phone_number or "", parent)
        parts.extend([
            f"[Farzand {idx}: {_full_name(ch)}]",
            f"  📞 Telefon: {ch_phone or "yo'q"}",
            f"  🎂 Yosh: {_age_from_birth(ch.birth_date)}",
            f"  ⚡ Chaqmoq: {int(getattr(ch, 'chaqmoq', 0) or 0)}",
            f"  📚 Guruhlar: {groups_str}",
            f"  📊 Davomat (30 kun): {att_pct}% ({att_present}/{att_total})",
            f"  💰 Bu davrda to'langan: {_compact_money(pay_period)}",
            f"  ⚠️ Qarz: {_compact_money(debt)}",
            "",
        ])

    return "\n".join(parts)


# ─────────────────────────── ANSWER ─────────────────────────────

ROLE_PROMPT_INTRO = {
    "teacher": (
        "Sen ustozning AI yordamchisisan. Sen FAQAT ushbu ustoz dars beradigan "
        "guruhlar, ularning o'quvchilari va shu guruhdagi davomat/to'lovlar haqida "
        "ma'lumot beradigan kontekstga egasan. Boshqa ustozlarning yoki guruhlarning "
        "ma'lumotini hech qachon eslatma."
    ),
    "student": (
        "Sen o'quvchining shaxsiy AI yordamchisisan. Sen FAQAT ushbu o'quvchining "
        "o'z ma'lumotlariga (guruhlari, davomati, to'lovlari, ballari) egasan. "
        "Boshqa o'quvchilarning ma'lumotini hech qachon eslatma yoki taqqoslama."
    ),
    "parent": (
        "Sen ota-onaning AI yordamchisisan. Sen FAQAT ushbu ota-onaning "
        "FARZAND(LAR)IGA tegishli ma'lumotlarni ko'rasan. Boshqa o'quvchilarning "
        "yoki guruhlarning ma'lumotini hech qachon eslatma."
    ),
}

STYLE_RULES = """
JAVOB STILI (juda muhim):
- QISQA bo'l. Maksimal 3-4 jumla. Foydalanuvchi keyingi savol berib aniqlashtira oladi.
- Sodda, kundalik o'zbek tilida yoz. Rasmiy iboralarni ishlatma.
- Mos joyda 1-3 ta emoji ishlat: 💰 to'lov, 👨‍🏫 ustoz, 👥 guruh, 📊 davomat, ⚠️ qarz, ✅ yaxshi, 📞 telefon.
- Markdown va * — kabi ro'yxat belgilarini ishlatma.
- Faqat KONTEKST asosida javob ber. Tashqi ma'lumot o'ylab topma.
- Agar so'ralgan ma'lumot kontekstda yo'q bo'lsa, qisqa "Bu haqida ma'lumot yo'q" deb ayt.
""".strip()


def _build_prompt(role: str, ctx_text: str, question: str, history: list[dict] | None) -> str:
    intro = ROLE_PROMPT_INTRO.get(role, "")
    history_text = ""
    if history:
        lines = []
        for m in (history or [])[-HISTORY_TAIL:]:
            who = "Foydalanuvchi" if m.get("role") == "user" else "AI"
            content = (m.get("content") or "")[:300]
            lines.append(f"{who}: {content}")
        history_text = "\n".join(lines)

    return f"""{intro}

{STYLE_RULES}

Oldingi suhbat (muloqot tarixi):
{history_text or "Yo'q"}

KONTEKST (faqat shu odamga tegishli ma'lumot):
{ctx_text}

Foydalanuvchi savoli: {question}

Javob:""".strip()


def answer_role_scoped_question(viewer: User, question: str, history: list[dict] | None = None) -> tuple[str, str]:
    """
    Returns (answer, source) where source is one of: gemini, cache, fallback, rate-limited.
    """
    role = getattr(viewer, "role", None)
    if role not in {"teacher", "student", "parent"}:
        return "Bu rol uchun AI hali sozlanmagan.", "fallback"

    if not viewer.center_id:
        return "Markaz aniqlanmadi.", "fallback"

    # Kontekst qurish — faqat foydalanuvchining o'z ma'lumotlari
    try:
        if role == "teacher":
            ctx_text = build_teacher_context(viewer)
        elif role == "student":
            ctx_text = build_student_context(viewer)
        else:
            ctx_text = build_parent_context(viewer)
    except Exception as exc:
        logger.warning("Role-scoped context build failed (role=%s): %s", role, exc)
        return f"Ma'lumotlarni o'qishda xatolik: {str(exc)[:120]}", "fallback"

    prompt = _build_prompt(role, ctx_text, question, history)

    cache_key = (
        f"role-ai-{role}:{viewer.id}:{viewer.center_id}:"
        f"{md5((question or '').encode('utf-8')).hexdigest()}:"
        f"{md5((ctx_text or '').encode('utf-8')).hexdigest()[:8]}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, "cache"

    # Lazy import — Gemini SDK
    try:
        from core.services.ai_insights import _prompt_text
    except Exception:
        return "AI moduli yuklanmadi.", "fallback"

    fallback = "Bu haqida ma'lumot yo'q."
    answer, source = _prompt_text(prompt, default=fallback)
    if source == "gemini" and answer:
        cache.set(cache_key, answer, ANSWER_CACHE_TTL)
    return answer, source
