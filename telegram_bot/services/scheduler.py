import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.api_client import get_parent_reports_api, get_settings_api
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

async def setup_scheduler(bot):
    scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
    
    async def scheduled_task():
        uz_tz = pytz.timezone('Asia/Tashkent')
        now = datetime.now(uz_tz).strftime("%H:%M")
        
        # Default 20:00 (In a real app, fetch from settings)
        target_time = "20:00" 
        
        if now == target_time:
            await send_daily_reports(bot)

    # Check every minute
    scheduler.add_job(scheduled_task, CronTrigger(second=0))
    scheduler.start()
    logger.info("Scheduler started.")
