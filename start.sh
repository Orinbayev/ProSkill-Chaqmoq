#!/bin/bash
# Install dependencies if needed (for local)
# pip install -r requirements.txt

echo "🚀 Starting Chaqmoq Academy System..."

# Start the Telegram Bot in the background
# We use & to run it concurrently with Django
python3 telegram_bot/bot.py &

# Wait a second for bot to initialize its API
sleep 2

# Start the Django application
# On Render, $PORT is provided automatically
if [ -z "$PORT" ]; then
  echo "Running locally on port 8000"
  python3 manage.py runserver 0.0.0.0:8000
else
  echo "Running on Render port $PORT"
  gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60
fi
