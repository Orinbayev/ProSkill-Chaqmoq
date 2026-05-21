#!/bin/bash
set -e

# ChaqmoqApp - Render-safe startup script
echo '--- 🚀 Starting ChaqmoqApp System ---'
echo "⚙️ DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}"
if [ -n "${DATABASE_URL:-}" ]; then
  echo '🗄️ DATABASE_URL is set'
else
  echo '🗄️ DATABASE_URL is missing'
fi

BOT_PID=""
cleanup() {
  if [ -n "$BOT_PID" ]; then
    echo "🧹 Stopping Telegram Bot (pid=$BOT_PID)..."
    kill "$BOT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

BOT_ENV_ENABLED="${TELEGRAM_BOT_ENABLED:-auto}"
BOT_TOKEN_VALUE="${BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"

if [ "$BOT_ENV_ENABLED" != "0" ] && [ "$BOT_ENV_ENABLED" != "false" ] && [ -n "$BOT_TOKEN_VALUE" ]; then
  # Pipe bot logs into the main Render log stream, but keep it optional so the
  # web app can stay alive on small 512MB instances.
  echo '🤖 Launching Telegram Bot...'
  python3 -u telegram_bot/bot.py &
  BOT_PID=$!
else
  echo '🤖 Telegram Bot skipped (set TELEGRAM_BOT_ENABLED=true and BOT_TOKEN/TELEGRAM_BOT_TOKEN to enable).'
fi

if [ -z "$RENDER" ]; then
  echo '🏠 Local dev mode'
  python3 manage.py runserver 0.0.0.0:8000
else
  echo '🗄️  Running migrations...'
  python3 manage.py migrate --noinput
  WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
  GUNICORN_THREADS="${GUNICORN_THREADS:-4}"
  GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-60}"
  GUNICORN_GRACEFUL_TIMEOUT="${GUNICORN_GRACEFUL_TIMEOUT:-30}"
  GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-500}"
  GUNICORN_MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-50}"

  echo "🌐 Production mode on Render (Port $PORT)"
  echo "🧠 Gunicorn: workers=$WEB_CONCURRENCY threads=$GUNICORN_THREADS timeout=$GUNICORN_TIMEOUT max_requests=$GUNICORN_MAX_REQUESTS"
  python3 -m gunicorn config.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers "$WEB_CONCURRENCY" \
    --threads "$GUNICORN_THREADS" \
    --timeout "$GUNICORN_TIMEOUT" \
    --graceful-timeout "$GUNICORN_GRACEFUL_TIMEOUT" \
    --max-requests "$GUNICORN_MAX_REQUESTS" \
    --max-requests-jitter "$GUNICORN_MAX_REQUESTS_JITTER" \
    --access-logfile - \
    --error-logfile -
fi
