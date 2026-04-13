import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.api_client import (
    get_parent_reports_api,
    get_scheduler_month_end_reminders_api,
    get_scheduler_parent_attendance_api,
    get_scheduler_payment_reminders_api,
    get_scheduler_weekly_reports_api,
)
from datetime import datetime
import pytz
from aiogram import html

logger = logging.getLogger(__name__)

async def send_daily_reports(bot):
    logger.info("Starting daily parent reports job...")
    
    status, data = await get_parent_reports_api()
    if status != 200:
        logger.error(f"Failed to fetch reports data: {status}")
        return

    reports = data.get("reports", {})
    if not reports:
        logger.info("No reports to send today.")
        return

    sent = 0
    uz_tz = pytz.timezone('Asia/Tashkent')
    today_str = datetime.now(uz_tz).strftime("%Y-%m-%d")

    for tg_id, children in reports.items():
        text = "📘 <b>Farzandingiz bo‘yicha kunlik hisobot</b>\n\n"
        
        for student in children:
            student_name = html.quote(student['name'])
            text += f"👦 <b>O‘quvchi:</b> {student_name}\n"
            text += f"📅 Sana: {today_str}\n\n"
            text += f"✅ Bugun qo‘shilgan: <b>{student['total_today_plus']}</b>\n"
            text += f"❌ Bugun ayrilgan: <b>{student['total_today_minus']}</b>\n"
            text += f"⚡ Joriy jami chaqmoq: <b>{student['current_total']}</b>\n\n"
            
            if student['added']:
                text += "<b>Qo‘shilganlar:</b>\n"
                for pair in student['added']:
                    reason = html.quote(pair['reason'])
                    by = html.quote(pair['by'])
                    text += f"- {pair['ball']} ta — {reason} — {by}\n"
            
            if student['removed']:
                text += "\n<b>Ayrilganlar:</b>\n"
                for pair in student['removed']:
                    reason = html.quote(pair['reason'])
                    by = html.quote(pair['by'])
                    text += f"- {pair['ball']} ta — {reason} — {by}\n"
            
            text += "\n" + "—" * 15 + "\n\n"

        try:
            await bot.send_message(tg_id, text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05) # Rate limit
        except Exception as e:
            logger.warning(f"Failed to send report to {tg_id}: {e}")

    logger.info(f"Daily reports job finished. Sent: {sent}")


async def _dispatch_scheduler_payload(bot, job_name: str, fetcher):
    logger.info("Scheduler job started: %s", job_name)
    try:
        status, data = await fetcher()
        if status != 200 or not data.get("ok"):
            logger.warning("Scheduler job failed: %s status=%s", job_name, status)
            return

        items = data.get("items", [])
        if not items:
            logger.info("Scheduler job has no recipients: %s", job_name)
            return

        sent = 0
        for item in items:
            chat_id = item.get("chat_id")
            text = item.get("text")
            if not chat_id or not text:
                continue
            try:
                await bot.send_message(chat_id, text, parse_mode="HTML")
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as exc:
                logger.warning("%s: failed to send to %s: %s", job_name, chat_id, exc)

        logger.info("Scheduler job finished: %s sent=%s", job_name, sent)
    except Exception as exc:
        logger.exception("Scheduler dispatch crashed: %s / %s", job_name, exc)

async def setup_scheduler(bot):
    scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
    
    async def configured_parent_reports_job():
        uz_tz = pytz.timezone('Asia/Tashkent')
        now = datetime.now(uz_tz).strftime("%H:%M")
        
        # Legacy daily points report saqlanadi.
        target_time = "20:00" 
        
        if now == target_time:
            await send_daily_reports(bot)

    async def payment_reminders_job():
        await _dispatch_scheduler_payload(bot, "payment_reminders", get_scheduler_payment_reminders_api)

    async def parent_attendance_job():
        await _dispatch_scheduler_payload(bot, "parent_attendance", get_scheduler_parent_attendance_api)

    async def weekly_reports_job():
        await _dispatch_scheduler_payload(bot, "weekly_reports", get_scheduler_weekly_reports_api)

    async def month_end_job():
        await _dispatch_scheduler_payload(bot, "month_end_reminders", get_scheduler_month_end_reminders_api)

    scheduler.add_job(configured_parent_reports_job, CronTrigger(second=0), id="legacy_daily_parent_reports")
    scheduler.add_job(payment_reminders_job, CronTrigger(day="*/2", hour=9, minute=0), id="payment_reminders")
    scheduler.add_job(parent_attendance_job, CronTrigger(hour=19, minute=0), id="parent_attendance")
    scheduler.add_job(weekly_reports_job, CronTrigger(day_of_week="sun", hour=20, minute=0), id="weekly_reports")
    scheduler.add_job(month_end_job, CronTrigger(day=25, hour=9, minute=0), id="month_end_reminders")
    scheduler.start()
    logger.info("Scheduler started.")
