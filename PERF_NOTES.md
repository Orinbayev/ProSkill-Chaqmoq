# Performance — Render + Postgres tuning

> Bu hujjat: ChaqmoqApp Render Starter ($7/mo) tier'da xizmat qilayotgan
> sayt uchun performance tavsiyalari va monitoring qadamlarini batafsil
> qiladi.

## 1. Joriy konfiguratsiya (kod bilan amalga oshirildi)

### Database (Postgres)
- `CONN_MAX_AGE = 600` (connection pool 10 daq)
- `connect_timeout = 10s`
- `statement_timeout = 30s` — har bitta query maksimal 30s
- `lock_timeout = 5s` — row-lock kutish 5s

Override qilish uchun env vars:
```bash
DJANGO_DB_STATEMENT_TIMEOUT_MS=30000
DJANGO_DB_LOCK_TIMEOUT_MS=5000
DJANGO_DB_CONNECT_TIMEOUT=10
```

### Cache
- `core/perf_cache.py` — markazlashtirilgan helper
- `versioned_cache_key()` — markaz darajasida invalidate
- `Attendance.save()` har safar `salary_sum` va `salary_list` cache'larini
  bekor qiladi (avtomatik)
- TTL'lar: `TTL_SHORT=60s`, `TTL_MEDIUM=300s`, `TTL_LONG=900s`

### Slow request middleware
- `core/middleware_perf.py` — har request'da vaqt va query soni hisoblaydi
- `>500ms`'dan oshganlar log'ga `WARNING` darajada chiqadi
- Log format:
  ```
  SLOW 1247ms q=156 GET /talim/teacher-salary/?year=2026&month=5 status=200 user=42
  ```

Override:
```bash
SLOW_REQUEST_MS=200          # qattiqroq
SLOW_REQUEST_LOG_QUERIES=0   # query sanashni o'chirish (RAM tejash)
```

### Database indexes (Phase A)
Quyidagi composite indexlar yaratildi:
- `att_group_date_idx` — `(group, date)` — group_month_attendance
- `att_center_date_idx` — `(center, date)` — center range queries
- `att_status_idx` — `(status)` — present filter
- `group_center_arch_idx` — `(center, is_archived)` — group lists
- `group_oqit_arch_idx` — `(oqituvchi, is_archived)` — teacher's groups
- `group_sup_arch_idx` — `(support_teacher, is_archived)` — support groups
- `user_center_role_idx` — `(center, role, is_archived)` — staff lists
- `user_phone_num_idx` — `(phone_number)` — login lookups
- `cent_sub_status_idx` — `(center, status)` — billing middleware

---

## 2. Render dashboard — kuzatuvchi qadamlar

### CPU + RAM kuzatish
1. https://dashboard.render.com → service → **Metrics**
2. **Looking for:**
   - RAM > 80% sustained → upgrade plan kerak
   - CPU > 80% spike → query optimizatsiya kerak
   - DB connection count > 15 → connection pool muammosi

### Logs filtering
```bash
# Render CLI orqali
render logs --service chaqmoqapp --tail | grep "SLOW"
```

Yoki dashboard'da: **Logs** → search "SLOW".

---

## 3. Postgres slow query setup (qo'lda qilish kerak)

### Variant A: pg_stat_statements
Render Postgres'da extension yoqish:
```sql
-- Database shell ochib (Render dashboard → Connect → PSQL):
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Eng sekin 20 ta queryni ko'rish:
SELECT
  substring(query, 1, 100) AS query_short,
  calls,
  ROUND(total_exec_time::numeric / 1000, 2) AS total_sec,
  ROUND(mean_exec_time::numeric, 2) AS avg_ms,
  ROUND((100.0 * total_exec_time / SUM(total_exec_time) OVER ())::numeric, 1) AS pct
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

### Variant B: log_min_duration_statement
Postgres `postgresql.conf`'da (Render shaxsiy plan'da emas, lekin Standard+):
```
log_min_duration_statement = 200ms
```

### EXPLAIN ANALYZE — eng sekin queryni tahlil
Misol:
```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT ... FROM education_attendance
WHERE group_id = 42 AND date BETWEEN '2026-04-01' AND '2026-04-30';
```
Index ishlatilayaptmi? `Seq Scan` o'rniga `Index Scan att_group_date_idx`
ko'rinishi kerak.

---

## 4. Redis upgrade (kelajakda — agar trafik oshsa)

Hozirgi: **LocMemCache** (single-process, RAM ichida).
Cheklov: Render Starter da bitta worker — bu yetarli.

Agar `WEB_CONCURRENCY > 1` (gunicorn workers):
1. Render dashboard → Add Service → **Redis** ($25/mo)
2. Env var: `REDIS_URL=redis://...`
3. `requirements.txt`'ga qo'shish:
   ```
   django-redis>=5.4.0
   ```
4. `settings_prod.py`:
   ```python
   if os.getenv("REDIS_URL"):
       CACHES = {
           "default": {
               "BACKEND": "django_redis.cache.RedisCache",
               "LOCATION": os.getenv("REDIS_URL"),
               "OPTIONS": {
                   "CLIENT_CLASS": "django_redis.client.DefaultClient",
               },
           }
       }
   ```

---

## 5. Cheklov va RAM tejash

### Render Starter (512MB RAM)
- Bitta gunicorn worker (kelganda) ~150-200MB egallaydi
- LocMemCache ~50-100MB
- DB connection pool ~30MB (10 active connections × 3MB each)
- **Dynamic loading:** templates, models — ~80MB

**Jami:** ~310-410MB statik. **Joy:** 100-200MB request handling uchun.

### Risk: bitta og'ir request 200MB qo'shib OOM (Out of Memory)
- Bu hisobotlar 5000+ row aggregation qilsa
- Excel export 10K rows uchun ~150MB peak

### Yechim:
1. **`teacher_salary_summary` cache** ✅ qo'shildi
2. **Bulk salary calc** (Phase G) — har teacher uchun loop o'rniga vectorized
3. **Pagination** Excel export'da ham — 1K row chunks

---

## 6. Test qilish

### Smoke test — har endpoint'ga
```bash
# Local'da Daphne yoki runserver
python3 manage.py runserver

# Sekin endpoint'larni hit qilamiz va log'larda SLOW chiqishini ko'ramiz:
curl -s -o /dev/null http://localhost:8000/talim/teacher-salary/
curl -s -o /dev/null http://localhost:8000/talim/teacher-salary/summary/

# Log'da:
# SLOW 1245ms q=156 GET /talim/teacher-salary/ status=200 user=1
```

### Cache check
```python
python3 manage.py shell
>>> from django.core.cache import cache
>>> cache.get('salary_sum:c=1:2026:5:v1')
# Birinchi marta None
# Endpoint hit qilingach — list of teacher_data
```

### Migration tekshirish
```bash
python3 manage.py showmigrations education accounts billing | grep -E "_idx"
# Quyidagi yangi migration'lar ishlamasdan ko'rinishi kerak:
# [X] 0055_attendance_att_group_date_idx_and_more
# [X] 0046_user_user_center_role_idx_user_user_phone_num_idx
# [X] 0021_centersubscription_cent_sub_status_idx
```

---

## 7. Production deploy checklist

```bash
# 1. Local commit
git add -A
git commit -m "perf: indexes, caching, slow request log"
git push

# 2. Render avtomatik deploy boshlaydi
# 3. Procfile'da `release: migrate --noinput` — index'lar qo'llanadi
# 4. Logs'ni kuzating:
#    https://dashboard.render.com/web/srv-XXX/logs

# 5. Post-deploy smoke test
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" \
  https://chaqmoqapp.uz/talim/teacher-salary/
# 200 0.123s — birinchi marta cache miss, ~1-2s
# Keyingi:
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" \
  https://chaqmoqapp.uz/talim/teacher-salary/
# 200 0.045s — cache hit (15 daq davomida)
```

---

## 8. Bekor qilish (rollback) — agar nimadir buzilsa

### Cache muammosi (cache poisoning yoki noto'g'ri data)
```bash
# Render shell ochib:
python3 manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

### Index xatolik
```bash
# Migration rollback:
python3 manage.py migrate education 0054_group_support_foiz_group_support_teacher
python3 manage.py migrate accounts 0045_<previous>
python3 manage.py migrate billing 0020_<previous>
```

### Middleware xatolik
`config/settings.py` MIDDLEWARE list'idan birinchi qatorni o'chirish:
```python
# "core.middleware_perf.SlowRequestLoggingMiddleware",  # commented
```

---

## 9. Keyingi qadamlar (Phase G — bulk salary)

`HistoricalFinanceService._build_dynamic_teacher_salary` har teacher uchun
alohida chaqiriladi. Buni vectorize qilish:

```python
# YANGI: education/services/historical_finance_service.py
@staticmethod
def batch_calculate_teacher_salaries(teacher_ids, year, month, center=None):
    """Bir martalik aggregate query — barcha teacher'lar uchun."""
    # Bitta query: barcha teacher uchun group + attendance + enrollment
    # join. In-Python aggregation.
    ...
```

Bu Phase G'da qo'shiladi — ammo hozirgi cache yetarli (15 daq cache hit
=> 0 query keyingi marta). Bulk faqat birinchi cache miss tezligini
oshiradi.
