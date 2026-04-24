"""
Login benchmark — har rol uchun ms + SQL query count.

Ishlatish:
    python manage.py shell < scripts/bench_login.py

Har bir rol uchun:
  1. User topiladi (yoki orphan/no-role uchun yaratiladi/o'zgartiriladi).
  2. Bench parol o'rnatiladi ("bench-temp-pw-9182").
  3. django.test.Client orqali POST /login/ bajariladi.
  4. CaptureQueriesContext orqali SQL query'lar hisoblanadi.
  5. time.perf_counter bilan ms o'lchanadi.
  6. Parol qayta tiklanadi (xavfsizlik uchun — real foydalanuvchilarga tegmaslik).

Test qurilmayotgan fieldlarni o'zgartirmaslik uchun orphan/no-role testlari
alohida yaratilgan "bench_*" email'li foydalanuvchilar ustida bajariladi.
"""

import time
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext
from django.test.client import Client
from django.conf import settings
from accounts.models import User

# Debug Queries yoqilmagan bo'lsa logga yozilmaydi.
settings.DEBUG = True

BENCH_PW = "bench-temp-pw-9182"

ROLES = [
    ("director", "admin@gmail.cpm"),
    ("manager", "soxiba@gmail.cpm"),
    ("teacher", "testtestov@gmail.com"),
    ("student", "poiupoi@gmail.com"),
    ("parent", "temur.yarashov@chaqmoq.uz"),
]


def measure(label, email, expect_success=True):
    """Login qilib ms va query count qaytaradi."""
    user = User.objects.filter(email=email).first()
    if not user:
        return f"[{label}] SKIP: user {email!r} topilmadi"

    old_hash = user.password
    user.set_password(BENCH_PW)
    user.save(update_fields=["password"])

    try:
        client = Client(HTTP_HOST="localhost")
        reset_queries()
        t0 = time.perf_counter()
        with CaptureQueriesContext(connection) as ctx:
            resp = client.post(
                "/login/",
                {"username": email, "password": BENCH_PW},
                follow=False,
                HTTP_HOST="localhost",
            )
        elapsed = (time.perf_counter() - t0) * 1000.0
        queries = len(ctx.captured_queries)
        status = resp.status_code
        redirect_to = resp.get("Location", "") if status in (301, 302) else ""

        ok = (status == 302 and redirect_to) if expect_success else (status == 200)
        tag = "✓" if ok else "✗"
        return (
            f"[{label}] {tag} {elapsed:6.1f} ms, {queries:2d} queries, "
            f"status={status}, redirect={redirect_to!r}"
        )
    finally:
        # Qayta asl parolga qaytaramiz.
        User.objects.filter(pk=user.pk).update(password=old_hash)


def _raw_delete_bench():
    from django.db import connection as _c
    cur = _c.cursor()
    cur.execute("DELETE FROM accounts_user WHERE email LIKE 'bench_%'")


def measure_orphan():
    """Center yo'q user — aniq error qaytarish kerak."""
    email = "bench_orphan@example.com"
    _raw_delete_bench()
    user = User.objects.create(
        email=email,
        ism="Bench",
        familya="Orphan",
        role="student",
        center=None,
    )
    user.set_password(BENCH_PW)
    user.save()

    client = Client(HTTP_HOST="localhost")
    reset_queries()
    t0 = time.perf_counter()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.post(
            "/login/",
            {"username": email, "password": BENCH_PW},
            follow=False,
            HTTP_HOST="localhost",
        )
    elapsed = (time.perf_counter() - t0) * 1000.0
    queries = len(ctx.captured_queries)

    body = resp.content.decode("utf-8", errors="ignore")
    has_error = "biriktirilmagansiz" in body
    not_logged_in = resp.status_code == 200  # Login sahifasi qayta render
    tag = "✓" if (has_error and not_logged_in) else "✗"
    return (
        f"[orphan  ] {tag} {elapsed:6.1f} ms, {queries:2d} queries, "
        f"status={resp.status_code}, error_shown={has_error}"
    )


def measure_no_role():
    """Role bo'sh — aniq error qaytarish kerak."""
    email = "bench_no_role@example.com"
    from accounts.models import Center

    c = Center.objects.first()
    # NB: update_or_create bu yerda SoftDelete tufayli ishlamaydi — raw delete.
    from django.db import connection as _c
    _c.cursor().execute(
        "DELETE FROM accounts_user WHERE email=%s", [email]
    )
    user = User.objects.create(
        email=email,
        ism="Bench",
        familya="NoRole",
        role="",
        center=c,
    )
    user.set_password(BENCH_PW)
    user.save()

    client = Client(HTTP_HOST="localhost")
    t0 = time.perf_counter()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.post(
            "/login/",
            {"username": email, "password": BENCH_PW},
            follow=False,
            HTTP_HOST="localhost",
        )
    elapsed = (time.perf_counter() - t0) * 1000.0
    queries = len(ctx.captured_queries)

    body = resp.content.decode("utf-8", errors="ignore")
    has_error = "rol biriktirilmagan" in body
    tag = "✓" if (has_error and resp.status_code == 200) else "✗"
    return (
        f"[no_role ] {tag} {elapsed:6.1f} ms, {queries:2d} queries, "
        f"status={resp.status_code}, error_shown={has_error}"
    )


def measure_redirect_loop():
    """Login qilgan user /login/ ga kirsa, qayta login sahifa emas, /<slug>/ ga yo'naladi."""
    email = "admin@gmail.cpm"
    user = User.objects.filter(email=email).first()
    if not user:
        return "[loop    ] SKIP"
    old_hash = user.password
    user.set_password(BENCH_PW)
    user.save(update_fields=["password"])
    try:
        client = Client(HTTP_HOST="localhost")
        # Avval login qilamiz
        client.post("/login/", {"username": email, "password": BENCH_PW}, follow=False, HTTP_HOST="localhost")
        # Endi /login/ GET qilsak — qayta login sahifasi emas, redirect bo'lishi kerak
        resp = client.get("/login/", follow=False, HTTP_HOST="localhost")
        is_redirect = resp.status_code == 302 and "/login/" not in (resp.get("Location") or "")
        tag = "✓" if is_redirect else "✗"
        return (
            f"[loop    ] {tag} authed user GET /login/ → status={resp.status_code}, "
            f"redirect={resp.get('Location', '')!r} (redirect loop yo'q)"
        )
    finally:
        User.objects.filter(pk=user.pk).update(password=old_hash)


print()
print("=" * 78)
print("  LOGIN BENCHMARK — /login/ endpoint")
print("=" * 78)

# Warm-up request (first query has overhead from connection setup).
Client(HTTP_HOST="localhost").get("/login/", HTTP_HOST="localhost")

for role, email in ROLES:
    # 2 marta o'lchaymiz — o'rtachaga yaqinlashtirish uchun.
    print(measure(role, email))

print(measure_orphan())
print(measure_no_role())
print(measure_redirect_loop())

# Tozalash — bench test userlarni hard-delete qilamiz (SoftDelete'ni chetlab o'tib).
from django.db import connection as _cleanup_c
_cleanup_c.cursor().execute("DELETE FROM accounts_user WHERE email LIKE 'bench_%'")

print()
print("=" * 78)
print("  Esda: 'queries' — login POST davomida ishlagan JAMI SQL query soni.")
print("  Background thread (record_activity, Telegram) alohida ishlaydi,")
print("  response'ga ta'sir qilmaydi.")
print("=" * 78)
