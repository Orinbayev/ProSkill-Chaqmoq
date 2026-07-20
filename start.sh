#!/bin/bash
set -e

# ChaqmoqApp - Render-safe startup script
# Muhim: avval Gunicorn portga bog'lanadi (health check / 502 oldini olish),
# Telegram bot keyinroq ishga tushadi (xotira + boot race).
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
    wait "$BOT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

start_bot_delayed() {
  BOT_ENV_ENABLED="${TELEGRAM_BOT_ENABLED:-auto}"
  BOT_TOKEN_VALUE="${BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
  BOT_START_DELAY="${BOT_START_DELAY:-12}"

  if [ "$BOT_ENV_ENABLED" = "0" ] || [ "$BOT_ENV_ENABLED" = "false" ]; then
    echo '🤖 Telegram Bot skipped (TELEGRAM_BOT_ENABLED=false).'
    return 0
  fi
  if [ -z "$BOT_TOKEN_VALUE" ]; then
    echo '🤖 Telegram Bot skipped (BOT_TOKEN / TELEGRAM_BOT_TOKEN yo‘q).'
    return 0
  fi

  # Port bind + health check o'tgach botni ishga tushiramiz — cold start 502 kamayadi.
  echo "🤖 Telegram Bot ${BOT_START_DELAY}s kechiktirib ishga tushadi..."
  (
    sleep "$BOT_START_DELAY"
    echo '🤖 Launching Telegram Bot...'
    exec python3 -u telegram_bot/bot.py
  ) &
  BOT_PID=$!
}

if [ -z "$RENDER" ]; then
  echo '🏠 Local dev mode'
  start_bot_delayed
  python3 manage.py runserver 0.0.0.0:8000
else
  WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
  GUNICORN_THREADS="${GUNICORN_THREADS:-4}"
  GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-60}"
  GUNICORN_GRACEFUL_TIMEOUT="${GUNICORN_GRACEFUL_TIMEOUT:-30}"
  # Kam worker restart = kam 502. 500 past edi — worker recycle paytida gateway xatosi.
  GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-2000}"
  GUNICORN_MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-100}"
  GUNICORN_KEEPALIVE="${GUNICORN_KEEPALIVE:-5}"

  echo "🌐 Production mode on Render (Port $PORT)"
  echo "🧠 Gunicorn: workers=$WEB_CONCURRENCY threads=$GUNICORN_THREADS timeout=$GUNICORN_TIMEOUT max_requests=$GUNICORN_MAX_REQUESTS"

  # Avval web — healthCheckPath=/health/ tez javob bersin.
  # exec ishlatmaymiz: trap botni to'g'ri o'chirsin; gunicorn foreground.
  start_bot_delayed

  python3 -m gunicorn config.wsgi:application \
    --bind "0.0.0.0:$PORT" \
    --workers "$WEB_CONCURRENCY" \
    --threads "$GUNICORN_THREADS" \
    --timeout "$GUNICORN_TIMEOUT" \
    --graceful-timeout "$GUNICORN_GRACEFUL_TIMEOUT" \
    --keep-alive "$GUNICORN_KEEPALIVE" \
    --max-requests "$GUNICORN_MAX_REQUESTS" \
    --max-requests-jitter "$GUNICORN_MAX_REQUESTS_JITTER" \
    --access-logfile - \
    --error-logfile -
fi
