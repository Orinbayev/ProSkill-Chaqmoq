"""
Savdo (sales) demo markazini to'ldiradi: director/manager/teacher loginlari +
o'quvchilar, guruhlar, to'lovlar, qarzdorlar, grafik ma'lumotlari, do'kon
mahsulotlari va xaridlar, leadlar hamda arxivlar.

Ishlatish (LOKAL):
    python manage.py migrate --noinput
    python manage.py seed_sales_demo              # slug: demo-markaz
    python manage.py seed_sales_demo --slug=demo2

Ishlatish (RENDER Shell) — deploy TUGAGANIDAN keyin:
    python manage.py migrate --noinput
    python manage.py seed_sales_demo --slug=demo-markaz

Idempotent: har safar demo markazni to'liq tozalab, yangidan quradi.
Loginlar (login == parol):
    director  d@gmail.com  / d@gmail.com
    manager   m@gmail.com  / m@gmail.com
    teacher   t@mail.com   / t@mail.com

⚠️ Deploy paytida (build/start) ishlatmang — migrate tugamaguncha
   "column ... does not exist" xatosi chiqadi va Render restart bo'lib ko'rinadi.
"""
import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from django.utils.text import slugify

# Determ. urug' — har safar bir xil demo
random.seed(2026)

DEMO_USERS = [
    ("director", "d@gmail.com", "Dilshod", "Direktorov"),
    ("manager", "m@gmail.com", "Malika", "Menejerova"),
    ("teacher", "t@mail.com", "Temur", "O'qituvchiyev"),
]

STUDENT_NAMES = [
    ("Aziz", "Yusupov"), ("Madina", "Rahimova"), ("Behruz", "Aliyev"),
    ("Shahzoda", "Normatova"), ("Kamron", "Usmonov"), ("Gulnoza", "Ergasheva"),
    ("Sherzod", "Jo'rayev"), ("Zilola", "Akbarova"), ("Sardor", "Mamatov"),
    ("Fotima", "Qobilova"), ("Oybek", "To'xtayev"), ("Nigina", "Sobirova"),
    ("Asliddin", "Qudratov"), ("Mubina", "Saidova"), ("Javohir", "Niyozov"),
    ("Lola", "Mahmudova"), ("Samandar", "Qosimov"), ("Dildora", "Abduqodir"),
    ("Rustam", "Rasulov"), ("Sevara", "Murodova"), ("Mirjalol", "Toshpo'lat"),
    ("Sarvinoz", "Qahhorova"), ("Umid", "Hakimov"), ("Shirin", "Yodgorova"),
    ("Jasur", "Ismoilov"), ("Malika", "Yo'ldosheva"), ("Bekzod", "Karimov"),
    ("Nozima", "Tairova"), ("Diyor", "Islomov"), ("Kamola", "Ne'matova"),
]

GROUP_DEFS = [
    ("Ingliz tili — Beginner", "Ingliz tili", 550_000, 40, 12),
    ("Ingliz tili — Intermediate", "Ingliz tili", 650_000, 45, 12),
    ("Matematika — Abituriyent", "Matematika", 500_000, 40, 12),
    ("IT — Frontend", "IT", 700_000, 50, 8),
]

PRODUCT_DEFS = [
    ("Chaqmoq ruchka", 50, 15_000),
    ("Bloknot A5", 80, 25_000),
    ("Sertifikat ramka", 150, 45_000),
    ("Chaqmoq futbolka", 300, 90_000),
    ("Termos idish", 500, 150_000),
]

MANBA_DEFS = ["Instagram", "Telegram", "Do'stlar tavsiyasi", "Google reklama"]
LEAD_STATUS_DEFS = [("Yangi", "new"), ("Bog'lanildi", ""), ("Sinov darsi", ""), ("Konvertatsiya", "")]
LEAD_NAMES = [
    ("Otabek", "Sattorov", 14), ("Malika", "Yusupova", 16), ("Sardorbek", "Aliyev", 13),
    ("Nilufar", "Karimova", 17), ("Jahongir", "Umarov", 15), ("Gulasal", "Rustamova", 12),
    ("Islom", "Nazarov", 18), ("Sabina", "Tosheva", 14), ("Doston", "Ergashev", 16),
    ("Ruxshona", "Qodirova", 13), ("Amir", "Sobirov", 15), ("Zarina", "Hamidova", 17),
    ("Bobur", "Xolmatov", 14), ("Sitora", "Ismatova", 16), ("Nodir", "Vohidov", 15),
]


class Command(BaseCommand):
    help = "Savdo demo markazini to'liq ma'lumot bilan tayyorlaydi (idempotent)."

    # ⚠️ Marketing/app band qilgan yo'llar bilan to'qnashmasligi kerak:
    # demo, about, features, pricing, resources, support, login, platform,
    # hisob, talim, do'kon, chaqmoq, api, admin, boshqaruv, c ...
    def add_arguments(self, parser):
        parser.add_argument("--slug", default="demo-markaz",
                            help="Demo markaz slug (default: demo-markaz). 'demo' MARKETING sahifasi bilan to'qnashadi!")
        parser.add_argument(
            "--skip-migrate-check",
            action="store_true",
            help="Migratsiya tekshiruvini o'tkazib yuborish (tavsiya etilmaydi).",
        )
        parser.add_argument(
            "--lite",
            action="store_true",
            help="Render uchun yengil rejim: 12 o'quvchi, kamroq to'lov (tezroq tugaydi).",
        )

    def handle(self, *args, **options):
        import sys

        slug = (options["slug"] or "demo-markaz").strip().lower()
        if slug in {"demo", "about", "features", "pricing", "login", "platform", "admin", "api"}:
            raise CommandError(
                f"Slug '{slug}' marketing/app yo'li bilan to'qnashadi. "
                f"Masalan: --slug=demo-markaz"
            )

        if not options.get("skip_migrate_check"):
            self._ensure_migrations_applied()

        def log(msg=""):
            # Render Shell chiqishini darhol ko'rsatish (buffer tufayli "to'xtab qolgandek" bo'lmasin)
            self.stdout.write(str(msg))
            try:
                sys.stdout.flush()
            except Exception:
                pass

        try:
            summary = seed(slug=slug, log=log, lite=bool(options.get("lite")))
        except Exception as exc:  # pragma: no cover - CLI qulayligi uchun
            import traceback
            self.stderr.write(traceback.format_exc())
            msg = str(exc)
            if "no column named" in msg or "does not exist" in msg:
                self.stderr.write(self.style.ERROR(
                    "\n❌ DB sxemasi eski. Avval migratsiya qiling, keyin seed:\n"
                    "   python manage.py migrate --noinput\n"
                    "   python manage.py seed_sales_demo --slug=demo-markaz --lite\n"
                ))
            elif "unique" in msg.lower() or "duplicate" in msg.lower():
                self.stderr.write(self.style.ERROR(
                    "\n❌ UNIQUE to'qnashuv. Qayta urinib ko'ring (seed eski demonu tozalaydi):\n"
                    "   python manage.py seed_sales_demo --slug=demo-markaz --lite\n"
                ))
            raise
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Demo tayyor! URL: /{slug}/hisob/login/  yoki  /{slug}/\n"
            f"   director  d@gmail.com  / d@gmail.com\n"
            f"   manager   m@gmail.com  / m@gmail.com\n"
            f"   teacher   t@mail.com   / t@mail.com\n"
            f"   O'quvchilar: {summary['students']}, guruhlar: {summary['groups']}, "
            f"to'lovlar: {summary['payments']}, qarzdorlar: {summary['debtors']}, "
            f"xarajatlar: {summary['expenses']}, leadlar: {summary['leads']}, "
            f"xaridlar: {summary['purchases']}, arxiv: {summary['archived']}"
        ))

    def _ensure_migrations_applied(self):
        """Deploy/shell da eng ko'p uchraydigan xato: migrate qilinmagan."""
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if not plan:
            return
        pending = [f"{m.app_label}.{m.name}" for m, _ in plan[:12]]
        self.stdout.write(self.style.WARNING(
            f"⚠️  {len(plan)} ta migratsiya qo'llanmagan (masalan: {', '.join(pending)}…).\n"
            f"   Avtomatik: python manage.py migrate --noinput"
        ))
        try:
            call_command("migrate", interactive=False, verbosity=1)
        except Exception as exc:
            raise CommandError(
                f"migrate muvaffaqiyatsiz: {exc}\n"
                f"Qo'lda ishga tushiring: python manage.py migrate --noinput"
            ) from exc


def seed(*, slug: str, log=print, lite: bool = False) -> dict:
    """
    NOTE: Butun seed bitta @transaction.atomic emas.
    Render free Postgres + Shell da uzun atomic:
      - timeout / disconnect → hammasi ROLLBACK (log bor, DB bo'sh)
      - "to'xtab qolgandek" seziladi
    Har bo'lim alohida atomic commit qilinadi.
    """
    from django.contrib.auth.hashers import make_password

    from accounts.models import Center, User
    from billing.models import CenterSubscription, SubscriptionPlan
    from education.models import Attendance, Category, Enrollment, Group, GroupSchedule
    from education.services.tuition import create_payment_and_allocate, ensure_tuition_month
    from store.models import (
        Expense, ExpenseCategory, Lead, LeadStatus, Manba, Product, PurchaseRequest,
    )

    today = timezone.localdate()
    student_names = STUDENT_NAMES[:12] if lite else STUDENT_NAMES
    # Bir xil parol hash — 30× set_password sekinligini oldini oladi
    demo_password_hash = make_password("demo")
    staff_password_hash = make_password("demo")

    # ─────────────── 1) Reset (idempotent, HARD delete) ───────────────
    # User/Center — SoftDeleteMixin: oddiy .delete() faqat is_deleted=True qiladi,
    # email/slug bazada qolib UNIQUE to'qnashadi. Shuning uchun hard_delete.
    log(f"• Eski demo tozalanmoqda (slug={slug})…")
    with transaction.atomic():
        demo_emails = [e for _, e, _, _ in DEMO_USERS]
        User.all_objects.filter(email__in=demo_emails).hard_delete()
        User.all_objects.filter(email__endswith=f"@{slug}.demo.local").hard_delete()
        old_center = Center.all_objects.filter(slug=slug).first()
        if old_center:
            User.all_objects.filter(center=old_center).hard_delete()
            old_center.hard_delete()  # cascade: guruh/enrollment/to'lov/lead/...
    log(f"• Eski demo tozalandi (slug={slug})")

    # ─────────────── 2–4) Markaz + loginlar + guruhlar ───────────────
    with transaction.atomic():
        all_features = [
            "finance", "imtihon", "hr", "sertifikat", "store", "leads", "analytics", "xarajatlar",
            "ui_exam_sessions", "ui_failed_students", "ui_certificates", "ui_weekly_schedule",
        ]
        center_kwargs = dict(
            name="Chaqmoq Demo O'quv Markazi",
            slug=slug,
            status=Center.STATUS_ACTIVE,
            features={f: True for f in all_features},
            max_students=100_000,
            capacity_limit=100_000,
            plan="DEMO_ALL",
            expires_at=timezone.now() + timedelta(days=3650),
        )
        if any(f.name == "is_demo" for f in Center._meta.fields):
            center_kwargs["is_demo"] = True
        center = Center.objects.create(**center_kwargs)
        plan, _ = SubscriptionPlan.objects.update_or_create(
            code="DEMO_ALL",
            defaults=dict(title="Demo All", name="DEMO_ALL", tier=99,
                          max_students=100_000, duration_days=3650, active=True),
        )
        CenterSubscription.objects.filter(
            center=center, status=CenterSubscription.Status.ACTIVE
        ).update(status=CenterSubscription.Status.EXPIRED)
        sub_kwargs = dict(
            center=center,
            plan=plan,
            status=CenterSubscription.Status.ACTIVE,
            expires_at=timezone.now() + timedelta(days=3650),
            manual_block=False,
        )
        if any(f.name == "is_grandfathered" for f in CenterSubscription._meta.fields):
            sub_kwargs["is_grandfathered"] = True
        CenterSubscription.objects.create(**sub_kwargs)
        log(f"• Markaz yaratildi: {center.name} (aktiv obuna + barcha modullar)")

        users = {}
        for i, (role, email, ism, familya) in enumerate(DEMO_USERS):
            # Har biriga alohida telefon — unique constraint (phone_number/telefon) to'qnashmasin
            u = User.objects.create_user(
                email=email, password=email, role=role, center=center,
                ism=ism, familya=familya, telefon1=f"+99890111000{i}",
            )
            users[role] = u
        director, manager, teacher = users["director"], users["manager"], users["teacher"]
        log("• Loginlar: d@gmail.com / m@gmail.com / t@mail.com (parol == login)")

        cats = {}
        for _, cat_name, *_ in GROUP_DEFS:
            if cat_name not in cats:
                cats[cat_name], _ = Category.objects.get_or_create(center=center, name=cat_name)

        groups = []
        for nom, cat_name, narx, foiz, dars in GROUP_DEFS:
            g = Group.objects.create(
                center=center, nom=nom, oqituvchi=teacher,
                kurs_narxi=narx, oqituvchi_foiz=foiz, oy_dars_soni=dars,
                category_obj=cats[cat_name],
            )
            groups.append(g)
        log(f"• {len(groups)} ta guruh yaratildi")

    # ─────────────── 4b) Qo'shimcha xodimlar (HR paneli demosi) ───────────────
    # HR dashboard panellari to'lishi uchun: hire date (so'nggi qo'shilganlar),
    # fan/Yo'nalish (yo'nalishlar bo'yicha), ish kunlari (jadval zichligi + haftalik
    # bandlik), bo'sh ustozlar (bugun dars bermaydiganlar).
    from education.models import StaffProfile, TeacherAvailability
    from store.models import Yonalish

    subj_names = ["Ingliz tili", "IELTS", "Matematika", "Rus tili", "Ona tili", "Speaking"]
    subjects = {n: Yonalish.objects.get_or_create(center=center, nom=n)[0] for n in subj_names}

    def _staff_role(role):
        return {
            "teacher": StaffProfile.Role.TEACHER,
            "manager": StaffProfile.Role.MANAGER,
        }.get(role, StaffProfile.Role.ADMIN)

    def _hire(months_ago):
        if months_ago == 0:
            return today.replace(day=max(1, today.day - 3))
        return _month_add(today, -months_ago).replace(day=min(today.day, 27))

    # (ism, familya, role, lavozim, oy_oldin, [fanlar], [ish_kunlari], [darajalar], [yo'nalishlar])
    STAFF_DEFS = [
        ("Aziza", "Karimova", "teacher", "Ingliz tili o'qituvchisi", 0, ["Ingliz tili", "IELTS"], [1, 3, 5], ["Intermediate", "Upper-Intermediate"], ["IELTS", "General English"]),
        ("Jasur", "Toshmatov", "teacher", "Matematika o'qituvchisi", 0, ["Matematika"], [2, 4, 6], ["Advanced"], ["SAT"]),
        ("Nilufar", "Rahimova", "teacher", "Speaking o'qituvchisi", 2, ["Speaking", "Ingliz tili"], [1, 3], ["Pre-Intermediate"], ["Speaking", "Kids"]),
        ("Sardor", "Aliyev", "teacher", "Rus tili o'qituvchisi", 4, ["Rus tili"], [2, 4], ["Elementary"], ["General English"]),
        ("Kamola", "Yusupova", "teacher", "Ona tili o'qituvchisi", 6, ["Ona tili"], [1, 3, 5, 6], ["Beginner"], ["Kids"]),
        ("Bekzod", "Nazarov", "teacher", "IELTS o'qituvchisi", 9, ["IELTS", "Matematika"], [3, 5], ["Upper-Intermediate", "Advanced"], ["IELTS"]),
        ("Gulnora", "Ismoilova", "manager", "Kichik menejer", 12, [], [], [], []),
    ]
    with transaction.atomic():
        extra_staff = 0
        for ism, familya, role, position, months_ago, fans, kunlar, levels, directions in STAFF_DEFS:
            u = User(
                email=f"{slugify(ism)}.{slugify(familya)}@{slug}.demo.local",
                role=role, center=center, ism=ism, familya=familya,
                telefon1=f"+9989015{extra_staff:05d}", lavozim=position,
            )
            u.password = staff_password_hash
            u.save()
            prof = StaffProfile.objects.create(
                user=u, tenant=center, full_name=f"{ism} {familya}", phone=u.telefon1,
                role=_staff_role(role), position=position, hire_date=_hire(months_ago),
                levels=levels, directions=directions, is_active=True,
            )
            if fans:
                prof.subjects.set([subjects[f] for f in fans])
            if role == "teacher":
                for wd in kunlar:
                    TeacherAvailability.objects.get_or_create(
                        tenant=center, teacher=u, weekday=wd, start_time=time(14, 0),
                        defaults={"end_time": time(18, 0), "type": TeacherAvailability.Type.AVAILABLE},
                    )
            extra_staff += 1

        tprof, _ = StaffProfile.objects.get_or_create(user=teacher, tenant=center)
        tprof.full_name = teacher.get_full_name() or "Temur O'qituvchiyev"
        tprof.role = StaffProfile.Role.TEACHER
        tprof.position = "Katta o'qituvchi"
        tprof.hire_date = _month_add(today, -18).replace(day=15)
        tprof.is_active = True
        tprof.save()
        tprof.subjects.set([subjects["Ingliz tili"], subjects["IELTS"]])
        log(f"• {extra_staff} ta qo'shimcha xodim (HR demo: hire date, fan, ish kunlari)")

    # ─────────────── 5) O'quvchilar + enrollmentlar ───────────────
    log(f"• O'quvchilar yaratilmoqda ({len(student_names)} ta)…")
    students = []
    enrollments = []
    month_starts = [_month_add(today.replace(day=1), -k) for k in range(5, -1, -1)]
    join_plan = [1, 2, 2, 2, 2, 3] if lite else [1, 3, 4, 5, 6, 8]
    join_dates = []
    for m, n in zip(month_starts, join_plan):
        for _ in range(n):
            day = random.randint(1, 26)
            join_dates.append(m.replace(day=min(day, 26)))
    join_dates = join_dates[:len(student_names)]

    with transaction.atomic():
        for idx, (ism, familya) in enumerate(student_names):
            s = User(
                email=f"student{idx+1}@{slug}.demo.local",
                role="student", center=center, ism=ism, familya=familya,
                telefon1=f"+9989012{idx:05d}",
                birth_date=date(2008 + (idx % 6), (idx % 12) + 1, (idx % 27) + 1),
            )
            if getattr(User, "Gender", None):
                s.gender = User.Gender.MALE if idx % 2 else User.Gender.FEMALE
            s.password = demo_password_hash  # already hashed — tezkor
            s.save()
            students.append(s)

            joined = join_dates[idx] if idx < len(join_dates) else month_starts[-1]
            grp = groups[idx % len(groups)]
            payable = grp.kurs_narxi
            if idx % 5 == 0:
                payable = int(grp.kurs_narxi * 0.7)
            e = Enrollment.objects.create(
                center=center, group=grp, student=s,
                kurs_narhi=grp.kurs_narxi, oqituvchi_foiz=grp.oqituvchi_foiz,
                student_payable_amount=payable, is_active=True, joined_at=joined,
            )
            enrollments.append(e)
            if (idx + 1) % 10 == 0:
                log(f"  … {idx + 1}/{len(student_names)} o'quvchi")
    log(f"• {len(students)} ta o'quvchi enroll qilindi")

    # ─────────────── 5b) Jadval + bugungi davomat (davomat nazorati demosi) ───────────────
    # Har guruh haftaning barcha kunlari darsga ega — bugun doim jadvalda bo'ladi.
    # Turli soatlar: erta (unutilgan ko'rinsin), kech (kutilmoqda), + biri qilingan.
    # Vaqtlar HOZIRGA nisbatan: 0=qilingan (o'tган), 1=unutilgan (o'tган+grace),
    # 2=kutilmoqda (kelajak). Shunda demo istalgan vaqtда 3 holatni ko'rsatadi.
    _nowm = timezone.localtime().hour * 60 + timezone.localtime().minute
    def _rel(delta):
        m = max(1, min(23 * 60 + 58, _nowm + delta))
        return time(m // 60, m % 60)
    sched_time = {0: _rel(-30), 1: _rel(-150), 2: _rel(+180), 3: time(9, 0)}
    for gi, g in enumerate(groups):
        if gi >= 2:
            # Demo: 3-guruhni JADVALSIZ (Avtomatik) qoldiramiz — "Jadval belgilash"
            # oqimi (davomat nazoratidagi havola) ko'rinib tursin.
            Enrollment.objects.filter(group=g).update(lesson_pattern="group")
            continue
        for wd in range(1, 8):  # Dushanba..Yakshanba (demo har kuni ko'rinsin)
            GroupSchedule.objects.get_or_create(
                center=center, group=g, weekday=wd,
                start_time=sched_time.get(gi, time(9, 0)),
                defaults={"end_time": time((sched_time.get(gi, time(9, 0)).hour + 1) % 24, 30)},
            )
    today = timezone.localdate()
    # Faqat 1-guruhда bugun davomat qilingan (taken); qolgani missing/pending.
    g_taken = groups[0]
    taken_statuses = ["present", "present", "present", "late", "absent_excused", "absent_unexcused"]
    for e, st in zip(list(Enrollment.objects.filter(group=g_taken, is_active=True))[:6], taken_statuses):
        Attendance.objects.get_or_create(
            center=center, group=g_taken, student=e.student, date=today,
            defaults={"teacher": g_taken.oqituvchi, "status": st, "present": st == "present"},
        )
    log("• Jadval + bugungi davomat qo'shildi (nazorat demosi: qilingan/unutilgan/kutilmoqda)")

    # ─────────────── 6) Tuition oylar + to'lovlar (paid / partial / qarzdor) ───────────────
    payments = 0
    debtors = set()
    cur_month = today.replace(day=1)
    for idx, e in enumerate(enrollments):
        m = e.joined_at.replace(day=1)
        months = []
        while m <= cur_month:
            ensure_tuition_month(e, m)
            months.append(m)
            m = _month_add(m, 1)

        scenario = idx % 5  # 0,1,2 = to'lagan; 3 = qisman; 4 = qarzdor
        for mi, month in enumerate(months):
            fee = int(e.student_payable_amount or e.kurs_narhi)
            is_current = (month == cur_month)
            if scenario <= 2:
                amount = fee  # to'liq to'lagan
            elif scenario == 3:
                amount = fee if not is_current else int(fee * 0.5)  # joriy oy qisman → qarzdor
            else:
                amount = 0  # umuman to'lamagan → qarzdor
            if amount > 0:
                pay_day = min(random.randint(2, 27), 27)
                paid_at = datetime.combine(month.replace(day=pay_day), datetime.min.time())
                try:
                    create_payment_and_allocate(
                        enrollment=e, created_by=manager,
                        cash_amount=amount, card_amount_som=0,
                        start_month=month, paid_at=paid_at, strict_month=True,
                        note="Demo to'lov",
                    )
                    payments += 1
                except Exception as exc:
                    log(f"  ! to'lov o'tkazilmadi (e={e.id} {month}): {exc}")
            if amount < fee:
                debtors.add(e.student_id)
    log(f"• {payments} ta to'lov yozildi, {len(debtors)} ta qarzdor hosil bo'ldi")

    # ─────────────── 7) Do'kon: mahsulotlar + xaridlar ───────────────
    products = []
    for nom, narx_chaqmoq, narx_som in PRODUCT_DEFS:
        p = Product.objects.create(
            center=center, nom=nom, narx_chaqmoq=narx_chaqmoq, narx_som=narx_som,
        )
        products.append(p)
    purchases = 0
    for i in range(14):
        st = students[i % len(students)]
        pr = products[i % len(products)]
        req = PurchaseRequest.objects.create(
            center=center, student=st, product=pr, qty=random.randint(1, 3),
            status=(PurchaseRequest.APPROVED if i % 3 else PurchaseRequest.PENDING),
        )
        purchases += 1
    log(f"• {len(products)} ta mahsulot, {purchases} ta xarid so'rovi")

    # ─────────────── 7b) Xarajatlar (manager kiritган — har oy) ───────────────
    # store.Expense — dashboard KPI ("Xarajatlar") va store:expenses bo'limi
    # AYNAN shu modeldan o'qiydi, shu sababdan karta raqami = bo'lim yig'indisi.
    expense_defs = [
        ("Ijara", 1_800_000, "Ijara to'lovi"),
        ("O'qituvchilar", 2_200_000, "O'qituvchilar ish haqi"),
        ("Kommunal", 450_000, "Kommunal (svet/suv/internet)"),
        ("Reklama", 550_000, "Instagram / Telegram reklama"),
        ("Jihoz", 300_000, "Marker, qog'oz, jihoz"),
    ]
    exp_cats = {n: ExpenseCategory.objects.get_or_create(center=center, nom=n)[0]
                for n, _, _ in expense_defs}
    expense_count = 0
    for month in month_starts:  # oxirgi 6 oy
        for name, amount, izoh in expense_defs:
            day = random.randint(2, 26)
            naive = datetime.combine(month.replace(day=day), datetime.min.time())
            sana = timezone.make_aware(naive, timezone.get_current_timezone())
            Expense.objects.create(
                center=center, summa=int(amount * random.uniform(0.85, 1.15)),
                izoh=izoh, category=exp_cats[name],
                sana=sana,
                worker=manager,
            )
            expense_count += 1
    log(f"• {expense_count} ta xarajat yozuvi (6 oy × {len(expense_defs)} kategoriya)")

    # ─────────────── 8) Leadlar (turli manba/status) ───────────────
    manbas = [Manba.objects.create(center=center, nom=n) for n in MANBA_DEFS]
    statuses = []
    for i, (nom, code) in enumerate(LEAD_STATUS_DEFS):
        ls = LeadStatus.objects.create(center=center, nom=nom, code=code, order=(i + 1) * 10)
        statuses.append(ls)
    leads = 0
    for i, (ism, familya, yosh) in enumerate(LEAD_NAMES):
        Lead.objects.create(
            center=center, ism=ism, familya=familya, yosh=yosh,
            telefon1=f"+9989033{i:05d}",
            manba=manbas[i % len(manbas)],
            status=statuses[i % len(statuses)],
            assigned_manager=manager, created_by=manager,
        )
        leads += 1
    log(f"• {leads} ta lead yaratildi")

    # ─────────────── 9) Arxiv (ba'zi o'quvchi + guruh) ───────────────
    archived = 0
    for s in students[-2:]:  # oxirgi 2 o'quvchini arxivlash
        try:
            s.is_archived = True
            s.save(update_fields=["is_archived"])
            Enrollment.objects.filter(student=s).update(is_active=False)
            archived += 1
        except Exception:
            pass
    try:
        arch_group = groups[-1]
        arch_group.is_archived = True
        arch_group.save(update_fields=["is_archived"])
        archived += 1
    except Exception:
        pass
    log(f"• {archived} ta arxiv (o'quvchi/guruh) belgilandi")

    return {
        "students": len(students), "groups": len(groups),
        "payments": payments, "debtors": len(debtors),
        "leads": leads, "purchases": purchases, "archived": archived,
        "expenses": expense_count,
    }


def _month_add(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, 1)
