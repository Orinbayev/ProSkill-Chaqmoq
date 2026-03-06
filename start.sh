#!/bin/bash
# Chaqmoq Academy Unified Startup Script

echo "--- 🚀 System Startup Initiated ---"

# 1. Start the Telegram Bot in the background and redirect logs to a file
echo "🤖 Starting Telegram Bot..."
# Use python3 -u for unbuffered output to see logs faster
python3 -u telegram_bot/bot.py > bot_output.log 2>&1 &
BOT_PID=$!

# 2. Wait a bit and check if bot is still alive
sleep 3
if ps -p $BOT_PID > /dev/null
then
   echo "✅ Bot is running effectively (PID: $BOT_PID)"
else
   echo "❌ ERROR: Bot failed to start! Check bot_output.log"
   cat bot_output.log
fi

# 3. Start the Django application
if [ -z "$PORT" ]; then
  echo "🏠 Running locally on port 8000"
  python3 manage.py runserver 0.0.0.0:8000
else
  echo "🌐 Running on Render port $PORT"
  # Using "python3 -m gunicorn" instead of just "gunicorn" is more robust on some server environments
  python3 -m gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile -
fi
