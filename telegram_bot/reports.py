from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.utils import timezone

from core.dashboard_metrics import (
    get_center_active_groups_count,
    get_center_attendance_snapshot,
    get_center_debtors_count,
    get_center_month_income,
    get_center_today_income,
    month_start,
)

logger = logging.getLogger(__name__)


def send_daily_report(center):
    """
    Har kuni soat 20:00 da direktorga yuboriladi.
    Tarkib:
    - Bugungi tushum
    - Bu oyning jami tushumi
    - Yangi qarzdorlar soni
    - Bugungi davomat foizi
    - Faol guruhlar soni
    """
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(center, "director_telegram_id", "") or ""
    if not bot_token or not chat_id:
        return False

    today = timezone.localdate()
    current_month = month_start(today)
    attendance = get_center_attendance_snapshot(center, today)
    today_income = get_center_today_income(center, today)
    month_income = get_center_month_income(center, current_month)
    debtors = get_center_debtors_count(center, current_month)
    active_groups = get_center_active_groups_count(center)

    text = (
        f"📊 *{center.name} — Kunlik hisobot*\n"
        f"📅 {today.strftime('%d.%m.%Y')}\n\n"
        f"💰 Bugungi tushum: *{today_income:,} so'm*\n"
        f"📈 Oylik jami: *{month_income:,} so'm*\n"
        f"❗ Qarzdorlar: *{debtors} ta*\n"
        f"✅ Bugungi davomat: *{attendance['pct']}%* ({attendance['label']})\n"
        f"👥 Faol guruhlar: *{active_groups} ta*"
    )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("send_daily_report failed for center=%s", center.pk)
        return False
