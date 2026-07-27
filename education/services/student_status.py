"""O'quvchi HOLATI — bo'lim (Category) kesimida to'liq tarix.

Bu servis bitta o'quvchining markaz ichidagi butun tarixini yig'adi:

  Bo'lim (IT / English / ...)
    └── Guruh
          ├── necha oy o'qigan (start/end sanasi bilan)
          ├── chaqmoq: qaysi sababdan, kim qo'shgan/ayirgan, qachon
          ├── to'lovlar: qaysi sanada qancha, chek yuklab olish havolasi bilan
          ├── oylik hisob: qaysi oyga qancha yozilgan / to'langan / qarz
          └── davomat: kelgan / kech qolgan / sababli / sababsiz kunlar

Muhim qarorlar (chalkashlik bo'lmasligi uchun):

* Chaqmoq bo'yicha YAGONA manba — ``chaqmoq.Ledger``. Balans ham shu jadvaldan
  hisoblanadi (``core.views.user_view`` va ``Ledger.student_balansi`` bilan bir xil
  filtr), shuning uchun sahifadagi bo'limlar yig'indisi umumiy balansga
  ANIQ teng chiqadi. ``DailyLightningRecord`` — UI uchun ko'chirma, u yerdan
  qo'shimcha qo'shilsa qo'sh hisob bo'lardi, shuning uchun ishlatilmaydi.
* Guruhga bog'lanmagan (``group=None``) chaqmoq yozuvlari — davomat jarimasi,
  to'lov intizomi bonusi va h.k. — alohida "Umumiy" bo'limda ko'rsatiladi.
* "Necha oy o'qigan" — real faoliyat bo'lgan oylar soni: davomat yozuvi yoki
  oylik hisob (TuitionMonth) mavjud oylar birlashmasi. Bir oyda ikki guruhda
  o'qigan bo'lsa, bo'lim/umumiy darajada u bir oy deb sanaladi.
* Davomat holati: ``present`` bayrog'i ustuvor, chunki eski siklik rejim
  ``status`` ni default 'present' holida qoldirib, faqat ``present=False``
  qilgan (``education.services.attendance_service.toggle_attendance``).
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import Optional

from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from chaqmoq.models import Ledger
from education.models import (
    Attendance,
    Enrollment,
    Group,
    Payment,
    PaymentAllocation,
    StudentGroupHistory,
    TuitionMonth,
)

MONTH_NAMES = (
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
)

# Dushanba = 0 (date.weekday() tartibida)
WEEKDAY_SHORT = ("Du", "Se", "Chor", "Pay", "Jum", "Shan", "Yak")

# Davomat holatlari — bitta joyda belgilanadi, shablon shu kalitlarga tayanadi.
ATT_PRESENT = "present"
ATT_LATE = "late"
ATT_EXCUSED = "excused"
ATT_UNEXCUSED = "unexcused"
ATT_FORCED = "forced"
ATT_ABSENT = "absent"

ATT_LABELS = {
    ATT_PRESENT: "Keldi",
    ATT_LATE: "Kech qoldi",
    ATT_EXCUSED: "Sababli kelmadi",
    ATT_UNEXCUSED: "Sababsiz kelmadi",
    ATT_FORCED: "Kelmadi (dars yozilgan)",
    ATT_ABSENT: "Kelmadi",
}

# "Kelgan" deb sanaladigan holatlar (davomat foizi shulardan chiqadi).
ATTENDED_STATES = (ATT_PRESENT, ATT_LATE)

PAYMENT_TYPE_LABELS = {
    "cash": "Naqd",
    "card": "Karta",
    "mixed": "Aralash",
}

DEFAULT_SECTION_ICON = "📚"


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_label(d: date) -> str:
    return f"{MONTH_NAMES[d.month]} {d.year}"


def money(amount) -> str:
    """1 250 000 ko'rinishida (yaxlitlamasdan — chek summasi aniq bo'lishi shart)."""
    try:
        value = int(amount or 0)
    except (TypeError, ValueError):
        value = 0
    return f"{value:,}".replace(",", " ")


def attendance_state(status: str, present: bool, forced: bool) -> str:
    """Attendance yozuvidan yagona holat kalitini chiqaradi."""
    status = (status or "").strip()
    if status == "late":
        return ATT_LATE
    if status == "absent_excused":
        return ATT_EXCUSED
    if status == "absent_unexcused":
        return ATT_UNEXCUSED
    if present:
        return ATT_PRESENT
    if forced:
        return ATT_FORCED
    # status='present' bo'lsa-yu present=False bo'lsa — eski siklik rejim "kelmadi".
    return ATT_ABSENT


def _new_att_bucket() -> dict:
    return {
        "total": 0,
        ATT_PRESENT: 0,
        ATT_LATE: 0,
        ATT_EXCUSED: 0,
        ATT_UNEXCUSED: 0,
        ATT_FORCED: 0,
        ATT_ABSENT: 0,
    }


def _att_attended(bucket: dict) -> int:
    return sum(bucket[state] for state in ATTENDED_STATES)


def _att_missed(bucket: dict) -> int:
    return bucket["total"] - _att_attended(bucket)


def _att_rate(bucket: dict) -> int:
    if not bucket["total"]:
        return 0
    return int(round(_att_attended(bucket) / bucket["total"] * 100))


def _finish_att(bucket: dict) -> dict:
    bucket["attended"] = _att_attended(bucket)
    bucket["missed"] = _att_missed(bucket)
    bucket["rate"] = _att_rate(bucket)
    return bucket


def _local_date(value) -> Optional[date]:
    """DateTime → mahalliy sana (naive/aware ikkalasiga ham chidamli)."""
    if not value:
        return None
    if hasattr(value, "date"):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def _person_name(user) -> str:
    if not user:
        return ""
    full = f"{getattr(user, 'ism', '') or ''} {getattr(user, 'familya', '') or ''}".strip()
    return full or (getattr(user, "get_full_name", lambda: "")() or getattr(user, "email", "") or "")


def _ledger_reason(row: Ledger) -> str:
    name = (row.rule_nom or "").strip()
    if name:
        return name
    if row.rule_id and row.rule:
        return row.rule.nom
    return "Qo'lda kiritilgan"


def build_student_status(student, center) -> dict:
    """O'quvchi holati sahifasi uchun to'liq ma'lumot to'plami.

    ``center`` majburiy — markazsiz hech qanday ma'lumot chiqarilmaydi
    (boshqa markaz yozuvlari sizib chiqmasligi uchun).
    """
    if center is None:
        return _empty_status(student, None)

    # ── 1) Guruhlar to'plami ────────────────────────────────────────────────
    # Enrollment o'chirilgan bo'lsa ham tarix ko'rinishi kerak → all_objects.
    enrollments = list(
        Enrollment.all_objects
        .filter(student=student, group__center=center)
        .select_related("group", "group__category_obj", "group__oqituvchi")
        .order_by("-is_active", "-id")
    )
    enrollment_by_group: dict[int, Enrollment] = {}
    group_of_enrollment: dict[int, int] = {}
    for enr in enrollments:
        # Bir guruhda bir nechta enrollment bo'lsa (o'chirilgan + qayta qo'shilgan)
        # eng oxirgisi/faoli ustuvor — queryset shunga qarab tartiblangan.
        enrollment_by_group.setdefault(enr.group_id, enr)
        group_of_enrollment[enr.id] = enr.group_id

    group_ids: set[int] = set(enrollment_by_group.keys())

    attendance_rows = list(
        Attendance.objects
        .filter(student=student, group__center=center)
        .values("group_id", "date", "status", "present", "forced")
        .order_by("date")
    )
    group_ids.update(row["group_id"] for row in attendance_rows)

    payment_rows = list(
        Payment.objects
        .filter(student=student, group__center=center)
        .select_related("created_by")
        .order_by("-paid_date", "-id")
    )
    group_ids.update(p.group_id for p in payment_rows if p.group_id)

    # Chaqmoq — user_view / Ledger.student_balansi bilan bir xil markaz filtri.
    ledger_rows = list(
        Ledger.objects
        .filter(student=student)
        .filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))
        .select_related("beruvchi", "group", "group__category_obj", "rule")
        .order_by("-sana", "-id")
    )
    ledger_group_ids = {row.group_id for row in ledger_rows if row.group_id}

    groups_by_id: dict[int, Group] = {
        enr.group_id: enr.group for enr in enrollments
    }
    missing_ids = (group_ids | ledger_group_ids) - set(groups_by_id)
    if missing_ids:
        for g in Group.objects.filter(id__in=missing_ids).select_related("category_obj", "oqituvchi"):
            groups_by_id[g.id] = g
    # Boshqa markaz guruhi ledger orqali kirib qolsa — "Umumiy" ga tushadi.
    group_ids = {gid for gid in group_ids | ledger_group_ids if gid in groups_by_id}
    group_ids = {gid for gid in group_ids if groups_by_id[gid].center_id == center.id}

    # ── 2) Oylik hisob (TuitionMonth) va to'lov taqsimoti ───────────────────
    enrollment_ids = [enr.id for enr in enrollments]
    tuition_rows = list(
        TuitionMonth.objects
        .filter(enrollment_id__in=enrollment_ids)
        .values("id", "enrollment_id", "month", "fee_amount")
        .order_by("month")
    ) if enrollment_ids else []

    tm_ids = [row["id"] for row in tuition_rows]
    tm_paid: dict[int, int] = {}
    if tm_ids:
        for row in (
            PaymentAllocation.objects
            .filter(tuition_month_id__in=tm_ids)
            .values("tuition_month_id")
            .annotate(total=Sum("amount"))
        ):
            tm_paid[row["tuition_month_id"]] = int(row["total"] or 0)

    # Har bir to'lov qaysi oy(lar)ni yopgani — chek qatorida ko'rsatiladi.
    payment_ids = [p.id for p in payment_rows]
    payment_months: dict[int, list[str]] = {}
    if payment_ids:
        for row in (
            PaymentAllocation.objects
            .filter(payment_id__in=payment_ids)
            .select_related("tuition_month")
            .values("payment_id", "tuition_month__month", "amount")
            .order_by("tuition_month__month")
        ):
            m = row["tuition_month__month"]
            if not m:
                continue
            payment_months.setdefault(row["payment_id"], []).append(
                f"{month_label(m)} — {money(row['amount'])} so'm"
            )

    # ── 3) Guruh a'zoligi sanalari ──────────────────────────────────────────
    history_by_group: dict[int, dict] = {}
    for h in StudentGroupHistory.objects.filter(student=student, group_id__in=group_ids).order_by("start_date"):
        item = history_by_group.setdefault(h.group_id, {"start": h.start_date, "end": h.end_date})
        if h.start_date and (not item["start"] or h.start_date < item["start"]):
            item["start"] = h.start_date
        # end=None → hozir ham guruhda
        if item["end"] is not None:
            item["end"] = None if h.end_date is None else max(item["end"], h.end_date)

    # ── 4) Guruh bo'yicha yig'ish ───────────────────────────────────────────
    att_by_group: dict[int, list[dict]] = {}
    for row in attendance_rows:
        if row["group_id"] in group_ids:
            att_by_group.setdefault(row["group_id"], []).append(row)

    pay_by_group: dict[int, list[Payment]] = {}
    for p in payment_rows:
        if p.group_id in group_ids:
            pay_by_group.setdefault(p.group_id, []).append(p)

    led_by_group: dict[int, list[Ledger]] = {}
    general_ledger: list[Ledger] = []
    for row in ledger_rows:
        if row.group_id and row.group_id in group_ids:
            led_by_group.setdefault(row.group_id, []).append(row)
        else:
            general_ledger.append(row)

    # Bir guruhda bir nechta enrollment bo'lishi mumkin (chiqarilgan + qayta
    # qo'shilgan) — oylik hisob GURUH darajasida birlashtiriladi, aks holda
    # eski enrollment oylari yo'qolib qolardi.
    tuition_by_group: dict[int, list[dict]] = {}
    for row in tuition_rows:
        gid = group_of_enrollment.get(row["enrollment_id"])
        if gid in group_ids:
            tuition_by_group.setdefault(gid, []).append(row)

    group_cards = []
    for gid in group_ids:
        group = groups_by_id[gid]
        enr = enrollment_by_group.get(gid)
        group_cards.append(
            _build_group_card(
                group=group,
                enrollment=enr,
                attendance=att_by_group.get(gid, []),
                payments=pay_by_group.get(gid, []),
                ledger=led_by_group.get(gid, []),
                tuition=tuition_by_group.get(gid, []),
                tm_paid=tm_paid,
                payment_months=payment_months,
                history=history_by_group.get(gid),
            )
        )

    # ── 5) Bo'limlar (Category) bo'yicha guruhlash ──────────────────────────
    sections = _build_sections(group_cards)

    # ── 6) Umumiy (guruhsiz) chaqmoq ────────────────────────────────────────
    general = _build_general_ledger(general_ledger)

    # ── 7) Umumiy ko'rsatkichlar ────────────────────────────────────────────
    totals = _build_totals(sections, general, group_cards)

    return {
        "student": student,
        "center": center,
        "sections": sections,
        "general": general,
        "totals": totals,
        "verdict": _build_verdict(totals),
        "has_data": bool(sections or general["count"]),
    }


def _empty_status(student, center) -> dict:
    general = _build_general_ledger([])
    totals = _build_totals([], general, [])
    return {
        "student": student,
        "center": center,
        "sections": [],
        "general": general,
        "totals": totals,
        "verdict": _build_verdict(totals),
        "has_data": False,
    }


def _build_group_card(
    *, group, enrollment, attendance, payments, ledger, tuition,
    tm_paid, payment_months, history,
) -> dict:
    months: set[str] = set()
    month_dates: dict[str, date] = {}

    def _remember_month(d: date):
        key = month_key(d)
        months.add(key)
        month_dates.setdefault(key, date(d.year, d.month, 1))

    # ── Davomat ──
    att_total = _new_att_bucket()
    att_months: "OrderedDict[str, dict]" = OrderedDict()
    first_att: Optional[date] = None
    last_att: Optional[date] = None

    for row in attendance:
        d = row["date"]
        if not d:
            continue
        _remember_month(d)
        if first_att is None or d < first_att:
            first_att = d
        if last_att is None or d > last_att:
            last_att = d

        state = attendance_state(row["status"], row["present"], row["forced"])
        att_total["total"] += 1
        att_total[state] += 1

        key = month_key(d)
        bucket = att_months.get(key)
        if bucket is None:
            bucket = {
                "key": key,
                "label": month_label(d),
                "month": date(d.year, d.month, 1),
                "days": [],
                "stats": _new_att_bucket(),
            }
            att_months[key] = bucket
        bucket["stats"]["total"] += 1
        bucket["stats"][state] += 1
        bucket["days"].append({
            "date": d,
            "day": d.day,
            "dow": WEEKDAY_SHORT[d.weekday()],
            "state": state,
            "label": ATT_LABELS[state],
            "attended": state in ATTENDED_STATES,
        })

    # ── Chaqmoq ──
    plus = sum(r.ball for r in ledger if r.ball > 0)
    minus = sum(-r.ball for r in ledger if r.ball < 0)
    ledger_entries = [{
        "date": _local_date(r.sana),
        "datetime": r.sana,
        "points": r.ball,
        "is_plus": r.ball > 0,
        "reason": _ledger_reason(r),
        "given_by": _person_name(r.beruvchi) or "Tizim (avtomatik)",
        "is_auto": r.beruvchi_id is None,
    } for r in ledger]

    # ── To'lovlar ──
    payment_rows = []
    paid_total = 0
    for p in payments:
        paid_total += int(p.summa or 0)
        payment_rows.append({
            "id": p.id,
            "date": p.paid_date,
            # 00:00 — vaqt kiritilmagan eski yozuvlar; shovqin qilmasin.
            "time": p.paid_time if p.paid_time and (p.paid_time.hour or p.paid_time.minute) else None,
            "amount": int(p.summa or 0),
            "amount_text": money(p.summa),
            "cash": int(p.cash_amount or 0),
            "cash_text": money(p.cash_amount),
            "card": int(p.card_amount_som or 0),
            "card_text": money(p.card_amount_som),
            "type": p.payment_type,
            "type_label": PAYMENT_TYPE_LABELS.get(p.payment_type, p.payment_type or "—"),
            "note": (p.note or "").strip(),
            "created_by": _person_name(p.created_by),
            "covered_months": payment_months.get(p.id, []),
            "receipt_url": reverse("education:payment_receipt_pdf", args=[p.id]),
        })

    # ── Oylik hisob (yozilgan / to'langan / qarz) ──
    # Bir oyda ikkita enrollment bo'lsa ham bitta qator ko'rsatiladi.
    tuition_by_month: "OrderedDict[str, dict]" = OrderedDict()
    for row in tuition:
        m = row["month"]
        if not m:
            continue
        _remember_month(m)
        key = month_key(m)
        item = tuition_by_month.get(key)
        if item is None:
            item = {
                "key": key,
                "month": date(m.year, m.month, 1),
                "label": month_label(m),
                "fee": 0,
                "paid": 0,
            }
            tuition_by_month[key] = item
        item["fee"] += int(row["fee_amount"] or 0)
        item["paid"] += int(tm_paid.get(row["id"], 0))

    tuition_display = []
    fee_total = 0
    paid_alloc_total = 0
    for item in sorted(tuition_by_month.values(), key=lambda x: x["month"], reverse=True):
        fee = item["fee"]
        paid = item["paid"]
        debt = max(0, fee - paid)
        fee_total += fee
        paid_alloc_total += paid
        item.update({
            "fee_text": money(fee),
            "paid_text": money(paid),
            "debt": debt,
            "debt_text": money(debt),
            "status": "paid" if debt == 0 and fee > 0 else ("partial" if paid > 0 else "unpaid"),
        })
        tuition_display.append(item)
    debt_total = max(0, fee_total - paid_alloc_total)

    # ── A'zolik sanalari ──
    start_date = None
    end_date = None
    if history:
        start_date = history.get("start")
        end_date = history.get("end")
    if not start_date and enrollment:
        start_date = enrollment.joined_at or _local_date(enrollment.created_at)
    if not start_date:
        start_date = first_att

    is_active = bool(enrollment and enrollment.is_active and not enrollment.is_deleted)
    if not is_active and not end_date:
        if enrollment and enrollment.last_lesson_date:
            end_date = enrollment.last_lesson_date
        else:
            end_date = last_att

    sorted_month_keys = sorted(months)
    ordered_months = [month_dates[k] for k in sorted_month_keys]

    # Oylik ko'rinishlarni eng yangisi birinchi bo'lib chiqadigan qilamiz.
    att_month_list = []
    for bucket in sorted(att_months.values(), key=lambda b: b["month"], reverse=True):
        bucket["stats"] = _finish_att(bucket["stats"])
        bucket["days"].sort(key=lambda x: x["date"])
        att_month_list.append(bucket)

    category = group.category_obj
    return {
        "id": group.id,
        "name": group.nom,
        "url": reverse("education:group_detail", args=[group.id]),
        "teacher": _person_name(group.oqituvchi) or "—",
        "is_active": is_active,
        "is_archived": bool(group.is_archived),
        "status_label": "Faol" if is_active else "Tugagan / chiqarilgan",
        "start_date": start_date,
        "end_date": end_date,
        "months_count": len(months),
        "month_keys": sorted_month_keys,
        "months_first": ordered_months[0] if ordered_months else None,
        "months_last": ordered_months[-1] if ordered_months else None,
        "section": {
            "id": category.id if category else None,
            "name": category.name if category else (group.get_category_display() or "Boshqa"),
            "icon": (category.icon if category and category.icon else DEFAULT_SECTION_ICON),
            "key": f"cat-{category.id}" if category else f"legacy-{group.category or 'other'}",
        },
        "chaqmoq": {
            "plus": plus,
            "minus": minus,
            "net": plus - minus,
            "count": len(ledger_entries),
            "entries": ledger_entries,
        },
        "payments": {
            "total": paid_total,
            "total_text": money(paid_total),
            "count": len(payment_rows),
            "rows": payment_rows,
        },
        "tuition": {
            "rows": tuition_display,
            "fee_total": fee_total,
            "fee_total_text": money(fee_total),
            "paid_total": paid_alloc_total,
            "paid_total_text": money(paid_alloc_total),
            "debt_total": debt_total,
            "debt_total_text": money(debt_total),
        },
        "attendance": {
            "stats": _finish_att(att_total),
            "months": att_month_list,
        },
    }


def _build_sections(group_cards: list[dict]) -> list[dict]:
    sections: "OrderedDict[str, dict]" = OrderedDict()
    for card in group_cards:
        meta = card["section"]
        section = sections.get(meta["key"])
        if section is None:
            section = {
                "key": meta["key"],
                "id": meta["id"],
                "name": meta["name"],
                "icon": meta["icon"],
                "groups": [],
                "month_keys": set(),
                "plus": 0, "minus": 0,
                "paid": 0, "fee": 0, "debt": 0,
                "att": _new_att_bucket(),
                "is_active": False,
                "start_date": None,
                "end_date": None,
                "has_open_end": False,
            }
            sections[meta["key"]] = section

        section["groups"].append(card)
        section["month_keys"].update(card["month_keys"])
        section["plus"] += card["chaqmoq"]["plus"]
        section["minus"] += card["chaqmoq"]["minus"]
        section["paid"] += card["payments"]["total"]
        section["fee"] += card["tuition"]["fee_total"]
        section["debt"] += card["tuition"]["debt_total"]
        for key in section["att"]:
            section["att"][key] += card["attendance"]["stats"][key]
        if card["is_active"]:
            section["is_active"] = True

        if card["start_date"]:
            if not section["start_date"] or card["start_date"] < section["start_date"]:
                section["start_date"] = card["start_date"]
        if card["end_date"]:
            if not section["end_date"] or card["end_date"] > section["end_date"]:
                section["end_date"] = card["end_date"]
        else:
            section["has_open_end"] = True

    result = []
    for section in sections.values():
        section["months_count"] = len(section["month_keys"])
        section["net"] = section["plus"] - section["minus"]
        section["paid_text"] = money(section["paid"])
        section["fee_text"] = money(section["fee"])
        section["debt_text"] = money(section["debt"])
        section["att"] = _finish_att(section["att"])
        section["groups_count"] = len(section["groups"])
        if section["has_open_end"]:
            section["end_date"] = None
        section["groups"].sort(key=lambda c: (not c["is_active"], -(c["months_count"]), c["name"]))
        result.append(section)

    # Faol bo'limlar tepada, keyin ko'proq o'qilgan bo'lim.
    result.sort(key=lambda s: (not s["is_active"], -s["months_count"], s["name"]))
    return result


def _build_general_ledger(rows: list[Ledger]) -> dict:
    plus = sum(r.ball for r in rows if r.ball > 0)
    minus = sum(-r.ball for r in rows if r.ball < 0)
    entries = [{
        "date": _local_date(r.sana),
        "points": r.ball,
        "is_plus": r.ball > 0,
        "reason": _ledger_reason(r),
        "given_by": _person_name(r.beruvchi) or "Tizim (avtomatik)",
        "is_auto": r.beruvchi_id is None,
        "group_name": r.group.nom if r.group_id and r.group else "",
    } for r in rows]
    return {
        "plus": plus,
        "minus": minus,
        "net": plus - minus,
        "count": len(entries),
        "entries": entries,
    }


def _build_totals(sections: list[dict], general: dict, group_cards: list[dict]) -> dict:
    all_months: set[str] = set()
    att = _new_att_bucket()
    plus = general["plus"]
    minus = general["minus"]
    paid = fee = debt = 0
    payments_count = 0
    active_groups = 0

    for card in group_cards:
        all_months.update(card["month_keys"])
        plus += card["chaqmoq"]["plus"]
        minus += card["chaqmoq"]["minus"]
        paid += card["payments"]["total"]
        payments_count += card["payments"]["count"]
        fee += card["tuition"]["fee_total"]
        debt += card["tuition"]["debt_total"]
        for key in att:
            att[key] += card["attendance"]["stats"][key]
        if card["is_active"]:
            active_groups += 1

    starts = [c["start_date"] for c in group_cards if c["start_date"]]
    ends = [c["end_date"] for c in group_cards if c["end_date"]]
    has_open = any(c["end_date"] is None for c in group_cards)

    return {
        "balance": plus - minus,
        "plus": plus,
        "minus": minus,
        "sections_count": len(sections),
        "groups_count": len(group_cards),
        "active_groups": active_groups,
        "months_count": len(all_months),
        "paid": paid,
        "paid_text": money(paid),
        "fee": fee,
        "fee_text": money(fee),
        "debt": debt,
        "debt_text": money(debt),
        "payments_count": payments_count,
        "attendance": _finish_att(att),
        "first_date": min(starts) if starts else None,
        "last_date": None if has_open else (max(ends) if ends else None),
    }


def _build_verdict(totals: dict) -> dict:
    """Do'kondan mahsulot berish qarori uchun qisqa ko'rsatkichlar.

    Hech narsani "hal qilmaydi" — faqat qaror qabul qiluvchiga uch signalni
    bir joyda ko'rsatadi: balans, davomat intizomi, to'lov intizomi.
    """
    att = totals["attendance"]
    rate = att["rate"]
    if att["total"] == 0:
        att_level, att_text = "none", "Davomat yozuvi yo'q"
    elif rate >= 90:
        att_level, att_text = "good", "A'lo davomat"
    elif rate >= 75:
        att_level, att_text = "ok", "Yaxshi davomat"
    else:
        att_level, att_text = "bad", "Davomat past"

    if totals["fee"] == 0:
        pay_level, pay_text = "none", "Oylik hisob yo'q"
    elif totals["debt"] == 0:
        pay_level, pay_text = "good", "Qarzi yo'q"
    else:
        pay_level, pay_text = "bad", f"Qarzi bor: {totals['debt_text']} so'm"

    return {
        "balance": totals["balance"],
        "attendance_level": att_level,
        "attendance_text": att_text,
        "payment_level": pay_level,
        "payment_text": pay_text,
    }
