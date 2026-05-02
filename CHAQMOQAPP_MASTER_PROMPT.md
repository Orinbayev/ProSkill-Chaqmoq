# ChaqmoqApp Platformasini 0 dan yaratish uchun master prompt

Quyidagi prompt ChaqmoqApp platformasini boshidan ishlab chiqish uchun mo'ljallangan. Uni boshqa AI coding agentga, senior full-stack developerga yoki product/engineering jamoasiga berish mumkin. Maqsad: mavjud ChaqmoqApp konsepsiyasini to'liq SaaS o'quv markaz CRM platformasi sifatida qayta qurish.

---

## Copy-paste qilinadigan asosiy prompt

Sen senior full-stack architect, product engineer va UI/UX engineer sifatida ishlaysan. Menga "ChaqmoqApp" nomli o'quv markazlari uchun professional SaaS platformani 0 dan yaratib ber. Platforma oddiy landing page emas, balki haqiqiy ishlab turgan web CRM, billing tizimi, mobil API, Flutter mobil ilova va Telegram bot integratsiyasiga ega to'liq ekotizim bo'lishi kerak.

Asosiy til: Uzbek Latin. Qo'shimcha tillar: Russian va English marketing sahifalari uchun. Dizayn yo'nalishi: web dashboardlarda premium dark glassmorphism va compact admin UI; ota-ona mobil ilovasida light soft-blue uslub; o'quvchi mobil ilovasida dark teal-forward glassmorphism.

Texnik stackni quyidagicha qur:

- Backend: Python 3.x, Django 5, Django templates, Django REST Framework, drf-spectacular Swagger/OpenAPI.
- Database: local development uchun SQLite, production uchun PostgreSQL.
- Static/media: WhiteNoise, Cloudinary yoki local media storage.
- Frontend web: Django templates, modern CSS tokens, minimal vanilla JavaScript, responsive layout.
- Mobile: Flutter + Dart, Provider state management, Dio API client, secure token storage, Material 3.
- Telegram bot: aiogram 3, internal API client, role-based menus.
- Payments: Click integration uchun prepare/complete/webhook flow.
- Exports/documents: openpyxl Excel export, ReportLab PDF receipts/certificates.
- Deployment: Gunicorn, Render-compatible config, env-based settings.

Platformani modul-modul qilib, production-quality tarzda qur. Har bir modulda tenant isolation, RBAC, soft delete, audit, loading/empty/error states, tests va aniq URL/API endpointlar bo'lsin.

---

## Product ta'rifi

ChaqmoqApp - o'quv markazlari faoliyatini to'liq avtomatlashtiradigan SaaS platforma. U quyidagilarni boshqaradi:

- markazlar va filiallar;
- direktor, manager, o'qituvchi, o'quvchi, ota-ona rollari;
- guruhlar, kurslar, dars jadvali va xonalar;
- o'quvchi ro'yxati, guruhga yozilish va transfer;
- davomat;
- oylik to'lov, qarzdorlik, o'qituvchi ulushi va moliyaviy hisobot;
- Chaqmoq ballari, reyting va gamification;
- lead CRM, sinov dars va leadni studentga aylantirish;
- ichki do'kon, mahsulotlar va Chaqmoq bilan xarid;
- SaaS tariflar, promo-kod, Click orqali to'lov va subscription limitlari;
- marketing sayti va superadmin marketing CMS;
- mobil ilova va Telegram bot xabarnomalari.

---

## Rollar va huquqlar

Rollar:

- Superadmin: butun platformani boshqaradi, markazlar yaratadi, billing/tariflarni boshqaradi, marketing CMS, demo leadlar, subscription requestlar, filial so'rovlarini ko'radi.
- Director: o'z markazi va filiallarini boshqaradi, dashboard, moliya, guruhlar, staff, o'quvchilar, billing, CRM, store, Chaqmoq qoidalari va hisobotlarga kiradi.
- Manager: markaz ichida operatsion ishlarni qiladi: o'quvchi qo'shish, lead, to'lov, davomat nazorati, do'kon so'rovlarini tasdiqlash, xabar yuborish. Manager huquqlari markaz sozlamasi bilan cheklanadi.
- Teacher: o'z guruhlarini, davomatni, o'quvchi progressini, imtihon natijalarini, Chaqmoq berishni va o'z daromadini ko'radi.
- Student: o'z dashboardi, Chaqmoq balansi, reytingi, davomat, to'lovlar, do'kon, xabarlar va profilini ko'radi.
- Parent: farzandlarini child code orqali bog'laydi, farzand dashboardi, davomat, to'lov, progress, xabarlar, profil va notification sozlamalarini boshqaradi.

Xavfsizlik talablari:

- Login email yoki telefon orqali bo'lsin.
- `?next=` orqali permission bypass bo'lmasin; login keyin har doim role-based dashboardga redirect qilsin.
- Har bir requestda RBAC middleware URL nomi va user role bo'yicha ruxsatni tekshirsin.
- Tenant isolation: foydalanuvchi faqat o'z center ma'lumotlarini ko'rsin.
- Director bir nechta markazga ruxsat olishi mumkin, sessionda active center tanlanadi.
- Filiallar root center subscriptionidan foydalanadi.
- Student/parent/teacher bloklangan subscription paytida cheklangan kirishga ega bo'lsin.

---

## Multi-tenant arxitektura

Asosiy model: `Center`.

Center maydonlari:

- name, slug, address, phone;
- director_telegram_id;
- status: ACTIVE, BLOCKED, ARCHIVED;
- plan, max_users, max_groups, max_students, capacity_limit;
- payment_day, monthly_price, trial_ends;
- features JSON;
- max_daily_lightning, max_daily_deduction;
- donation_enabled, donation_card_number, donation_card_holder, donation_qr_image;
- promo_code, discount_amount, discount_percent, promo_start, promo_end;
- manager_can_access_trash;
- manager_can_add_student, manager_can_remove_student;
- teacher_can_add_student, teacher_can_remove_student;
- is_system, is_demo;
- parent_center for filial/root hierarchy;
- DB metadata fields for future per-tenant PostgreSQL database support.

URL patterns:

- Public marketing: `/`
- Platform superadmin: `/platform/`
- Tenant login: `/hisob/login/`
- Slug-prefixed tenant: `/<center_slug>/...`
- Center scoped login/billing: `/c/<center_slug>/hisob/login/`, `/c/<center_slug>/hisob/billing/`
- Core app: `/`
- Education: `/talim/`
- Chaqmoq: `/chaqmoq/`
- Store/CRM: `/do'kon/`
- Billing: `/hisob/billing/`
- Mobile API: `/api/mobile/...`
- API docs: `/api/docs/`, `/api/redoc/`

Middleware:

- TenantMiddleware: session active center, user center fallback, slug detection, request.center binding, center cache, subscription status check.
- RoleBasedAccessMiddleware: role whitelist, wildcard app namespace support.
- MobileApiCorsMiddleware: local Flutter/web preview CORS for `/api/mobile/`.

---

## Accounts va user management

Custom `User` model:

- username ishlatilmaydi;
- email unique login;
- phone_number login uchun;
- telegram_id, telegram_username, is_telegram_linked;
- parent_telegram_id, parent_telegram_username, parent_telegram_linked_at;
- reset_code, reset_code_expire_at, reset_code_used, reset_attempts;
- avatar;
- ism, familya, otchestvo;
- telefon1, telefon2;
- birth_date, gender, passport_id, jshr, address;
- lavozim;
- role;
- center;
- gmail;
- chaqmoq balance;
- oqituvchi_foizi;
- is_archived, archived_at, is_demo_user;
- children ManyToMany self for parent-to-student;
- child_code format like `CHQ-123456`, auto-generated for student.

Account funksiyalari:

- Secure login, logout, password reset code flow.
- Email/phone authentication backend.
- User CRUD: director/manager/teacher/student/parent.
- Student/teacher detail pages.
- Excel import/export for users/students.
- Student archive, restore, hard delete.
- Parent create/edit/delete.
- Parent child link status, link token creation, reminder.
- User activity logging: IP, user agent, device info.
- Bot admin va bot settings.
- Admin audit log.
- Director multi-center access.
- Branch request: director filial so'raydi, superadmin Telegram orqali approve/reject qiladi.
- Branch CRUD and branch stats.

---

## Dashboardlar

Dashboardlar role-based bo'lsin:

- Director/Manager main dashboard.
- Teacher dashboard.
- Student dashboard.
- Parent dashboard.
- Guest/dashboard fallback.

Director dashboard bo'limlari:

- Boshqaruv overview.
- Financial dashboard.
- Student performance dashboard.
- Teacher performance dashboard.
- Groups dashboard.
- Billing dashboard.
- Marketing dashboard.
- Inventory dashboard.
- Analytics dashboard.

Har bir dashboardda:

- date range filter;
- branch filter;
- KPI cards;
- trend charts;
- table summaries;
- empty/error/loading states;
- API endpoint with JSON payload.

KPI misollar:

- tushum, xarajat, foyda;
- faol studentlar;
- yangi studentlar;
- qarzdorlik;
- davomat foizi;
- o'qituvchi kutilgan daromadi;
- guruhlar bandligi;
- lead conversion;
- store/inventory activity;
- billing subscription holati.

Director AI chat:

- Center scoped chat session.
- One session per center/user.
- Chat messages: user/assistant role, content, metadata.
- Launcher position saqlansin.
- Dashboard konteksti asosida maslahat bera olsin.

---

## Education moduli

### Courses, categories va groups

Category:

- name, center, icon, description, image;
- soft delete;
- unique per center.

Group:

- center, branch;
- nom, izoh;
- category legacy: lang/it;
- category_obj;
- oqituvchi;
- kurs_narxi, oqituvchi_foiz, oy_dars_soni, max_students;
- course_start_date, duration_months, lessons_per_week, estimated_end_date;
- schedule_estimation_note, estimated_end_date_manual;
- is_archived, is_closed, closed_at, closed_by.

GroupSchedule:

- group, weekday, start_time, end_time, room;
- unique group + weekday + start_time;
- weekly schedule view;
- teacher schedule view;
- schedule conflict check API.

Group funksiyalari:

- group create/edit/delete/archive;
- group detail;
- students list;
- add student to group;
- bulk remove;
- category detail;
- groups by category;
- groups hub;
- group schedule management;
- max students validation;
- teacher availability bilan moslik.

### Enrollment

Enrollment studentni groupga bog'laydi:

- group, course, student, center;
- kurs_narhi, oqituvchi_foiz;
- monthly_price, monthly_lessons;
- joined_at, lesson_pattern;
- active_lessons_count;
- remaining_lessons_override;
- last_lesson_date;
- paid_amount;
- pricing_type: full, prorated, custom;
- is_active, is_deferred;
- student_payable_amount;
- jami_tolangan.

Enrollment funksiyalari:

- groupga student qo'shish;
- pricing snapshot;
- prorated tuition calculation;
- lesson pattern: automatic/group, even, odd, daily;
- remaining lessons override;
- student payable amount course price dan katta bo'lmasin;
- enrollment edit/delete;
- remove/leave/defer;
- transfer student to another group;
- StudentGroupHistory and StudentGroupTransfer audit.

### Davomat

Attendance:

- group, student, teacher, center;
- date;
- status: present, absent_excused, absent_unexcused;
- present backward-compatible bool;
- forced bool;
- created_by.

Davomat funksiyalari:

- group rollcall;
- attendance today;
- toggle cell API;
- attend all students;
- force absent/present;
- monthly attendance view;
- group month attendance export;
- attendance summary for mobile;
- absence types and colors;
- AttendanceHistory;
- DailyLightningRecord.

### To'lov va moliya

Payment:

- enrollment, student, group, center;
- payment_type: cash, card, mixed;
- cash_amount;
- card_amount, card_rate, card_currency;
- summa auto calculated;
- note;
- paid_date, paid_time;
- created_by;
- soft delete.

TuitionMonth:

- enrollment, month, fee_amount;
- one per enrollment per month.

PaymentAllocation:

- payment, tuition_month, amount;
- payment qaysi oylarni yopganini saqlaydi.

FinancialMonth:

- center, year, month, is_closed, closed_at, closed_by.

MonthlyFinanceSnapshot:

- total_income, total_expense, center_profit, student_count, attendance_rate.

Finance funksiyalari:

- create/update/delete payment;
- payment history by student and enrollment;
- PDF receipt;
- payment export XLSX;
- student payments PDF summary;
- qarzdorlar page;
- tuition preview;
- month preview;
- close finance month;
- historical snapshots;
- reset/fix income commands;
- mixed payment support;
- deleted payment allocations hisobga olinsin;
- payment bonus triggers Chaqmoq rules.

### Teacher salary va HR

TeacherIncome:

- teacher, group, attendance;
- amount, center_amount, total_amount.

TeacherCompensationRule:

- types: percent, fixed, per_student, per_lesson.

SalaryPayout:

- teacher, center, period year/month, amount, paid_at, note.

TeacherExpectedIncomeSnapshot:

- teacher, center, year, month, active_students, expected_income, income_per_student.

Teacher salary funksiyalari:

- teacher salary list;
- teacher groups;
- group salary report;
- teacher salary summary;
- salary export;
- expected income API;
- teacher income dashboard.

HR:

- StaffProfile with role, position, hire_date, subjects, levels, directions, active state.
- TeacherAvailability with weekday/start/end/type/note.
- Employee API: list/create/update/delete.
- Available teachers API with filtering.
- HR dashboard.

### Exam, ranking, certificate

CenterExamSetting:

- exam_system_enabled;
- exam_every_n_lessons;
- passing_score_percent;
- failed_student_threshold;
- exam_file_upload_enabled;
- exam_result_required;
- optional_task_upload_prompt_enabled;
- minimum_certificate_attendance_percent;
- minimum_certificate_average_percent.

ExamSession:

- center, group, teacher;
- attendance_date, exam_date;
- lesson_number_reference;
- exam_sequence_number;
- teacher_decision: yes/no/later;
- status: draft/completed/cancelled;
- created_by/updated_by.

ExamResult:

- session, group, student, teacher;
- score, percent, passed;
- teacher_comment, assignment_description;
- absent_in_exam;
- retake_recommended;
- fail_reason;
- follow_up_status;
- follow_up_note;
- files.

Exam funksiyalari:

- exam settings;
- exam reminders every N lessons;
- teacher decision action;
- exam list;
- exam create;
- exam session entry;
- exam session detail;
- group exam history;
- teacher exam history;
- failed students list;
- student exam report;
- exam files and task files.

Internal ranking:

- GroupInternalRankingSnapshot;
- scores: attendance, activity, exam, homework, discipline, lightning bonus;
- total_internal_score;
- explanation text.

Academic summary:

- exam_count, average_score, pass/fail count;
- attendance stats;
- internal rank;
- completion recommendation: eligible, needs_review, not_eligible;
- recommendation reason.

Certificate:

- CertificateTemplate: certificate/diploma, file, active state.
- CertificateRecord: number, verification token, issue date, status, PDF file.
- CertificateVerificationLog.
- Certificate pages: templates, activate, candidates, issue, detail, download PDF, public verify.

Group closure:

- GroupClosureWorkflow: open, continue, remind_later, closed.
- group completion recommendations.
- closure action.

---

## Chaqmoq gamification moduli

Chaqmoq bu platformaning motivatsiya va reyting tizimi.

Rule types:

- plus: qo'lda plus Chaqmoq.
- minus: qo'lda minus Chaqmoq.
- attendance_penalty: sababsiz dars qoldirish jarimasi.
- attendance_bonus: muntazam kelish bonusi.
- payment_bonus: 100% to'lov bonusi.
- payment_discipline: deadline gacha to'lov bonusi va deadline o'tsa jarima.

Rule maydonlari:

- nom, center, tur;
- min_baho, max_baho;
- can_director, can_manager, can_teacher;
- absence_limit, presence_limit;
- period: monthly;
- lightning_penalty, lightning_bonus;
- payment_bonus_lightning;
- discipline_deadline_day;
- discipline_bonus_score;
- discipline_penalty_score;
- discipline_active.

Ledger:

- student, beruvchi, group, rule;
- rule snapshot fields;
- ball;
- sana;
- related_month;
- student_balansi helper.

LightningHistory:

- student, points, reason, source: attendance/bonus/penalty/manual, teacher.

Chaqmoq funksiyalari:

- reyting page;
- student Chaqmoq detail;
- my Chaqmoq;
- group students API;
- students JSON;
- Chaqmoq berish page;
- rule list/settings/add/edit/delete;
- penalty rule save/delete;
- discipline rule save;
- center daily max lightning/deduction limits;
- notification on point change;
- daily lightning records;
- mobile Chaqmoq history.

Rule engine:

- check_attendance_penalty: monthly sababsiz qoldirish limitiga yetganda bir marta jarima.
- check_attendance_bonus: monthly presence limit va sababsiz qoldirish yo'q bo'lsa bonus.
- check_payment_bonus: enrollment fully paid bo'lsa bonus.
- check_payment_discipline_bonus: deadline gacha full payment bo'lsa bonus.
- apply_payment_discipline_penalties: cron orqali deadline o'tgan qarzdorlarga jarima.

---

## Store va CRM moduli

### Ichki do'kon

Product:

- nom;
- narx_chaqmoq;
- narx_som;
- sotilgan_soni;
- izoh;
- center;
- images.

PurchaseRequest:

- student, product, qty;
- status: pending, approved, rejected;
- manager;
- sana.

Sale:

- student, product, qty;
- narx_chaqmoq, narx_som;
- manager, sana.

Comment:

- product, user, text, parent reply.

Store funksiyalari:

- product listing and detail;
- product image gallery;
- comment/reply;
- student purchase request;
- manager approve/reject;
- approval deducts Chaqmoq balance and creates Sale;
- product CRUD;
- request list;
- mobile store products;
- mobile purchase requests and create.

### Expenses

ExpenseCategory:

- nom, center.

Expense:

- summa, izoh, sana;
- product optional;
- category;
- payment_method: naqd, plastik, o'tkazma;
- receiver, worker.

Expense funksiyalari:

- expenses page;
- create/edit/delete;
- category create;
- comment;
- XLSX export.

### Lead CRM

Catalog:

- Yonalish: nom, center, color, active.
- Manba: nom, center.
- LeadStatus: nom, code, order, active.

LeadGroup:

- name, subject, department;
- min_students;
- note;
- status: collecting, ready, converted;
- converted_group;
- archive/restore.

Lead:

- personal data: ism, familya, otchestvo, birth_date, gender, passport_id, jshr;
- telefon1, telefon2, parent_phone;
- yosh, address;
- manba, yonalish, status;
- assigned_manager;
- lead_group, added_to_group_at;
- comment, lost_reason, next_follow_up_date;
- created_by;
- converted_user, converted_at, converted_by;
- converted_to_student;
- is_confirmed, confirmed_at, confirmed_by;
- archive fields.

Lead pipeline statuses:

- new;
- contacted;
- trial;
- confirmed;
- converted;
- canceled.

TrialLesson:

- lead, group, teacher;
- scheduled_at;
- attended;
- result_status: pending, attended, absent, converted, not_interested, follow_up_needed;
- notes;
- registered_after_trial;
- created_by/updated_by.

CRM funksiyalari:

- lead list page with filters/search/pagination;
- lead API list/detail/create/update;
- archive/restore;
- confirm;
- assign lead group;
- convert lead to student;
- lead groups CRUD;
- convert lead group to real education group;
- subject/status APIs;
- lead settings UI;
- followups today;
- trial list/create/edit;
- LeadActivity and TrialLessonActivity logs.

---

## Billing va SaaS subscription

PlanFeature:

- code, name, description;
- category: core, finance, marketing, team, advanced;
- is_core, order.

SubscriptionPlan:

- tier, code, title/name;
- monthly_price/price;
- duration_days;
- max_users, max_groups, max_students, max_branches;
- is_popular, discount_percent;
- price_3m, price_6m, price_9m, price_12m;
- caption;
- features JSON;
- plan_features M2M;
- active.

CenterSubscription:

- center, plan;
- status: ACTIVE, PAUSED, EXPIRED, BLOCKED;
- started_at, expires_at;
- paused_at, remaining_seconds;
- manual_block;
- grace period;
- unique active subscription per center;
- paused subscription support;
- filiallar root center subscriptionidan foydalanadi.

Other billing:

- Subscription for user-level legacy flow.
- PaymentTransaction: pending/paid/cancelled, transaction_id, click_trans_id, paid_at.
- PromoCode: percent_off, starts_at/ends_at, max_uses, once_per_center, plans.
- SubscriptionOrder: center, plan, duration_months, base_price, discount, final_price, promo, status.
- SubscriptionRequest: user, center, plan, duration, merchant_trans_id, amount, promo_code, status.

Billing funksiyalari:

- plans page;
- plans API;
- current subscription API;
- upgrade preview API;
- order create;
- demo confirm/reject;
- subscription request approve/reject;
- Click create payment URL;
- Click prepare/complete/webhook;
- payment status API;
- payment success/cancel pages;
- blocked page;
- feature flag check: can_center_use_feature;
- apply plan to center;
- resolve center student limit;
- plan switch calculator: new/extend/convert modes;
- subscription expiry command;
- pause/resume support if needed.

Student limit policy:

- FREE fallback limit;
- paid plan max_students;
- center capacity limit;
- import/add student paths must enforce same resolver.

---

## Marketing website va CMS

Public pages:

- home;
- about;
- features;
- pricing;
- demo;
- resources;
- support;
- vacancies;
- privacy;
- terms;
- robots.txt;
- sitemap.xml.

Marketing CMS models:

- SiteSetting: site name, logo, favicon, social links, address, meta title/description, hero title/subtitle/image, CTAs, stats.
- PartnerLogo.
- FeatureBlock: feature/integration/solution sections, localized title/subtitle/description, icon, image.
- ScreenshotSection.
- PricingPlan and PricingFeature for public pricing.
- Testimonial.
- FAQ.
- DemoLead with phone validator and Uzbekistan regions.
- SupportCard.
- Vacancy.
- StaticPage for privacy/terms/about.

CMS talablari:

- Superadmin dashboard.
- List/create/edit/delete for all marketing entities.
- Uzbek/Russian/English localized fields.
- Pricing plan import from XLSX.
- Demo leads management and contacted state.

---

## Notifications

Notification model:

- center, sender, recipient;
- title, message;
- is_read;
- type: coin, broadcast, purchase, system;
- created_at.

NotificationPreference:

- receive_coin;
- receive_broadcast;
- receive_purchase;
- receive_system.

Web funksiyalari:

- notification dropdown;
- notifications page;
- mark read/read all;
- broadcast send by manager/admin;
- notification preferences.

Mobile funksiyalari:

- list notifications;
- read single;
- read all;
- detail sheet;
- type-based badges;
- unread count.

Telegram:

- parent payment due;
- low attendance;
- branch approval;
- daily reports;
- backup notifications.

---

## Mobile API

Endpointlar:

- `GET /api/mobile/health/`
- `GET /api/mobile/auth/csrf/`
- `POST /api/mobile/auth/login/`
- `POST /api/mobile/auth/logout/`
- `GET /api/mobile/auth/status/`
- `GET /api/mobile/auth/me/`
- `POST /api/mobile/auth/change-password/`
- `GET /api/mobile/me/`
- `GET /api/mobile/home/`
- `GET /api/mobile/dashboard/`
- `GET /api/mobile/attendance/`
- `GET /api/mobile/payments/`
- `GET /api/mobile/progress/`
- `GET/PATCH /api/mobile/profile/`
- `GET /api/mobile/teacher/home/`
- `GET /api/mobile/student/home/`
- `GET /api/mobile/parent/home/`
- `GET /api/mobile/parent/dashboard/`
- `GET /api/mobile/parent/children/`
- `POST /api/mobile/parent/children/add/`
- `POST /api/mobile/parent/select-child/`
- `GET /api/mobile/parent/children/<id>/attendance/`
- `GET /api/mobile/parent/children/<id>/payments/`
- `GET /api/mobile/parent/children/<id>/progress/`
- `GET/PATCH /api/mobile/parent/profile/`
- `POST /api/mobile/parent/profile/avatar/`
- `GET/PATCH /api/mobile/parent/notification-preferences/`
- `GET /api/mobile/parent/notifications/`
- `POST /api/mobile/parent/notifications/<id>/read/`
- `GET /api/mobile/student/debt/`
- `GET /api/mobile/notifications/`
- `POST /api/mobile/notifications/<id>/read/`
- `POST /api/mobile/notifications/read-all/`
- `GET /api/mobile/billing/status/`
- `GET /api/mobile/leads/`
- `GET /api/mobile/store/products/`
- `GET /api/mobile/chaqmoq/history/`
- `GET /api/mobile/store/purchase-requests/`
- `POST /api/mobile/store/purchase-requests/create/`

Mobile auth:

- Login payload center_slug, email/phone, password, device_name, device_platform.
- Bearer token `MobileAccessToken`.
- Token hash saqlansin, raw token faqat login responseida qaytsin.
- Token expiry and revoke.
- Unauthorized handler appda logout qilsin.

Mobile serializerlar:

- center payload;
- user payload;
- session payload;
- notification payload;
- group payload;
- product payload;
- student summary;
- parent dashboard;
- attendance summary;
- payments with monthly debt;
- progress timeline;
- Chaqmoq stats and history;
- billing status.

---

## Flutter mobil ilova

Ilova nomi: `ChaqmoqApp Mobile`.

Dependencies:

- dio;
- flutter_secure_storage;
- provider;
- google_fonts;
- intl;
- shimmer;
- fl_chart;
- cached_network_image;
- flutter_animate;
- flutter_local_notifications;
- image_picker;
- url_launcher.

Architecture:

- `main.dart` creates services and providers.
- `ApiClient` handles base URL, auth header, unauthorized callback.
- `StorageService` stores token/session/theme.
- `AuthRepository` and `LoginService`.
- Providers: auth, dashboard, students, teachers, groups, attendance, payments, notifications, parent_dashboard, app_preferences.
- Shared widgets: buttons, inputs, cards, avatars, badges, bottom sheets, loading/empty/error/offline states, mini charts.

Role routing:

- parent -> `ParentAppShell`
- student -> `StudentAppShell`
- all others -> `AppShell`

Generic staff shell:

- Dashboard;
- Students;
- Teachers for director/manager only;
- Groups;
- Notifications;
- Profile.

Parent app:

- Light theme: background `#F4F7FB`, primary soft blue, amber secondary.
- Screens:
  - login;
  - dashboard;
  - child selector bottom sheet;
  - attendance;
  - payments;
  - payment reminder sheet;
  - progress;
  - subject detail sheet;
  - profile;
  - add child by child code;
  - notifications;
  - notification detail sheet;
  - loading/empty/error/offline states.
- Bottom nav: dashboard, attendance, payments, progress, profile.
- Dashboard structure:
  - greeting header with notification badge;
  - selected child gradient card;
  - Chaqmoq stats card;
  - 2x2 stats grid;
  - quick actions.

Student app:

- Dark teal-forward theme:
  - bg `#0A0A0F`;
  - primary `#00D4AA`;
  - secondary violet `#6C63FF`;
  - glass surfaces.
- Screens:
  - dashboard;
  - offline dashboard state;
  - payments;
  - progress;
  - attendance;
  - notifications dark;
  - notification detail sheet;
  - account/profile;
  - theme toggle;
  - security/change password.
- Student dashboard structure:
  - header with Chaqmoq logo and notification badge;
  - hero card with quick actions: payments, messages, profile;
  - Chaqmoq rating card;
  - stats grid: attendance, debt, average score, activity;
  - recommendation card;
  - activity chart;
  - attendance card;
  - payment summary;
  - homework placeholder.

State requirements:

- Loading skeleton.
- Empty state with CTA.
- Error state with retry.
- Offline banner and cached data label.
- Pull to refresh.
- Responsive for Android/iOS.

---

## Telegram bot

Bot aiogram 3 asosida bo'lsin.

Core bot funksiyalari:

- `/start`;
- contact sharing orqali phone linking;
- profile selection if one Telegram user has multiple profiles;
- role-based main menu.

Menus:

- Student menu: mening reytingim, Chaqmoq tarixi, do'kon, sozlamalar.
- Parent menu: farzand tanlash, farzand dashboard, davomat, to'lov, progress.
- Teacher menu: guruhlarim, davomat olish, bugungi darslar.
- Manager menu: broadcast, lead/student stats, reports.
- Admin menu: broadcast, role filter, branch approval.

Integrations:

- internal API client;
- phone normalization;
- deep link service;
- parent Telegram link tokens;
- branch request approve/reject inline buttons;
- parent notifications: payment due, low attendance;
- daily report scheduler;
- database backup to Telegram/Google Drive.

---

## Trash, audit va soft delete

SoftDeleteMixin:

- is_deleted, deleted_at, deleted_by, deleted_reason;
- restored_at, restored_by;
- objects manager only alive;
- all_objects manager all;
- delete/restore/hard_delete methods.

Trash page:

- deleted items list;
- model_key based restore;
- hard delete;
- manager access toggle;
- manager user access toggle.

Audit:

- UserActivity for login/profile actions.
- AdminAuditLog for superadmin/bot admin actions.
- EducationAuditLog for education module changes.
- LeadActivity and TrialLessonActivity.
- Student transfer history.
- Certificate verification log.

---

## Reports, exports, maintenance

Exports:

- users/students Excel;
- payments Excel;
- teacher salary Excel;
- attendance month Excel;
- expenses Excel.

PDF:

- payment receipt;
- student payments summary;
- certificate PDF;
- public certificate verify page.

Management commands:

- generate_monthly_tuition;
- apply_monthly_rules;
- process_lightning_rules;
- close_month;
- expire_subscriptions;
- seed_plan_features;
- seed_marketing_data;
- backup_databases;
- send_db_backups;
- restore_center_backup;
- send_daily_reports;
- notify_parents;
- backfill_lightning_history;
- reset_center_to_april_debt.

Performance:

- indexes on center/date/status/student/group fields;
- query select_related/prefetch_related;
- cached center resolution in middleware;
- dashboard payload APIs optimized;
- pagination for long lists.

---

## UI/UX talablar

Web dashboard:

- compact, data-dense, professional admin style;
- premium dark/glassmorphism, but forms/tables readable;
- sidebar with modules;
- notification/profile dropdown;
- dashboard cards with charts;
- mobile responsive;
- no marketing-style hero inside app dashboard.

Marketing site:

- real SaaS landing;
- hero must show product/platform value;
- pricing section;
- screenshots;
- testimonials;
- FAQ;
- demo request form.

Mobile:

- parent light and student dark themes separate;
- bottom nav;
- familiar icons;
- no text overflow;
- stable card heights for metrics/charts;
- all screens have loading/empty/error/offline states.

Uzbek copy examples:

- "Assalomu alaykum"
- "Farzandni tanlang"
- "Davomat"
- "To'lovlar"
- "Qarzdorlik"
- "Chaqmoq reyting"
- "O'quvchi paneli"
- "Guruhlar"
- "Sinov dars"
- "Qayta aloqa"
- "Sertifikat"

---

## API va schema talablari

- DRF Spectacular OpenAPI schema.
- JSON response consistent:
  - `ok: true/false` for mutation APIs where useful;
  - validation errors with field keys;
  - list endpoints with pagination metadata;
  - mobile endpoints with stable payload keys.
- CSRF for web session APIs.
- Bearer mobile token for mobile APIs.
- Permission checks per endpoint.
- Center isolation in every query.

---

## Test talablari

Kamida quyidagilarni test qil:

- RBAC redirect and permission deny.
- Tenant isolation.
- Student limit policy.
- Center subscription expiry/grace/block.
- Payment creation, allocation and enrollment paid totals.
- Prorated tuition and lesson calculation.
- Attendance statuses and unique per group/student/date.
- Chaqmoq rule engine: attendance penalty, attendance bonus, payment bonus, payment discipline.
- Lead conversion to student.
- Lead group conversion to real group.
- Parent child_code linking.
- Mobile auth and parent/student home endpoints.
- Soft delete restore/hard delete.
- Exam workflow and certificate issue.
- Teacher salary calculations.
- Billing plan switch calculator.

---

## Implementation plan

1. Project setup:
   - Django project, apps, settings, env config, auth user, static/media, DRF, Swagger.

2. Tenant and RBAC foundation:
   - Center, Branch, custom User, TenantMiddleware, RBAC middleware, secure login.

3. Core dashboard foundation:
   - base template, sidebar, role dashboards, notification system, soft delete/trash.

4. Education core:
   - categories, groups, schedules, enrollments, students, attendance.

5. Finance:
   - payments, tuition months, allocations, debts, receipts, exports, financial month close.

6. Chaqmoq:
   - rules, ledger, history, ranking, automatic rule engine, notifications.

7. Teacher salary and HR:
   - teacher income, compensation, payouts, staff profiles, availability APIs.

8. CRM and store:
   - products, purchase requests, sales, expenses, leads, lead groups, trials, conversion.

9. Exams and certificates:
   - exam settings, sessions, results, rankings, academic summaries, certificates.

10. Billing SaaS:
    - plan features, subscription plans, center subscriptions, promos, orders, Click, blocked flow.

11. Marketing:
    - public site, CMS, localized content, demo leads, pricing import.

12. Mobile API:
    - token auth, serializers, parent/student/staff endpoints.

13. Flutter app:
    - auth, role shells, parent and student redesign, staff screens.

14. Telegram bot:
    - linking, role menus, notifications, branch approval, reports/backups.

15. QA and deploy:
    - tests, seed data, migrations, documentation, Render deployment.

---

## Acceptance criteria

Platforma tayyor hisoblanadi, agar:

- superadmin yangi center yaratib, tarif biriktira olsa;
- director markazga kirib dashboard, guruh, student, to'lov, CRM va Chaqmoqni boshqara olsa;
- manager o'quvchi/lead/to'lov/do'kon operatsiyalarini bajara olsa;
- teacher o'z guruhlari davomatini olib, Chaqmoq bera olsa va daromadini ko'ra olsa;
- student mobil ilovada o'z Chaqmoq, to'lov, davomat, progress va xabarlarini ko'ra olsa;
- parent child code orqali farzand qo'shib, barcha farzand ma'lumotini ko'ra olsa;
- billing limitlari va feature flags real ishlasa;
- Click payment webhook subscriptionni yangilasa;
- lead studentga, lead group real groupga konvertatsiya bo'lsa;
- payment allocations qarzdorlikni to'g'ri hisoblasa;
- certificate verify public link ishlasa;
- Telegram bot asosiy role menyularni va xabarnomalarni yuborsa;
- barcha querylar center isolationga amal qilsa;
- testlar o'tsa va deployment production env bilan ishga tushsa.

---

## Muhim engineering qoidalari

- Har bir yangi model center bilan bog'lansin yoki centerga yetib boradigan relationga ega bo'lsin.
- Hech qachon global query bilan boshqa markaz ma'lumotini chiqarma.
- Role permissionlarni view va middleware darajasida ikki qatlamda tekshir.
- Soft delete mavjud joylarda hard delete faqat trash/admin action orqali bo'lsin.
- To'lov, Chaqmoq, subscription kabi pul/ballga ta'sir qiladigan joylarda transaction ishlat.
- Payment va Chaqmoq ledger tarixini o'zgartirma, correction entry orqali tuzat.
- Mobile payload keys stable bo'lsin, appni sindiradigan breaking change qilma.
- Uzbek Latin copy bir xil uslubda bo'lsin.
- Har bir list sahifada search, filter, pagination bo'lsin.
- Har bir dashboard API N+1 queriesdan himoyalangan bo'lsin.
- Har bir mutationdan keyin audit/log kerakli joyda yozilsin.

---

## Qisqa bir jumlalik prompt varianti

"Django 5 + Flutter + aiogram asosida ChaqmoqApp nomli multi-tenant SaaS o'quv markaz CRM platformasini 0 dan yarating: center/filial, RBAC rollar, education groups/enrollment/attendance/payments, Chaqmoq gamification, CRM leads/trials, store, billing Click subscription, marketing CMS, mobile parent/student app, Telegram bot, tenant isolation, soft delete, audit, exports, PDFs, tests va production deployment bilan to'liq ishlaydigan qilib implement qiling."
