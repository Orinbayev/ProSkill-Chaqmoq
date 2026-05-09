"""
Performance logging middleware — production diagnostics.

Har request uchun stdout'ga chiqaradi (Render logsida ko'rinadi):

  [PERF] GET /api/boshqaruv/ | 4175ms | 298q | 200  [CRITICAL][N+1?]
  [PERF] GET /dashboard/     |  450ms |  22q | 200
  [PERF] POST /qoshish/      |  230ms |   8q | 302

Render logsida filtrlash:
  grep "[PERF]"
  grep "CRITICAL\|N+1\|HIGH-Q"

Settings (config/settings.py yoki Render env vars):
  SLOW_REQUEST_MS  = 800     # ms, bu'dan sekin bo'lsa [SLOW] tegi
  PERF_LOG_ALL     = True    # False qilsangiz faqat sekin/yuqori-query loglanadi
"""
from __future__ import annotations

import time
from contextlib import ExitStack

from django.conf import settings
from django.db import connections

_SKIP_PREFIXES = ("/static/", "/favicon.", "/.well-known/", "/robots.txt")


class SlowRequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Render env var bilan o'zgartirish mumkin: SLOW_REQUEST_MS=1000
        self.threshold_ms: int = int(getattr(settings, "SLOW_REQUEST_MS", 800))
        # PERF_LOG_ALL=False qilsangiz faqat sekin/high-query so'rovlar loglanadi
        self.log_all: bool = bool(getattr(settings, "PERF_LOG_ALL", True))

    def __call__(self, request):
        path = request.path

        # Static fayllar uchun logging kerak emas
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return self.get_response(request)

        # Har bir thread o'z query counter'iga ega (thread-safe)
        query_count = 0

        def _count_query(execute, sql, params, many, context):
            nonlocal query_count
            query_count += 1
            return execute(sql, params, many, context)

        # Barcha DB connectionlarni wrap qilamiz (default: bitta connection)
        t0 = time.perf_counter()
        with ExitStack() as stack:
            for conn in connections.all():
                stack.enter_context(conn.execute_wrapper(_count_query))
            response = self.get_response(request)
        ms = (time.perf_counter() - t0) * 1000.0

        status = getattr(response, "status_code", "?")
        method = request.method

        # ── Teglar ──
        tags: list[str] = []

        if ms >= self.threshold_ms * 5:          # > 4000ms (800*5)
            tags.append("[CRITICAL]")
        elif ms >= self.threshold_ms * 2:         # > 1600ms
            tags.append("[SLOW]")
        elif ms >= self.threshold_ms:             # > 800ms
            tags.append("[!SLOW]")

        if query_count >= 200:
            tags.append("[N+1?]")
        elif query_count >= 80:
            tags.append("[HIGH-Q]")
        elif query_count >= 40:
            tags.append("[!HIGH-Q]")

        tag_str = " ".join(tags)

        # ── Render logsida chiqaramiz ──
        should_log = self.log_all or bool(tags)
        if should_log:
            # Har bir satr grep uchun [PERF] bilan boshlanadi
            line = (
                f"[PERF] {method:<5} {path[:100]:<55}"
                f" | {ms:>6.0f}ms"
                f" | {query_count:>3}q"
                f" | {status}"
                + (f"  {tag_str}" if tag_str else "")
            )
            print(line, flush=True)

        return response
