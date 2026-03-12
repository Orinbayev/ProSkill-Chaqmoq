#!/bin/bash
# ChaqmoqApp - ULTIMATE STARTUP SCRIPT
echo '--- 🚀 Starting ChaqmoqApp System ---'

# 1. Start the bot and pipe logs directly to the main console (stdout) 
# so we can see errors in the Render log dashboard!
echo '🤖 Launching Telegram Bot...'
python3 -u telegram_bot/bot.py 2>&1 | sed 's/^/[BOT] /' &

# 2. Start the Django application
if [ -z "$RENDER" ]; then
  echo '🏠 Local dev mode'
  python3 manage.py runserver 0.0.0.0:8000
else
  echo "🌐 Production mode on Render (Port $PORT)"
  python3 -m gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --access-logfile - --error-logfile -
fi
