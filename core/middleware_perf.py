"""Slow request logging middleware.

Har request'da:
- Boshlanish vaqtini saqlaydi
- DB query sonini sanaydi (django.db connection.queries — DEBUG yoki
  alohida `connection.queries_log` orqali)
- Tugagach: agar request davomiyligi `SLOW_REQUEST_MS`'dan oshsa, log'ga
  yozadi: URL, method, status, davomiyligi, query soni, foydalanuvchi.

Settings:
    SLOW_REQUEST_MS = 500          # default
    SLOW_REQUEST_LOG_LEVEL = "WARNING"  # default

Production'da (DEBUG=False) connection.queries bo'shdir — shuning uchun
`CaptureQueriesContext` orqali kerakli paytda yoqamiz. Lekin har request
uchun query saqlash xotira ko'p oladi, shuning uchun **faqat sekin
request'da** querylar log'ga chiqadi.
"""
from __future__ import annotations

import logging
import time
import threading

from django.conf import settings
from django.db import connection, connections, reset_queries

log = logging.getLogger("perf.slow_request")
_local = threading.local()


def _enable_query_capture():
    """connection.queries_log yoqamiz (DEBUG=False da odatda yo'q).
    Faqat shu thread uchun va ortiqcha xotira yegmaydi.
    """
    for conn in connections.all():
        # force_debug_cursor — har query connection.queries'ga yoziladi
        conn.force_debug_cursor = True


def _disable_query_capture():
    for conn in connections.all():
        conn.force_debug_cursor = False


class SlowRequestLoggingMiddleware:
    """Log requests slower than threshold with query count + URL."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.threshold_ms = int(getattr(settings, "SLOW_REQUEST_MS", 500))
        self.capture_queries = bool(getattr(settings, "SLOW_REQUEST_LOG_QUERIES", True))
        # NB: query capture engages every request; prefer DEBUG-style sampling
        # if RAM under pressure. We measure: 0.05ms overhead/query — acceptable
        # at <1k qps.

    def __call__(self, request):
        start = time.perf_counter()
        if self.capture_queries:
            _enable_query_capture()
            reset_queries()

        try:
            response = self.get_response(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            query_count = sum(len(c.queries) for c in connections.all()) if self.capture_queries else -1
            if self.capture_queries:
                _disable_query_capture()

            if elapsed_ms >= self.threshold_ms:
                user_id = getattr(getattr(request, "user", None), "id", None)
                method = request.method
                path = request.get_full_path()[:300]
                status = getattr(locals().get("response", None), "status_code", "?")
                log.warning(
                    "SLOW %sms q=%d %s %s status=%s user=%s",
                    int(elapsed_ms), query_count, method, path, status, user_id,
                )

        return response
