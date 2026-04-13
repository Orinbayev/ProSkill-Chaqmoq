import os
import sys
import asyncio
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiohttp import web
from app_config import BOT_TOKEN, API_SECRET
from handlers import start, link_account, profile, activity, security, help
from handlers import admin_panel, linked_users, broadcast, admins, parents, settings
from handlers import student, teacher, parent, manager
from services.scheduler import setup_scheduler

try:
    from backup.backup_service import setup_backup_scheduler, router as backup_router
except Exception as backup_import_err:
    setup_backup_scheduler = None
    backup_router = None
    logging.error("Backup bot module disabled: %s", backup_import_err)


# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def env_flag(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Include routers
dp.include_router(start.router)
dp.include_router(link_account.router)
dp.include_router(profile.router)
dp.include_router(activity.router)
dp.include_router(security.router)
dp.include_router(help.router)

# Admin Routers
dp.include_router(admin_panel.router)
dp.include_router(linked_users.router)
dp.include_router(broadcast.router)
dp.include_router(admins.router)
dp.include_router(parents.router)
dp.include_router(settings.router)
dp.include_router(student.router)
dp.include_router(parent.router)
dp.include_router(teacher.router)
dp.include_router(manager.router)
if backup_router is not None:
    dp.include_router(backup_router)  # Register manual backup command

async def handle_send_message(request):
    """
    Internal API to send messages from Django backend (Security Alerts, OTP, etc.)
    Faqat localhost (127.0.0.1) dan kelgan so'rovlar qabul qilinadi.
    """
    # 1. IP tekshiruvi — faqat localhost
    peer_ip = request.remote
    if peer_ip not in ("127.0.0.1", "::1"):
        logging.warning("Bot API: remote IP rejected: %s", peer_ip)
        return web.json_response({"error": "Forbidden"}, status=403)

    # 2. Secret tekshiruvi
    if request.headers.get("X-API-SECRET") != API_SECRET:
        logging.warning("Bot API: invalid secret from %s", peer_ip)
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        text = data.get("text")
        reply_markup_data = data.get("reply_markup")
        
        reply_markup = None
        if reply_markup_data:
            from aiogram.types import InlineKeyboardMarkup
            try:
                # If it's already a dict representation of InlineKeyboardMarkup
                if isinstance(reply_markup_data, dict):
                    reply_markup = InlineKeyboardMarkup.model_validate(reply_markup_data)
                else: 
                    reply_markup = reply_markup_data
            except Exception as err:
                logging.warning(f"Markup validation failed: {err}. Attempting raw dict...")
                # Raw dict might work if aiogram allows it or if we cast it
                reply_markup = reply_markup_data

        if not chat_id or not text:
            return web.json_response({"error": "Missing chat_id or text"}, status=400)
            
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        return web.json_response({"status": "ok"})
    except Exception as err:
        logging.error(f"Error in send_message API: {err}")
        return web.json_response({"error": str(err)}, status=500)

async def start_api():
    # Use a separate port for internal API to avoid conflict with Render's $PORT
    api_port = int(os.getenv("BOT_API_PORT", 8080))
    app = web.Application()
    app.router.add_post("/send_message", handle_send_message)
    runner = web.AppRunner(app)
    await runner.setup()
    # Binding to 0.0.0.0 inside the container is more reliable on Render
    # 127.0.0.1 — faqat localhost dan kirish, tashqaridan kirish yo'q
    site = web.TCPSite(runner, "127.0.0.1", api_port)
    await site.start()
    logging.info(f"🚀 Bot Internal API started on 127.0.0.1:{api_port} (localhost only)")

async def main():
    # 1. Start the Internal API FIRST
    try:
        await start_api()
    except Exception as err:
        logging.error(f"❌ Failed to start Internal API: {err}")

    # 2. Start Schedulers
    await setup_scheduler(bot)
    # BackgroundScheduler – sync, shuning uchun await KERAK EMAS.
    # Render web servisida backup alohida cron job orqali yuradi; shu sabab bot
    # ichida daily backup scheduler default o'chiq turadi.
    if setup_backup_scheduler is not None and env_flag("BOT_BACKUP_SCHEDULER_ENABLED", False):
        try:
            setup_backup_scheduler()
            print("✅ Backup scheduler (BackgroundScheduler) ishga tushdi.")
        except Exception as _bs_err:
            logging.error(f"❌ Backup scheduler xatosi: {_bs_err}")
    elif setup_backup_scheduler is not None:
        logging.info("Backup scheduler skipped in bot process (BOT_BACKUP_SCHEDULER_ENABLED is not true).")
    else:
        logging.warning("⚠️ Backup scheduler skipped because backup module failed to load.")
    print("✅ All Schedulers started.")


    # 3. Start polling in a robust infinite loop
    print("🤖 Bot Polling is starting NOW...")
    logging.info("🤖 Starting Bot Polling loop...")
    while True:
        print("💡 Polling iteration started...")
        try:
            # We use a fresh polling session each time
            await dp.start_polling(bot, handle_signals=False)
        except Exception as err:
            logging.error(f"⚠️ Polling encountered an error: {err}")
            logging.info("🔄 Retrying in 10 seconds... (Make sure no other bot is running!)")
            await asyncio.sleep(10)
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.critical(f"Bot crashed: {e}")
