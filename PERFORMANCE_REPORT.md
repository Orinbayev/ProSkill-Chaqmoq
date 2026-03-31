# ChaqmoqApp — Performance Audit & Optimization Report

**Sana:** 2026-03-31
**Muhit:** Django multi-tenant SaaS, Render.com, PostgreSQL, WhiteNoise
**Muhandis:** Senior Django Performance Engineer (AI-assisted audit)

---

## A. Smoke Test Checklist — Test qilingan sahifalar va oqimlar

| # | Sahifa / Oqim | Holat | Eslatma |
|---|--------------|-------|---------|
| 1 | `GET /health/` | ✅ | Render health check — "OK" qaytarishi shart |
| 2 | `GET /hisob/login/` | ✅ | CSRF token mavjud |
| 3 | `POST /hisob/login/` — noto'g'ri parol | ✅ | 200, xato xabari, throttle ishlaydi |
| 4 | `POST /hisob/login/` — to'g'ri parol | ✅ | Session yaratiladi, role-based redirect |
| 5 | `POST /logout/` | ✅ | Session tozalanadi, login sahifaga redirect |
| 6 | `GET /platform/` (superadmin) | ✅ | 302 → login (autentifikatsiyasiz) |
| 7 | `GET /admin/` | ✅ | Django admin redirect ishlaydi |
| 8 | `GET /<slug>/` | ✅ | TenantMiddleware center topadi |
| 9 | `GET /<slug>/stat/students/` | ✅ | 302 → login (autentifikatsiyasiz) |
| 10 | `GET /<slug>/stat/teachers/` | ✅ | 302 → login |
| 11 | `GET /click/prepare/` | ✅ | 400/405 (POST kutadi, 500 emas) |
| 12 | `GET /click/complete/` | ✅ | 400/405 |
| 13 | `GET /payment/success/` | ✅ | Sahifa yukladi |
| 14 | `GET /payment/cancel/` | ✅ | Sahifa yukladi |
| 15 | `GET /<slug>/api/director/stats/` | ✅ | 302 → login (autentifikatsiyasiz) |
| 16 | `GET /platform/api/centers/list/` | ✅ | 302/403 (autentifikatsiyasiz) |
| 17 | DB ulanish (`SELECT 1`) | ✅ | PostgreSQL javob beradi |
| 18 | Migratsiya holati | ✅ | Kutilayotgan migratsiya yo'q (0036 qo'shilgandan so'ng) |
| 19 | Billing modellari import | ✅ | Plan, Subscription, PromoCode |
| 20 | Education modellari import | ✅ | Group, Lesson, Attendance |
| 21 | `core.middleware` import | ✅ | TenantMiddleware, cache |
| 22 | `accounts.backends` import | ✅ | EmailOrPhoneBackend |
| 23 | `billing.services` import | ✅ | get_active_subscription va boshqalar |
| 24 | `core.services.db_backup_service` | ✅ | BackgroundScheduler, requests-based |

**Smoke testni ishlatish:**
```bash
# Anonim (minimal)
python manage.py smoke_test

# To'liq (real login bilan)
python manage.py smoke_test --center-slug myschool \
    --username admin@example.com --password secret123

# Faqat billing bo'limi
python manage.py smoke_test --section billing

# Tez (og'ir checklar o'tkazib yuboriladi)
python manage.py smoke_test --quick
```

---

## B. Root Cause List — Sekinlik sabablari (prioritet bo'yicha)

### 🔴 Kritik (Login 3–8 soniya kechikishi)

**1. Telegram HTTP bloklanishi — login jarayonida**
- **Fayl:** `accounts/auth_views.py` — eski `form_valid()`
- **Sabab:** `record_activity()` Telegram API ga sinxron `requests.post()` chaqirardi. Telegram server 5s timeout bo'lsa, foydalanuvchi 5 soniya kutardi.
- **Ta'sir:** Har bir muvaffaqiyatli login + har bir noto'g'ri urinish bloklanardi.

**2. Har so'rovda Center DB query**
- **Fayl:** `core/middleware.py` — `TenantMiddleware.process_request()`
- **Sabab:** `Center.objects.get(pk=user.center.pk)` — har bir HTTP so'rovida 1 ta qo'shimcha DB query.
- **Ta'sir:** 100 ta parallel so'rov = 100 ta keraksiz DB query.

**3. N+1 query — `_build_stats()` da**
- **Fayl:** `core/views.py`
- **Sabab:** 3 ta alohida `users.filter(role=...).count()` chaqiruvi — 3 ta DB query.

### 🟡 O'rtacha (Sahifalar 500–2000ms kechikishi)

**4. Subscription 3x tekshirilishi — har requestda**
- **Fayl:** `core/context_processors.py` — eski kod
- **Sabab:** `get_subscription_ui_state()` va `get_feature_flags()` har biri ichida `get_active_subscription()` chaqirardi. Natija: 1 ta requestda 3x DB query.

**5. Notifikatsiya: 2 query (count + list)**
- **Fayl:** `core/context_processors.py`
- **Sabab:** `Notification.objects.filter(...).count()` va `.order_by(...)[:5]` — ikki alohida query.

**6. Auth backend: center preload yo'q**
- **Fayl:** `accounts/backends.py`
- **Sabab:** Login so'rovidan so'ng middleware `user.center` ga murojaat qilib yangi DB query qilardi (N+1).

**7. User subscription — center bo'lgan foydalanuvchilar uchun ham tekshirilgan**
- **Fayl:** `core/context_processors.py`
- **Sabab:** `get_user_subscription_dashboard_data()` center bo'lgan director/teacher uchun ham chaqirilardi (keraksiz).

### 🟢 Kichik (Indekslar yo'qligi)

**8. `phone_number` indeksi yo'q**
- Telefon bilan login qilganda full table scan bo'lardi.

**9. `(center, role)` composite indeks yo'q**
- `stat_students`, `stat_teachers` sahifalarida full table scan.

**10. `(slug, is_deleted)` composite indeks yo'q**
- Slug bo'yicha center qidiruvida indeks yo'q edi.

---

## C. O'zgartirilgan fayllar

| Fayl | O'zgarish turi | Sabab |
|------|---------------|-------|
| `accounts/auth_views.py` | Major refactor | Telegram + DB ni fon threadiga ko'chirish |
| `accounts/backends.py` | Optimization | `select_related("center")` + `.only()` |
| `accounts/migrations/0036_perf_indexes.py` | Yangi fayl | 8 ta DB indeks qo'shildi |
| `core/middleware.py` | Major optimization | In-process center cache (30s TTL) |
| `core/context_processors.py` | v3 rewrite | Sub 3x→1x, notif 2q→1q, user_sub only orphan |
| `core/signals.py` | Minor addition | Center cache busting signali |
| `core/views.py` | Query optimization | 3 COUNT → 1 aggregate |
| `core/services/db_backup_service.py` | Full rewrite | async→sync, aiogram→requests, BackgroundScheduler |
| `core/apps.py` | Minor addition | Backup scheduler startup in `ready()` |
| `core/management/commands/backup_and_send.py` | Enhanced | `--center`, `--dry-run`, `sys.exit(1)` |
| `core/management/commands/test_backup_send.py` | Yangi fayl | Diagnostics va manual test |
| `core/management/commands/smoke_test.py` | Yangi fayl | 24+ test, 9 bo'lim |
| `config/settings_prod.py` | Minor | Redis timeout, slow query log |
| `render.yaml` | Modified | Cron Job backup service qo'shildi |
| `telegram_bot/backup/backup_service.py` | Rewrite | `run_backup_async()` wrapper ishlatish |

---

## D. Kod patchlari (asosiy o'zgarishlar)

### Patch 1: Login — Telegram bloklanishi bartaraf

**Oldin** (`accounts/auth_views.py`):
```python
def form_valid(self, form):
    response = super().form_valid(form)
    # ❌ BLOCKING: 5 soniya kutishi mumkin
    record_activity(self.request.user, "Login successful", self.request)
    return response
```

**Keyin:**
```python
def form_valid(self, form):
    response = super().form_valid(form)
    meta_copy = {k: v for k, v in self.request.META.items()
                 if k in ('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR', 'HTTP_USER_AGENT')}
    # ✅ NON-BLOCKING: daemon thread
    threading.Thread(
        target=_record_activity_bg,
        args=(self.request.user, "Login successful (Website)", meta_copy),
        daemon=True,
    ).start()
    return response
```

---

### Patch 2: TenantMiddleware — In-process cache

**Oldin** (`core/middleware.py`):
```python
# ❌ Har so'rovda: 1 qo'shimcha DB query
center_obj = Center.objects.get(pk=request.user.center.pk)
request.center = center_obj
```

**Keyin:**
```python
# ✅ 30s TTL in-process cache — DB ga bormaydigan so'rovlar
center_obj = _get_center_cached(center_pk)
request.center = center_obj

# Cache: {center_id: (Center obj, fetch_time)}
_CENTER_CACHE: dict[int, tuple] = {}
_CENTER_CACHE_TTL = 30  # soniya

def _get_center_cached(center_id: int):
    now = time.monotonic()
    cached = _CENTER_CACHE.get(center_id)
    if cached and now - cached[1] < _CENTER_CACHE_TTL:
        return cached[0]
    center_obj = Center.objects.get(pk=center_id)
    _CENTER_CACHE[center_id] = (center_obj, now)
    return center_obj
```

---

### Patch 3: _build_stats — 3 query → 1 aggregate

**Oldin** (`core/views.py`):
```python
# ❌ 3 alohida COUNT query
manager_count  = users.filter(role="manager").count()
teacher_count  = users.filter(role="teacher").count()
student_count  = users.filter(role="student", is_archived=False).count()
```

**Keyin:**
```python
# ✅ 1 aggregate query
user_agg = U.objects.filter(center=center).aggregate(
    managers=Count("id", filter=Q(role="manager")),
    teachers=Count("id", filter=Q(role="teacher")),
    students=Count("id", filter=Q(role="student", is_archived=False)),
)
```

---

### Patch 4: Context processor — subscription 3x→1x

**Oldin** (eski context_processors.py):
```python
# ❌ get_subscription_ui_state ichida get_active_subscription() chaqiradi
# ❌ get_feature_flags ichida ham get_active_subscription() chaqiradi
# ❌ middleware da check_subscription_expiry ham chaqiradi
# Jami: 1 requestda 3+ subscription DB query
sub_ui = get_subscription_ui_state(center)
features = get_feature_flags(center)
```

**Keyin:**
```python
# ✅ Bitta cache key, 60s TTL
sub_cache_key = f"tenant_ctx:sub:v3:{center.id}"
cached = cache.get(sub_cache_key)
if cached:
    sub_ui = cached.get("sub_ui")
    features = set(cached.get("features", []))
else:
    sub_ui = get_subscription_ui_state(center)
    features = get_feature_flags(center)
    cache.set(sub_cache_key, {"sub_ui": sub_ui, "features": sorted(features)}, timeout=60)
```

---

### Patch 5: DB Indexes migration

```python
# accounts/migrations/0036_perf_indexes.py
operations = [
    # Phone number login uchun
    migrations.AddIndex(models.Index(fields=["phone_number"], name="user_phone_perf_idx")),
    # Role filter uchun
    migrations.AddIndex(models.Index(fields=["role"], name="user_role_perf_idx")),
    # Archive filter uchun
    migrations.AddIndex(models.Index(fields=["is_archived"], name="user_is_archived_perf_idx")),
    # stat_managers, stat_teachers uchun
    migrations.AddIndex(models.Index(fields=["center", "role"], name="user_center_role_perf_idx")),
    # stat_students (active only) uchun
    migrations.AddIndex(models.Index(fields=["center", "role", "is_archived"], name="user_center_role_arch_idx")),
    # TenantMiddleware slug lookup uchun
    migrations.AddIndex(models.Index(fields=["slug", "is_deleted"], name="center_slug_deleted_perf_idx")),
    migrations.AddIndex(models.Index(fields=["status"], name="center_status_perf_idx")),
    migrations.AddIndex(models.Index(fields=["is_deleted"], name="center_is_deleted_perf_idx")),
]
```

**Migratsiya qo'llash:**
```bash
python manage.py migrate accounts 0036_perf_indexes
```

---

## E. Before / After — Tezlashish taxminlari

| Muammo | Oldin | Keyin | Yaxshilanish |
|--------|-------|-------|-------------|
| **Login vaqti** (Telegram blok) | ~3–8 soniya | ~80–150ms | **~30–50x tezroq** |
| **Har requestda center query** | +1 DB query (10–30ms) | 0 (cache hit) | **~10–30ms tejaldi** |
| **Dashboard stats** (`_build_stats`) | 3 COUNT query | 1 aggregate | **~2x DB load kamaydi** |
| **Subscription tekshiruvi** | 3x per request (30–90ms) | 1x + 60s cache | **~3x kamaydi** |
| **Notification query** | 2 query (count+list) | 1 query | **~1 query tejaldi** |
| **Auth backend** | Login + center N+1 | `select_related` | **~1 query tejaldi** |
| **phone_number lookup** | Full table scan | Index scan | **~10–100x** (katta tableda) |
| **center+role filter** | Full table scan | Composite index | **~5–20x** |
| **Slug lookup (middleware)** | Partial index | Composite index | **~2–5x** |
| **Backup scheduler** | Crash (event loop) | Stable (requests) | **✅ Ishlaydi** |

**Taxminiy umumiy login tezligi:** 5000ms → 150ms (**~33x yaxshilandi**)

**Taxminiy sahifa yuklash tezligi (dashboard):** 800ms → 300ms (**~2.5x yaxshilandi**)

> **Eslatma:** Bu raqamlar DB hajmi, server resurslari va tarmoq holatiga qarab farq qilishi mumkin. Real o'lchov uchun `DEBUG=True` + `django-debug-toolbar` yoki production da `SLOW_QUERY_MS=100` environment variable qo'ying.

---

## F. Manual Verification — Qo'lda tekshirish yo'riqnomasi

### F.1. Login tezligini tekshirish

1. Brauzerda DevTools → Network panelini oching
2. `https://chaqmoqapp.uz/hisob/login/` ga kiring
3. To'g'ri email/parol bilan login qiling
4. Network panelda `login/` POST so'rovining vaqtini ko'ring
5. ✅ Maqsad: **200ms dan kam** (oldin 3–8 soniya edi)

### F.2. DB querylarni tekshirish (Django Debug Toolbar)

```bash
# Local da:
pip install django-debug-toolbar
# settings.py ga qo'shing:
INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
INTERNAL_IPS = ["127.0.0.1"]
```

Dashboard sahifasini ochasiz va:
- ✅ Sahifada 10 dan kam SQL query bo'lishi kerak
- ✅ `select_related` ishlayotganini `EXPLAIN` da ko'ring
- ✅ Duplicate querylar bo'lmasligi kerak

### F.3. Backup botni tekshirish

```bash
# 1. Token va group tekshirish
python manage.py test_backup_send --check-only

# 2. Bitta markaz uchun to'liq test
python manage.py test_backup_send --center <slug>

# 3. Barcha markazlar uchun backup (production test)
python manage.py backup_and_send

# 4. Faqat bitta markaz, dry-run
python manage.py backup_and_send --center <slug> --dry-run
```

### F.4. Indekslarni tekshirish

```bash
python manage.py dbshell
```

PostgreSQL da:
```sql
-- Indekslar mavjudligini tekshirish
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE tablename IN ('accounts_user', 'accounts_center')
AND indexname LIKE '%perf%';

-- Jadval skanlanish turi (seq scan yoki index scan?)
EXPLAIN SELECT * FROM accounts_user WHERE phone_number = '+998901234567';
-- ✅ "Index Scan" ko'rinishi kerak, "Seq Scan" emas
```

### F.5. Smoke test ishlatish

```bash
# To'liq test (anonim)
python manage.py smoke_test

# To'liq test (autentifikatsiya bilan)
python manage.py smoke_test \
    --center-slug <slug> \
    --username admin@chaqmoqapp.uz \
    --password <password>
```

✅ Barcha testlar yashil bo'lishi kerak.

### F.6. Redis cache ishlayotganini tekshirish

```bash
# Redis ulangan bo'lsa
python manage.py shell -c "
from django.core.cache import cache
cache.set('test_key', 'hello', 10)
print(cache.get('test_key'))  # 'hello' ko'rinishi kerak
"
```

### F.7. Slow query log (production)

`settings_prod.py` da yoki Render environment variable:
```
SLOW_QUERY_MS=100
```

Render dasturlari logida `django.db.backends` dan `WARNING` levelda 100ms+ querylar chiqadi. Ularni monitoring qiling.

### F.8. Session persistence tekshirish

Render.com ga deploy qilib:
1. Login qiling
2. Render service restart qiling (manual)
3. Sahifaga qaytib kiring
4. ✅ Session saqlanishi kerak (DB session engine tufayli)

---

## Qo'shimcha tavsiyalar (ixtiyoriy)

### GZip middleware (HTML compression)
`config/settings_prod.py` → `MIDDLEWARE` listiga qo'shing (CommonMiddleware DAN OLDIN):
```python
"django.middleware.gzip.GZipMiddleware",
```

### Frontend CDN bloklanishi
`base.html` da 5 ta external CDN (Bootstrap, FontAwesome, Google Fonts, ApexCharts) sahifa yuklanishini sekinlashtirishi mumkin. Self-hosting yoki `preload` strategiyasi ko'rib chiqilsin.

### Render Cron Job (eng ishonchli backup)
`render.yaml` dagi cron job `0 11 * * *` (UTC) = 16:00 UZT — bu in-process scheduler dan ko'ra ishonchli. Ikkalasini birga qoldirish OK, lekin cron job birlamchi hisoblansin.

---

*Hisobot yakunlandi. Barcha o'zgarishlar `git diff` orqali tekshirilishi mumkin.*
