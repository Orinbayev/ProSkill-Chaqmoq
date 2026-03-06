import os
import sys
import asyncio
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiohttp import web
from config import BOT_TOKEN, API_SECRET
from handlers import start, link_account, profile, activity, security, help

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Include routers
dp.include_router(start.router)
dp.include_router(link_account.router)
dp.include_router(profile.router)
dp.include_router(activity.router)
dp.include_router(security.router)
dp.include_router(help.router)

async def handle_send_message(request):
    """
    Internal API to send messages from Django backend (Security Alerts, OTP, etc.)
    """
    if request.headers.get("X-API-SECRET") != API_SECRET:
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
            except Exception as e:
                logging.warning(f"Markup validation failed: {e}. Attempting raw dict...")
                # Raw dict might work if aiogram allows it or if we cast it
                reply_markup = reply_markup_data

        if not chat_id or not text:
            return web.json_response({"error": "Missing chat_id or text"}, status=400)
            
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        return web.json_response({"status": "ok"})
    except Exception as e:
        logging.error(f"Error in send_message API: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def start_api():
    # Use a separate port for internal API to avoid conflict with Render's $PORT
    api_port = int(os.getenv("BOT_API_PORT", 8080))
    app = web.Application()
    app.router.add_post("/send_message", handle_send_message)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", api_port)
    await site.start()
    logging.info(f"Bot Internal API started on port {api_port}")

async def main():
    # 🚨 CRITICAL: Start the Internal API FIRST
    await start_api()
    
    # Then start polling
    logging.info("Starting Bot Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
