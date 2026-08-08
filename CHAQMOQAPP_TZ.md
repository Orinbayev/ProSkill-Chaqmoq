# ChaqmoqApp — TO'LIQ TEXNIK TOPSHIRIQ (TZ) / PLATFORMA BILIM BAZASI

**Versiya:** 1.0
**Sana:** 2026-08-08
**Hujjat maqsadi:** ChaqmoqApp platformasini (as-built, ya'ni **hozir real ishlab turgan holati**) AI agentga (Gemini) yoki yangi kelgan senior developerga **to'liq** tushuntirish.
**Til:** O'zbek (lotin). Kod, model nomlari va URL'lar asl holida (ular kodda shunday).

---

## 0. HUJJATDAN QANDAY FOYDALANISH KERAK

### 0.1 Bu hujjat nima

Bu hujjat **ikki xil** vazifani bajaradi:

1. **Bilim bazasi (knowledge base)** — platforma qanday ishlaydi, qaysi model nimani anglatadi, qaysi qoida qaysi faylda yozilgan.
2. **Texnik topshiriq (TZ)** — platformani qayta qurish yoki kengaytirish uchun talablar to'plami.

### 0.2 AI agent (Gemini) uchun ish qoidalari

Agar sen AI agent bo'lsang va bu hujjat senga berilgan bo'lsa:

| Qoida | Izoh |
|---|---|
| **Til** | Foydalanuvchi bilan **o'zbek tilida** gaplash. Kod izohlari ham o'zbekcha. |
| **Ma'lumot yo'qolishi taqiqlanadi** | Bu **real pul aylanadigan** production tizim. Migratsiya, `delete()`, `flush`, `reset` kabi amallarni **hech qachon** o'zboshimchalik bilan bajarma. |
| **Soft delete** | Ma'lumot o'chirilmaydi — `is_deleted=True` qilinadi. `Model.objects` — tirik yozuvlar, `Model.all_objects` — hammasi. |
| **Tenant izolyatsiyasi** | Har bir query'da `center` filtri bo'lishi **shart**. Filtrsiz query = xavfsizlik teshigi (IDOR). |
| **N+1** | Markaz bo'ylab per-o'quvchi loop yozish taqiqlanadi (pastda 22-bo'lim). |
| **Test** | O'zgarish kiritgandan keyin tegishli test faylini ishga tushir. Testlar tartibga bog'liq (24-bo'lim). |
| **Legacy** | `education/views/legacy.py` — 12 700 qatorli fayl. Uni **butunlay refaktor qilishga urinma**, faqat kerakli funksiyani tahrirlash. |
| **Tasdiqlash** | Deploy, git push, DB migratsiya, tashqi API'ga xabar yuborish — faqat foydalanuvchi so'ragan bo'lsa. |

### 0.3 Terminologiya (kodda o'zbekcha nomlar bor)

Kodda **o'zbek va ingliz** aralash nomlar ishlatilgan. Bu ataylab: domen atamalari o'zbekcha, texnik atamalar inglizcha.

| Kodda | Ma'nosi |
|---|---|
| `Center` | O'quv markaz (tenant) |
| `Group` / `guruh` | O'quv guruhi |
| `Enrollment` | O'quvchining guruhga yozilishi (asosiy moliyaviy birlik) |
| `Oquvchi`, `oqituvchi` | O'quvchi, o'qituvchi |
| `kurs_narxi`, `kurs_narhi` | Oylik kurs narxi (ikkita imlo bor — tarixiy) |
| `oy_dars_soni` | Bir oydagi darslar soni |
| `oqituvchi_foiz` | O'qituvchi ulushi (%) |
| `tolov` | To'lov |
| `qarzdorlar` | Qarzdor o'quvchilar |
| `davomat` | Davomat (attendance) |
| `chaqmoq` | Ball / valyuta (gamifikatsiya) |
| `Ledger` | Chaqmoq harakatlari daftari |
| `TuitionMonth` | Bir enrollment uchun bir oylik hisob-faktura |
| `PaymentAllocation` | To'lovning qaysi oyga taqsimlanganini yozadi |
| `jon` | O'yindagi "hayot" (life) |
| `duel` | O'yindagi ikki o'yinchi bahsi |
| `motor` | O'yin mexanikasi (game engine) |
| `sorov` | So'rov (request) |
| `filial` | Branch (markazning bo'limi) |
| `tarif` | Tarif reja (plan) |

---

## 1. MAHSULOT TA'RIFI

### 1.1 Bir gapda

**ChaqmoqApp** — O'zbekistondagi xususiy o'quv markazlari (til kurslari, IT kurslari, repetitorlik markazlari) uchun **multi-tenant SaaS CRM/ERP** platformasi: o'quvchi, davomat, to'lov, qarzdorlik, o'qituvchi oyligi, marketing lead'lari, imtihon, sertifikat, gamifikatsiya va mobil ilovani bir tizimda birlashtiradi.

### 1.2 Biznes modeli

- **B2B SaaS**: o'quv markaz oyiga tarif to'lovi to'laydi (FREE / STANDARD / PRO / PREMIUM).
- To'lov: **Click** (O'zbekiston to'lov tizimi) yoki naqd (superadmin qo'lda tasdiqlaydi).
- Qo'shimcha daromad oqimi: **Chaqmoq Game** — o'quvchilar uchun mobil o'yin, ichida tariflar (jon tiklanish tezligi) sotiladi.
- Brend: `chaqmoqapp.uz`, yuridik shaxs: **PROSKILL LLC** (Google Play developer).

### 1.3 Hozirgi holat (2026-08)

| Ko'rsatkich | Qiymat |
|---|---|
| Backend | Django 5.0.7, ~122 000 qator Python (migratsiyalarsiz) |
| Django app'lar | 8 ta: `accounts`, `education`, `chaqmoq`, `store`, `core`, `billing`, `marketing`, `game` |
| Modellar | ~120 ta |
| Migratsiyalar | 208 ta |
| HTML shablonlar | ~474 ta (`templates/` + app'lar ichida) |
| URL endpointlar | ~600+ (web + API) |
| Test fayllari | 86 ta |
| Mobil ilova | Flutter, 186 Dart fayl, v1.1.0+8, Google Play'da |
| Telegram botlar | 3 ta (Asosiy/Family, Backup, English Teacher), aiogram 3, ~5100 qator |
| Production | Render.com, Standard plan (2GB/1CPU), Frankfurt, PostgreSQL |
| Real mijozlar | 2 tenant; birinchi pullik mijoz 2026-06-01 dan |

### 1.4 Kim foydalanadi (personalar)

| Persona | Ehtiyoji | Asosiy ekranlar |
|---|---|---|
| **Superadmin** (platforma egasi) | Markazlar, tariflar, to'lovlar, marketing CMS | `/platform/` |
| **Direktor** | Markaz moliyasi, o'qituvchi samaradorligi, umumiy KPI | `/boshqaruv/`, `/dashboards/` |
| **Manager** (administrator) | Kunlik operatsiya: o'quvchi qo'shish, to'lov qabul qilish, lead, qarzdor qo'ng'iroqlari | `/`, `/talim/tolovlar/`, `/do'kon/leads/` |
| **O'qituvchi** | Davomat, o'z guruhlari, o'z daromadi, chaqmoq berish | `/talim/mening-guruhlarim/`, `/talim/daromadim/` |
| **O'quvchi** | Chaqmoq balansi, reyting, davomat, to'lov, do'kon, o'yin | `/` (student panel), mobil ilova |
| **Ota-ona** | Farzand davomati, to'lovi, progressi | Mobil ilova, Telegram Family bot, `/dashboard/parent/` |

---

## 2. YUQORI DARAJALI ARXITEKTURA

### 2.1 Komponentlar

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            FOYDALANUVCHILAR                              │
│  Brauzer (web)   Flutter ilova (Android/iOS)   Telegram   Click to'lov   │
└──────┬─────────────────┬───────────────────────┬──────────────┬──────────┘
       │ HTTPS/session   │ HTTPS/Bearer token    │ Bot API      │ Webhook
       ▼                 ▼                       ▼              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      RENDER.COM (Frankfurt, Standard)                     │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  gunicorn (2 worker × 4 thread, --preload, timeout 120s)           │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  Django 5.0.7  —  config.settings → config.settings_prod     │  │  │
│  │  │                                                              │  │  │
│  │  │  MIDDLEWARE zanjiri:                                         │  │  │
│  │  │   Security → SlowRequestLogging → WhiteNoise → Session →      │  │  │
│  │  │   Locale → MobileApiCors → Common → CSRF → Auth →             │  │  │
│  │  │   Messages → XFrame → TenantMiddleware → RBAC                 │  │  │
│  │  │                                                              │  │  │
│  │  │  APP'LAR: accounts education chaqmoq store core billing       │  │  │
│  │  │           marketing game                                      │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  telegram_bot/bot.py  (aiogram 3, alohida process, 12s kechikish)  │  │
│  │   • Asosiy bot + Family bot (2 ta token, 1 process)                │  │
│  │   • aiohttp internal API :8080  (X-API-SECRET bilan Django'ga)     │  │
│  │   • APScheduler: kunlik hisobot 18:00, DB backup                   │  │
│  │   • english_teacher/bot.py (alohida polling)                       │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────┬──────────────────────────────┬────────────────────────────┘
               │                              │
               ▼                              ▼
   ┌────────────────────────┐    ┌──────────────────────────────┐
   │ PostgreSQL (Render)    │    │ Tashqi servislar             │
   │  • default DB          │    │  • Google Gemini (AI)        │
   │  • conn_max_age tuned  │    │  • Click Merchant API        │
   │  • per-tenant DB —     │    │  • Cloudinary (media, opt.)  │
   │    kod tayyor, OFF     │    │  • Google Drive (backup)     │
   └────────────────────────┘    │  • Telegram Bot API          │
                                 │  • Google OAuth (o'yin)      │
                                 └──────────────────────────────┘
```

### 2.2 Request oqimi (web)

```
1. Brauzer → GET /demo-markaz/talim/qarzdorlar/
2. SecurityMiddleware, WhiteNoise (static bo'lsa shu yerda tugaydi)
3. SessionMiddleware → session'dan user
4. LocaleMiddleware → uz/ru/en
5. TenantMiddleware:
     a) session['active_center_id'] bormi? → request.center
     b) yo'q bo'lsa: URL path'dagi /<slug>/ dan Center topiladi
     c) yo'q bo'lsa: request.user.center
     d) Center BLOCKED/ARCHIVED/is_deleted → logout yoki /billing/blocked/
     e) set_current_tenant(center)  ← thread-local, db_router uchun
     f) path_info dan /<slug>/ prefiksi olib tashlanadi (URL'lar bir xil bo'ladi)
6. RoleBasedAccessMiddleware:
     resolve(path) → namespace:url_name
     ROLE_PERMISSIONS[user.role] da bormi?
       yo'q → JSON so'rov bo'lsa 403 JSON, aks holda o'z dashboardiga redirect
7. View ishlaydi. Ichida:
     @login_required, @require_feature("debtors"), tenant filtri
8. Response → clear_current_tenant()
```

### 2.3 Request oqimi (mobil)

```
1. Flutter → POST /api/mobile/auth/login/  {identifier, password, center_slug?}
2. RBAC middleware bu prefiksni SKIP qiladi (EXTERNAL_API_PREFIXES)
3. core.mobile_api.mobile_auth_login:
     • login_throttle tekshiruvi (IP + identifier)
     • authenticate_login_identifier (email yoki telefon)
     • MobileAccessToken yaratiladi: raw = token_urlsafe(40),
       DB'da faqat SHA-256 hash + key_prefix saqlanadi
     • eski tokenlar 8 tadan oshsa — eng eskisi revoke
4. Keyingi so'rovlar: Authorization: Bearer <raw_token>
     @mobile_login_required → hash bo'yicha token topiladi
     muddati/revoke tekshiriladi, request.user va request.center bog'lanadi
5. Javob: JSON. Xato formati: {"ok": false, "error": "...", "code": "..."}
```

---

## 3. TEXNOLOGIYA STEKI

### 3.1 Backend

| Paket | Versiya | Nima uchun |
|---|---|---|
| Django | 5.0.7 | Asosiy framework, server-side rendering |
| djangorestframework | latest | Ba'zi API view'lar (asosiy mobil API oddiy `JsonResponse`) |
| drf-spectacular | latest | OpenAPI/Swagger: `/api/docs/`, `/api/schema/` |
| gunicorn | latest | WSGI server |
| whitenoise | latest | Static fayllar (CompressedStaticFilesStorage) |
| psycopg2-binary | latest | PostgreSQL drayver |
| dj-database-url | latest | `DATABASE_URL` parsing |
| django-jazzmin | latest | Django admin skin (`/admin/`) |
| django-extensions | latest | `shell_plus`, `runserver_plus` |
| Pillow | latest | Rasm (avatar, mahsulot, sertifikat) |
| openpyxl | latest | Excel eksport/import |
| reportlab | latest | PDF (to'lov cheki, sertifikat) |
| aiogram | >=3.17 | Telegram botlar |
| apscheduler | latest | Bot ichidagi jadval (backup, hisobot) |
| google-genai | 1.73.1 | Gemini AI (yangi SDK) |
| anthropic | >=0.34 | Zaxira AI provayder |
| google-api-python-client, google-auth-oauthlib | latest | Google Drive backup, OAuth |
| cloudinary, django-cloudinary-storage | latest | Ixtiyoriy media storage |
| sentry-sdk[django] | latest | Xato monitoring |
| freezegun | >=1.5 | **Faqat test**: sana-bog'liq testlar uchun soat muzlatish |
| pytz | latest | `Asia/Tashkent` |

### 3.2 Frontend (web)

- **Django template engine** (SSR). SPA emas.
- **Vanilla JS** + kichik modullar: `static/js/theme.js`, `notifications.js`, `chart-tooltip.js`, `student-drawer.js`, `role-theme.js`, `login-lightning.js`.
- **Bootstrap 5** (`static/vendor/bootstrap/`) — lokal, CDN yo'q.
- **ApexCharts** (`static/vendor/apexcharts/`) — barcha diagrammalar.
- **Font Awesome** ikonkalari.
- CSS: `static/css/theme.css` (tokenlar), `dashboards.css`, `superadmin.css`, `moliya.css`, `role-theme.css`, `light-mode-fixes.css`.

### 3.3 Mobil

- **Flutter** (Dart SDK ^3.11.4), Material 3.
- State: **Provider** (`ChangeNotifier`).
- HTTP: **Dio 5**.
- Token saqlash: **flutter_secure_storage**.
- Diagramma: **fl_chart**. Skeleton: **shimmer**. Animatsiya: **flutter_animate**.
- Bildirishnoma: **flutter_local_notifications** + **timezone**.
- Google login: **google_sign_in** (faqat Chaqmoq Game uchun).
- Ikonka: **flutter_launcher_icons**.

### 3.4 Ma'lumotlar bazasi

- **Lokal dev:** SQLite (`db.sqlite3`), `OPTIONS.timeout = 60`.
- **Production:** PostgreSQL (Render), `DATABASE_URL` orqali, `sslmode=require`.
- **Multi-DB routing:** `core/db_router.TenantDatabaseRouter` — kod tayyor, lekin `TENANT_DB_ROUTING_ENABLED=0` (o'chirilgan). Yoqilganda `SHARED_APPS` (accounts, core, auth, sessions...) `default` DB'da qoladi, `TENANT_APPS` esa `tenant_<root_center_id>` connection'ga boradi.

---

## 4. REPOZITORIYA TUZILISHI

```
ChaqmoqApp/
├── config/                          # Django proyekt konfiguratsiyasi
│   ├── settings.py                  # 426 qator, lokal + umumiy
│   ├── settings_prod.py             # production override (DEBUG=False, DATABASE_URL)
│   ├── urls.py                      # root URLconf (tartib MUHIM — 2.4 ga qara)
│   ├── slug_prefix_urls.py          # /<slug>/ prefiksli URL'lar
│   ├── shared_secret.py             # API_SECRET ni SECRET_KEY dan deterministik hosil qilish
│   ├── storage.py                   # media storage tanlash
│   ├── wsgi.py / asgi.py
│
├── accounts/                        # Tenant + foydalanuvchi + auth + superadmin
│   ├── models.py (801)              # Center, User, Roles, Branch, BranchRequest, ...
│   ├── auth_views.py                # SecureLoginView (?next ni IGNORE qiladi)
│   ├── auth_urls.py                 # /hisob/login/ + bot internal API
│   ├── backends.py                  # EmailOrPhoneBackend
│   ├── login_throttle.py            # brute-force himoyasi
│   ├── magic_login.py               # bir-bosishli kirish havolasi
│   ├── password_reset_views.py      # kod bilan parol tiklash
│   ├── telegram_views.py            # Telegram ulash
│   ├── api_auth.py, api_superadmin.py
│   ├── views.py (1320)              # tenant view'lar
│   ├── views_superadmin.py, views_platform.py, views_branch_admin.py, views_game_admin.py
│   ├── student_limit.py, duplicate_checks.py, utils.py (normalize_phone)
│   ├── services/                    # branch_requests, demo_center_service, parent_telegram_link
│   └── management/commands/         # create_superadmin, seed_demo_center, seed_sales_demo, ...
│
├── education/                       # ⭐ ENG KATTA APP: o'quv jarayoni + moliya
│   ├── models.py (2097)             # 44 model: Group, Enrollment, Payment, Attendance,
│   │                                # TuitionMonth, PaymentAllocation, Exam*, Certificate*, ...
│   ├── views/
│   │   ├── legacy.py (12 718!)      # ⚠️ tarixiy monolit — asosiy web view'lar shu yerda
│   │   ├── courses.py, exam_hub.py, student_status.py, helpers.py
│   │   └── __init__.py              # legacy'dan re-export
│   ├── services/                    # ⭐ biznes logika shu yerda bo'lishi kerak
│   │   ├── tuition.py (2364)        # ⭐⭐ narxlash + qarz + to'lov taqsimlash — YURAK
│   │   ├── historical_finance_service.py (630)
│   │   ├── exam_service.py (1077), certificate_service.py (1089)
│   │   ├── hr.py (771), student_status.py (744), ranking_service.py (503)
│   │   ├── student_transfer.py (414), progress_service.py (331)
│   │   ├── support_teacher.py (283), reset_center_debt_service.py (280)
│   │   ├── removed_debt_repair.py (222), expected_income_service.py (202)
│   │   ├── attendance_monitor.py (203), attendance_service.py (199)
│   │   ├── group_schedule_service.py (175), enrollment_service.py (152)
│   │   ├── closure_service.py (131), lesson_planning.py (93), audit_service.py (42)
│   ├── hr_views.py (659)            # Xodimlar dashboard + /api/hr/*
│   ├── api.py, signals.py, permissions.py, helpers.py, forms.py
│   ├── tests/                       # 32 test moduli
│   └── management/commands/         # close_month, generate_monthly_tuition, ...
│
├── chaqmoq/                         # Gamifikatsiya (ball tizimi)
│   ├── models.py (193)              # Rule, Ledger, LightningHistory
│   ├── services.py                  # avtomatik qoidalar (davomat/to'lov bonusi va jarimasi)
│   └── views.py, urls.py
│
├── store/                           # Ichki do'kon + CRM (lead)
│   ├── models.py (834)              # Product, Sale, PurchaseRequest, Expense, Lead, LeadGroup,
│   │                                # TrialLesson, LeadStatus, Manba, Yonalish, PaymentMethod
│   ├── crm_views.py (1733)          # lead CRM (HTML + JSON API)
│   ├── lead_services.py, trial_services.py, services.py, serializers.py
│   └── views.py
│
├── core/                            # Umumiy infratuzilma + dashboard + mobil API
│   ├── models.py (665)              # Notification, MobileAccessToken, ChurnRisk, chat, metrikalar
│   ├── middleware.py (526)          # TenantMiddleware + MobileApiCorsMiddleware
│   ├── middleware_rbac.py (328)     # RoleBasedAccessMiddleware
│   ├── middleware_perf.py           # SlowRequestLoggingMiddleware
│   ├── mobile_api.py (4528)         # ⭐ butun mobil API
│   ├── api_views.py (2383)          # web AJAX API'lar
│   ├── views.py (3585)              # umumiy web view'lar (home, stat/*, trash, chat, games)
│   ├── dashboard_views.py (3314)    # direktor dashboardlari + AI chat
│   ├── api_dashboard.py             # DRF class-based dashboard API
│   ├── api_bot.py                   # Telegram bot uchun internal API
│   ├── tenant.py, tenant_context.py, db_router.py, db_config.py
│   ├── soft_delete.py               # SoftDeleteMixin + all_objects
│   ├── trash.py                     # Trash (o'chirilganlar) UI
│   ├── perf_cache.py, rate_limit.py, alerts.py, churn_service.py
│   ├── center_features.py           # markaz darajasidagi UI feature flag'lar
│   ├── dashboard_metrics.py, context_processors.py
│   ├── services/                    # ai_insights (2315), center_ai_context (1477),
│   │                                # db_backup_service (1484), gdrive_backup, role_scoped_ai,
│   │                                # app_adoption, user_import_service, center_ai_security
│   └── management/commands/         # backup_and_send, restore_center_backup, smoke_test, ...
│
├── billing/                         # SaaS obuna + tarif + Click
│   ├── models.py (544)              # PlanFeature, SubscriptionPlan, PlanFeatureRule,
│   │                                # CenterSubscription, PaymentTransaction, PromoCode, ...
│   ├── services.py                  # tarif qo'llash, narx hisoblash, obuna aktivatsiya
│   ├── click_views.py               # prepare / complete / webhook
│   ├── plan_tiers.py                # SIDEBAR_FEATURE_GATES — tier gating
│   ├── decorators.py                # @require_feature, @require_active_subscription
│   ├── middleware.py                # SubscriptionMiddleware (hozir MIDDLEWARE'da YO'Q)
│   └── telegram_notifications.py
│
├── marketing/                       # Public sayt + CMS
│   ├── models.py (446)              # SiteSetting, FeatureBlock, PricingPlan, FAQ, Vacancy, ...
│   ├── views.py, views_superadmin.py
│   ├── urls.py (canonical), urls_i18n.py (/uz/ /ru/ /en/), urls_superadmin.py
│   └── templates/ (58 html)
│
├── game/                            # ⚡ Chaqmoq Game (alohida mobil o'yin)
│   ├── models.py (1384)             # GameProfile, Duel, GameMode, Tarif, Obuna, ShopItem, ...
│   ├── engines.py                   # MOTORLAR registri (duel, viktorina, ...)
│   ├── mobile_api.py (1735)         # /api/mobile/game/*
│   ├── matchmaking.py, cooldowns.py, session_services.py, services.py
│   ├── payments.py                  # o'yin tariflari uchun alohida Click webhook
│   └── google_auth.py               # Google Sign-In tekshiruvi
│
├── telegram_bot/                    # aiogram 3 botlar (~5100 qator)
│   ├── bot.py                       # entrypoint: 2 bot token, routerlar, aiohttp :8080
│   ├── handlers/                    # start, link_account, parent, student, teacher, manager,
│   │                                # admin_panel, broadcast, branch_approval, family_onboarding
│   ├── keyboards/, states/, utils/, services/  # api_client, scheduler, deep_link, profile_ctx
│   ├── i18n.py                      # uz/ru/cy (kirill) tillari
│   └── backup/backup_service.py     # kunlik DB backup Telegram'ga
│
├── english_teacher/                 # alohida AI bot (ingliz tili o'qituvchisi)
├── mobile_app/                      # ⭐ Flutter ilova (186 dart fayl)
├── desktop/                         # Electron/desktop wrapper artefaktlari
├── scripts/                         # yordamchi skriptlar (deploy, smoke, icon generator)
├── templates/                       # global shablonlar: base.html (1186), partials/, components/
├── static/                          # css, js, vendor, img, downloads (dmg/exe)
├── staticfiles/                     # collectstatic natijasi (git'da bo'lmasligi kerak)
├── media/                           # yuklangan fayllar
├── render.yaml                      # Render blueprint (infra as code)
├── start.sh                         # production start (gunicorn + bot)
├── Procfile                         # web: ./start.sh
├── requirements.txt
├── .env.example                     # ⭐ barcha env o'zgaruvchilar ro'yxati
└── Hujjatlar: README.md, RBAC_DOCUMENTATION.md, PERFORMANCE_REPORT.md, PERF_NOTES.md,
              RESTORE_GUIDE.md, BACKUP_TELEGRAM.md, GOOGLE_SETUP.md, MOBILE_DEPLOY_SETUP.md,
              DESIGN_PROMPT.md, CHAQMOQAPP_MASTER_PROMPT.md, CHAQMOQAPP_TZ.md (bu fayl)
```

### 4.1 Tozalanishi kerak bo'lgan artefaktlar (repo'da bor, lekin kod emas)

`_app_archive/`, `_ui_archive/`, `director-dashboard-pro/`, `lumina-director/`, `scratch/`,
`db.sqlite3.bak*`, `data.json` (5.4MB), `backup_before_saas.json`, `*.png`, `*.apk`, `*.ipa`, `venv/`.
`.git` hajmi **807MB** — tarixga commit qilingan DB fayllari sabab (27-bo'lim).

---

## 5. MULTI-TENANCY (KO'P MARKAZ ARXITEKTURASI)

### 5.1 Asosiy g'oya

Barcha markazlar **bitta PostgreSQL bazasida** yashaydi. Ajratish **`center_id` foreign key** orqali. Har bir "biznes" model'da `center` FK bor.

> **Muhim qoida:** har bir query'da `center` filtri bo'lishi shart. Bu qoida buzilgan joy = boshqa markazning ma'lumotini ko'rish (IDOR). `education/tests/test_idor_tenant.py` va `test_isolation.py` shuni tekshiradi.

### 5.2 `Center` modeli (accounts/models.py:13)

Asosiy maydonlar guruhlab:

**Identifikatsiya**
- `name`, `slug` (unique), `address`, `phone`, `director_telegram_id`
- `status`: `ACTIVE` / `BLOCKED` / `ARCHIVED`
- `is_system`, `is_demo`
- `parent_center` — filial ierarxiyasi (root markaz + filiallar)

**Limitlar**
- `max_users`, `max_groups`, `max_students`, `capacity_limit`

**Moliya**
- `payment_day` (oyning nechchisida to'lov kutiladi), `monthly_price`, `trial_ends`

**Feature flag'lar**
- `features` (JSONField) — markaz darajasidagi UI flag'lar:
  `ui_exam_sessions`, `ui_failed_students`, `ui_certificates`, `ui_weekly_schedule`, `support_teacher_enabled`
- `telegram_bot_enabled` (superadmin har markaz uchun alohida yoqadi, default **False**; mavjud markazlar migratsiyada yoqilgan — grandfather)
- `ai_enabled`, `ai_teacher_enabled`, `ai_student_enabled`, `ai_parent_enabled`

**Chaqmoq sozlamalari**
- `max_daily_lightning` (0 = cheksiz), `max_daily_deduction`

**Xayriya (donation)**
- `donation_enabled`, `donation_card_number`, `donation_card_holder`, `donation_qr_image`

**Promo**
- `promo_code`, `discount_amount`, `discount_percent`, `promo_start`, `promo_end`

**Ruxsat delegatsiyasi (markaz sozlamasi)**
- `manager_can_access_trash`, `manager_can_add_student`, `manager_can_remove_student`
- `teacher_can_add_student`, `teacher_can_remove_student`

**Per-tenant DB metadata (kelajak uchun, hozir ishlatilmaydi)**
- `db_name`, `db_user`, `db_password`, `db_host`, `db_port`

**Hisoblanadigan xossalar (`cached_property`)**
- `subscription` — ACTIVE, bo'lmasa PAUSED, bo'lmasa eng oxirgi obuna (backward-compat)
- `active_subscription` — faqat haqiqiy ACTIVE

### 5.3 Markaz aniqlanishining 3 usuli (TenantMiddleware)

Ustuvorlik tartibida:

1. **Session** (asosiy): `request.session['active_center_id']` — direktor bir nechta markazga ega bo'lishi mumkin, panelda almashtiradi.
2. **URL path** (ikkilamchi): `/<slug>/...` → `_get_center_by_slug_cached(slug)`. Slug topilgach `request.path_info` dan prefiks **olib tashlanadi** — shuning uchun barcha view va URL pattern'lar prefikssiz yozilgan.
3. **`request.user.center`** (fallback).

Aniqlangandan keyin:
- `request.center` va `request.active_center` o'rnatiladi.
- `set_current_tenant(center)` — **thread-local** kontekst (`core/tenant_context.py`), `db_router` shundan foydalanadi.
- Response oxirida `clear_current_tenant()`.

### 5.4 Cache qatlamlari (in-process, per-worker)

`core/middleware.py` da 3 ta dict cache:

| Cache | Kalit | TTL setting | Default |
|---|---|---|---|
| `_CENTER_CACHE` | `center_id` | `CENTER_CACHE_TTL` | 15s |
| `_SLUG_CACHE` | `slug` | `CENTER_SLUG_CACHE_TTL` | 60s |
| `_SUB_BLOCK_CACHE` | root `center_id` | `SUBSCRIPTION_BLOCK_CACHE_TTL` | 15s |

Bekor qilish funksiyalari: `invalidate_center_cache(center_id)`, `invalidate_center_tree_cache(center)` — billing eventlaridan chaqiriladi.

> ⚠️ Bu cache **worker-local**. 2 worker bo'lsa, biri yangilangan, ikkinchisi eskisini ko'rishi mumkin (TTL davomida). Shuning uchun TTL'lar qisqa.

### 5.5 Bloklash mantiqiy

`_is_center_blocked(center)`:
1. `center.status == "BLOCKED"` yoki root markaz BLOCKED → bloklangan.
2. Aks holda ACTIVE obuna olinadi va `sub.is_blocked()` tekshiriladi (muddat tugagan + grace period o'tgan, yoki `manual_block`).
3. Obuna umuman yo'q bo'lsa — bloklangan deb hisoblanmaydi (feature gate'lar alohida ishlaydi).

**Filial qoidasi:** filial hech qachon o'z obunasiga ega bo'lmaydi — **root markaz obunasidan** foydalanadi (`_root_center()` → `get_root_center()`).

### 5.6 URL arxitekturasi va tartib (config/urls.py)

Tartib **juda muhim** — Django birinchi mos kelgan pattern'ni oladi:

```
1.  /test-db/, /test-center/          — diagnostika (eng oldinda)
2.  /health/                          — Render health check (insert(2))
3.  /api/schema/, /api/docs/, /api/redoc/
4.  /admin/                           — Django admin (jazzmin)
5.  /hisob/login/                     — auth (accounts.auth_urls)
6.  /login/                           — SecureLoginView alias
7.  /api/v1/auth/link-telegram/, /api/calculate-lessons/, /api/hr/*
8.  /logout/
9.  /click/prepare|complete|webhook/  — Click (markaz obunasi)
10. /click/game/prepare|complete/     — Click (o'yin tariflari, ALOHIDA)
11. /api/click/*                      — legacy callback yo'llari
12. /payment/success|cancel/, /robots.txt, /sitemap.xml
13. /platform/                        — superadmin (accounts.urls)
14. /i18n/
15. ^(uz|ru|en)/                      — ⚠️ legacy slug pattern'dan OLDIN turishi SHART
16. legacy slug-prefiksli marketing redirect'lari
17. ''                                — marketing (public sayt)
18. /api/mobile/game/                 — ⚠️ core.urls dan OLDIN (core '' ga ulangan)
19. ''                                — core.urls (asosiy ilova)
20. /hisob/                           — accounts.urls_tenant
21. /hisob/billing/                   — billing
22. /chaqmoq/, /talim/, /do'kon/      — modul app'lari
23. /c/<slug>/                        — legacy center-scoped login/billing
24. ^(?:[a-z0-9-]+)/                  — slug prefiksli (NON-CAPTURING!) → slug_prefix_urls
```

> **Kritik izoh (kodda ham yozilgan):** 15-qator 16-dan oldin bo'lishi shart. Aks holda `/ru/support/` legacy pattern'ga tushib (`center_slug="ru"`), `NoReverseMatch` bilan qulaydi.

> **Kritik izoh 2:** 24-qatordagi regex **non-capturing** (`(?:...)`) — aks holda `center_slug` har bir view'ga kwarg sifatida uzatilib, hamma yerda `TypeError` beradi.

### 5.7 Filiallar (Branch)

Ikkita mexanizm parallel yashaydi (tarixiy):

1. **`Center.parent_center`** — filial ham to'liq `Center` yozuvi, root markazga bog'langan. Obuna, feature gate, bloklash root'dan olinadi.
2. **`accounts.Branch`** modeli — bir markaz ichidagi yengil "bo'lim" (guruhga `branch` FK). Ma'lumot ajratish emas, faqat guruhlash/filtrlash.

**`BranchRequest`** — direktor yangi filial so'raydi → superadmin (`/platform/filiallar/`) yoki Telegram bot tasdiqlaydi. Ikkalasi ham **bitta servisni** chaqiradi: `accounts/services/branch_requests.py`.

Filial limiti: `SubscriptionPlan.max_branches` (1 = faqat asosiy, 0 = cheksiz), `billing.services.can_add_branch()`.

---

## 6. ROLLAR VA RUXSATLAR (RBAC)

### 6.1 Rollar

`accounts.Roles` (TextChoices):

| Kod | Nomi | Doirasi |
|---|---|---|
| `director` | Direktor | Bir yoki bir nechta markaz |
| `manager` | Manager | Bitta markaz |
| `teacher` | O'qituvchi | O'z guruhlari |
| `student` | O'quvchi | O'zi |
| `parent` | Ota-ona | Farzandlari |

**Superadmin** alohida rol emas — `User.is_superuser=True`. RBAC middleware superuser'ni **butunlay o'tkazib yuboradi**.

### 6.2 3 qatlamli xavfsizlik

**Qatlam 1 — `SecureLoginView`** (`accounts/auth_views.py`)
`?next=` parametrini **butunlay ignore** qiladi. Login'dan keyin har doim rolga mos dashboardga yuboradi. Bu URL injection orqali ruxsat bypass qilishni to'sadi.

**Qatlam 2 — `RoleBasedAccessMiddleware`** (`core/middleware_rbac.py`)

Whitelist modeli: har rol uchun ruxsat berilgan **namespace'lar** va aniq **URL nomlari**.

```python
ROLE_PERMISSIONS = {
  'student':  {'namespaces': {'store', 'chaqmoq'},
               'names': {core:home, core:profile, core:notifications*,
                         core:student_panel_*_api, core:game_*, core:chat_*, ...}},
  'parent':   {'namespaces': set(),   # namespace ruxsati YO'Q — faqat aniq nomlar
               'names': {core:home, core:dashboard_parent, core:toggle_child,
                         core:parent_panel_*_api, ...}},
  'teacher':  {'namespaces': {'education', 'chaqmoq', 'store'},
               'names': {core:home, core:chat_*, accounts:profile, password_set, ...}},
  'manager':  {'namespaces': {'core','education','chaqmoq','store','billing','accounts'},
               'names': {logout, hr_*_api, ...}},
  'director': {'namespaces': {'core','education','chaqmoq','store','billing',
                              'marketing','accounts'}, 'names': {...}},
}
```

**Skip qilinadigan yo'llar** (`SKIP_PREFIXES`): `/static/`, `/media/`, `/admin/`, `/logout/`, `/hisob/login/`, `/hisob/billing/`, `/click/`, `/health/`, `/c/`, `/favicon.ico`.

**Tashqi auth API'lar** (`EXTERNAL_API_PREFIXES`) — o'z auth qatlami bor: `/api/mobile/`, `/api/click/`, `/api/schema/`, `/api/docs/`, `/api/redoc/`, `/api/v1/`.

> ⚠️ **Blanket `/api/` skip ataylab YO'Q.** Web sessiya bilan ishlaydigan API'lar RBAC'dan o'tadi — aks holda IDOR/RBAC bypass bo'lardi. Test: `core/tests_rbac_api.py`.

Ruxsat bo'lmasa:
- JSON kutilsa (`/api/` yo'lida, yoki `X-Requested-With: XMLHttpRequest`, yoki `Accept: application/json`) → `403 {"ok": false, "error": "...", "code": "rbac_forbidden"}`
- aks holda → `DASHBOARD_MAP[role]` ga redirect (hamma rol uchun `core:home`).

Slug-prefiksli URL'larda namespace bo'sh chiqishi mumkin — middleware slug'ni olib tashlab qayta `resolve()` qiladi.

**Qatlam 3 — view darajasi**
`@login_required`, `@require_feature("...")`, `@require_active_subscription`, view ichidagi rol/center tekshiruvlari.

### 6.3 Ruxsatlar matritsasi (funksional)

| Modul | Superadmin | Direktor | Manager | O'qituvchi | O'quvchi | Ota-ona |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Markazlar CRUD | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Tariflar / feature matritsasi | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Marketing CMS | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Filial so'rovini tasdiqlash | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Filial so'rovi yuborish | — | ✅ | ❌ | ❌ | ❌ | ❌ |
| Boshqaruv dashboard + AI | ✅ | ✅ | qisman | ❌ | ❌ | ❌ |
| Moliyaviy hisobot | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Guruh CRUD | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| O'quvchi qo'shish/olib tashlash | ✅ | ✅ | markaz sozlamasi bilan | markaz sozlamasi bilan | ❌ | ❌ |
| Davomat qilish | ✅ | ✅ | ✅ | ✅ (o'z guruhi) | ❌ | ❌ |
| To'lov qabul qilish | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Qarzdorlar ro'yxati | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| O'qituvchi oyligi (hammasi) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| O'z daromadi | — | — | — | ✅ | ❌ | ❌ |
| Chaqmoq berish | ✅ | qoidada `can_director` | `can_manager` | `can_teacher` | ❌ | ❌ |
| Chaqmoq qoidalari CRUD | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Lead CRM | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Do'kon (mahsulot CRUD) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Do'kondan xarid so'rovi | — | — | — | — | ✅ | ❌ |
| Imtihon o'tkazish | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Sertifikat berish | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Trash (o'chirilganlar) | ✅ | ✅ | `manager_can_access_trash` yoki `user.can_access_trash` | ❌ | ❌ | ❌ |
| Guruh chat | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Farzand ma'lumotlari | ✅ | ✅ | ✅ | ✅ (o'z guruhi) | — | ✅ |
| Obuna sotib olish | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## 7. AUTENTIFIKATSIYA VA SESSIYALAR

### 7.1 `User` modeli xususiyatlari

- `AbstractUser` dan meros, lekin **`username = None`**.
- `USERNAME_FIELD = "email"` — login **email** orqali.
- `phone_number` — ikkinchi login identifikatori. **Partial unique constraint**: faqat tirik (`is_deleted=False`) va `NOT NULL` yozuvlar orasida unique (`user_alive_phone_unique`). Bo'sh telefon **NULL** saqlanadi (bir nechta foydalanuvchi telefonsiz bo'lishi mumkin).
- Telefon `save()` da `normalize_phone()` bilan normalizatsiya qilinadi.
- `role` + `center` — RBAC va tenant uchun.
- **Ism maydonlari:** `ism`, `familya`, `otchestvo` (o'zbekcha). `full_name()` dublikatlarni olib tashlab birlashtiradi.
- **O'quvchi maydonlari:** `birth_date`, `gender`, `passport_id`, `jshr` (PINFL), `address`.
- **Ota-ona bog'lash:** `children` — `ManyToManyField("self", symmetrical=False, related_name="parents")`, `limit_choices_to={"role": "student"}`.
- **`child_code`** — `CHQ-XXXXXX` formatida (`secrets.randbelow`), o'quvchi yaratilganda avtomatik generatsiya. Ota-ona mobil ilovada shu kod bilan farzandni bog'laydi.
- **Telegram:** `telegram_id`, `telegram_username`, `is_telegram_linked`, `parent_telegram_id`, `parent_telegram_username`, `parent_telegram_linked_at`.
- **Parol tiklash:** `reset_code`, `reset_code_expire_at`, `reset_code_used`, `reset_attempts`, `reset_last_attempt`.
- **O'yin:** `game_only` (markazsiz o'yinchi — davomat/to'lov/qarz yo'q), `google_sub` (Google hisob ID).
- **Chaqmoq:** `chaqmoq` (balans), `oqituvchi_foizi` (default 40).
- **Arxiv:** `is_archived`, `archived_at`, `is_demo_user`.
- **Maxsus ruxsat:** `can_access_trash`.

**Indekslar:** `(center, role, is_archived)`, `(phone_number)`.

> ⚠️ **KRITIK PERFORMANCE TUZOG'I:** O'qituvchi `User.save()` ni `update_fields` bermasdan chaqirish `handle_rate_change` signalini ishga tushiradi va **butun markaz davomatini qayta hisoblaydi** (o'lchangan: 94 sekund, 24 550 query). Masalan reset-kodni saqlaganda ham. **Har doim `save(update_fields=[...])` ishlatish shart.**

### 7.2 Auth backend

`accounts/backends.EmailOrPhoneBackend` — identifikator email yoki telefon bo'lishi mumkin. `AUTHENTICATION_BACKENDS` da birinchi, keyin standart `ModelBackend`.

Yordamchilar: `accounts/auth_helpers.py` → `authenticate_login_identifier()`, `mask_login_identifier()`, `resolve_login_attempt()` (web va mobil bir xil mantiq ishlatadi).

### 7.3 Brute-force himoyasi (`accounts/login_throttle.py`)

| Setting | Default | Ma'nosi |
|---|---|---|
| `LOGIN_MAX_FAILED_ATTEMPTS` | 8 | Bir identifikator uchun |
| `LOGIN_THROTTLE_WINDOW_SECONDS` | 900 (15 min) | Oyna |
| `LOGIN_IP_MAX_FAILED_ATTEMPTS` | 40 | Bir IP uchun (credential stuffing) |

Test: `core/tests_login_hardening.py`.

### 7.4 Parol tiklash

Ikki yo'l:
1. **Telegram orqali kod** — bot foydalanuvchiga kod yuboradi, saytda kiritadi (`password_reset_views.py`, `forgot_password_*` URL'lari).
2. **Magic login** (`accounts/magic_login.py`) — "Kirish havolasi":
   - Token `django.core.signing.dumps({"uid", "s": parol_hash_oxiri}, salt="chaqmoq-magic-login-v1")`.
   - Muddat: **30 kun** (`MAGIC_MAX_AGE`).
   - **Bir martalik xarakter:** foydalanuvchi parol o'rnatishi bilan `password` hash o'zgaradi → `s` mos kelmaydi → eski havola kuchsizlanadi.
   - Oqim: manager panelda "Kirish havolasi" tugmasi → link (yoki Telegram bot yuboradi) → bir bosishda kiradi → PIN/parol o'rnatadi → keyingi safar telefon+parol.
   - Maqsad: "login-parolni eslamayman" muammosini kamaytirish.

### 7.5 Ota-onani Telegram'ga ulash

`accounts/services/parent_telegram_link.py` + `ParentTelegramLinkToken` modeli:
- O'quvchi uchun token yaratiladi (`created_by`, muddat, ishlatilgan bayrog'i).
- Havola **Family bot**ga boradi (`TELEGRAM_BOT_USERNAME_FAMILY`), chunki to'liq ota-ona paneli shu botda.
- Deep-link: `https://t.me/<family_bot>?start=<token>`.
- Bot start'da tokenni tekshiradi → `user.parent_telegram_id` to'ldiriladi → panel avtomatik ochiladi.
- Manager panelda: link yaratish, holat ko'rish, eslatma yuborish (`student_parent_link_*` URL'lari).

> ⚠️ Tarixiy bug: PostgreSQL'da `SELECT ... FOR UPDATE` nullable outer join bilan ishlamaydi — tuzatilgan (commit `ab1b446`).

### 7.6 Mobil token (Bearer)

`core.models.MobileAccessToken`:

| Maydon | Izoh |
|---|---|
| `key_prefix` | Xom tokenning boshi (indekslangan, tez topish uchun) |
| `key_hash` | SHA-256 hash, **unique**. Xom token **DB'da saqlanmaydi** |
| `device_name`, `device_platform` | Sessiya ro'yxatida ko'rsatish uchun |
| `expires_at`, `is_revoked`, `last_used_at` | Muddat va holat |
| `center`, `user` | Bog'lanish |

Sozlamalar:
- `MOBILE_ACCESS_TOKEN_DAYS` = 30 (kodda 1..90 kunga clamp qilinadi; ilgari 180 kun hardcode edi — o'g'irlangan qurilma xavfi).
- `MOBILE_ACCESS_TOKEN_MAX_PER_USER` = 8 (oshsa eng eskisi revoke).

Endpointlar: `/api/mobile/auth/login|logout|logout-all|refresh|sessions|sessions/<id>/revoke|status|me|change-password/`.

> **Qoida:** Bearer token bo'lsa **har doim ustun**. Muddati tugagan/revoke token qolib ketgan Django session cookie bilan "qutqarilmaydi" (ataylab).

Testlar: `core/tests_mobile_api.py`, `core/tests_mobile_token_ttl.py`.

### 7.7 Google Sign-In (faqat Chaqmoq Game)

- `GOOGLE_OAUTH_CLIENT_IDS` — vergul bilan ajratilgan client ID'lar (iOS, Android debug, Android Play signing, Web — 4 ta).
- Bo'sh bo'lsa ilovada Google tugmasi **ko'rinmaydi**.
- `game/google_auth.py` id_token'ni tekshiradi → `User.google_sub` bo'yicha topadi/yaratadi → `game_only=True`, `center=None`.
- Hujjat: `GOOGLE_SETUP.md`.

### 7.8 Telegram bot ↔ Django internal API

- Bot `BOT_INTERNAL_API_URL` (`http://localhost:8080`) orqali **o'z** aiohttp serverini ko'taradi; Django'ga esa `X-API-SECRET` header bilan murojaat qiladi (`/api/v1/...`, `accounts/auth_urls.py` ichidagi bot endpointlari, `core/api_bot.py`).
- `API_SECRET` = `config/shared_secret.resolve_api_secret(secret_key=SECRET_KEY)` — env berilmasa `SECRET_KEY`dan deterministik hosil qilinadi (bot va Django bir xil qiymatni topadi).
- Test: `core/tests_bot_api.py`.

---

## 8. MA'LUMOTLAR MODELI — TO'LIQ KATALOG

Umumiy: **~120 model**, 8 app'da. Quyida app bo'yicha, muhim maydonlar va cheklovlar bilan.

### 8.1 Umumiy naqshlar

**SoftDeleteMixin** (`core/soft_delete.py`)
```python
class SoftDeleteMixin(models.Model):
    is_deleted   = BooleanField(default=False)
    deleted_at   = DateTimeField(null=True)
    deleted_by   = FK(User, null=True)
    objects      = AliveManager()   # is_deleted=False
    all_objects  = models.Manager() # hammasi
```
Ishlatadigan modellar: `Center`, `User`, `Group`, `Enrollment`, `Payment`, `TuitionMonth`, `PaymentAllocation`, `StudentActivity`, `Category`, `Product`, `game.QuestionCategory`, `game.Question`, `game.NewsPost`, `game.ShopItem`, `game.GameMode`.

> ⚠️ **Qarz hisoblashda `all_objects` ishlatiladi** — o'chirilgan `TuitionMonth` uchun fee=0 hisoblanadi (virtual qarz yozilmasligi kerak). Bu ataylab qilingan.

**Boshqa naqshlar:**
- Deyarli har bir modelda `center` FK (tenant).
- `created_at` / `updated_at` (`auto_now_add` / `auto_now`).
- `created_by` / `updated_by` FK — kim qildi (audit).
- Snapshot modellari: qoida keyin o'zgarsa ham tarix buzilmasligi uchun (`Ledger.rule_nom`, `TeacherSalarySnapshot.details`, `StudentGroupTransfer.old_payment_state`).
- `metadata = JSONField` — kelajakda migratsiyasiz kengaytirish uchun.

---

### 8.2 `accounts` — 12 model

| Model | Vazifasi | Muhim maydonlar/cheklovlar |
|---|---|---|
| **Center** | Tenant (o'quv markaz) | `slug` unique, `status`, `parent_center`, `features` JSON, limitlar, promo, donation, per-tenant DB metadata. `subscription`/`active_subscription` cached_property |
| **User** | Barcha rollar uchun yagona model | `email` USERNAME_FIELD, `phone_number` partial-unique, `role`, `center`, `children` M2M(self), `child_code` (CHQ-XXXXXX), `game_only`, `google_sub`, `chaqmoq` |
| **DirectorCenterAccess** | Direktorga bir nechta markazga ruxsat | `director`, `center`, `granted_by`, `is_active` |
| **BranchRequest** | Direktor yangi filial so'raydi | `requester`, `parent_center`, `status`, `telegram_message_id`, `created_center`, `reject_reason` |
| **Branch** | Markaz ichidagi yengil filial | `center`, `name`, `is_active`, `order`; `Group.branch` FK |
| **ParentTelegramLinkToken** | Ota-onani botga ulash tokeni | `student`, `token` unique, `created_by`, muddat, ishlatilgan bayrog'i |
| **UserActivity** | Foydalanuvchi faolligi jurnali | `user`, harakat, vaqt |
| **BotAdmin** | Telegram bot admini | Telegram ID + ruxsat |
| **BotSettings** | Bot global sozlamalari | Kalit-qiymat |
| **AdminAuditLog** | Superadmin harakatlari jurnali | Kim, nima, qachon |
| **Roles** | TextChoices (model emas) | director/manager/teacher/student/parent |
| **UserManager** | `BaseUserManager` (email bilan) | `create_user`, `create_superuser` |

---

### 8.3 `education` — 44 model (ENG MUHIM APP)

#### 8.3.1 O'quv jarayoni

| Model | Vazifasi | Muhim tafsilotlar |
|---|---|---|
| **Group** | O'quv guruhi | `center`, `branch`, `nom`, `oqituvchi`, `support_teacher` + `support_foiz`, `kurs_narxi`, `oqituvchi_foiz`, `oy_dars_soni`, `max_students`, `category`(lang/it) + `category_obj` FK, `course_template`, `course_start_date`, `duration_months`, `lessons_per_week`, `estimated_end_date`(+`_manual`), `is_archived`, `is_closed`/`closed_at`/`closed_by`. Metod: `dars_boshiga_tolov()` |
| **GroupSchedule** | Dars jadvali | `weekday` (1=Du..7=Yak), `start_time`, `end_time`, `room`. `unique_together (group, weekday, start_time)` |
| **Category** | Bo'lim/fan (Tillar, IT, ...) | `name`, `icon` (emoji), `center` |
| **CourseTemplate** | Kurs shabloni (narx, davomiylik) | Guruh yaratganda default qiymatlar |
| **Enrollment** ⭐ | O'quvchi ↔ guruh bog'lami. **Asosiy moliyaviy birlik** | Pastda alohida jadval |
| **GroupStudent** | Legacy bog'lam | Yangi kodda `Enrollment` ishlatiladi |
| **Oquvchi**, **Dars**, **OylikHisobot**, **Student** | Legacy modellar | Yangi kodda ishlatilmaydi, saqlangan |
| **StudentGroupHistory** | O'quvchi guruhda qachondan-qachongacha bo'lgan | `start_date`, `end_date` (NULL = hozir ham guruhda), `kurs_narxi`/`oqituvchi_foiz` snapshot |
| **StudentGroupTransfer** | Guruhdan guruhga o'tkazish | `old_group`/`new_group` PROTECT, `old_payment_state` JSON, `old_attendance_summary` JSON, `performed_by` |
| **StaffProfile** | Xodim profili (HR) | `user` OneToOne, `tenant`, `role`(teacher/manager/admin/other), `position`, `hire_date`, `subjects` M2M(`store.Yonalish`), `levels`/`directions` JSON |
| **TeacherAvailability** | O'qituvchi bo'sh/band vaqtlari | `weekday`, `start_time`, `end_time`, `type`(available/busy). `clean()` da tenant mosligi tekshiriladi |

**`Enrollment` maydonlari to'liq:**

| Maydon | Ma'nosi |
|---|---|
| `group`, `student`, `center`, `course` | Bog'lanishlar (`course` = `group.category_obj`, `save()` da avtomatik) |
| `kurs_narhi` | Enrollment darajasidagi oylik narx (bo'sh bo'lsa `group.kurs_narxi`) |
| `monthly_price`, `monthly_lessons` | Yozilish paytidagi **snapshot** (keyin guruh narxi o'zgarsa ham tarix buzilmaydi) |
| `oqituvchi_foiz` | 0..100 |
| `joined_at` | Qo'shilgan sana (prorated hisob uchun) |
| `pricing_type` | `full` (to'liq oy) / `prorated` (dars bo'yicha) / `custom` (admin qo'lda) |
| `lesson_pattern` | `group` (avtomatik/jadvaldan) / `even` (juft: Se,Pay,Shan) / `odd` (toq: Du,Chor,Ju) / `daily` |
| `active_lessons_count` | Joriy oy uchun hisoblangan darslar |
| `remaining_lessons_override` | Qo'lda kiritilgan qolgan dars soni (bo'sh = avtomatik) |
| `last_lesson_date` | Oxirgi dars sanasi — **chiqarilgan o'quvchi qarzini cheklaydi** |
| `student_payable_amount` | O'quvchidan real olinadigan summa (chegirma). `clean()`: kurs narxidan katta bo'lmaydi |
| `paid_amount`, `jami_tolangan` | Hisoblangan to'langan summalar |
| `credit_balance` | Ortiqcha to'lov — keyingi oy fee yozilganda avtomatik ayiriladi |
| `is_active`, `is_deferred` | Faol / kechiktirilgan |

`unique_together = (group, student)`. Indekslar: `(center, is_active, is_deleted)`, `(group, is_active)`, `(student, is_active)`.

Xossalar: `resolved_monthly_price`, `resolved_monthly_lessons`, `full_course_amount`, `effective_student_payable_amount`, `oqituvchi_daromadi`, `real_oqituvchi_daromadi(year, month)`.

#### 8.3.2 Davomat

| Model | Tafsilot |
|---|---|
| **Attendance** | `group`, `student`, `teacher`, `center`, `date`. `status`: `present`/`late`/`absent_excused`/`absent_unexcused`. Legacy: `present` (bool), `forced` (kelmadi, lekin o'qituvchiga pul yozilsin). `unique_together (group, student, date)`. Indekslar: `(group,date)`, `(center,date)`, `(status)`. `save()` da `teacher` avtomatik guruh o'qituvchisidan, `perf_cache` bekor qilinadi |
| **AttendanceHistory** | Legacy kunlik yozuv: `is_present`, `plus_coin`, `minus_coin` |
| **DailyLightningRecord** | Kunlik chaqmoq: `plus_points`, `minus_points`, `attendance_status`. `unique_together (group,student,date)` |
| **DailyLightningSetting** | Markaz uchun kunlik chaqmoq limiti (`date`, `max_lightning`, 0=cheksiz) |

> **Muhim:** bir o'quvchi bir kunda 2 guruhda bo'lsa — **2 ta alohida Attendance** yozuvi.

#### 8.3.3 Moliya (⭐ eng nozik qism)

| Model | Tafsilot |
|---|---|
| **TuitionMonth** ⭐ | Bir `enrollment` uchun bir oylik hisob. `month` = oyning 1-kuni. `fee_amount`. `unique_together (enrollment, month)` va `(center, enrollment, month)`. Indekslar: `(enrollment,month,is_deleted)`, `(center,month,is_deleted)` |
| **PaymentAllocation** ⭐ | To'lov qaysi oyga qancha ketganini yozadi. `payment` + `tuition_month` + `amount`. Misol: 600k to'lov → Yanvar 550k + Fevral 50k. `save()` da to'lov intizomi bonusi tekshiriladi |
| **Payment** | `enrollment`, `student`, `group`, `center`, `payment_type`(cash/card/mixed), `cash_amount`, `card_amount`+`card_rate`+`card_currency`, `summa` (hisoblanadi), `paid_date`, `paid_time`, `created_by`, `note`. `save()`: summa hisoblanadi → `Enrollment.jami_tolangan` yangilanadi → chaqmoq bonusi tekshiriladi. `pre_save` signal: enrollment berilmasa avtomatik topiladi |
| **TeacherIncome** | Har `Attendance` uchun o'qituvchi ulushi. `attendance` OneToOne, `amount`, `center_amount`, `total_amount` |
| **TeacherCompensationRule** | O'qituvchi maosh turi: `PERCENT` / `FIXED` / `PER_STUDENT` / `PER_LESSON`, `effective_from` |
| **SalaryPayout** | O'qituvchiga to'langan oylik: `period_year`, `period_month`, `amount`, `paid_at` |
| **TeacherExpectedIncomeSnapshot** | Kutilayotgan daromad snapshoti: `active_students`, `expected_income`, `income_per_student` |
| **CenterExpense** | Markaz xarajati (kategoriya, summa, sana) |
| **FinancialMonth** | Oy yopilishi: `center`, `year`, `month`, `is_closed`, `closed_at`, `closed_by` |
| **MonthlyFinanceSnapshot** | `FinancialMonth` ga OneToOne: `total_income`, `total_expense`, `center_profit`, `student_count`, `attendance_rate` |
| **TeacherSalarySnapshot** | Yopilgan oy uchun o'qituvchi oyligi: `salary`, `attendance_count`, `details` JSON (guruh/o'quvchi bo'yicha breakdown) |

#### 8.3.4 Imtihon moduli

| Model | Tafsilot |
|---|---|
| **CenterExamSetting** | `center` OneToOne. `exam_system_enabled`, `exam_every_n_lessons` (default 12), `passing_score_percent` (60), `failed_student_threshold` (3), `exam_file_upload_enabled`, `exam_result_required`, `optional_task_upload_prompt_enabled`, `minimum_certificate_attendance_percent` (70), `minimum_certificate_average_percent` (60) |
| **ExamReminderLog** | O'qituvchiga "imtihon vaqti keldi" eslatmasi va uning javobi (`yes`/`no`/`later`/`telegram`) |
| **ExamSession** | `center`, `group`, `teacher`, `attendance_date`, `exam_date`, `lesson_number_reference`, `exam_sequence_number`, `teacher_decision`, `status` (draft/completed/cancelled) |
| **ExamResult** | Har o'quvchi natijasi: ball, foiz, o'tdi/o'tmadi, `follow_up_status` (not_required/pending/parent_contacted/support_required/reviewed) |
| **ExamResultFile**, **ExamSessionTaskFile** | Yuklangan fayllar (ish varaqlari, topshiriqlar) |
| **ExamQuestion** | Imtihon savollar banki |

#### 8.3.5 Reyting, progress, sertifikat

| Model | Tafsilot |
|---|---|
| **StudentActivity** | Ball beruvchi faoliyat: `type` (attendance/homework/participation/test/penalty/other), `score` (musbat/manfiy), `source_attendance`, `source_exam` |
| **GroupInternalRankingSnapshot** | Guruh ichidagi reyting: `attendance_score`, `activity_score`, `exam_score`, `homework_score`, `discipline_score`, `lightning_bonus_score` → `total_internal_score`, `rank_position`, `explanation_text` (nega shu o'rin) |
| **StudentAcademicSummary** | Yakuniy xulosa: imtihon soni, o'rtacha ball/foiz, o'tish foizi, davomat foizi, ichki reyting, `completion_recommendation` |
| **CertificateTemplate** | Sertifikat/diplom shabloni (fayl), `is_active`, `template_type` |
| **CertificateRecord** | Berilgan sertifikat: `certificate_number` unique, `verification_token` UUID unique, `status` (draft/…), `recommendation_status`, `approved_by`/`issued_by`, `pdf_file` |
| **CertificateVerificationLog** | Ommaviy tekshiruv jurnali: `ip_address`, `user_agent` |
| **GroupClosureWorkflow** | Guruhni yopish jarayoni: `group` OneToOne, `status` (open/…), bosqichlar |
| **EducationAuditLog** | Education modulidagi muhim o'zgarishlar jurnali |

---

### 8.4 `chaqmoq` — 3 model (gamifikatsiya)

| Model | Tafsilot |
|---|---|
| **Rule** | Chaqmoq qoidasi. `tur`: `plus`, `minus`, `attendance_penalty`, `attendance_bonus`, `payment_bonus`, `payment_discipline`. `min_baho`..`max_baho` diapazon. Rol ruxsatlari: `can_director`, `can_manager`, `can_teacher`. Davomat qoidalari: `absence_limit` (3), `presence_limit` (12), `lightning_penalty` (-5), `lightning_bonus` (10), `period`(monthly). To'lov: `payment_bonus_lightning` (5). Intizom: `discipline_deadline_day` (10), `discipline_bonus_score` (5), `discipline_penalty_score` (-10), `discipline_active` |
| **Ledger** | Chaqmoq harakati (daftar). `student`, `beruvchi`, `group`, `rule` (SET_NULL) + **snapshot**: `rule_nom`, `rule_tur`, `rule_min_baho`, `rule_max_baho`. `ball` (musbat/manfiy), `sana`, qaysi oy uchun (dublikat himoyasi) |
| **LightningHistory** | Chaqmoq balans tarixi (umumiy balans shundan hisoblanadi) |

---

### 8.5 `store` — 17 model (do'kon + CRM)

**Do'kon:**

| Model | Tafsilot |
|---|---|
| **Product** | `nom`, `narx_chaqmoq`, `narx_som`, `sotilgan_soni`, `allowed_categories` M2M (qaysi bo'lim o'quvchilari sotib olishi mumkin) |
| **ProductImage** | Bir mahsulotga bir nechta rasm |
| **PurchaseRequest** | O'quvchi so'rovi: `student`, `product`, `qty`, `status` (kutilmoqda/tasdiqlangan/rad etilgan), `manager` |
| **Sale** | Amalga oshgan savdo: `narx_chaqmoq`, `narx_som`, `manager` |
| **Comment** | Mahsulot izohi, `parent` bilan javob (thread) |

**Xarajat va to'lov usuli:**

| Model | Tafsilot |
|---|---|
| **ExpenseCategory** | Xarajat toifasi |
| **Expense** | `summa`, `izoh`, `sana`, `category`, `payment_method`, `receiver`, `worker`, `product` |
| **PaymentMethod** | Markazning to'lov usullari CRUD (`nom`, `is_active`) |

**CRM (lead):**

| Model | Tafsilot |
|---|---|
| **Lead** | To'liq ariza: `ism`/`familya`/`otchestvo`, `birth_date`, `gender`, `passport_id`, `jshr`, `telefon1`/`telefon2`, `parent_phone`/`parent_name`, `yosh`, `address`, `bilim_darajasi`, `manba` FK, `yonalish` FK, `status` FK, `assigned_manager`, `lead_group` FK, `next_follow_up_date` (indeksli), `comment`, `lost_reason`. **Konversiya:** `converted_user`, `converted_at`, `converted_by`, `converted_to_student`, `is_confirmed`/`confirmed_at`/`confirmed_by`. Enum'lar: `Subject` (ielts/general_english/math/russian/other), `PipelineStatus` (new/contacted/trial/confirmed/converted/canceled) |
| **LeadGroup** | Guruh yig'ilayotgan "to'plam": `name`, `subject`, `department`, `min_students`, `status`. To'lganda → real `Group` ga aylantiriladi |
| **LeadStatus** | Sozlanadigan pipeline bosqichi: `nom`, `code`, `order`, `is_active` |
| **LeadActivity** | Lead bilan bo'lgan har bir muloqot jurnali |
| **TrialLesson** | Sinov darsi: sana, guruh, natija |
| **TrialLessonActivity** | Sinov darsi harakatlari |
| **Manba** | Lead qaydan kelgani (Instagram, tanish, ...) |
| **Yonalish** | Yo'nalish/fan (`nom`, `color`, `is_active`) — `StaffProfile.subjects` ham shuni ishlatadi |

---

### 8.6 `core` — 22 model (infratuzilma)

| Model | Tafsilot |
|---|---|
| **Notification** | `center`, `sender`, `recipient`, `title`, `message`, `is_read`, `type` (system/coin/broadcast/purchase/…) |
| **NotificationPreference** | `user` OneToOne: `receive_coin`, `receive_broadcast`, `receive_purchase`, `receive_system` |
| **MobileAccessToken** | Mobil Bearer token (7.6-bo'lim) |
| **DirectorAIChatSession** | AI chat sessiyasi: `title`, `launcher_position` JSON (widget joyi) |
| **DirectorAIChatMessage** | `role` (user/assistant), `content`, `source` (gemini/cache/fallback/rate-limited), `metadata` |
| **CenterDailyMetric** | Markaz kunlik: `students_count`, `teachers_count`, `revenue` |
| **TeacherDailyMetric** | O'qituvchi kunlik: `students_count`, `revenue` |
| **StudentDailyMetric** | O'quvchi kunlik: `attendance`, `payment_status` |
| **ChurnRisk** | Ketib qolish xavfi: skor, holat, `debt_amount`, `notified_at`, `assessed_at` |
| **GroupChat**, **ChatMessage**, **ChatAttachment**, **ChatPresence**, **ChatMessageRead** | Guruh chat: xabar, javob (`reply_to`), fayl/rasm/link biriktirish, "yozmoqda" holati, o'qilgan belgisi |
| **GameSession** | O'yin sessiyasi (web mini-o'yinlar): `game_slug`, `score`, `level`, `duration_sec`, `coins_earned`, `balls_earned` |
| **GlobalGameConfig** | O'yin global yoq/o'chir (`game_slug`, `is_enabled`) |
| **CenterGameConfig** | Markaz uchun: `is_enabled`, `max_coins`, `min_score` |
| **StudentGameProgress** | `current_level`, `best_score`, `total_sessions` |
| **GameSuggestion** | O'quvchi taklif qilgan o'yin (`is_reviewed`) |
| **GameQuestion** | Mini-o'yin savollari (`question_data` JSON, `is_ai_generated`) |
| **GameBallsConfig** | Ball→chaqmoq konvertatsiya: `min_balls_to_convert`, `chaqmoq_per_conversion` |
| **StudentBallsWallet** | `total_balls`, `lifetime_balls`, `last_ball_at` |
| **GameBallsConversionLog** | `balls_spent` → `chaqmoq_earned` |

> ⚠️ **Diqqat:** `core.GameSession` va `game.GameSession` — **ikki xil model**. `core` dagisi web mini-o'yinlar uchun, `game` dagisi Chaqmoq Game (mobil) uchun. Aralashtirmang.

---

### 8.7 `billing` — 11 model (SaaS)

| Model | Tafsilot |
|---|---|
| **PlanFeature** | Bitta huquq/imkoniyat. `code` unique, `category` (core/finance/marketing/team/advanced), `type`: `CORE` (doim ochiq) / `BOOLEAN` / `LIMIT` (raqamli chek) / `QUOTA` (oylik kvota). Ko'p tilli: `name_uz/ru/en`, `description_uz`. Landing: `implementation_status` (READY/PARTIAL/PLANNED), `show_on_landing`, `is_highlight` |
| **SubscriptionPlan** | Tarif: `tier` (1=FREE, 10=STANDARD, 20=PRO, 30=PREMIUM), `code` unique, `title`, `monthly_price`/`price`, `duration_days`, `max_users`/`max_groups`/`max_students`/`max_branches`, davriy narxlar `price_3m/6m/9m/12m`, `discount_percent`, `is_popular`/`is_recommended`, `original_price`, `badge_label`, `features` JSON (legacy) + `plan_features` M2M, landing meta (`subtitle_uz`, `description_uz`, `student_range_uz`, `landing_visible`) |
| **PlanFeatureRule** | Tarif ↔ feature: `enabled` + `limit_value` (NULL = cheksiz). Superadmin matritsasi shu jadvalni tahrirlaydi; `enabled=True` bo'lganda M2M ham sinxronlanadi (backward-compat) |
| **FeatureUsage** | QUOTA hisobi: `center`, `feature`, `period` ("YYYY-MM"), `used_count` |
| **CenterSubscription** ⭐ | Markaz obunasi: `plan` (PROTECT), `status` (ACTIVE/PAUSED/…), `started_at`, `expires_at`, `paused_at`+`remaining_seconds`, `manual_block`, `is_grandfathered`. Metodlar: `GRACE_PERIOD_HOURS`, `hard_expires_at`, `is_expired()`, `is_hard_expired()`, `is_blocked()`, `in_grace_period()`, `is_over_student_limit()`, `days_left` |
| **CenterFeatureOverride** | Superadmin bitta markazga feature'ni qo'lda yoqadi/o'chiradi (tarifdan qat'i nazar) |
| **Subscription** | Legacy: user-darajali obuna |
| **PaymentTransaction** | Click tranzaksiyasi: `transaction_id` unique, `click_trans_id`, `amount`, `status`, `paid_at` |
| **PromoCode** | `code` unique, `percent_off`, `starts_at`/`ends_at`, `max_uses`/`used_count`, `once_per_center`, `plans` M2M. `is_valid_now()` |
| **SubscriptionOrder** | Buyurtma: `plan`, `duration_months`, `base_price`, `discount_percent`, `final_price`, `promo`, `status`, `paid_at` |
| **SubscriptionRequest** | Naqd to'lov so'rovi (superadmin tasdiqlaydi/rad etadi) |

---

### 8.8 `marketing` — 13 model (public sayt CMS)

Barchasi `TimeStampedModel` dan meros. Superadmin `/platform/marketing/` dan tahrirlaydi.

| Model | Tafsilot |
|---|---|
| **SiteSetting** | Global sozlamalar (logo, kontakt, meta, hero matnlari) |
| **PartnerLogo** | Hamkor logolari |
| **FeatureBlock** | "Imkoniyatlar" bloklari |
| **ScreenshotSection** | Skrinshot galereyasi |
| **PricingPlan** | Landing'da ko'rinadigan tarif kartasi (billing'dagi `SubscriptionPlan` dan alohida — marketing matni) |
| **PricingFeature** | Tarif kartasidagi qatorlar |
| **Testimonial** | Mijoz fikri |
| **FAQ** | Savol-javob |
| **DemoLead** | Demo so'ragan potensial mijoz (platforma o'zining lead'i) |
| **SupportCard** | Qo'llab-quvvatlash kartalari |
| **Vacancy** | Vakansiya |
| **StaticPage** | Statik sahifa (privacy, terms, data-deletion) |

Import/eksport: `marketing/pricing_plan_io.py` (test: `tests_pricing_plan_io.py`).

---

### 8.9 `game` — 18 model (Chaqmoq Game)

> **Kritik izoh:** O'yin **chaqmog'i** ChaqmoqApp'ning `chaqmoq.Ledger` balansidan **BUTUNLAY ALOHIDA**. ChaqmoqApp o'quvchisi ham o'yinda 0 dan boshlaydi. Bu ataylab: o'yin iqtisodiyoti markaz iqtisodiyotiga tegmasligi kerak.
> **Tenant izolyatsiyasi:** `center=None` → barcha markazlarga ko'rinadi (global kontent).

**Kontent (admin paneldan kiritiladi):**

| Model | Tafsilot |
|---|---|
| **QuestionCategory** | Savollar to'plami, masalan "Mevalar (A1)". `daraja`: A1/A2/B1/B2/C1 |
| **Question** | Savol + variantlar + to'g'ri javob |
| **NewsPost** | O'yin ichidagi yangiliklar |
| **GameMode** ⭐ | Katalogdagi bitta **o'yin**. `nom`, `slug`, `motor` (mexanika kaliti), `izoh`, `yoriqnoma`, `ikonka`, `rang`, `rasm`, `kategoriyalar` M2M, `daraja` filtri, `savollar_soni`, `savol_soniya`, `jon_narxi`, `xp_mukofot`, `chaqmoq_koef`, `sozlamalar` JSON |
| **ShopItem** | Do'kon mahsuloti (avatar, tema, boost) |
| **Tarif** | O'yin tarifi: `narx_som`, `kun`, `jon_soni`, `soat` (jon tiklanishi), `oyin_qulf_soat`, `chaqmoq_bonus_foiz` |

**O'yinchi va o'yin:**

| Model | Tafsilot |
|---|---|
| **GameProfile** ⭐ | O'yinchi: `user` (robot uchun NULL), `robot` bool, `robot_ism`, `maxorat` (0.5–0.9), `avatar`, `center`, `xp`, `hafta_xp`, `chaqmoq` (Decimal), jon, streak, `liga` (bronza/kumush/oltin/olmos) |
| **Duel** | Ikki o'yinchi bahsi + natija |
| **DuelQuestion** | Duel savollari va javoblar |
| **DuelQueue** | Real raqib qidirish navbati |
| **DuelInvite** | Do'stni duelga chaqirish |
| **GameSession** | Yakka o'yin sessiyasi |
| **GameSessionQuestion** | Sessiya savollari |
| **GameCooldown** | O'ynalgan o'yin qulfi (`oyin_qulf_soat`) |
| **Obuna** | Faol tarif: `boshlangan`, `tugaydi`, `tolangan`. `faol` xossasi |
| **TarifSorovi** | Tarif sotib olish so'rovi: `usul` (click/naqd), `holat` (kutilmoqda/tolangan/bekor), `narx_som` (muzlatilgan), `transaction_id`, `obuna` |
| **Purchase** | Do'kondan xarid |
| **Friendship** | Do'stlik (so'rov + tasdiq) |
| **Feedback** | Shikoyat/taklif |

**O'yin qoidalari (kodda konstanta, `game/models.py` boshida):**

```python
SAVOLLAR_SONI = 10           # bitta duelda savol soni
SAVOL_SONIYA = 10            # bitta savolga soniya

BEPUL_JON = 3                # har tiklanishda 3 jon
BEPUL_JON_SOAT = 8           # 8 soatda tiklanadi
BEPUL_OYIN_QULF_SOAT = 24    # o'ynalgan o'yin 24 soatga qulflanadi

# Chaqmoq mukofoti — ANIQLIK FOIZIDAN (savol soniga bog'liq emas)
CHAQMOQ_NARVONI = [(1.00, +5), (0.75, +3), (0.50, +2), (0.30, 0)]
CHAQMOQ_JARIMA = -1          # 30% dan past → jarima
```

Jarima **hech qachon** koeffitsiyentga ko'paytirilmaydi (`mukofotni_olchash`): jazo o'yin tanloviga bog'liq bo'lmasligi kerak.

**Motorlar (`game/engines.py`):**

Motor = o'yin mexanikasi, **Flutter kodida** yozilgan. Admin panelda motor ustiga *o'yin* (`GameMode`) qo'yiladi.
- Admin yangi **o'yin** qo'shsa → ilova avtomatik ko'radi (katalog API).
- Yangi **motor** → ilovaning yangi versiyasi kerak.
- Ilova tanimaydigan motor kelsa → katalogda "ilovani yangilang" holatida ko'rsatiladi (ro'yxat buzilmaydi).

Motor maydonlari: `kalit`, `nom`, `izoh`, `yoriqnoma`, `ikonka`, `rang`, `savollar_soni`, `savol_soniya`, `min_savol`, `javob_ochiq` (savol bilan javobni ham yuborishmi — xotira o'yinida ha), `duel_oqimi`, `sozlamalar`.

Mavjud motorlar: `duel` (⚔️), `viktorina` (🧠) va boshqalar.

---

## 9. BIZNES LOGIKA — QOIDALAR VA ALGORITMLAR

> Bu bo'lim platformaning **eng qimmatli** qismi. Bu yerdagi qoidalar real pul bilan bog'liq. Har bir o'zgarish testlar bilan qoplangan bo'lishi kerak.

### 9.1 Guruh va dars jadvali

**Guruh yaratish:**
- `Group.category` (`lang`/`it`) — legacy; `category_obj` FK (`education.Category`) — hozirgi.
- `course_template` tanlanganda narx/davomiylik default'lari to'ldiriladi.
- `kurs_narxi`, `oqituvchi_foiz`, `oy_dars_soni` — moliyaning asosi.
- `estimated_end_date` avtomatik hisoblanadi (`course_start_date` + `duration_months`, `lessons_per_week` bilan), lekin `estimated_end_date_manual=True` bo'lsa qo'lda kiritilgan sana saqlanadi.
- Izoh matni: *"Bu sana taxminiy hisob bo'lib, bayramlar, tadbirlar yoki dars ko'chirilishlari sabab o'zgarishi mumkin"*.

**Dars jadvali (`GroupSchedule`):**
- Weekday konvensiyasi: **isoweekday** (1=Dushanba … 7=Yakshanba). Butun kodda shu.
- `unique_together (group, weekday, start_time)`.
- Konflikt tekshiruvi: `education:schedule_conflict_check` — bir xona/bir o'qituvchi bir vaqtda ikki guruhda bo'lmasligi.
- Servis: `education/services/group_schedule_service.py`.

**Support o'qituvchi:**
- Markaz feature flag'i: `features["support_teacher_enabled"]` (default **False**).
- `Group.support_teacher` + `support_foiz` — davomatni asosiy o'qituvchi qiladi, lekin support'ga ham foiz yoziladi. Support har qanday xodim bo'lishi mumkin (teacher/manager/admin).
- Servis: `education/services/support_teacher.py`.

**Guruhni yopish/arxivlash:**
- `is_archived` — ro'yxatlardan yashiriladi.
- `is_closed` + `closed_at` + `closed_by` — kurs tugadi.
- To'liq oqim: `GroupClosureWorkflow` + `education/services/closure_service.py`.
- Tavsiyalar: `group_completion_recommendations` — kim sertifikat olishga tayyor, kim yo'q.

---

### 9.2 O'quvchini guruhga yozish va narxlash

**Narxlash turlari (`Enrollment.pricing_type`):**

| Tur | Ma'nosi | Qachon |
|---|---|---|
| `full` | To'liq oy narxi | O'quvchi oy boshidan qo'shilgan |
| `prorated` | Dars bo'yicha (proporsional) | O'quvchi oy o'rtasida qo'shilgan |
| `custom` | Admin qo'lda kiritgan | Maxsus kelishuv |

**Dars naqshi (`lesson_pattern`)** — jadval bo'lmagan holatda darslar sonini taxmin qilish uchun:

| Naqsh | Kunlar (isoweekday) |
|---|---|
| `group` | Avtomatik: `GroupSchedule` dan olinadi |
| `odd` (toq) | {1, 3, 5} = Du, Chor, Ju |
| `even` (juft) | {2, 4, 6} = Se, Pay, Shan |
| `daily` | {1..6} = Du–Shan |

`auto_lesson_pattern_for_date(start_date)` — boshlanish sanasidan naqshni taxmin qiladi.

**Yozilish sanasi aniqlanishi (`enrollment_start_date`)** — ustuvorlik:
1. `enrollment._tuition_start_date` (aniq berilgan)
2. `StudentGroupHistory.start_date` (eng oxirgi yozuv) — lekin agar `joined_at` ≠ `created_at.date()` bo'lsa `joined_at` ustun (admin qo'lda o'zgartirgan)
3. `joined_at`
4. `created_at.date()`

> **PERF:** natija `enrollment.__resolved_start_date__` da memoizatsiya qilinadi. Dashboard render'da bu funksiya minglab marta chaqiriladi — memoizatsiyasiz `StudentGroupHistory` ga minglab bir xil query ketadi. `preload_enrollment_history_starts(enrollments)` — bulk preload helper.

**Chegirma (`student_payable_amount`):**
- `None` → to'liq kurs narxi olinadi.
- `0` → bepul o'quvchi (to'lovlar bo'limida 0 so'm ko'rinishi uchun avtomatik 0-summa Payment yaratiladi).
- `clean()`: kurs narxidan **katta** bo'lishi mumkin emas.
- Test: `education/tests/test_student_payable_amount.py`.

---

### 9.3 Davomat

**4 status:**

| Status | Ma'nosi | O'qituvchiga pul | Chaqmoq jarimasi |
|---|---|---|---|
| `present` | Keldi | ✅ | — |
| `late` | Kech qoldi | ✅ | ixtiyoriy |
| `absent_excused` | Sababli kelmadi | ❌ | ❌ |
| `absent_unexcused` | Sababsiz kelmadi | ❌ (lekin o'quvchidan pul olinadi) | ✅ |

**Legacy maydonlar** (hali kodda ishlatiladi):
- `present` (bool) — eski "kelgan" bayrog'i.
- `forced` — "kelmadi, lekin o'qituvchiga pul yozilsin". Chaqmoq jarimasida `absent_unexcused` bilan **teng** ko'riladi.

**Billable attendance** (`_billable_attendance_q()`): o'quvchidan pul olinadigan darslar = `present` yoki `absent_unexcused` (kelmasa ham to'lov qiladi) — `education/services/tuition.py`.

**Davomat qilish yo'llari:**
- Web: `/talim/guruh/<pk>/davomat/` (group_rollcall), `/talim/guruh/<pk>/attendance_today/`
- Bulk: `/talim/guruh/<g_id>/attend-all/` (hammaga "keldi")
- Oylik jadval: `/talim/attendance/groups/<group_id>/` + `attendance_toggle_cell` (bir katakni bosib o'zgartirish)
- Majburlash: `/talim/attendance/force/`
- Mobil: `POST /api/mobile/teacher/attendance/mark/`
- Eksport: `group_month_attendance_export` (Excel)

**Davomat nazorati (`education/services/attendance_monitor.py`):**

Manager/Director dashboardida "o'qituvchi davomat qilmagan guruhlar" ro'yxati.

Dars kuni qanday aniqlanadi:
1. `GroupSchedule` bo'lsa → aniq `weekday` + `start_time` (eng ishonchli).
2. Yo'q bo'lsa → enrollment naqshidan (`odd`/`even`/`daily`).
3. Naqsh `group` (Avtomatik) + jadval yo'q → dars kuni aniqlanmaydi → **"jadval belgilanmagan"** ro'yxatiga tushadi (manager jadval sozlashi kerak).

Konstantalar: `GRACE_MINUTES = 60` (dars boshlangandan keyin 60 daqiqa o'tsa "qilinmadi"), `DEFAULT_CUTOFF = 21:00` (jadvalsiz guruhlar uchun).
Statuslar: `taken` / `missing` / `pending`.

> **Holat:** web tomoni tayyor, Flutter tomoni hali qilinmagan.

---

### 9.4 To'lov va oylik hisob (TuitionMonth / PaymentAllocation)

Bu platformaning **eng nozik** mexanizmi. Yurak fayl: `education/services/tuition.py` (2364 qator).

#### 9.4.1 Konseptual model

```
Enrollment (o'quvchi + guruh)
   │
   ├── TuitionMonth (2026-01-01, fee=550 000)   ← bir oylik hisob-faktura
   │      ├── PaymentAllocation (payment#12, 400 000)
   │      └── PaymentAllocation (payment#19, 150 000)   → to'liq to'landi
   │
   ├── TuitionMonth (2026-02-01, fee=550 000)
   │      └── PaymentAllocation (payment#19,  50 000)   → qarz 500 000
   │
   └── credit_balance = 0
```

Qarz formulasi **bitta**: `debt = max(0, fee - paid)` har `(enrollment, month)` uchun, keyin yig'iladi.

#### 9.4.2 Prorated fee (`prorated_monthly_fee`)

**Muammo:** o'quvchi 18-sanada qo'shilsa ham `fee_amount` to'liq oylik narxga qo'yilardi → qarzdorlarda **yolg'on qarz** (masalan 550k − 4 dars × 45.8k = 367k sun'iy qarz).

**Yechim (3 bosqich):**
1. `prorated_monthly_fee()` — enrollment yaratilganda birinchi oy uchun `expected_lessons` (GroupSchedule dan) × per_lesson.
2. `reconcile_tuition_month()` — oy oxirida **haqiqiy davomatga** qarab (`present` + `absent_unexcused`) `fee_amount` qayta yoziladi:
   `fee = min(billable_lessons × per_lesson, effective_student_payable_amount)`
3. Ikkalasi ham `effective_student_payable_amount` (chegirmali narx) dan hisoblanadi.

> ⚠️ **O'qituvchi maoshi bu yerda O'ZGARTIRILMAYDI.** U alohida `HistoricalFinanceService` orqali **asl `kurs_narhi`** dan hisoblanadi. Bu ataylab: o'quvchining chegirmasi o'qituvchi maoshini kamaytirmasligi kerak.

Xavfsizlik: `reconcile` fee'ni **pastga tushirmaydi** agar oy allaqachon to'langan bo'lsa (ma'lumot yo'qolmasligi uchun).

#### 9.4.3 `ensure_tuition_month()` — himoyalangan oylar

Oy yozuvini yaratadi yoki fee'ni yangilaydi. **Himoyalangan** (`deleted_reason`) oylarga tegmaydi:

| `deleted_reason` prefiksi | Ma'nosi |
|---|---|
| `manual_cleared` | Foydalanuvchi ataylab o'chirgan |
| `cleanup_*` | Reset skriptlari tozalagan |
| `move_future_*` | Credit balance operatsiyasi |
| `reset_*` | Boshqa reset skriptlari |
| `user_edit*` | Foydalanuvchi tahriri |

Himoyalangan oy: `restore()` qilinmaydi, fee qayta yozilmaydi.

Boshqa qoidalar:
- **Yopilgan oy** (`FinancialMonth.is_closed`) → fee o'zgartirilmaydi.
- `auto_fee_raise_blocked_for_past_month(month, cur_fee, new_fee)` — o'tgan oyning fee'sini avtomatik **oshirish** bloklanadi (buxgalteriyani buzmaslik uchun).
- **Credit auto-apply:** yangi TuitionMonth yaratilganda `enrollment.credit_balance` bo'lsa, `min(fee, credit)` avtomatik allocation qilinadi va credit kamaytiriladi.
- **Bepul o'quvchi** (`student_payable_amount == 0`, fee=0) → 0 so'mlik Payment yaratiladi (UI'da ko'rinishi uchun).
- **Auto-link:** to'lov bor lekin allocation yo'q bo'lsa avtomatik bog'lanadi (`_auto_link_payment_to_tm`) — aks holda qarzdorlarda yolg'on qarz chiqadi.

#### 9.4.4 To'lovni taqsimlash algoritmi (`_allocate_amount_forward`)

**FIFO forward** (eng eski qarzdan boshlab oldinga):

```
1. start_month dan boshlanadi (default: eng erta to'lanmagan oy).
2. Har oyga min(qolgan_summa, owed = fee - paid) yoziladi.
   • YOPILGAN oyga allocation YOZILMAYDI (buxgalter oyni mahkamlagan).
   • fee <= 0 bo'lgan oy o'tkazib yuboriladi.
3. Mavjud oylar tugagach pul qolsa → kelgusi oylar uchun TuitionMonth
   avtomatik yaratiladi (max 12 oy oldinga: _FUTURE_OVERFLOW_MONTH_LIMIT).
4. 12 oydan keyin ham pul qolsa → Enrollment.credit_balance ga yoziladi.
   Keyingi oy ensure_tuition_month chaqirilganda avtomatik ayiriladi.
```

**Stsenariylar (kodda hujjatlangan):**
- Aprel 40k qarz + May 250k qarz, 290k to'lov → ikkalasi yopiladi, qarzdorlar safidan chiqadi.
- May 250k qarz, 500k to'lov → May yopiladi, Iyun uchun TuitionMonth yaratilib 250k unga yoziladi.

Asosiy funksiyalar:
- `create_payment_and_allocate(enrollment, cash_amount, card_amount_som, start_month, created_by)`
- `update_payment_and_reallocate(...)` — to'lovni tahrirlash
- `reallocate_enrollment(enrollment)` — hammasini qayta taqsimlash (tuzatish uchun)
- `auto_net_student_credits(student)` — o'quvchi bo'ylab credit'larni netlash
- `find_earliest_unpaid_month(enrollment)` — qaysi oydan boshlash
- `sync_tuition_fee(enrollment, start_month, new_fee)` — narx o'zgarganda kelgusi oylarni yangilash

#### 9.4.5 Qarzdorlik hisoblash (`calculate_enrollment_debt_snapshots`) ⭐

**Read-only** (DB'ga yozmaydi) snapshot. Signatura:

```python
calculate_enrollment_debt_snapshots(
    enrollments, months, *,
    virtual_missing_months=None,   # virtual fee faqat shu oylarga
    cumulative_up_to=None,         # kumulativ qarz shu oygacha
    synthesize_past_virtual=True,  # o'tgan oyga virtual qarz yozilsinmi
) -> dict[enrollment_id, {total_fee, total_paid, debt, lesson_count, months: {...}}]
```

**Fee aniqlanish tartibi (har `(enrollment, month)` uchun):**

```
1. TuitionMonth mavjud (is_deleted=False)?
     → saqlangan fee ishlatiladi.
     → LEKIN: fee==0 va month > joriy_oy va paid==0 bo'lsa
       → prorated_monthly_fee bilan qayta hisoblanadi
         (noto'g'ri tahrirlash natijasini tuzatish).

2. TuitionMonth O'CHIRILGAN (is_deleted=True)?
     → fee = 0, virtual hisoblash YO'Q, paid ham 0.
       (Foydalanuvchi ataylab o'chirgan — qarz tiklanmasligi kerak.)

3. TuitionMonth YO'Q va synthesize_past_virtual=False va month < joriy_oy?
     → fee = 0.
       ⭐ FOYDALANUVCHI QOIDASI: o'tgan oyga TuitionMonth yozuvi bo'lmasa,
         avtomatik (virtual) qarz YOZILMAYDI. Qarz faqat haqiqiy yozuv
         (davomat/to'lov orqali) bo'lsagina hisoblanadi.

4. TuitionMonth YO'Q va (virtual_missing_months=None yoki month ∈ to'plam)?
     → fee = prorated_monthly_fee(enrollment, month)  — faqat xotirada.

5. Aks holda fee = 0.
```

`paid` — `PaymentAllocation` yig'indisi (`tuition_month__is_deleted=False`, `payment__is_deleted=False`).
`debt = max(0, fee - paid)`.

**Kumulativ qarz** (`cumulative_up_to` berilganda): enrollment boshlanishidan shu oygacha barcha oylar bo'ylab qarz yig'iladi (`TuitionMonth.all_objects` bilan, o'chirilgan oylar fee=0).

**⭐ CHIQARILGAN O'QUVCHI QOIDASI (juda muhim):**

`enrollment_is_removed(enrollment)` — ikki xil chiqarish yo'li bor va **ikkalasi teng ko'riladi**:
1. `EnrollmentService.remove_student` → `is_active=False` (+ `last_lesson_date` qo'yiladi)
2. `enr.delete()` (soft-delete, "guruhdan o'chirish") → `is_deleted=True` (`is_active` True qolishi mumkin, `last_lesson_date` qo'yilmaydi)

`enrollment_last_billable_date(enrollment)` — chiqarilgan o'quvchi uchun hisobga kiradigan **oxirgi sana**:
1. `enrollment.last_lesson_date`
2. bo'lmasa: `StudentGroupHistory.end_date` (eng oxirgi yopilgan yozuv)
3. Faol o'quvchi uchun `None` (cheklov yo'q)

> **Qoida:** chiqarilgan o'quvchi faqat `last_lesson_date` gacha hisoblanadi. Undan keyingi darslar/davomat **qarzga qo'shilmasligi kerak**. Bu joy tarixiy bug hotspot — testlar: `test_removed_student_post_removal_debt.py`, `test_removed_students_visibility.py`, `education/services/removed_debt_repair.py`.

Natija memoizatsiya qilinadi (`__resolved_last_billable_date__`) — N+1 oldini olish.

#### 9.4.6 Boshqa muhim tuition funksiyalari

| Funksiya | Vazifasi |
|---|---|
| `tuition_month_preview(enrollment, month)` | UI uchun preview: fee, paid, debt, darslar |
| `enrollment_month_financial_snapshot(enrollment, month)` | Bir oy uchun to'liq moliyaviy kesim |
| `center_month_debt_summary(center, months, branch=None)` | Markaz bo'ylab oylik qarz yig'indisi |
| `is_month_closed_for_center(center, month)` | `FinancialMonth.is_closed` tekshiruvi |
| `get_effective_month_fee(enrollment, month)` | Amaldagi oylik fee |
| `billable_attendance_count(enrollment, month)` | Pul olinadigan darslar soni |
| `expected_lessons_in_period(enrollment, start, end)` | Kutilayotgan darslar (jadval yoki naqsh) |
| `scheduled_lessons_between(group, start, end)` | Jadval bo'yicha darslar |
| `round_money_to_thousand(amount)` | Ming so'mga yumaloqlash |
| `format_money(amount, compact=False)` | UI uchun formatlash |
| `preload_group_schedules(group_ids)` | ⭐ N+1 oldini oluvchi bulk preload |
| `clear_group_schedule_cache()` | Test/uzoq process uchun |

**Qo'lda qarz operatsiyalari (UI'dan):**
- `edit_tuition_month_fee` — bir oyning fee'sini tahrirlash
- `edit_student_month_debt` — barcha guruhlar uchun oylik umumiy qarzni o'rnatish
- `add_student_manual_debt` — qo'lda qarz yozish (qarzdorlarga qo'shish)
- `delete_student_month` — kelajak oylik yozuvni o'chirish
- `reset_student_month_payments` — oylik to'lovlarni bekor qilish (oy to'liq qarzga qaytadi)
- `student_monthly_breakdown` — oylik breakdown AJAX

---

### 9.5 O'qituvchi maoshi (`HistoricalFinanceService`)

**Formula (`teacher_monthly_financials`):**

```
per_lesson       = (kurs_narxi × oqituvchi_foiz%) / oy_dars_soni
teacher_salary   = round_div(teacher_salary_cap × billable_lessons, monthly_lessons)
turnover         = min(proportional(full_amount, billable, monthly), full_amount)
center_profit    = turnover - teacher_salary
```

Misol (`kurs_narxi=250 000`, `foiz=50%`, `oy_dars_soni=12`):

| Darslar | O'qituvchi | Izoh |
|---|---|---|
| 12 | 125 000 | Standart |
| 13 | 135 417 | Ortiqcha dars uchun qo'shimcha |
| 14 | 145 834 | — |

> **Muhim:** o'qituvchi ortiqcha dars uchun qo'shimcha oladi, lekin **o'quvchi to'lovi (turnover) kurs narxidan oshmaydi** (`turnover_cap`).

**Guruh standarti aniqlanishi (`_build_dynamic_teacher_salary`):**
```
_oy_ds = group.oy_dars_soni
if _oy_ds >= 4:  group_standard = _oy_ds
else:            group_standard = scheduled_lessons_between(...) or _oy_ds or 12
```
Bu "haftada 2 kun" kabi noto'g'ri `oy_dars_soni=2` holatini tuzatadi.

**Cheklov:** `capped_lessons = min(len(days), group_standard)` — 13-dars **to'lanmaydi** deb hisoblanadi bu joyda (yuqoridagi formula bilan ziddiyat emas: `capped` cheklash guruh standarti bo'yicha).

**A'zolik tekshiruvi:** `_student_was_in_group(history_lookup, gid, sid, month_start, month_end)` — `StudentGroupHistory` orqali o'quvchi o'sha oyda guruhda bo'lganini tekshiradi. `None` (tarix yo'q) bo'lsa `enrollment.created_at` bilan tekshiriladi.

**Bir o'quvchi bir guruhda ikki enrollment** bo'lishi mumkin (o'chirilgan + faol) → **faol ustuvor**.

**Maosh turlari (`TeacherCompensationRule`):** `PERCENT` (default), `FIXED`, `PER_STUDENT`, `PER_LESSON` + `effective_from`.

**Kutilayotgan daromad:** `education/services/expected_income_service.py` → `calculate_expected_income()`, API: `/talim/api/finance/teacher-expected-income/`.

**Oy yopish (`close_month`):**
```bash
python manage.py close_month 2026-04 --center 3 [--dry-run]
```
1. Faol enrollment'lar `reconcile_tuition_month` qilinadi.
2. Har o'qituvchi uchun `TeacherSalarySnapshot` yaratiladi (`details` JSON: guruh/o'quvchi breakdown).
3. `MonthlyFinanceSnapshot` yaratiladi (`total_income`, `total_expense`, `center_profit`, `student_count`, `attendance_rate`).
4. `FinancialMonth.is_closed = True`.

Teskari: `HistoricalFinanceService.open_month(center, year, month, user)`.
Web: `/talim/finance/close-month/`, preview: `/talim/finance/month-preview/`.

---

### 9.6 Chaqmoq tizimi (gamifikatsiya)

**Chaqmoq** = markaz ichidagi ball/valyuta. O'quvchi uni do'kondan mahsulot sotib olish uchun ishlatadi.

#### 9.6.1 Qo'lda berish

- `/chaqmoq/berish/` — o'qituvchi/manager guruh tanlaydi, o'quvchilarni belgilaydi, qoidani tanlaydi, ball kiritadi.
- Qoida `min_baho`..`max_baho` diapazonini cheklaydi.
- Rol ruxsati: `Rule.can_director` / `can_manager` / `can_teacher`.
- Kunlik limit: `Center.max_daily_lightning` (0=cheksiz), `Center.max_daily_deduction`, hamda `DailyLightningSetting` (sana bo'yicha).
- Har berish → `Ledger` yozuvi + `Notification`.

#### 9.6.2 Avtomatik qoidalar (`chaqmoq/services.py`)

**1. Davomat jarimasi (`attendance_penalty`)**
```
Agar joriy OY ichida sababsiz qoldirish (absent_unexcused yoki forced)
soni >= rule.absence_limit (default 3):
   → Ledger'ga rule.lightning_penalty (default -5) yoziladi
   → Bildirishnoma yuboriladi
   → Bir oyda BIR MARTA (related_month bo'yicha dublikat himoyasi)
```

**2. Davomat bonusi (`attendance_bonus`)**
```
Agar joriy oyda kelgan darslar soni >= rule.presence_limit (default 12):
   → rule.lightning_bonus (default +10)
```

**3. To'lov bonusi (`payment_bonus`)**
```
Payment.save() da chaqiriladi. 100% to'lov bo'lsa
   → rule.payment_bonus_lightning (default +5)
```

**4. To'lov intizomi (`payment_discipline`)**
```
PaymentAllocation.save() da chaqiriladi.
Agar to'lov rule.discipline_deadline_day (default 10) gacha bo'lsa
   → +rule.discipline_bonus_score (default +5)
Deadline'gacha to'lamaganlar
   → rule.discipline_penalty_score (default -10)
     (apply_payment_discipline_penalties(center) — cron/management orqali)
Faqat rule.discipline_active=True bo'lsa ishlaydi.
```

**Qoidalar `center=None` bo'lsa — global** (barcha markazlarga). `Q(center=center) | Q(center__isnull=True)` naqshi.

**Cron:** `python manage.py process_lightning_rules`, `python manage.py apply_monthly_rules`, `run_monthly_attendance_bonus`.

#### 9.6.3 Reyting

- `/chaqmoq/reyting/` — markaz bo'ylab o'quvchilar reytingi (chaqmoq balansi bo'yicha).
- Guruh ichidagi reyting: `GroupInternalRankingSnapshot` (6 komponent: davomat, faollik, imtihon, uyga vazifa, intizom, chaqmoq bonusi) → `total_internal_score` + `explanation_text` (nega shu o'rin).
- Servis: `education/services/ranking_service.py`.

#### 9.6.4 Ball → Chaqmoq konvertatsiyasi (web mini-o'yinlar)

- O'quvchi web mini-o'yinlarda **ball** yig'adi (`StudentBallsWallet`).
- `GameBallsConfig`: `min_balls_to_convert`, `chaqmoq_per_conversion`.
- API: `POST /api/student/game/convert-balls/` → `GameBallsConversionLog`.

---

### 9.7 Imtihon moduli

**Oqim:**
```
1. Markazda imtihon tizimi yoqiladi (CenterExamSetting.exam_system_enabled).
2. exam_every_n_lessons (default 12) darsdan keyin tizim o'qituvchiga
   eslatma yuboradi (dashboard + Telegram):
   "Guruh 12 ta darsni tugatdi. Imtihon o'tkazasizmi?"
     → ExamReminderLog (yes / no / later / telegram)
3. "Ha" → ExamSession yaratiladi (draft).
4. O'qituvchi natijalarni kiritadi → ExamResult (ball, foiz).
   passing_score_percent (60%) dan past → "o'tmadi".
5. Fayl yuklash: ExamResultFile, ExamSessionTaskFile
   (exam_file_upload_enabled bilan boshqariladi).
6. ExamSession status = completed.
7. Past natijali o'quvchilar: failed_student_threshold (3) dan ko'p
   marta o'tmasa → "failed students" ro'yxatiga tushadi
   → follow_up_status (pending → parent_contacted → reviewed).
8. StudentAcademicSummary qayta hisoblanadi.
```

**Sahifalar:** `/talim/exam/` (hub), `/exam/list/`, `/exam/create/`, `/exam/sessions/<id>/`, `/exam/questions/`, `/exam/settings/`, `/exam/annual/`, `/exam/teacher-history/`, `/exam/failed-students/`, `/exam/groups/<id>/history/`, `/exam/groups/<id>/internal-ranking/`.

**Servis:** `education/services/exam_service.py` (1077 qator).
**Cron:** `python manage.py notify_exam_reminders`.
**Feature gate:** tarif tier PRO (`exams`) + markaz flag `ui_exam_sessions`.
**Testlar:** `test_phase2_exam_workflow.py`, `test_exam_telegram_reminder.py`, `test_exam_certificate_module.py`.

---

### 9.8 Sertifikat moduli

```
1. CertificateTemplate yuklanadi (markaz o'z dizaynini beradi), is_active.
2. Guruh tugagach nomzodlar aniqlanadi:
     attendance_percent >= minimum_certificate_attendance_percent (70%)
     average_percent    >= minimum_certificate_average_percent (60%)
   → group_certificate_candidates
3. CertificateRecord yaratiladi (status=draft):
     certificate_number (unique), verification_token (UUID)
4. Tasdiqlash (approved_by) → berish (issued_by)
5. PDF generatsiya (ReportLab) → pdf_file
6. Ommaviy tekshiruv: /talim/certificates/verify/<certificate_number>/
   → har tekshiruv CertificateVerificationLog ga yoziladi (IP, user agent)
```

**Servis:** `education/services/certificate_service.py` (1089 qator).
**Qayta generatsiya:** `python manage.py regenerate_certificate_pdfs`.
**Feature gate:** PRO tier (`certificates`) + `ui_certificates`.

---

### 9.9 Lead CRM

**Pipeline:** `new` → `contacted` → `trial` → `confirmed` → `converted` (yoki `canceled`).
`LeadStatus` modeli orqali markaz o'z bosqichlarini sozlashi mumkin (`order`, `is_active`).

**Oqim:**
```
1. Lead qo'lda kiritiladi yoki marketing saytdan (DemoLead) keladi.
2. assigned_manager belgilanadi, next_follow_up_date qo'yiladi.
   → /do'kon/leads/followups/today/ — bugun qo'ng'iroq qilinadigan lead'lar
3. Har muloqot → LeadActivity.
4. Sinov darsi: TrialLesson (sana, guruh, natija) → TrialLessonActivity.
5. LeadGroup — guruh yig'ish: bir nechta lead bir "to'plam"ga yig'iladi.
   min_students to'lganda → lead_group_convert_api → real Group yaratiladi.
   Teskari: lead_group_revert_api.
6. Lead → O'quvchi: lead_api_convert / lead_convert
     • User yaratiladi (role=student, avtomatik email/parol)
     • Enrollment yaratiladi
     • Lead: converted_to_student=True, converted_user, converted_at, converted_by
```

**Fayllar:** `store/crm_views.py` (1733), `store/lead_services.py`, `store/trial_services.py`.
**Sozlamalar:** `/do'kon/leads/settings/` — `Manba`, `Yonalish`, `LeadStatus` CRUD.
**Feature gate:** PRO tier (`leads`).

---

### 9.10 Do'kon (ichki magazin)

```
1. Manager mahsulot qo'shadi: nom, narx_chaqmoq, narx_som, rasmlar,
   allowed_categories (qaysi bo'lim o'quvchilari ko'rishi mumkin).
2. O'quvchi ko'radi → PurchaseRequest yaratadi (qty).
3. Manager tasdiqlaydi:
     • O'quvchi chaqmog'i yetarlimi tekshiriladi
     • Ledger'dan chaqmoq ayiriladi
     • Sale yozuvi yaratiladi, Product.sotilgan_soni oshadi
     • Bildirishnoma yuboriladi
   yoki rad etadi (izoh bilan).
4. Izohlar: Comment (thread — parent bilan javob).
```

**Feature gate:** PRO tier (`store`).

---

### 9.11 Xarajatlar va moliya bo'limi

- `Expense` — markaz xarajati: summa, izoh, sana, `category` (`ExpenseCategory`), `payment_method`, `receiver`, `worker`, `product`.
- `CenterExpense` — alohida (education app'da) kategoriyalangan xarajat.
- `PaymentMethod` CRUD — markaz o'z to'lov usullarini boshqaradi (`/do'kon/payment-methods/`).
- Eksport: `expenses_export_xlsx`, `payment_export_xlsx`.
- PDF: `payment_receipt_pdf` (to'lov cheki), `student_payments_pdf` (o'quvchi to'lovlari xulosasi).

---

### 9.12 HR moduli (Xodimlar)

`/talim/hr/` — reference uslubdagi overview: KPI kartalari, ApexCharts diagrammalar, panellar, heatmap.

- Ma'lumot **client-side** yuklanadi: `GET /api/hr/employees/`, `/api/hr/employees/<id>/`, `/api/hr/teachers/available/`.
- Modellar: `StaffProfile` (rol, lavozim, ishga kirgan sana, fanlar, darajalar), `TeacherAvailability` (bo'sh/band slotlar).
- Servis: `education/services/hr.py` (771 qator), view: `education/hr_views.py` (659).
- Til: to'liq o'zbekcha.
- Feature gate: STANDARD tier (`hr`).
- Test: `education/tests/test_hr_module.py`.

---

### 9.13 Churn (ketib qolish xavfi) va analitika

**`core/churn_service.py` + `core/services/ai_insights.py`:**
```
Har o'quvchi uchun skor hisoblanadi:
  • davomat pasayishi (oxirgi 2-4 hafta trend)
  • qarz miqdori (debt_amount)
  • imtihon natijalari tushishi
  • chaqmoq faolligining pasayishi
→ ChurnRisk (skor, holat: yashil/sariq/qizil)
→ Dashboard: /dashboard/students/dangerous/, /dashboard/students/low-activity/
→ "Xabar yuborish" tugmasi: /dashboard/students/churn-notify/<pk>/
→ API: /api/churn/summary/
```

**Kunlik metrikalar:** `CenterDailyMetric`, `TeacherDailyMetric`, `StudentDailyMetric` — trend grafiklar uchun.

**Prognoz:** `_forecast_bundle()` — WMA (weighted moving average) bilan keyingi 3 oy daromadi.

---

### 9.14 Guruh chat

- `GroupChat` (guruhga OneToOne) → `ChatMessage` (`body`, `reply_to`) → `ChatAttachment` (fayl/rasm/link).
- `ChatPresence` — `last_seen`, `typing_until` ("yozmoqda" indikatori).
- `ChatMessageRead` — o'qilgan belgisi.
- API: `/api/chat/<group_id>/messages/`, `/send/`, `/typing/` — **polling** (WebSocket yo'q, chunki Render'da bitta process).
- Kirish: student, teacher, manager, director (parent **yo'q**).

---

### 9.15 O'quvchi holati va transfer

**Holat (`education/services/student_status.py`, 744 qator):**
`/talim/student/<id>/holat/` — o'quvchining to'liq kesimi: davomat trendi, to'lov intizomi, imtihonlar, chaqmoq, xavf darajasi.

**Transfer (`education/services/student_transfer.py`, 414 qator):**
```
/talim/kiritish/<enrollment_id>/transfer/
1. Eski guruhdagi to'lov holati snapshot qilinadi (old_payment_state JSON)
2. Davomat xulosasi snapshot (old_attendance_summary JSON)
3. StudentGroupHistory yopiladi (end_date)
4. Yangi guruhda Enrollment + StudentGroupHistory ochiladi
5. StudentGroupTransfer yozuvi (PROTECT — guruhlar o'chirilmaydi)
6. Kreditlar/qarzlar yangi guruhga ko'chiriladi (qoidaga muvofiq)
```
Testlar: `test_student_group_transfer.py`, `test_group_transfer_verification.py`.

**Guruhdan chiqarish:**
- `/talim/kiritish/<pk>/olib-tashlash/` — `enrollment_remove`
- `/talim/kiritish/<pk>/chiqish/` — `enrollment_leave` (`last_lesson_date` bilan)
- `/talim/kiritish/<pk>/kechiktir/` — `enrollment_toggle_deferred`
- `/talim/groups/<pk>/bulk_remove/` — ko'p o'quvchini birdan

**O'quvchi arxivi:** `archive_student`, `restore_student`, `hard_delete_student`.

---

## 10. BILLING VA SAAS OBUNA TIZIMI

### 10.1 Tarif darajalari (tier)

`billing/plan_tiers.py`:

```python
TIER_FREE = 1;  TIER_STANDARD = 10;  TIER_PRO = 20;  TIER_PREMIUM = 30
```

**Feature gate matritsasi (`SIDEBAR_FEATURE_GATES`):**

| Feature kodi | Tier | Sidebar yorlig'i |
|---|---|---|
| `dashboard` | FREE | Boshqaruv paneli |
| `students` | FREE | O'quvchilar |
| `groups` | FREE | Guruhlar |
| `hr` | STANDARD | Xodimlar |
| `attendance` | STANDARD | Davomat |
| `payments` | STANDARD | To'lovlar |
| `chaqmoq` | STANDARD | Chaqmoq tizimi |
| `debtors` | STANDARD | Qarzdorlar |
| `notifications` | STANDARD | Xabar yuborish |
| `leads` | PRO | Leadlar (CRM) |
| `analytics` | PRO | Hisobot va Analitika |
| `store` | PRO | Do'kon |
| `exams` | PRO | Imtihon Sessiyalar |
| `certificates` | PRO | Sertifikatlar |
| `schedule` | PRO | Haftalik Jadval |
| `kpi` | PRO | KPI va Hisobotlar |
| `sms` | PREMIUM | SMS Xabarnoma |
| `branches` | PREMIUM | Filiallar |
| `ai` | PREMIUM | AI Yordamchi |

**Landing narxlari (`PLAN_UPGRADE_INFO`):** STANDARD 199 000 / PRO 399 000 / PREMIUM 699 000 so'm oyiga.

Funksiyalar: `get_plan_tier_from_code()`, `get_plan_tier_from_subscription()`, `is_feature_locked(code, tier)`, `get_required_tier(code)`.

### 10.2 Feature tekshiruvining 4 qatlami

```
1. PlanFeature.type == CORE           → hech qachon qulflanmaydi
2. CenterFeatureOverride              → superadmin qo'lda yoqdi/o'chirdi (ENG USTUN)
3. PlanFeatureRule (tarif ↔ feature)  → enabled + limit_value
4. SubscriptionPlan.plan_features M2M → legacy (backward-compat)
```

Asosiy API (`billing/services.py`):
- `center_has_feature(center, slug) -> bool`
- `get_center_feature_limit(center, slug)` — `None` = cheksiz
- `get_center_quota_usage(center, slug)` / `consume_center_quota(center, slug, n)`
- `get_feature_flags(center) -> set[str]`
- `apply_plan_to_center(center, plan)` — tarif o'zgarganda limitlar/flag'lar ko'chiriladi

Dekoratorlar (`billing/decorators.py`):
- `@require_feature("leads")` — feature yo'q bo'lsa: HTML → xabar + redirect, API → `403 {"ok": false, "error": "...", "feature": "...", "upgrade_url": "/billing/plans/"}`
- `@require_active_subscription` — bloklangan bo'lsa `billing:blocked`
- Superuser har doim o'tadi.

Cache: `_chf_cache()` — **request-scoped** cache; `clear_feature_request_cache()` chaqirilishi kerak.

### 10.3 Obuna hayot tsikli

```
TRIAL (default_trial_expires) → ACTIVE → (expires_at o'tdi) → GRACE PERIOD
    → (BILLING_GRACE_PERIOD_HOURS=72 soat o'tdi) → BLOCKED
    ↕ PAUSED (paused_at + remaining_seconds saqlanadi)
```

`CenterSubscription` metodlari:
- `is_expired()` — `expires_at < now`
- `hard_expires_at` — `expires_at + GRACE_PERIOD_HOURS`
- `is_hard_expired()` — grace ham tugadi
- `in_grace_period()` — muddat tugagan, lekin grace ichida
- `is_blocked()` — `manual_block` yoki hard expired
- `is_over_student_limit()` — o'quvchi soni tarif limitidan oshgan
- `days_left`

**Sozlamalar:**
| Setting | Default |
|---|---|
| `BILLING_GRACE_PERIOD_HOURS` | 72 |
| `BILLING_EXPIRY_WARN_DAYS` | 7 |
| `SUBSCRIPTION_CHECK_INTERVAL_SECONDS` | 120 |
| `SUBSCRIPTION_BLOCK_CACHE_TTL` | 15 |

**`is_grandfathered`** — eski mijozlar yangi limitlardan ozod.

**Cron:** `python manage.py expire_subscriptions`.
**UI:** `billing/templatetags` + `templates/partials/plan_preview_bar.html`, `upgrade_modal.html`, `dashboard_upgrade_block.html`, `components/grace_period_modal.html`.

> ⚠️ `billing/middleware.SubscriptionMiddleware` mavjud, lekin `settings.MIDDLEWARE` da **YO'Q**. Bloklash `TenantMiddleware` ichida (`_is_center_blocked`) amalga oshiriladi. RBAC hujjatida middleware ro'yxati eskirgan.

### 10.4 Click to'lov integratsiyasi

**Ikki mustaqil oqim:**

| Oqim | URL'lar | Nima uchun |
|---|---|---|
| Markaz obunasi | `/click/prepare/`, `/click/complete/`, `/click/webhook/` | `billing/click_views.py` |
| O'yin tariflari | `/click/game/prepare/`, `/click/game/complete/` | `game/payments.py` — **ataylab alohida**, chunki mavjud to'lov oqimi tirik pul bilan ishlaydi va unga tegmaslik xavfsizroq |

**Oqim:**
```
1. Direktor tarif tanlaydi → POST /hisob/billing/order/click-create/
     → SubscriptionRequest + merchant_trans_id
     → Click to'lov URL'iga redirect
2. Click → POST /click/prepare/
     • imzo tekshiruvi (MD5): xato → ClickError.SIGN_CHECK_FAILED
     • service_id / merchant_id validatsiya
     • summa mosligi
     → {click_trans_id, merchant_trans_id, merchant_prepare_id, error: 0}
3. Click → POST /click/complete/
     • imzo qayta tekshiriladi
     • activate_center_subscription_from_click():
         - CenterSubscription yaratiladi/uzaytiriladi
         - apply_plan_to_center() → limitlar ko'chiriladi
         - PaymentTransaction status=PAID
         - invalidate_center_tree_cache()
         - Telegram bildirishnoma (billing/telegram_notifications.py)
4. Brauzer → /payment/success/ yoki /payment/cancel/
5. Frontend poll: GET /hisob/billing/api/payment-status/
```

**Sozlamalar:** `CLICK_SERVICE_ID`, `CLICK_MERCHANT_ID`, `CLICK_SECRET_KEY`, `CLICK_RETURN_URL`.
Click Merchant panelida aynan shu URL'lar bo'lishi kerak:
`https://chaqmoqapp.uz/click/prepare/` va `https://chaqmoqapp.uz/click/complete/`.

**Demo markaz** uchun to'lov bypass: `order_confirm_demo` / `order_reject_demo` (superadmin).

**Naqd to'lov:** `SubscriptionRequest` → superadmin `subscription_request_approve` / `_reject`.

**Narx hisoblash:** `calculate_price(plan, months, promo_code, center)` → `PricingResult`. Davriy narxlar `price_3m/6m/9m/12m` yoki `monthly_price × months`. Promo: `validate_promocode()` (`once_per_center`, `max_uses`, sana oynasi, `plans` M2M).

**Upgrade preview:** `calculate_upgrade_preview()` + `calculate_plan_switch_days()` — tarifni o'zgartirganda qolgan kunlar qayta hisoblanadi (`/hisob/billing/api/upgrade-preview/`).

---

## 11. SUPERADMIN PLATFORM PANELI (`/platform/`)

| URL | Vazifasi |
|---|---|
| `/platform/` | Dashboard: markazlar, MRR, o'quvchi soni, mobil ilova qamrovi |
| `/platform/centers/` | Markaz tanlash (center picker) |
| `/platform/center-switch/` | Markazga "kirish" (impersonation emas — active_center o'zgaradi) |
| `/platform/center/create/`, `/center/<pk>/edit/` | Markaz CRUD (direktor login/parol ham shu formada) |
| `/platform/centers/<pk>/manage/`, `/stats/` | Markazni boshqarish, statistika |
| `/platform/center/<pk>/update-capacity/` | O'quvchi limitini o'zgartirish |
| `/platform/center/<pk>/toggle-feature/` | UI feature flag'ni yoq/o'chir |
| `/platform/center/<pk>/toggle-bot/` | Telegram botni yoq/o'chir |
| `/platform/bot/` | Bot paneli: per-center ruxsat + foydalanish statistikasi |
| `/platform/plans/matritsa/` | ⭐ **Tarif × feature matritsasi** (data-driven, `PlanFeatureRule`) |
| `/platform/plans/`, `/promos/` | Tarif va promo HTML sahifalari |
| `/platform/filiallar/`, `/filiallar/<id>/amal/` | Filial so'rovlari |
| `/platform/game/` | Chaqmoq Game boshqaruvi: do'kon CRUD, to'lov so'rovlari, o'yinchi qidirish/grant |
| `/platform/marketing/` | Marketing CMS (namespace: `marketing`) |
| `/platform/api/centers/*` | Markaz JSON API (create/list/detail/update/delete/archive) |
| `/platform/api/plans/*` | Tarif API: list, features, create, update, delete, feature-rule, feature/create, set-popular, price |
| `/platform/api/promos/*` | Promo CRUD API |
| `/platform/api/finance/payments/` | To'lov tarixi (SaaS analitika) |

**Mobil ilova qamrovi** (`core/services/app_adoption.py`): har markazda nechta o'quvchi ilovadan foydalanayotgani. Manba — `MobileAccessToken` (yangi migratsiya kerak emas). "O'rnatgan" = kamida bir marta login qilgan; "Faol" = oxirgi `active_days` (30) kun ichida ishlatgan. SuperAdmin panel + Telegram bot **bitta funksiyani** ishlatadi.

**Demo/savdo markazlari:**
- `python manage.py seed_demo_center` — demo markaz
- `python manage.py seed_sales_demo` — to'liq savdo demosi: `d@`/`m@`/`t@` (login == parol), slug **`demo-markaz`** (`demo` slug marketing bilan to'qnashadi!)
- `python manage.py reset_demo_center`

---

## 12. MARKETING SAYTI VA CMS

### 12.1 Sahifalar

Canonical (`marketing/urls.py`): `/`, `/about/`, `/features/`, `/pricing/`, `/demo/`, `/resources/`, `/support/`, `/vacancies/`, `/privacy/`, `/terms/`, `/data-deletion/`.
Ko'p tilli (`marketing/urls_i18n.py`): `/uz/...`, `/ru/...`, `/en/...`.
SEO: `/robots.txt`, `/sitemap.xml`.

`legacy_prefixed_marketing_redirect` — eski `/<center_slug>/uz/pricing/` kabi havolalarni canonical'ga yo'naltiradi.

### 12.2 CMS

Superadmin `/platform/marketing/` dan barcha kontentni tahrirlaydi: `SiteSetting`, `FeatureBlock`, `ScreenshotSection`, `PricingPlan` + `PricingFeature`, `Testimonial`, `FAQ`, `PartnerLogo`, `SupportCard`, `Vacancy`, `StaticPage`.

`/demo/` formasi → `DemoLead` (platformaning o'z lead'i).

### 12.3 i18n

- `LANGUAGE_CODE = "uz"`, `LANGUAGES = [uz, ru, en]`, `LOCALE_PATHS = [BASE_DIR/"locale"]`.
- `LocaleMiddleware` yoqilgan, `/i18n/` (`set_language`) ulangan.
- **Ilova (dashboard) ichi faqat o'zbekcha** — tarjima faqat marketing saytda.
- Telegram Family bot: **3 til** (uz / ru / **cy** = kirill o'zbek).

---

## 13. WEB UI VA DIZAYN TIZIMI

### 13.1 `templates/base.html` (1186 qator)

Tuzilishi:
```
<head>
  favicon'lar (16/32/180)
  vendor: bootstrap-icons, bootstrap CSS, apexcharts (lokal)
  CDN: Font Awesome 6.5.1, Google Fonts "Plus Jakarta Sans"
  inline <script>: tema aniqlash (FOUC oldini olish)
  {% block extra_css %}
  css/role-theme.css, light-mode-fixes.css, admin-pages-dark.css,
  chart-tooltip.css, plan-features.css   ← barchasi ?v=... cache-bust bilan
</head>
<body class="layout-auth|layout-guest has-role-theme role-<ROLE>">
  js/notifications.js
  {% include "partials/sidebar.html" %}
  {% include "partials/upgrade_modal.html" %}
  {% block pre_layout %}
  django messages (rangi: yashil/qizil/amber)
  {% block content %}
  {% block modals %}
  {% block ai_widget %} → partials/ai_chat_widget.html
  bootstrap bundle, js/role-theme.js
  {% block extra_js %}
</body>
```

### 13.2 Dizayn yo'nalishi

- **Web dashboard:** Premium **dark glassmorphism**, compact admin UI, ma'lumot zichligi yuqori.
- **Light mode:** bitta override fayl — `static/css/light-mode-fixes.css`. Bu 42+ shablonga retrofit qilingan. Yangi light-mode tuzatish **shu faylga** yoziladi, shablonlarga emas.
- **Rol temasi:** `<body class="role-director|role-manager|role-teacher|role-student|role-parent|role-superadmin">` + `html[data-role-theme="light|dark"]` → `role-theme.css` har rol uchun alohida aksent rangi beradi.
- **Tema almashtirish:** `static/js/theme.js` + `role-theme.js`, `localStorage` da saqlanadi, FOUC'ni oldini olish uchun `<head>` da inline skript.
- **Diagrammalar:** ApexCharts, `chart-tooltip.js` bilan yagona tooltip uslubi.
- **Sidebar:** `partials/sidebar.html` — yig'iladigan (`body.sidebar-collapsed`), mobil overlay, feature gate bilan qulflangan bandlar (qulf ikonkasi + upgrade modal), maxsus tugmalar (O'yinlar, Global Reyting, Guruh Chat, Asosiy).
- **Skeleton-first:** bosh sahifa avval skeleton ko'rsatadi, keyin `/api/dashboard/*` orqali ma'lumot yuklaydi (`dashboard_low_activity_api`, `dashboard_student_init_api`, `dashboard_quick_stats`).

### 13.3 Muhim shablon papkalari

| Papka | Mazmuni |
|---|---|
| `templates/partials/` | `sidebar.html`, `ai_chat_widget.html`, `upgrade_modal.html`, `plan_preview_bar.html`, `moliya_header.html`, `pagination.html`, `sa_subnav.html`, `dashboard_upgrade_block.html`, `sidebar_boshqaruv_section.html` |
| `templates/components/` | `notification_dropdown.html`, `profile_dropdown.html`, `grace_period_modal.html` |
| `templates/moliya/` | `tolov_usullari.html` |
| `templates/429.html`, `no_permission.html` | Xato sahifalari |

### 13.4 Direktor dashboardlari

| URL | Mazmuni |
|---|---|
| `/boshqaruv/` | ⭐ Asosiy direktor paneli + AI chat |
| `/dashboards/` | Hub (barcha dashboardlar ro'yxati) |
| `/dashboards/overview/` | Umumiy kesim |
| `/dashboards/financial/` | Moliya |
| `/dashboards/students/` | O'quvchi samaradorligi |
| `/dashboards/teachers/` | O'qituvchi samaradorligi |
| `/dashboards/groups/` | Guruhlar |
| `/dashboards/billing/` | Obuna/billing |
| `/dashboards/marketing/` | Marketing/lead |
| `/dashboards/inventory/` | Do'kon/ombor |
| `/dashboards/analytics/` | Analitika |

Har biriga mos `/api/dashboards/<name>/` endpointi (client-side yuklash).
Eksport: `/boshqaruv/export/` (Excel). Faollik tarixi: `/boshqaruv/faollik-tarixi/`.

---

## 14. MOBIL API KONTRAKTI

### 14.1 Umumiy qoidalar

| Jihat | Qiymat |
|---|---|
| Baza | `https://chaqmoqapp.uz` |
| Prefiks | `/api/mobile/` (asosiy), `/api/mobile/game/` (o'yin) |
| Auth | `Authorization: Bearer <token>` |
| Markaz | `X-Center-Slug: <slug>` header yoki token'dagi center |
| Format | JSON. Muvaffaqiyat: `{...ma'lumot}` yoki `{"ok": true, ...}` |
| Xato | `{"ok": false, "error": "O'zbekcha xabar", "code": "mashina_kodi"}` |
| Xato kodlari | `not_authenticated`, `rbac_forbidden`, `validation_error`, `throttled`, ... |
| CORS | `core.middleware.MobileApiCorsMiddleware` |
| CSRF | Bearer token bilan `@csrf_exempt`; sessiya bilan `/auth/csrf/` orqali token olinadi |
| Debug | `MOBILE_AUTH_DEBUG=1` yoki `DEBUG=True` → batafsil log |

### 14.2 Endpoint katalogi (`/api/mobile/`)

**Sog'liq va auth**
```
GET   health/
GET   auth/csrf/
POST  auth/login/                      {identifier, password, center_slug?, device_name?, device_platform?}
POST  auth/logout/                     joriy tokenni revoke
POST  auth/logout-all/                 barcha tokenlarni revoke
POST  auth/refresh/                    tokenni rotatsiya (eskisi revoke, yangisi beriladi)
GET   auth/sessions/                   faol qurilmalar
POST  auth/sessions/<id>/revoke/
GET   auth/status/
GET   auth/me/  |  GET me/
POST  auth/change-password/
```

**Umumiy (rolga qarab)**
```
GET   home/            → rolga mos bosh ekran
GET   dashboard/       GET attendance/   GET payments/   GET progress/
GET   profile/         POST profile/avatar/
GET   notifications/   POST notifications/<id>/read/   POST notifications/read-all/
GET   billing/status/
```

**Direktor**
```
GET   director/home/                                GET director/report/
GET   director/students/                            GET director/students/<id>/
POST  director/students/<id>/add-group/             POST director/students/<id>/remove-group/
POST  director/students/<id>/set-price/             POST director/students/<id>/pay/
GET   director/groups/
```

**O'qituvchi**
```
GET   teacher/home/         GET teacher/groups/     GET teacher/groups/<id>/students/
POST  teacher/attendance/mark/
GET   teacher/income/
GET   teacher/chaqmoq/rules/    POST teacher/chaqmoq/award/
```

**O'quvchi**
```
GET   student/home/       GET student/debt/
GET   chaqmoq/history/    GET chaqmoq/leaderboard/    GET chaqmoq/students/<id>/
GET   store/products/     GET store/purchase-requests/   POST store/purchase-requests/create/
```

**Ota-ona**
```
GET   parent/home/  |  parent/dashboard/
GET   parent/children/            POST parent/children/add/        {child_code}
POST  parent/select-child/
GET   parent/children/<id>/attendance/ | payments/ | progress/
GET   parent/profile/             POST parent/profile/avatar/
GET/POST parent/notification-preferences/
GET   parent/notifications/       POST parent/notifications/<id>/read/
```

**Boshqa**
```
GET   leads/
```

### 14.3 O'yin API (`/api/mobile/game/`)

```
POST  register/                     ChaqmoqApp hisobi bo'lmaganlar uchun
POST  auth/google/                  Google id_token bilan kirish (markazsiz)
POST  auth/profile/                 profil sozlash (nick, avatar)
GET   me/                           GET home/    GET catalog/
POST  play/<mode_id>/start/
POST  play/session/<id>/answer/     POST play/session/<id>/finish/
GET   play/history/
GET   queue/<id>/                   POST queue/<id>/robot/    POST queue/<id>/cancel/
POST  duel/start/                   POST duel/<id>/answer/    POST duel/<id>/finish/
GET   duel/history/
GET   league/                       GET news/
GET   shop/                         POST shop/<item_id>/buy/     GET purchases/
GET   tariffs/                      POST tariffs/<id>/buy/       GET tariffs/requests/
GET   profile/                      POST profile/avatar/
GET   users/<id>/                   GET users/search/            GET online/
GET   friends/                      POST friends/<uid>/request/  POST friends/<fid>/respond/
GET   invites/                      POST invites/<uid>/send/     POST invites/<id>/respond/
GET   feedback/                     POST feedback/send/
```

### 14.4 Web AJAX API'lar (sessiya bilan, RBAC'dan o'tadi)

```
/api/dashboard/quick-stats|low-activity|student-init|manager/
/api/student/dashboard|groups|attendance|payments|game/status|game/result|game/convert-balls/
/api/parent/children/  /api/parent/child/<pk>/dashboard|groups|attendance|payments/
/api/churn/summary/  /api/exam/summary/
/api/boshqaruv/  /api/boshqaruv/chat/ (+history, clear, sessions, new)  /api/boshqaruv/ai-role-settings/
/api/dashboards/<name>/  /api/director/dashboard/ (+debtor-diagram, category-revenue, students-chart)
/api/branches/ (+create, <pk>/update, <pk>/delete)
/api/games/config|global-config|suggestion|balls-config|<slug>/questions[/manage|/ai-generate]/
/api/chat/<group_id>/messages|send|typing/
/api/hr/employees/ (+<id>/, teachers/available/)
/api/calculate-lessons/  /talim/api/finance/teacher-expected-income/
/talim/api/student/<id>/month-debt|debt-form|manual-debt|month-delete|month-reset-payments|monthly-breakdown/
/do'kon/api/leads/... /api/lead-groups/... /api/lead-subjects/... /api/lead-statuses/...
```

### 14.5 OpenAPI

`drf-spectacular`: `/api/schema/`, `/api/docs/` (Swagger UI), `/api/redoc/`.
Teglar: `auth`, `mobile`, `director`, `ai`, `billing`.
> ⚠️ Mobil API ko'p qismi oddiy Django `JsonResponse` bilan yozilgan (DRF emas) — shuning uchun schema **to'liq emas**. Bu hujjat schema'ni to'ldiradi.

---

## 15. FLUTTER MOBIL ILOVA

### 15.1 Umumiy

| Jihat | Qiymat |
|---|---|
| Paket | `uz.chaqmoq.chaqmoq_mobile` |
| Nomi | `chaqmoq_mobile` / "ChaqmoqApp Mobile" |
| Versiya | 1.1.0+8 |
| Dart SDK | ^3.11.4 |
| Fayllar | 186 `.dart` |
| Do'kon | Google Play (PROSKILL LLC), iOS (TestFlight/App Store) |

### 15.2 Konfiguratsiya (`lib/core/config/app_config.dart`)

Compile-time `String.fromEnvironment` orqali:

| Kalit | Default |
|---|---|
| `APP_ENV` | `prod` |
| `API_BASE_URL` | `https://chaqmoqapp.uz` |
| `CENTER_SLUG` | `proskill` |
| `GOOGLE_SERVER_CLIENT_ID` | `""` (bo'sh → Google tugmasi yashiriladi) |
| `GOOGLE_IOS_CLIENT_ID` | `""` |

Timeout'lar: connect 12s, receive 20s, send 15s.

Build misoli:
```bash
flutter build appbundle --dart-define=API_BASE_URL=https://chaqmoqapp.uz \
  --dart-define=CENTER_SLUG=proskill \
  --dart-define=GOOGLE_SERVER_CLIENT_ID=<web-client-id>
```

### 15.3 Papka tuzilishi

```
lib/
├── main.dart                    # entrypoint, Provider daraxti, tema
├── design_showcase.dart         # dizayn tizimini web'da ko'rish uchun entrypoint
├── director_preview.dart        # Direktor panelini mock bilan ko'rish uchun entrypoint
├── core/
│   ├── config/app_config.dart
│   ├── design/                  # ⭐ YANGI 6-rolli dizayn tizimi (Sky/Slate)
│   │   ├── ds_colors, ds_tokens, ds_typography, ds_theme,
│   │   ├── ds_components, ds_bottom_nav, ds_format, ds_showcase
│   ├── theme/                   # eski/rol-spetsifik temalar
│   │   ├── app_colors, app_theme, app_spacing, app_text_styles, app_foundation,
│   │   ├── panel_tokens, parent_colors, parent_text_styles,
│   │   ├── student_colors, student_tokens
│   └── utils/                   # formatters, role_utils, role_panel_style
├── models/                      # app_models, game_models, lead_models,
│                                # login_models, parent_models, teacher_models
├── providers/                   # 14 ChangeNotifier
├── repositories/auth_repository.dart
├── services/                    # api_client (Dio), api_services, storage_service,
│                                # login_service, profile_service, teacher_service,
│                                # parent_dashboard_service, leads_service,
│                                # game_service, game_auth_service,
│                                # local_notification_service
├── screens/
│   ├── splash/, auth/login_screen.dart, shell/app_shell.dart
│   ├── director/   # shell, dashboard, students(+detail), debtors, payments,
│   │               # report, notifications, profile, widgets/, data/, director_mock
│   ├── teacher/    # shell, dashboard, groups, attendance, income, profile
│   ├── student/    # shell, dashboard, attendance, payments, progress, store,
│   │               # purchase_history, leaderboard, chaqmoq_detail, account,
│   │               # notifications, game/
│   ├── parent/     # shell, dashboard, add_child, notifications, parent_ui
│   ├── gameonly/   # shell, register, profile_setup, profile (markazsiz o'yinchi)
│   ├── dashboard/, attendance/, payments/, progress/, groups/, students/,
│   ├── teachers/, leads/, notifications/, profile/, settings/, account/
└── widgets/                     # umumiy widget'lar
```

### 15.4 Providerlar (state)

`auth_provider`, `app_preferences_provider`, `dashboard_provider`, `attendance_provider`, `payments_provider`, `groups_provider`, `students_provider`, `teachers_provider`, `teacher_provider`, `parent_dashboard_provider`, `notifications_provider`, `chaqmoq_history_provider`, `leads_provider`, `game_provider`.

> ⚠️ **KRITIK TUZOQ:** `didChangeDependencies()` ichida `provider.load()` chaqirish **qizil ekran** (build davomida `notifyListeners`) beradi. To'g'ri yo'l:
> ```dart
> WidgetsBinding.instance.addPostFrameCallback((_) => provider.load());
> ```

### 15.5 Rollar bo'yicha ilova qobiqlari

Login'dan keyin rol aniqlanadi va mos `*_app_shell.dart` ochiladi:

| Rol | Shell | Tab'lar |
|---|---|---|
| Direktor | `director_app_shell` | Dashboard, O'quvchilar, To'lovlar, Hisobot, Profil |
| O'qituvchi | `teacher_app_shell` | Dashboard, Guruhlar, Davomat, Daromad, Profil |
| O'quvchi | `student_app_shell` | Dashboard, **O'yin (3-tab)**, Do'kon/Hisob, ... |
| Ota-ona | `parent_app_shell` | Dashboard, Farzandlar, Bildirishnoma, Profil |
| Faqat o'yin | `game_only_shell` | O'yin, Reyting, Profil |

**Dizayn:**
- Ota-ona: light soft-blue uslub (`parent_colors`, `parent_text_styles`).
- O'quvchi: dark teal glassmorphism (`student_colors`, `student_tokens`).
- Yangi 6-rolli **Sky/Slate** dizayn tizimi: `lib/core/design/` (`ds_*`). Web preview entrypoint'lari orqali ko'riladi (`design_showcase.dart`, `director_preview.dart`).

**Offline/fallback:** ba'zi ekranlar mock ma'lumot bilan ishlaydi (`director_mock.dart`, `screens/director/data/`) — API yo'q bo'lganda ham UI ko'rinadi.

### 15.6 Ikonka va reliz

- Launcher ikonka: `flutter_launcher_icons`, `assets/icon/app_icon.png` + adaptive foreground. Brend: **sariq yashin / ochiq fon** ("Yorqin"). Generator: `~/Desktop/ChaqmoqApp_icons/`.
- Android: `flutter build appbundle` → Google Play (PROSKILL LLC).
- iOS: `xcodebuild` bilan parolsiz yuklash. **Tuzoqlar:** versiya mosligi (`pubspec` ↔ Xcode) va eksport-shifrlash deklaratsiyasi (`ITSAppUsesNonExemptEncryption`).
- Hujjat: `MOBILE_DEPLOY_SETUP.md`.

---

## 16. CHAQMOQ GAME (⚡ mobil o'yin)

### 16.1 Falsafa

> O'yin **chaqmog'i** ChaqmoqApp'ning `chaqmoq.Ledger` balansidan **BUTUNLAY ALOHIDA**. ChaqmoqApp o'quvchisi ham o'yinda 0 dan boshlaydi. O'yin iqtisodiyoti markaz iqtisodiyotiga tegmasligi kerak.

Ikki xil o'yinchi:
1. **Markaz o'quvchisi** — mavjud hisobi bilan kiradi, o'yin O'quvchi panelining **3-tabida**.
2. **Mustaqil o'yinchi** (`User.game_only=True`, `center=None`) — Google bilan ro'yxatdan o'tadi, davomat/to'lov/qarz yo'q, 3 tabli alohida panel.

### 16.2 Iqtisodiyot

```
Mukofot ANIQLIK FOIZIDAN (savol soniga bog'liq emas):
  100%      → +5 chaqmoq
  75–99%    → +3
  50–74%    → +2
  30–49%    →  0
  <30%      → −1  (jarima — tavakkaliga bosishning ma'nosi qolmaydi)

Bepul reja:
  3 jon / 8 soat   (BEPUL_JON=3, BEPUL_JON_SOAT=8)
  o'yin qulfi 24 soat  (BEPUL_OYIN_QULF_SOAT=24)

GameMode.chaqmoq_koef → faqat MUKOFOTNI ko'paytiradi.
Jarima har doim aniq −1 (koeffitsiyentsiz).
Tarif.chaqmoq_bonus_foiz → mukofotga qo'shimcha % (masalan 50 → 4 o'rniga 6).
```

**Nega ikkita kutish bor:** faqat jonni tezlashtirish deyarli hech narsa bermaydi — 6 ta o'yin bo'lsa, 24 soatlik qulf kuniga 6 o'yin bilan cheklaydi. Shuning uchun tarif **ikkalasini** ham qisqartiradi (`soat` + `oyin_qulf_soat`).

### 16.3 Motorlar (mexanikalar)

`game/engines.py` — `MOTORLAR: dict[str, Motor]`. Motor Flutter kodida yozilgan.

```
Admin panelda: motor ustiga O'YIN (GameMode) qo'yiladi
  → nomi, savollar to'plami, nechta savol, necha soniya, mukofot, jon narxi

Yangi O'YIN  → ilova avtomatik ko'radi (katalog API)
Yangi MOTOR  → ilovaning yangi versiyasi kerak
Tanimagan motor → katalogda "ilovani yangilang" holatida (ro'yxat buzilmaydi)
```

Motor maydonlari: `kalit`, `nom`, `izoh`, `yoriqnoma`, `ikonka`, `rang`, `savollar_soni`, `savol_soniya`, `min_savol`, `javob_ochiq`, `duel_oqimi`, `sozlamalar`.
Mavjud: `duel` (⚔️, `duel_oqimi=True`, `min_savol=10`), `viktorina` (🧠) va boshqalar.

### 16.4 Duel va matchmaking

```
1. O'quvchi duel boshlaydi → navbatga_qoy(user, center, mode, savollar)
     • Kutayotgan raqib bo'lsa → darhol juftlanadi (_juft_duel_yarat):
       ikkala o'yinchiga BIR XIL savollar
     • Bo'lmasa → DuelQueue da kutadi
2. Ilova poll qiladi: GET queue/<id>/  → ("topildi" | "kutmoqda" | "vaqt_tugadi")
3. Vaqt tugasa → POST queue/<id>/robot/ → robot bilan duel
4. Bekor qilish → POST queue/<id>/cancel/
5. Eskirgan navbatlar avtomatik tozalanadi (_eskirganlarni_tozala)
```

**Robotlar:** `GameProfile(robot=True)` — `python manage.py game_demo` **50 ta** robot yaratadi.
- `maxorat` (0.50–0.90) = 10 savoldan o'rtacha shuncha ulushiga to'g'ri javob beradi. Har robotda har xil.
- Model `user=None` ni ruxsat etadi, lekin seed har robotga **login qila olmaydigan `User`** biriktiradi — sababi: foydalanuvchi robotga ham do'stlik yuborishi kerak.
- Robotlar reytingda odamlar bilan bir qatorda ko'rinadi va chaqmoq yig'adi. Ilovada "robot" belgisi **ko'rsatilmaydi** (ataylab — jonli tuyulishi uchun).

**Qulf (`game/cooldowns.py`):** `qulflar_xaritasi(profile) -> {mode_id: qolgan_soniya}`, `qulflangan_soniya()`, `qulfni_yangila()`.

### 16.5 Tariflar va to'lov

`Tarif`: `narx_som`, `kun`, `jon_soni`, `soat`, `oyin_qulf_soat`, `chaqmoq_bonus_foiz`.
Ko'rinishi: `tavsif` xossasi ("Har 4 soatda 3 ta jon · o'yin 6 soatda ochiladi · +50% chaqmoq").
Taqqoslash: `haftalik_narx`.

**Sotib olish:**
```
1. POST tariffs/<id>/buy/ → TarifSorovi (narx MUZLATILADI)
2a. usul=click → /click/game/prepare/ + /click/game/complete/
      → obunani_yoq(sorov) → Obuna (tolangan=True)
2b. usul=naqd → o'quvchi markazga/Telegram'ga to'laydi
      → superadmin /platform/game/payments/<id>/ da tasdiqlaydi
3. Obuna.faol = tolangan AND tugaydi > now
```

Telegram yo'nalishi: `GAME_SUPPORT_TELEGRAM` (default `de_amirxon`) — ilova bu nomni **serverdan** oladi, o'zgarganda ilovani yangilash shart emas.

### 16.6 Boshqa

- **Liga:** bronza / kumush / oltin / olmos (`hafta_xp` bo'yicha).
- **Do'kon (`ShopItem`)** — chaqmoqqa avatar/tema sotib olish → `Purchase`.
- **Do'stlar (`Friendship`)** + duelga chaqiriq (`DuelInvite`).
- **Yangiliklar (`NewsPost`)**, **Feedback** (shikoyat/taklif → `/platform/game/`).
- **Alohida Flutter loyiha** ham bor: `~/Desktop/ChaqmoqGame` (o'yin prototipi).
- Management: `python manage.py game_demo`, `game_oyinlar`, `google_tekshir`.
- Testlar: `game/tests.py`, `game/tests_google.py`, `accounts/tests_game_admin.py`.

> ⚠️ **Test tuzoqlari:** `flutter_animate` pending timer + lazy `ListView` — testda "timer still pending" xatolari mantiq xatosi emas, test tuzilishi aybdor.

---

## 17. TELEGRAM BOTLAR

### 17.1 Arxitektura

`telegram_bot/bot.py` — bitta process, **ikki bot tokeni**:
- `BOT_TOKEN` — asosiy bot
- `BOT_TOKEN_FAMILY` — Family bot (ota-ona/o'quvchi paneli)

Ichida: aiogram 3 `Dispatcher` + routerlar, `aiohttp` internal server (`:8080`), `APScheduler`.
Django'ga murojaat: `services/api_client.py` → `X-API-SECRET` header bilan.
Ishga tushish: `start.sh` gunicorn portga bog'langandan **12 sekund keyin** (`BOT_START_DELAY`) — cold-start 502 ni kamaytirish uchun.

### 17.2 Routerlar (`telegram_bot/handlers/`)

| Handler | Vazifasi |
|---|---|
| `start.py` | `/start`, deep-link (`?start=<token>`), til tanlash |
| `link_account.py` | Telefon/kod bilan hisobni ulash |
| `family_onboarding.py` | Ota-ona onboarding (3 tilli) |
| `parent.py`, `parents.py` | Ota-ona paneli: bolalarim, davomat, to'lovlar, chaqmoq, o'qituvchi |
| `student.py` | O'quvchi paneli |
| `teacher.py` | O'qituvchi paneli |
| `manager.py` | Manager paneli |
| `profile.py` | Profil, sayt login/parol |
| `activity.py` | Faollik |
| `security.py` | Xavfsizlik (sessiyalar, parol) |
| `admin_panel.py`, `admins.py` | Bot admin paneli (`BotAdmin`) |
| `broadcast.py` | Ommaviy xabar yuborish |
| `branch_approval.py` | Filial so'rovini tasdiqlash (superadmin panel bilan **bitta servis**) |
| `linked_users.py` | Ulangan foydalanuvchilar |
| `settings.py`, `help.py`, `fallback.py` | Sozlama, yordam, tushunilmagan xabar |

**Klaviaturalar:** `keyboards/` — `admin_menu`, `manager_menu`, `parent_menu`, `student_menu`, `teacher_menu`, `menu`, `contact_button`, `profile_selector`.
**FSM holatlar:** `states/` — `link_state`, `admin_state`, `broadcast_state`, `manager_broadcast_state`.

### 17.3 i18n (`telegram_bot/i18n.py`)

- Tillar: `uz` (lotin), `ru`, **`cy`** (kirill o'zbek).
- Til `telegram_id → lang` xotira dict'ida (`_LANG_CACHE`). `/start` har safar tilni qayta so'raydi, shuning uchun xotira yetarli.
- **Tugma yozuvlari (`BTN`) ham, ularni ushlaydigan filtrlar ham SHU dict'dan** — handler har doim to'g'ri mos keladi.
- Xabarlar **qisqa** (2 og'iz gap) — bu ataylab qo'yilgan dizayn qoidasi.

### 17.4 Jadval (`services/scheduler.py`)

- Kunlik hisobot: **18:00 Asia/Tashkent** (`BACKUP_SEND_TIME`, `BACKUP_TIMEZONE`).
- DB backup: `backup/backup_service.py` → Telegram guruhga ZIP yuboradi.
- `/dbb` komandasi — on-demand backup.
- `BOT_BACKUP_SCHEDULER_ENABLED=true` (Render'da), `BACKUP_SCHEDULER_ENABLED=false` (Django tomonida) — **ikki marta yubormaslik uchun**.
- Nega botdan: bot process doim ishlab turadi, Render cron servisiga bog'liq emas → ishonchliroq.

### 17.5 Botni yoqish/o'chirish

- Global: `TELEGRAM_BOT_ENABLED` env (`auto`/`true`/`false`/`0`).
- Token yo'q bo'lsa avtomatik skip.
- **Per-center:** `Center.telegram_bot_enabled` (default **False**). Superadmin `/platform/bot/` dan yoqadi. Gate bot handler'larida tekshiriladi.

### 17.6 English Teacher bot

`english_teacher/bot.py` — alohida AI bot (ingliz tili o'qituvchisi). `bot.py` da try/except bilan import qilinadi — import xatosi butun botni yiqitmaydi.

---

## 18. AI QATLAMI (GEMINI)

### 18.1 Provayderlar

| Paket | Rol |
|---|---|
| `google-genai` 1.73.1 | ⭐ Asosiy (yangi SDK) — `_GoogleGenAIModel` |
| eski `google-generativeai` | Zaxira — `_LegacyGeminiModel` |
| `anthropic` >=0.34 | Ikkinchi zaxira provayder |

Kalit: `GEMINI_API_KEY`. Model: `GEMINI_MODEL` env yoki kod ichidagi kandidatlar ro'yxati (`_gemini_candidates`). Kalit yo'q bo'lsa → **fallback** (qoidaga asoslangan javob), ilova ishlashda davom etadi.

### 18.2 Direktor AI (`core/services/ai_insights.py`, 2315 qator)

**Imkoniyatlar:**
- `generate_insights(center, stats)` — dashboard uchun avtomatik xulosalar ("Qarzdorlar 12% oshdi, sababi...").
- `calculate_churn_risk(center)` — ketib qolish xavfi.
- `_forecast_bundle(center, months_ahead=3)` — WMA bilan daromad prognozi.
- Chat: `/api/boshqaruv/chat/` — direktor markaz haqida savol beradi.

**Savol tushunish (LLM'siz ham ishlaydi):**
- `_normalize_question`, `_question_tokens`, `_token_similarity` (threshold 0.78), `_question_has(...)` — o'zbekcha savol variantlarini fuzzy tanish.
- `_extract_specific_date`, `_extract_month_year`, `_extract_search_query` — savoldan sana/oy/ism ajratish.
- `_advanced_rule_bundle` — LLM'ga bormasdan aniq javob berish (masalan "Ali Valiyevning qarzi qancha?").
- `_is_social_prompt` — "salom" kabi savollarga qisqa javob.

**Kontekst qurish:**
- `_site_context`, `_compact_context`, `_full_center_context`, `_profile_lookup_block` — markaz ma'lumotlarini **siqilgan** formatda prompt'ga joylash (token tejash).
- `core/services/center_ai_context.py` (1477 qator) — markaz kontekstini qurish.

**Cache:** `_prompt_json(cache_key, ttl=INSIGHT_CACHE_TTL)`, `_prompt_text(ttl=ANSWER_CACHE_TTL)`, `_stats_digest`, `_history_digest` — bir xil savol qayta LLM'ga ketmaydi.

**Sessiyalar:** `DirectorAIChatSession` + `DirectorAIChatMessage` (`source`: `gemini` / `cache` / `fallback` / `rate-limited`). Widget joyi `launcher_position` JSON'da saqlanadi.
API: `/api/boshqaruv/chat/history/`, `/clear/`, `/sessions/`, `/new/`.

### 18.3 Rol bo'yicha AI (`core/services/role_scoped_ai.py`)

`answer_role_scoped_question(viewer, question, history) -> (answer, source)`

Kontekst **faqat viewer ko'rishga haqli** ma'lumotdan qurilади:
- `build_teacher_context(teacher)` — o'z guruhlari, o'quvchilari, daromadi
- `build_student_context(student)` — o'z davomati, to'lovi, chaqmog'i
- `build_parent_context(parent)` — farzandlari

Yoqish: `Center.ai_enabled` (superadmin) + `ai_teacher_enabled` / `ai_student_enabled` / `ai_parent_enabled` (direktor/manager).
UI: `templates/partials/ai_chat_widget.html`.
Sozlash API: `/api/boshqaruv/ai-role-settings/`.

### 18.4 AI xavfsizligi (`core/services/center_ai_security.py`)

- Prompt injection'dan himoya, boshqa markaz ma'lumoti kontekstga tushmasligini kafolatlash.
- Rate limit: `core/rate_limit.py` (test: `core/tests_rate_limit.py`), `source="rate-limited"`.
- Kvota: `PlanFeature` type=QUOTA + `FeatureUsage` (oylik AI so'rovlari).

### 18.5 AI savol generatsiyasi

`/api/games/<game_slug>/questions/ai-generate/` — mini-o'yinlar uchun savol generatsiya (`GameQuestion.is_ai_generated=True`).

---

## 19. BILDIRISHNOMALAR TIZIMI

### 19.1 Ichki bildirishnomalar

`core.Notification` — `center`, `sender`, `recipient`, `title`, `message`, `is_read`, `type` (`system` / `coin` / `broadcast` / `purchase` / ...).

**Yaratilish joylari:**
- Chaqmoq berish/ayirish (`chaqmoq/services.py` → `send_notification()`)
- Do'kon so'rovi tasdiqlanishi/rad etilishi
- Imtihon eslatmasi
- Churn ogohlantirishi
- Ommaviy xabar (`notification_broadcast`)
- Obuna/to'lov holati

**Sozlamalar:** `NotificationPreference` (`receive_coin`, `receive_broadcast`, `receive_purchase`, `receive_system`) — `user` OneToOne.

**UI:** `templates/components/notification_dropdown.html` + `static/js/notifications.js` (polling).
**Web:** `/notifications/`, `/notifications/read/`, `/notifications/read-one/<pk>/`, `/notifications/preferences/`, `/notifications/api/read-all/`.
**Mobil:** `/api/mobile/notifications/`, `/<id>/read/`, `/read-all/` + `flutter_local_notifications` (lokal push).

### 19.2 Telegram bildirishnomalar

- `accounts/utils_bot.py`, `billing/telegram_notifications.py`, `telegram_bot/parent_notify.py`
- `python manage.py notify_parents` — ota-onalarga xabar
- `python manage.py send_daily_reports` — kunlik hisobot
- `python manage.py notify_exam_reminders` — imtihon eslatmasi
- `core/alerts.py` — tizim ogohlantirishlari (admin Telegram ID'lariga)

> **Push notification (FCM/APNs) hozircha YO'Q.** Faqat lokal notification + Telegram. Bu roadmap'da.

---

## 20. BACKUP VA TIKLASH

### 20.1 Ikki mustaqil manzil

| Manzil | Vaqt | Nima uchun |
|---|---|---|
| **Telegram guruh** | Har kuni 18:00 (Asia/Tashkent) | Tez kirish, tarixga qarash |
| **Google Drive** | Telegram'dan keyin | Telegram bloklansa ham qoladi |

**Fayl turlari (har kun):**
- `<slug>_YYYY-MM-DD.json` — har markaz alohida (faqat o'sha markazga tegishli ma'lumot)
- `postgres_full_YYYY-MM-DD.sql` — butun DB (barcha markazlar + Django tizim jadvallari)

Drive tartibi: `ChaqmoqApp Backups / 2026-04 / 2026-04-19 / <fayllar>`

### 20.2 Sozlamalar

```env
TELEGRAM_BOT_TOKEN=            # yoki BACKUP_BOT_TOKEN
TELEGRAM_BACKUP_CHAT_ID=       # fallback: BACKUP_GROUP_ID, TELEGRAM_GROUP_ID
BACKUP_TIMEZONE=Asia/Tashkent
BACKUP_SEND_TIME=18:00
BACKUP_KEEP_DAYS=7
TELEGRAM_ZIP_MIN_SIZE_MB=8     # bundan katta fayllar avtomatik zip
TELEGRAM_SEND_TIMEOUT_LARGE=180
TELEGRAM_SEND_RETRIES=2
BACKUP_GDRIVE_ENABLED=false
ADMIN_TELEGRAM_IDS=123,456     # bo'sh bo'lsa BotAdmin yoki Telegram-bog'langan superuser
```

### 20.3 Buyruqlar

```bash
python manage.py backup_databases        # backups/ ichiga yaratadi, yubormaydi
python manage.py send_db_backups         # yaratadi + Telegram'ga yuboradi
python manage.py backup_and_send         # to'liq oqim
python manage.py configure_backup_bot    # token/chat tekshirish, /db komandasini ro'yxatga olish
python manage.py test_backup_send
python manage.py test_gdrive_upload
python manage.py gdrive_oauth_setup      # OAuth (shaxsiy Gmail Drive uchun)
python manage.py restore_center_backup   # markazni JSON'dan tiklash
```

Telegram'da: `/db`, `/dbb` (on-demand backup).

> ⚠️ **Google Drive Service Account** shaxsiy Drive storage kvotasiga ega **emas** — u faqat Shared Drive yoki domain delegation bilan ishonchli ishlaydi. Shaxsiy Gmail Drive uchun OAuth (`gdrive_oauth_setup`) ishlating.

### 20.4 Tiklash

To'liq qo'llanma: **`RESTORE_GUIDE.md`** — "xotirjam paytda o'qib, panik paytda qadam-baqadam bajarish uchun".

Asosiy stsenariylar:
1. **Bitta markaz ma'lumoti buzildi** → `restore_center_backup` bilan `<slug>_YYYY-MM-DD.json` dan tiklash.
2. **Butun DB buzildi** → `postgres_full_*.sql` ni `psql` bilan tiklash.
3. Servislar: `core/services/db_backup_service.py` (1484 qator), `core/services/gdrive_backup.py`.
4. Test: `core/tests_backup_schedule.py`.

---

## 21. SOFT DELETE, TRASH VA AUDIT

### 21.1 SoftDeleteMixin

```python
is_deleted, deleted_at, deleted_by, deleted_reason
restored_at, restored_by            # tiklash auditi
objects      = AliveManager()       # is_deleted=False
all_objects  = Manager()            # hammasi
```

QuerySet metodlari: `.delete(deleted_by=user)` (soft), `.hard_delete()` (haqiqiy), `.alive()`, `.dead()`.

**`deleted_reason` — biznes mantiqiga ta'sir qiladi!** `TuitionMonth` uchun quyidagi prefikslar "himoyalangan" hisoblanadi va `ensure_tuition_month` ularga tegmaydi: `manual_cleared`, `cleanup_*`, `move_future_*`, `reset_*`, `user_edit*` (9.4.3-bo'lim).

### 21.2 Trash UI (`core/trash.py`)

`/trash/` — o'chirilgan yozuvlarni ko'rish va tiklash.

Qo'llanadigan modellar (`MODELS` dict):

| Kalit | Model | Yorliq |
|---|---|---|
| `teachers` | `accounts.User` (role=teacher) | O'qituvchilar |
| `managers` | `accounts.User` (role=manager) | Managerlar |
| `students` | `accounts.User` (role=student) | O'quvchilar |
| `parents` | `accounts.User` (role=parent) | Ota-onalar |
| `groups` | `education.Group` | Guruhlar |
| `courses` | `education.Category` | Kurslar |
| `payments` | `education.Payment` | To'lovlar |
| `products` | `store.Product` | Mahsulotlar |

Amallar: `/trash/<model_key>/<pk>/restore/`, `/trash/<model_key>/<pk>/hard-delete/`.

**Kirish huquqi:** superuser yoki `director`; `manager` — `Center.manager_can_access_trash` yoki `User.can_access_trash` bo'lsa. Toggle: `/trash/toggle-access/`, `/trash/manager-access/<user_id>/`.

### 21.3 Audit jurnallari

| Model | Nimani yozadi |
|---|---|
| `accounts.AdminAuditLog` | Superadmin harakatlari |
| `accounts.UserActivity` | Foydalanuvchi faolligi |
| `education.EducationAuditLog` | Education modulidagi muhim o'zgarishlar (`services/audit_service.py`) |
| `education.CertificateVerificationLog` | Sertifikat tekshiruvlari (IP, user-agent) |
| `education.ExamReminderLog` | Imtihon eslatmalari va javoblar |
| `core.GameBallsConversionLog` | Ball→chaqmoq konvertatsiyalari |
| `billing.PaymentTransaction` | To'lov tranzaksiyalari |

Foydalanuvchi faolligi tarixi UI: `/boshqaruv/faollik-tarixi/`.

---

## 22. PERFORMANCE

### 22.1 Ma'lum muammolar tarixi

**502 xatolar sababi:**
- Render Starter (512MB / 0.5 CPU) da **1 gunicorn worker**, `timeout=60s`.
- Og'ir sahifalar (qarzdorlar, finance month-preview) markaz bo'ylab **per-o'quvchi N+1 loop** qilardi → 60s timeout → 502.
- `GUNICORN_MAX_REQUESTS=500` → juda tez worker recycle → tasodifiy 502.

**Tuzatishlar:**
- Standard plan'ga o'tish (2GB / 1 CPU): `WEB_CONCURRENCY=2`, `GUNICORN_THREADS=4`, `GUNICORN_TIMEOUT=120`.
- `GUNICORN_MAX_REQUESTS` pastki chegarasi **2000** (env undan past bo'lsa ham kodda 2000'ga ko'tariladi — `start.sh`).
- `--preload`: ilova master jarayonda bir marta yuklanadi, worker recycle'da fork qilinadi → reboot <1s.
- Qarzdorlar + month-preview: preload helper + `select_related` + optional-param memoizatsiya.
- 456-sahifali **smoke harness** (`python manage.py smoke_test`).

### 22.2 N+1 oldini olish naqshlari

| Helper | Nima qiladi |
|---|---|
| `preload_enrollment_history_starts(enrollments)` | `StudentGroupHistory.start_date` ni bulk yuklaydi |
| `preload_group_schedules(group_ids)` | Guruh jadvallarini bulk yuklaydi (`_get_cached_group_weekdays`) |
| `enrollment.__resolved_start_date__` | Per-obyekt memoizatsiya |
| `enrollment.__resolved_last_billable_date__` | Per-obyekt memoizatsiya |
| `enrollment.__preloaded_history_start_date__` | Preload natijasi |
| `HistoricalFinanceService._attendance_lookup(group_ids, year, month)` | Bir query bilan barcha davomat |
| `HistoricalFinanceService._history_lookup(group_ids)` | Bir query bilan barcha tarix |
| `calculate_enrollment_debt_snapshots(enrollments, months)` | ⭐ Butun markaz qarzini **bir necha query** bilan |

> **QOIDA:** yangi kod yozganda **hech qachon** `for student in students: calculate_debt(student)` naqshini ishlatmang. Bulk snapshot funksiyasini chaqiring.

### 22.3 Cache qatlamlari

**1. `core/perf_cache.py`** — markazlashtirilgan Django cache helper:
```python
TTL_SHORT  = 60     # tez-tez yangilanadigan ro'yxatlar
TTL_MEDIUM = 300    # paginatsiyali ro'yxatlar
TTL_LONG   = 900    # oylik hisobotlar
TTL_DAILY  = 3600   # yillik agregatlar

cache_key_for_center(prefix, center_id, *parts)
versioned_cache_key(prefix, center_id, *parts)   # versiyalangan → bulk invalidate
perf_cache_get_or_set(key, fn, ttl=TTL_MEDIUM)
invalidate_center(center_id, prefix="")
get_center_version(center_id, prefix="")
```

Avtomatik invalidatsiya:
- `Attendance.save()` → `salary_sum`, `salary_list`
- `Payment.save()` → `boshqaruv_api`
- `Enrollment.save()` → `boshqaruv_api`

**2. Middleware in-process cache** (5.4-bo'lim): `_CENTER_CACHE`, `_SLUG_CACHE`, `_SUB_BLOCK_CACHE`.

**3. Request-scoped:** `billing.services._chf_cache()` (feature tekshiruvlari).

**4. AI cache:** `_prompt_json` / `_prompt_text` (savol digest bo'yicha).

### 22.4 DB tuning (`config/settings_prod.py`)

```
CONN_MAX_AGE = 600            # connection pool 10 daqiqa
connect_timeout = 10s
statement_timeout = 30s       # har query maksimum
lock_timeout = 5s             # row-lock kutish

Override: DJANGO_DB_STATEMENT_TIMEOUT_MS, DJANGO_DB_LOCK_TIMEOUT_MS,
          DJANGO_DB_CONNECT_TIMEOUT
```

### 22.5 Indekslar

| Indeks | Jadval / maydonlar |
|---|---|
| `att_group_date_idx` | `Attendance(group, date)` |
| `att_center_date_idx` | `Attendance(center, date)` |
| `att_status_idx` | `Attendance(status)` |
| `group_center_arch_idx` | `Group(center, is_archived)` |
| `group_oqit_arch_idx` | `Group(oqituvchi, is_archived)` |
| `group_sup_arch_idx` | `Group(support_teacher, is_archived)` |
| `enr_center_active_idx` | `Enrollment(center, is_active, is_deleted)` |
| `enr_group_active_idx` | `Enrollment(group, is_active)` |
| `enr_student_active_idx` | `Enrollment(student, is_active)` |
| `pay_center_del_date_idx` | `Payment(center, is_deleted, paid_date)` |
| `pay_enr_del_idx` | `Payment(enrollment, is_deleted)` |
| `tm_enr_month_idx` | `TuitionMonth(enrollment, month, is_deleted)` |
| `tm_center_month_idx` | `TuitionMonth(center, month, is_deleted)` |
| `pa_tm_deleted_idx` | `PaymentAllocation(tuition_month, is_deleted)` |
| `pa_payment_deleted_idx` | `PaymentAllocation(payment, is_deleted)` |
| `user_center_role_idx` | `User(center, role, is_archived)` |
| `user_phone_num_idx` | `User(phone_number)` |
| `staffprof_t_role_idx` | `StaffProfile(tenant, role, is_active)` |
| `teachavail_t_day_idx` | `TeacherAvailability(tenant, teacher, weekday)` |

### 22.6 Slow request monitoring

`core/middleware_perf.SlowRequestLoggingMiddleware` — har request'da vaqt + query soni.

```
[PERF] GET /api/boshqaruv/ | 4175ms | 298q | 200  [CRITICAL][N+1?]
```

Teglar (default `SLOW_REQUEST_MS=800`):
- `> 800ms` → `[!SLOW]`
- `> 1600ms` (×2) → `[SLOW]`
- `> 4000ms` (×5) → `[CRITICAL]`
- Ko'p query → `[N+1?]`, `[HIGH-Q]`

Loglarni filtrlash:
```bash
grep -E "CRITICAL|N\+1|HIGH-Q"
```

Env: `SLOW_REQUEST_MS`, `SLOW_REQUEST_LOG_QUERIES`, `PERF_LOG_ALL`, `PERF_MIDDLEWARE_DEBUG`.

Hujjatlar: **`PERF_NOTES.md`**, **`PERFORMANCE_REPORT.md`**.

### 22.7 ⚠️ Kritik performance tuzoqlari (esda tut)

1. **O'qituvchi `User.save()` `update_fields`siz** → `handle_rate_change` signali butun markaz davomatini qayta hisoblaydi (**94s / 24 550 query**). Har doim `save(update_fields=[...])`.
2. **`enrollment_start_date` memoizatsiyasiz** → dashboard render'da minglab bir xil query.
3. **Markaz bo'ylab per-o'quvchi loop** → 502.
4. **Worker-local cache** — 2 worker orasida TTL davomida nomuvofiqlik bo'lishi mumkin.
5. **Chat polling** — WebSocket yo'q; polling intervalini oshirib yubormang.

---

## 23. XAVFSIZLIK

### 23.1 Qatlamlar

| Qatlam | Mexanizm |
|---|---|
| Transport | HTTPS (Render), `SECURE_PROXY_SSL_HEADER`, `USE_X_FORWARDED_HOST` |
| Sessiya | `SESSION_COOKIE_SAMESITE=Lax`, prod'da `Secure` |
| CSRF | Django CSRF middleware; `CSRF_TRUSTED_ORIGINS` (chaqmoqapp.uz, *.onrender.com, localhost) |
| Login | `?next` ignore (`SecureLoginView`), brute-force throttle (identifier + IP) |
| RBAC | Whitelist middleware, blanket `/api/` skip **yo'q** |
| Tenant | Har query'da `center` filtri; IDOR testlari |
| Mobil token | Xom token DB'da saqlanmaydi (SHA-256 hash), 30 kun, max 8 sessiya |
| Bot API | `X-API-SECRET` (deterministik `SECRET_KEY` dan) |
| Click | MD5 imzo tekshiruvi, `service_id`/`merchant_id`/summa validatsiya |
| Magic login | Signed token + parol-hash bog'lanishi (bir martalik xarakter) |
| AI | Prompt injection himoyasi, kontekst faqat viewer huquqidan |
| Rate limit | `core/rate_limit.py` (AI, ba'zi API'lar) |
| Clickjacking | `XFrameOptionsMiddleware` |
| Xato monitoring | Sentry (`sentry-sdk[django]`) |

### 23.2 Xavfsizlik testlari

| Test | Nimani tekshiradi |
|---|---|
| `education/tests/test_idor_tenant.py` | Boshqa markaz obyektiga kirish mumkinmi |
| `education/tests/test_isolation.py` | Tenant izolyatsiyasi |
| `core/tests_rbac_api.py` | API'lar RBAC'dan o'tadimi |
| `core/tests_login_hardening.py` | Throttle ishlaydimi |
| `core/tests_mobile_token_ttl.py` | Token muddati/revoke |
| `accounts/tests_phone_unique.py` | Telefon unique constraint |
| `accounts/tests_magic_login.py` | Magic login xavfsizligi |
| `core/tests_tenant.py`, `tests_db_router.py` | Tenant kontekst va routing |

### 23.3 ⚠️ Diqqat talab qiladigan joylar

1. **`config/settings.py` da `DEBUG = True` hardcode** (`# ✅ Force Debug for Local Dev`). Production'da `settings_prod.py` `DEBUG=False` qiladi. **Lekin** agar `MODE`/`RENDER` env o'rnatilmasa — production'da DEBUG yoqilib ketadi. **Xatarli**.
2. **`Center.db_password`** ochiq matnda (kodda `TODO: хранить безопасно` izohi bor). Hozir ishlatilmaydi (`TENANT_DB_ROUTING_ENABLED=0`).
3. **`.env` fayl repo'da bor** (`.gitignore` da bo'lsa ham, tarixda qolgan bo'lishi mumkin) — 27-bo'limga qara.
4. `/test-db/`, `/test-center/` — diagnostika endpointlari **production'da ham ochiq**, URL ro'yxatining eng boshida.
5. Font Awesome CDN'dan yuklanadi (`cdnjs.cloudflare.com`) — offline/CSP muhitida ishlamaydi.

---

## 24. TEST STRATEGIYASI

### 24.1 Test inventari (86 fayl)

| App | Testlar |
|---|---|
| `education/tests/` (32) | `test_prorated_tuition`, `test_mid_month_prorated`, `test_payment_carryover_scenarios`, `test_qarzdorlar_multi_month_payment`, `test_removed_student_post_removal_debt`, `test_removed_students_visibility`, `test_student_payable_amount`, `test_student_group_transfer`, `test_group_transfer_verification`, `test_phase2_exam_workflow`, `test_phase3_internal_ranking`, `test_phase4_certificate_closure`, `test_exam_certificate_module`, `test_exam_telegram_reminder`, `test_hr_module`, `test_attendance_monitor`, `test_attendance_groups_search`, `test_lightning_persistence`, `test_idor_tenant`, `test_isolation`, `test_full_integration`, `test_debtor_price_and_redirect`, `test_group_payment_status_indicator`, `test_category_uniqueness`, `test_my_groups_theme`, `test_payment_excel_export`, `test_qarzdorlar_pagination`, `test_tolovlar_pagination`, `test_reset_center_to_april_debt`, `test_session_payment_fixes`, `test_student_status` |
| `core/` (15) | `tests`, `tests_tenant`, `tests_db_router`, `tests_tenant_db_foundation`, `tests_mobile_api`, `tests_mobile_token_ttl`, `tests_login_hardening`, `tests_rbac_api`, `tests_rate_limit`, `tests_subscription_lag`, `tests_dashboard`, `tests_dashboard_features`, `tests_backup_schedule`, `tests_bot_api`, `test_utils` |
| `accounts/` (6) | `tests`, `tests_magic_login`, `tests_phone_unique`, `tests_parent_telegram_link`, `tests_branch_requests`, `tests_game_admin` |
| `billing/` (2) | `tests`, `tests_tarif_v2` |
| `game/` (2) | `tests`, `tests_google` |
| `marketing/` (2) | `tests`, `tests_pricing_plan_io` |
| `store/`, `chaqmoq/` | `tests` |

### 24.2 Ishga tushirish

```bash
python manage.py test                                  # hammasi
python manage.py test education                        # bitta app
python manage.py test education.tests.test_prorated_tuition
python manage.py test education.tests.test_prorated_tuition.ClassName.test_method
```

### 24.3 ⚠️ Ma'lum test tuzoqlari

1. **Tartibga bog'liqlik:** ba'zi testlar boshqa testlardan keyin ishga tushsa yiqiladi (global state — `_CENTER_CACHE`, `_SLUG_CACHE`, `perf_cache`, `_LANG_CACHE`, `clear_group_schedule_cache`).
2. **Sana-eskirgan testlar:** hardcode qilingan sanalar (masalan "2026-04") vaqt o'tishi bilan yiqiladi. `freezegun` (`@freeze_time`) ishlatilishi kerak.
3. **Baseline solishtirish shart:** o'zgarish kiritishdan oldin **baseline worktree** da testlarni ishga tushirib, qaysi testlar allaqachon yiqilayotganini bilib olish kerak. Aks holda "mening o'zgarishim buzdi" deb noto'g'ri xulosa chiqadi.
4. **Flutter testlari:** `flutter_animate` pending timer + lazy `ListView` — "timer still pending" xatolari **mantiq xatosi emas**, test tuzilishi aybdor.

### 24.4 Smoke test

```bash
python manage.py smoke_test
python manage.py smoke_test --base-url https://chaqmoqapp.uz
python manage.py smoke_test --center-slug myschool
python manage.py smoke_test --username admin@example.com --password secret
python manage.py smoke_test --section auth|routing|billing|education|admin|api|all
python manage.py smoke_test --quick
```
456 sahifani bosib chiqadi, 500/502 xatolarni topadi.

---

## 25. DEPLOYMENT

### 25.1 Render.com konfiguratsiyasi (`render.yaml`)

```yaml
type: web
name: ProSkill-Chaqmoq
env: python
plan: standard          # 2GB / 1 CPU ($25). Dashboard'da upgrade qilingan —
                        # bu yerda ham 'standard' turishi SHART, aks holda
                        # blueprint sync 'starter'ga qaytaradi!
region: frankfurt
healthCheckPath: /health/

buildCommand: >-
  RENDER_BUILD_PHASE=1 pip install -r requirements.txt &&
  RENDER_BUILD_PHASE=1 python manage.py collectstatic --noinput &&
  (python manage.py migrate --noinput || echo migrate_skipped)

startCommand: ./start.sh
```

`RENDER_BUILD_PHASE=1` — build paytida `settings.py` production secret tekshiruvlarini yumshoq o'tkazib yuboradi (`DATABASE_URL` hali yo'q).

### 25.2 `start.sh` mantiqiy

```
Lokal (RENDER yo'q):
  bot 12s kechikib ishga tushadi (fon), keyin runserver 0.0.0.0:8000

Production:
  1. start_bot_delayed()  → 12s kutib telegram_bot/bot.py ishga tushadi
  2. gunicorn config.wsgi:application
       --bind 0.0.0.0:$PORT
       --workers 2 --threads 4 --preload
       --timeout 120 --graceful-timeout 30 --keep-alive 5
       --max-requests 2000 --max-requests-jitter 100
       --access-logfile - --error-logfile -
  trap cleanup: gunicorn to'xtaganda bot ham to'xtaydi
```

**Nega shunday:**
- Avval **gunicorn** portga bog'lanadi → health check tez javob beradi → cold-start 502 yo'q.
- Bot keyinroq (xotira + boot race).
- `--preload` → worker recycle'da Django qayta import qilinmaydi.
- `GUNICORN_MAX_REQUESTS` **kodda 2000 pastki chegara** bilan majburlanadi.

### 25.3 Muhit o'zgaruvchilari (to'liq)

**Django yadro**
| Kalit | Izoh |
|---|---|
| `SECRET_KEY` | Production'da **majburiy** (yo'q bo'lsa `RuntimeError`) |
| `MODE` | `local` / `render` / `production` |
| `ALLOWED_HOSTS` | Vergul bilan |
| `LANGUAGE_CODE` | `uz` |
| `TIME_ZONE` | `Asia/Tashkent` |
| `API_SECRET` | Bot ↔ Django (yo'q bo'lsa `SECRET_KEY` dan hosil qilinadi) |

**Ma'lumotlar bazasi**
| Kalit | Izoh |
|---|---|
| `DATABASE_URL` | Render avtomatik beradi. **Production'da yo'q bo'lsa `RuntimeError`** (sqlite'ga tushib qolmaslik uchun) |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_SSLMODE` | `MODE=render` uchun |
| `LOCAL_DB_ENGINE`, `LOCAL_DB_NAME` | Lokal (⭐ buzuq DB'ni chetlab o'tish uchun ishlatiladi) |
| `TENANT_DB_ROUTING_ENABLED` | `0` (o'chirilgan) |
| `TENANT_DB_CONN_MAX_AGE` | 60 |
| `TENANT_DB_AUTO_FILL_METADATA` | `0` |
| `DJANGO_DB_STATEMENT_TIMEOUT_MS` | 30000 |
| `DJANGO_DB_LOCK_TIMEOUT_MS` | 5000 |
| `DJANGO_DB_CONNECT_TIMEOUT` | 10 |

**Gunicorn**
`WEB_CONCURRENCY=2`, `GUNICORN_THREADS=4`, `GUNICORN_TIMEOUT=120`, `GUNICORN_GRACEFUL_TIMEOUT=30`, `GUNICORN_KEEPALIVE=5`, `GUNICORN_MAX_REQUESTS=2000`, `GUNICORN_MAX_REQUESTS_JITTER=100`

**Performance**
`SLOW_REQUEST_MS=800`, `SLOW_REQUEST_LOG_QUERIES=1`, `PERF_LOG_ALL=1`, `PERF_MIDDLEWARE_DEBUG=0`,
`CENTER_CACHE_TTL=15`, `CENTER_SLUG_CACHE_TTL=60`, `SUBSCRIPTION_BLOCK_CACHE_TTL=15`, `SUBSCRIPTION_CHECK_INTERVAL_SECONDS=120`

**Auth / mobil**
`MOBILE_ACCESS_TOKEN_DAYS=30`, `MOBILE_ACCESS_TOKEN_MAX_PER_USER=8`,
`LOGIN_MAX_FAILED_ATTEMPTS=8`, `LOGIN_THROTTLE_WINDOW_SECONDS=900`, `LOGIN_IP_MAX_FAILED_ATTEMPTS=40`,
`MOBILE_AUTH_DEBUG`

**Telegram**
`TELEGRAM_BOT_TOKEN` / `BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_BOT_USERNAME_FAMILY`,
`TELEGRAM_GROUP_ID`, `TELEGRAM_BACKUP_CHAT_ID`, `BACKUP_BOT_TOKEN`, `BACKUP_GROUP_ID`,
`ADMIN_TELEGRAM_IDS`, `TELEGRAM_BOT_ENABLED`, `BOT_INTERNAL_API_URL`, `BOT_API_PORT=8080`, `BOT_START_DELAY=12`,
`BACKUP_TIMEZONE`, `BACKUP_SEND_TIME=18:00`, `BACKUP_KEEP_DAYS=7`, `TELEGRAM_ZIP_MIN_SIZE_MB=8`,
`TELEGRAM_SEND_TIMEOUT_LARGE=180`, `TELEGRAM_SEND_RETRIES=2`,
`BACKUP_SCHEDULER_ENABLED=false`, `BOT_BACKUP_SCHEDULER_ENABLED=true`, `BACKUP_GDRIVE_ENABLED=false`

**To'lov**
`CLICK_SERVICE_ID`, `CLICK_MERCHANT_ID`, `CLICK_SECRET_KEY`, `CLICK_RETURN_URL`

**Billing**
`BILLING_GRACE_PERIOD_HOURS=72`, `BILLING_EXPIRY_WARN_DAYS=7`

**AI**
`GEMINI_API_KEY`, `GEMINI_MODEL`

**O'yin**
`GOOGLE_OAUTH_CLIENT_IDS` (vergul bilan, 4 ta ID), `GAME_SUPPORT_TELEGRAM=de_amirxon`

**Media**
`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`

**Lokal dev**
`LOCAL_DEV_HOST` (telefon bilan test uchun; `ipconfig getifaddr en0`), `LOCAL_DEFAULT_CENTER_SLUG`

### 25.4 Domenlar

- Production: `https://chaqmoqapp.uz`, `www.chaqmoqapp.uz`
- Render: `*.onrender.com`
- Cloudflare proxy orqali (real IP `X-Forwarded-For` dan)
- Lokal: `localhost:8000`, `127.0.0.1:8000`, LAN IP, `10.0.2.2` (Android emulator)

### 25.5 Deploy tartibi

```bash
# 1. Lokal test
python manage.py test
python manage.py smoke_test --quick

# 2. Migratsiya tekshiruvi
python manage.py makemigrations --check --dry-run

# 3. Git
git add -A && git commit -m "..." && git push

# 4. Render avtomatik deploy qiladi (blueprint sync)
#    buildCommand → collectstatic + migrate
#    startCommand → start.sh

# 5. Tekshirish
curl https://chaqmoqapp.uz/health/          # "OK"
python manage.py smoke_test --base-url https://chaqmoqapp.uz
```

---

## 26. MANAGEMENT BUYRUQLARI KATALOGI

### 26.1 `accounts`

| Buyruq | Vazifasi |
|---|---|
| `create_superadmin` | Superuser yaratish |
| `create_center` | Yangi markaz |
| `create_director` | Direktor |
| `create_bot_admin` | Telegram bot admini |
| `seed_demo_center` | Demo markaz |
| `seed_sales_demo` | ⭐ To'liq savdo demosi (`d@`/`m@`/`t@`, slug `demo-markaz`) |
| `reset_demo_center` | Demoni tozalash |
| `generate_student_link_codes` | `child_code` generatsiya |
| `reset_mobile_password` | Mobil parol tiklash |
| `diagnose_mobile_login` | Mobil login diagnostikasi |
| `filiallarni_tuzat`, `fix_branch_parent`, `fix_branch_subscriptions` | Filial tuzatishlari |

### 26.2 `education`

| Buyruq | Vazifasi |
|---|---|
| `close_month` | ⭐ Oyni yopish (reconcile + snapshotlar) |
| `generate_monthly_tuition` | Oylik `TuitionMonth` yozuvlarini yaratish |
| `mark_month_debtors`, `force_month_debtors`, `rebuild_month_debtors` | Qarzdorlar belgilash/tuzatish |
| `apply_monthly_rules` | Oylik chaqmoq qoidalari |
| `run_monthly_attendance_bonus` | Davomat bonusi |
| `backfill_lightning_history` | Chaqmoq tarixini to'ldirish |
| `notify_exam_reminders` | Imtihon eslatmalari |
| `regenerate_certificate_pdfs` | Sertifikat PDF'larini qayta yasash |
| `reconcile_removed_students` | Chiqarilgan o'quvchilarni tekshirish |
| `fix_over_allocations` | Ortiqcha taqsimlashni tuzatish |
| `fix_teacher_income_limit` | O'qituvchi daromad limitini tuzatish |
| `init_student_history` | `StudentGroupHistory` to'ldirish |
| `reset_center_to_april_debt`, `reset_june_payments` | Bir martalik tuzatish skriptlari (tarixiy) |

### 26.3 `core`

| Buyruq | Vazifasi |
|---|---|
| `backup_and_send`, `backup_databases`, `send_db_backups` | Backup |
| `restore_center_backup` | Tiklash |
| `configure_backup_bot`, `test_backup_send` | Backup sozlash/test |
| `gdrive_oauth_setup`, `test_gdrive_upload` | Google Drive |
| `notify_parents` | Ota-onalarga xabar |
| `send_daily_reports` | Kunlik hisobot |
| `smoke_test` | ⭐ 456-sahifa smoke harness |
| `show_tenant_db_config` | Tenant DB konfiguratsiyasini ko'rish |

### 26.4 `billing` / `chaqmoq` / `marketing` / `game`

| Buyruq | Vazifasi |
|---|---|
| `billing setup_plans` | Boshlang'ich tariflar |
| `billing seed_plan_features`, `seed_features_v2` | Feature'lar |
| `billing migrate_tariff_v2` | Tarif v2 migratsiyasi |
| `billing remap_legacy_overrides` | Legacy override'larni ko'chirish |
| `billing expire_subscriptions` | Muddati o'tgan obunalar |
| `chaqmoq process_lightning_rules` | Chaqmoq qoidalarini qayta ishlash |
| `marketing seed_landing`, `seed_marketing_data` | Landing kontenti |
| `game game_demo`, `game_oyinlar` | O'yin demo/katalog |
| `game google_tekshir` | Google OAuth tekshiruvi |

### 26.5 Kunlik/oylik cron tavsiyasi

```
Kunlik 18:00  → backup (bot scheduler orqali, hozir shunday)
Kunlik 09:00  → notify_exam_reminders
Kunlik 20:00  → process_lightning_rules
Kunlik 07:00  → expire_subscriptions
Oy 1-kuni     → generate_monthly_tuition
Oy 1-kuni     → close_month (o'tgan oy uchun)
Oy 1-kuni     → apply_monthly_rules, run_monthly_attendance_bonus
```

---

## 27. TEXNIK QARZ VA MA'LUM MUAMMOLAR

> Bu bo'lim halol. AI agent bu ro'yxatni bilishi kerak, aks holda "nega bu shunday yozilgan?" deb noto'g'ri refaktor qiladi.

### 27.1 Kod tuzilishi

| Muammo | Tafsilot |
|---|---|
| **`education/views/legacy.py` — 12 718 qator** | Barcha asosiy web view'lar bitta faylda. `__init__.py` dan re-export qilinadi. **Butunlay refaktor qilishga urinmang** — faqat kerakli funksiyani tahrirlash |
| **`core/mobile_api.py` — 4528 qator** | Butun mobil API bitta faylda |
| **`core/views.py` 3585 + `dashboard_views.py` 3314** | Juda katta view fayllar |
| **Dublikat URL nomlari** | `group_edit` / `group_edit_en`, `group_delete` / `group_delete_en`, `my_groups` uchun 3 xil URL (`mening-guruhlarim`, `guruhlar/meniki`, `mening_guruhlarim`) |
| **Ikki imlo** | `kurs_narxi` (Group) va `kurs_narhi` (Enrollment) |
| **Legacy modellar** | `Oquvchi`, `Dars`, `OylikHisobot`, `Student`, `GroupStudent`, `AttendanceHistory` — ishlatilmaydi, lekin o'chirilmagan |
| **`Attendance` da 3 xil holat** | `status` (yangi), `present` (bool, eski), `forced` (eski) — barchasi hali o'qiladi |
| **Ikkita filial mexanizmi** | `Center.parent_center` va `accounts.Branch` |
| **`core.GameSession` vs `game.GameSession`** | Bir xil nomli ikki model |
| **`SubscriptionMiddleware`** | Yozilgan, lekin `MIDDLEWARE` da yo'q; `RBAC_DOCUMENTATION.md` eskirgan |

### 27.2 Repozitoriya

| Muammo | Tafsilot |
|---|---|
| **`.git` = 807MB** | Tarixga commit qilingan DB fayllari sabab. 2026-07-17 da junk untrack qilindi (staged, commitsiz), **history rewrite hali kutilyapti** (`git filter-repo` yoki BFG) |
| **Repo'da bo'lmasligi kerak fayllar** | `db.sqlite3` (10.7MB) va 3 ta `.bak`, `data.json` (5.4MB), `backup_before_saas.json`, `.apk`/`.ipa`/`.aab`, `venv/`, `staticfiles/`, PNG'lar, `desktop/` artefaktlari, `_app_archive/`, `_ui_archive/`, `director-dashboard-pro/`, `lumina-director/`, `scratch/` |
| **`.env` repo'da** | `.gitignore` da bo'lsa ham tarixda qolgan bo'lishi mumkin → **SECRET_KEY/token'larni rotatsiya qilish kerak** |

### 27.3 Lokal dev muhiti

| Muammo | Yechim |
|---|---|
| **`db.sqlite3` buzuq** | Yetim FK'lar bor, migratsiya to'xtaydi. **Yechim:** `LOCAL_DB_NAME=db_dev.sqlite3` bilan alohida baza ishlatish |
| **`DEBUG = True` hardcode** | `config/settings.py:19`. Production'da `settings_prod` tuzatadi, lekin env noto'g'ri bo'lsa xatarli |
| **Bir nechta dev DB** | `db_game_dev.sqlite3`, `db_hrpreview.sqlite3` — turli feature'lar uchun |

### 27.4 Hozirgi ish (tugallanmagan)

| Ish | Holat |
|---|---|
| **Davomat nazorati** | Web tayyor (commitsiz), Flutter tomoni qolgan |
| **Tarif v2** | Data-driven matritsa (`/platform/plans/matritsa/`) — ishlaydi, migratsiya davom etadi |
| **Per-tenant DB** | Kod tayyor, `TENANT_DB_ROUTING_ENABLED=0` |
| **Push notification** | Yo'q (faqat lokal notification + Telegram) |
| **WebSocket chat** | Yo'q (polling) |
| **Chaqmoq Game** | Ishlaydi, alohida Flutter loyiha ham bor (`~/Desktop/ChaqmoqGame`) |
| **Git holati** | `main` branch, ish daraxti toza. Ba'zi commit xabarlari sifatsiz (`fd`, `f`, `sd`) |

### 27.5 Nomuvofiq commit xabarlari

Repo tarixida `fd`, `f`, `sd`, `toliq muommolar` kabi xabarlar bor. Yangi commit'lar **conventional commits** uslubida (`feat(...)`, `fix(...)`, `chore(...)`, `docs(...)`) o'zbekcha tavsif bilan yozilsin — oxirgi commit'lar shunday.

---

## 28. TERMINOLOGIYA LUG'ATI (to'liq)

| O'zbekcha / kodda | Inglizcha | Izoh |
|---|---|---|
| markaz | center / tenant | `Center` |
| filial | branch | `Center.parent_center` yoki `Branch` |
| guruh | group | `Group` |
| bo'lim / kategoriya | category | `Category`, `category_obj` |
| kurs shabloni | course template | `CourseTemplate` |
| o'quvchi | student | `User(role="student")` |
| o'qituvchi | teacher | `User(role="teacher")` |
| ustoz | teacher | `StaffProfile.Role.TEACHER` |
| xodim | staff / employee | `StaffProfile` |
| ota-ona | parent | `User(role="parent")` |
| direktor | director | `User(role="director")` |
| kiritish / yozilish | enrollment | `Enrollment` |
| davomat | attendance | `Attendance` |
| dars | lesson | — |
| dars jadvali | schedule | `GroupSchedule` |
| to'lov | payment | `Payment` |
| oylik hisob | tuition month | `TuitionMonth` |
| taqsimlash | allocation | `PaymentAllocation` |
| qarz / qarzdor | debt / debtor | `debt = max(0, fee - paid)` |
| kurs narxi | course price | `kurs_narxi` / `kurs_narhi` |
| oy dars soni | monthly lessons | `oy_dars_soni` |
| o'qituvchi foizi | teacher percent | `oqituvchi_foiz`, `oqituvchi_foizi` |
| daromad | income | `TeacherIncome` |
| maosh / oylik | salary | `SalaryPayout`, `TeacherSalarySnapshot` |
| xarajat | expense | `Expense`, `CenterExpense` |
| oyni yopish | close month | `FinancialMonth.is_closed` |
| chaqmoq | lightning (points) | `Ledger`, `LightningHistory` |
| qoida | rule | `Rule` |
| jarima | penalty | `lightning_penalty` |
| bonus | bonus | `lightning_bonus` |
| reyting | rating / ranking | `reyting` |
| imtihon | exam | `ExamSession`, `ExamResult` |
| sertifikat | certificate | `CertificateRecord` |
| do'kon | store | `Product`, `Sale` |
| so'rov | request | `PurchaseRequest`, `BranchRequest`, `TarifSorovi` |
| mahsulot | product | `Product` |
| manba | source | `Manba` (lead qaydan keldi) |
| yo'nalish | direction / subject | `Yonalish` |
| lead / ariza | lead | `Lead` |
| sinov darsi | trial lesson | `TrialLesson` |
| tarif | plan | `SubscriptionPlan`, `game.Tarif` |
| obuna | subscription | `CenterSubscription`, `game.Obuna` |
| bildirishnoma | notification | `Notification` |
| axlat qutisi | trash | `/trash/` |
| jon | life | O'yin |
| duel | duel | O'yin |
| motor | engine | O'yin mexanikasi |
| yoriqnoma | instructions | O'yin qoidasi matni |
| navbat | queue | `DuelQueue` |
| qulf | cooldown | `GameCooldown` |
| liga | league | bronza/kumush/oltin/olmos |
| mahorat | skill | Robot `maxorat` (0.5–0.9) |

---

## 29. ROADMAP (kelajak ishlar)

### 29.1 Yaqin muddat

1. **Davomat nazoratini Flutter'ga qo'shish** (web tayyor).
2. **Git history rewrite** — `.git` 807MB → ~50MB (`git filter-repo`), keyin secret rotatsiya.
3. **Sana-bog'liq testlarni `freezegun` ga o'tkazish** — barqaror CI.
4. **`DEBUG = True` hardcode'ni olib tashlash** — env bilan boshqarish.
5. **Push notification (FCM)** — hozir faqat lokal + Telegram.
6. **`education/views/legacy.py` ni asta-sekin bo'lish** — yangi view'lar alohida modulga, legacy'ga faqat tahrir.

### 29.2 O'rta muddat

7. **Per-tenant PostgreSQL** yoqish (`TENANT_DB_ROUTING_ENABLED=1`) — katta mijozlar uchun.
8. **WebSocket chat** (Django Channels yoki tashqi servis).
9. **SMS integratsiyasi** (PREMIUM tarifda e'lon qilingan, lekin hali yo'q).
10. **API'ni to'liq DRF + OpenAPI** ga o'tkazish — mobil kontraktni avtomatik hujjatlash.
11. **Ko'p tilli dashboard** (hozir faqat marketing sayt tarjima qilingan).

### 29.3 Uzoq muddat

12. **Chaqmoq Game'ni alohida mahsulot** sifatida chiqarish (o'z brendi, o'z billing'i).
13. **Marketplace** — o'quv markazlari orasida kurs/kontent almashinuvi.
14. **AI o'qituvchi yordamchisi** — dars rejasi, uy vazifasi generatsiyasi.
15. **Public API** — tashqi integratsiyalar uchun (token bilan).

---

## 30. AI AGENT (GEMINI) UCHUN ISH REGLAMENTI

### 30.1 Har qanday ishdan oldin

```
1. Foydalanuvchi bilan O'ZBEK tilida gaplash.
2. Qaysi faylni tahrirlash kerakligini aniqla (bu hujjatning 4-bo'limi — xarita).
3. Faylni o'qi. Taxmin qilma.
4. Tegishli servisni top: biznes logika services/ da bo'lishi kerak, view'da emas.
5. Test bor-yo'qligini tekshir. Bor bo'lsa — oldin ishga tushirib baseline ol.
```

### 30.2 Qat'iy qoidalar

| # | Qoida |
|---|---|
| 1 | **Ma'lumot yo'qolishi mumkin bo'lgan amallarni bajarma.** `delete()`, `flush`, `migrate --fake`, `reset_*` buyruqlar — faqat foydalanuvchi aniq so'rasa va tasdiqlasa. |
| 2 | **Soft delete** — `Model.objects` (tirik) va `Model.all_objects` (hammasi) farqini tushun. Qarz hisoblashda `all_objects` **ataylab** ishlatiladi. |
| 3 | **Tenant filtri** — har query'da `center`. Filtrsiz query = IDOR. |
| 4 | **`update_fields`** — `User.save()` chaqirganda **har doim** `update_fields=[...]` ber. Aks holda 94 sekundlik signal zanjiri ishga tushadi. |
| 5 | **N+1 yo'q** — markaz bo'ylab per-o'quvchi loop yozma. `calculate_enrollment_debt_snapshots` va preload helper'larni ishlat. |
| 6 | **`deleted_reason` himoyalangan prefikslari** — `manual_cleared`, `cleanup_*`, `move_future_*`, `reset_*`, `user_edit*` bo'lgan `TuitionMonth`ga tegma. |
| 7 | **Yopilgan oy** (`FinancialMonth.is_closed`) — fee o'zgartirma, allocation yozma. |
| 8 | **Chiqarilgan o'quvchi** faqat `last_lesson_date` gacha hisoblanadi. |
| 9 | **O'qituvchi maoshi** asl `kurs_narhi` dan hisoblanadi (o'quvchi chegirmasi ta'sir qilmaydi). |
| 10 | **URL tartibi** (`config/urls.py`) — i18n pattern legacy'dan oldin, slug regex non-capturing, `/api/mobile/game/` core'dan oldin. Tartibni o'zgartirma. |
| 11 | **Light mode** tuzatishlari faqat `static/css/light-mode-fixes.css` ga. |
| 12 | **O'yin chaqmog'i** markaz chaqmog'idan alohida. Aralashtirma. |
| 13 | **Click to'lov** — markaz obunasi va o'yin tariflari **alohida** oqim. `billing/click_views.py` ga tegishda ehtiyot bo'l (tirik pul). |
| 14 | **Flutter provider** — `didChangeDependencies` da `load()` chaqirma, `addPostFrameCallback` ishlat. |
| 15 | **Telegram bot i18n** — tugma matni va filtr **bitta `BTN` dict**dan olinadi. Faqat bittasini o'zgartirsang handler ishlamay qoladi. |
| 16 | **Deploy / git push / migratsiya** — faqat foydalanuvchi so'rasa. |

### 30.3 Yangi feature qo'shish cheklisti

```
[ ] Model kerakmi? → center FK + SoftDeleteMixin (kerak bo'lsa) + indekslar
[ ] Migratsiya: python manage.py makemigrations <app>
[ ] Biznes logika → <app>/services/<name>.py (view'ga yozma)
[ ] View → tegishli fayl. Dekoratorlar: @login_required + @require_feature("...")
[ ] URL → <app>/urls.py. Nomi unikal bo'lsin
[ ] RBAC → core/middleware_rbac.py ROLE_PERMISSIONS ga qo'sh (namespace yoki aniq nom)
[ ] Feature gate → billing/plan_tiers.py SIDEBAR_FEATURE_GATES + PlanFeature yozuvi
[ ] Shablon → base.html dan meros, sidebar'ga band qo'sh
[ ] Mobil kerakmi? → core/mobile_api.py + core/mobile_urls.py + Flutter service/provider/screen
[ ] Test → <app>/tests*.py yoki education/tests/test_*.py
[ ] Bu hujjatni yangila (8/9/14-bo'limlar)
```

### 30.4 Debug cheklisti

| Muammo | Qaraydigan joy |
|---|---|
| 502 | Render log → `[CRITICAL]`/`[N+1?]` teglari, gunicorn timeout |
| Qarz noto'g'ri | `calculate_enrollment_debt_snapshots` → `TuitionMonth` fee va `PaymentAllocation` |
| O'qituvchi oyligi noto'g'ri | `HistoricalFinanceService._build_dynamic_teacher_salary` + `teacher_monthly_financials` |
| Rol ko'rmasligi kerak sahifani ko'radi | `core/middleware_rbac.py ROLE_PERMISSIONS` |
| Feature qulflanmagan/qulflangan | `billing.services.center_has_feature` → `CenterFeatureOverride` → `PlanFeatureRule` |
| Markaz aniqlanmayapti | `TenantMiddleware` → session / URL slug / user.center; cache TTL |
| Mobil 401 | `MobileAccessToken` (revoke/expired), `X-Center-Slug` |
| Chaqmoq berilmayapti | `Rule.can_<role>`, `Center.max_daily_lightning`, `DailyLightningSetting` |
| Bot javob bermayapti | `Center.telegram_bot_enabled`, `BOT_TOKEN`, `API_SECRET`, bot process holati |
| AI javob bermayapti | `GEMINI_API_KEY`, `Center.ai_enabled`, rate limit, `source` maydoni |
| Click to'lov o'tmayapti | Imzo (MD5), `CLICK_SECRET_KEY`, `merchant_trans_id`, `PaymentTransaction` |
| Test yiqilyapti | Tartib bog'liqligi? Sana hardcode? Baseline bilan solishtir |

### 30.5 Foydali buyruqlar

```bash
# Django shell (shell_plus — barcha modellar avtomatik import)
python manage.py shell_plus

# URL'larni ko'rish
python manage.py show_urls | grep talim

# Migratsiya holati
python manage.py showmigrations
python manage.py makemigrations --check --dry-run

# Tenant DB konfiguratsiyasi
python manage.py show_tenant_db_config

# Smoke test
python manage.py smoke_test --quick

# Sekin so'rovlarni topish (log'dan)
grep -E "CRITICAL|N\+1|HIGH-Q" render.log

# Lokal ishga tushirish (buzuq DB'ni chetlab)
LOCAL_DB_NAME=db_dev.sqlite3 python manage.py runserver 0.0.0.0:8000
```

---

## ILOVA A — URL XARITASI (qisqa ma'lumotnoma)

```
PUBLIC
  /                              marketing bosh sahifa
  /about|features|pricing|demo|resources|support|vacancies|privacy|terms|data-deletion/
  /uz/... /ru/... /en/           ko'p tilli marketing
  /robots.txt  /sitemap.xml  /health/

AUTH  (barchasi /hisob/login/ ostida — accounts/auth_urls.py)
  /hisob/login/                          SecureLoginView   name=login
  /login/                                alias             name=login_alias
  /logout/
  /hisob/login/k/<token>/                magic login       name=magic_login
  /hisob/login/parol-ornatish/           parol o'rnatish    name=magic_set_password
  /hisob/login/parolni-tiklash/          forgot_password_init
  /hisob/login/parolni-tiklash/tanlash/  forgot_password_verify_choice
  /hisob/login/parolni-tiklash/tanlash-tasdiqlash/  forgot_password_confirm_choice
  /hisob/login/parolni-tiklash/tasdiqlash/          forgot_password_verify
  /hisob/login/parolni-tiklash/yangi/               forgot_password_set
  /hisob/login/phone-kirish/             phone_login_init
  /hisob/login/telegram-boglash/         connect_telegram
  /hisob/login/telegram-link-status/     telegram_link_status

BOT INTERNAL API  (X-API-SECRET bilan, /hisob/login/ ostida — RBAC skip qiladi)
  bot-user-status/  bot-user-details/  bot-parent-connect/  bot-unlink-telegram/
  bot-admin-dashboard/  bot-app-adoption/  bot-centers/  bot-center-toggle/
  bot-center-detail/  bot-finance/  bot-linked-users/  bot-broadcast-list/
  bot-excel-export/  bot-manage-admins/  bot-settings/  bot-parent-reports-data/
  bot-dashboard/  bot-notification-settings/  bot-store-purchase-request/
  /api/v1/auth/link-telegram/

SUPERADMIN
  /platform/                     dashboard
  /platform/centers|center/*     markazlar
  /platform/plans/matritsa/      tarif × feature matritsasi
  /platform/promos|plans/        tarif/promo UI
  /platform/bot/                 bot paneli
  /platform/filiallar/           filial so'rovlari
  /platform/game/                o'yin boshqaruvi
  /platform/marketing/           CMS
  /platform/api/*                JSON API'lar

ILOVA (tenant — /<slug>/ prefiksi bilan ham ishlaydi)
  /                              rolga mos bosh sahifa
  /boshqaruv/                    direktor paneli + AI
  /dashboards/*                  10 ta dashboard
  /stat/managers|teachers|students|parents|products|requests|ledger/
  /teachers/*  /parents/*  /user/*  /students/*
  /notifications/*               bildirishnomalar
  /trash/*                       axlat qutisi
  /chat/  /chat/<group_id>/      guruh chat
  /games/*                       web mini-o'yinlar
  /permissions/*                 rol ruxsatlari
  /api/*                         web AJAX API'lar

  /talim/                        EDUCATION
    guruhlar/*  guruh/<pk>/*     guruhlar
    tolovlar/*  tolov/*          to'lovlar
    qarzdorlar/                  qarzdorlar
    attendance/*                 davomat
    exam/*                       imtihon
    certificates/*               sertifikat
    teacher-salary/*             o'qituvchi oyligi
    mening-guruhlarim/  daromadim/
    finance/close-month|month-preview/
    student/<id>/*  kiritish/<id>/*
    kurslar/*  hr/  schedule/*

  /chaqmoq/                      CHAQMOQ
    reyting/  berish/  mening/  rules/*  student/<pk>/

  /do'kon/                       STORE
    mahsulot/<pk>/*  so'rovlar/*  product/*
    leads/*  api/leads/*  api/lead-groups/*
    expenses/*  payment-methods/*

  /hisob/                        ACCOUNTS (tenant)
    profil/  qoshish/  user/<pk>/edit/  talaba/<id>/  oqtuvchi/<id>/
    my-centers/  switch-center/  branch-request/

  /hisob/billing/                BILLING
    plans/  blocked/  order/*  requests/<pk>/approve|reject/
    api/plans|upgrade-preview|current-subscription|payment-status/

TO'LOV (webhook)
  /click/prepare|complete|webhook/       markaz obunasi
  /click/game/prepare|complete/          o'yin tariflari
  /payment/success|cancel/

MOBIL API
  /api/mobile/*                  asosiy (Bearer)
  /api/mobile/game/*             o'yin (Bearer)

ADMIN / DOCS
  /admin/                        Django admin (jazzmin)
  /api/schema|docs|redoc/        OpenAPI
```

---

## ILOVA B — HUJJATLAR RO'YXATI

| Fayl | Mazmuni |
|---|---|
| **`CHAQMOQAPP_TZ.md`** | ⭐ **Bu hujjat** — to'liq TZ / bilim bazasi |
| `README.md` | Qisqa tanishtiruv |
| `CHAQMOQAPP_MASTER_PROMPT.md` | Platformani 0 dan qayta qurish uchun prompt |
| `RBAC_DOCUMENTATION.md` | RBAC arxitekturasi (middleware ro'yxati **eskirgan**) |
| `PERF_NOTES.md` | Performance tuning tavsiyalari |
| `PERFORMANCE_REPORT.md` | Performance audit hisoboti |
| `RESTORE_GUIDE.md` | ⭐ Backup'dan tiklash — panik paytda o'qiladigan qo'llanma |
| `BACKUP_TELEGRAM.md` | Telegram backup sozlamalari |
| `GOOGLE_SETUP.md` | Google OAuth (o'yin) + Drive sozlash |
| `MOBILE_DEPLOY_SETUP.md` | Mobil ilova reliz jarayoni |
| `DESIGN_PROMPT.md` | Dizayn tizimi tavsifi |
| `billing/SUBSCRIPTION_INTEGRATION.md` | Obuna integratsiyasi |
| `.env.example` | ⭐ Barcha muhit o'zgaruvchilari |

---

## XULOSA

**ChaqmoqApp** — 122 000 qatorli Django monolit + Flutter mobil ilova + 3 Telegram bot + AI qatlami. 8 app, ~120 model, 600+ endpoint, 86 test fayli.

**Eng qimmatli va eng nozik qism:** `education/services/tuition.py` — narxlash, qarz va to'lov taqsimlash. Bu yerda har bir qoida real pulni anglatadi.

**Eng katta xatar:** N+1 query'lar (502) va tenant filtrini unutish (IDOR).

**Eng katta texnik qarz:** `education/views/legacy.py` (12 718 qator) va 807MB `.git`.

**Eng muhim qoida:** *ma'lumot yo'qolishi qabul qilinmaydi.*

---

*Hujjat oxiri. Savol bo'lsa — mos bo'limga qaytib qara, keyin kodni o'qi, keyin so'ra.*
