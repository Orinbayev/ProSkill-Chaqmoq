from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.timezone import localdate
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from chaqmoq.models import Ledger
from django.contrib import messages
from django.shortcuts import render, get_object_or_404

from store.models import Product, PurchaseRequest, Sale
U = get_user_model()
from django.db.models import Count
from accounts.models import User
from education.models import Group
from django.core.paginator import Paginator


@login_required
def teacher_list(request):
    teachers = User.objects.filter(role="teacher").annotate(
        group_count=Count('group')
    )

    return render(request, "core/teacher_list.html", {
        "teachers": teachers
    })


@login_required
def teacher_detail(request, pk):
    teacher = get_object_or_404(User, pk=pk, role="teacher")

    groups = Group.objects.filter(oqituvchi=teacher)

    return render(request, "core/teacher_detail.html", {
        "teacher": teacher,
        "groups": groups
    })

from accounts.forms import TeacherForm


@login_required
def teacher_edit(request, pk):
    # 1) O‘qituvchini topamiz (role bilan emas, chunki manager → teacher bo‘lishi mumkin)
    teacher = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        form = TeacherForm(request.POST, instance=teacher)

        if form.is_valid():
            teacher = form.save(commit=False)

            # 🔥 Otasining ismi albatta saqlansin
            teacher.otchestvo = form.cleaned_data.get("otchestvo")

            # 🔥 Telefonlarni tozalash
            tel1 = form.cleaned_data.get("telefon1", "")
            tel2 = form.cleaned_data.get("telefon2", "")

            if tel1:
                teacher.telefon1 = "+998" + tel1.replace("+998", "").replace(" ", "").replace("-", "")
            if tel2:
                teacher.telefon2 = "+998" + tel2.replace("+998", "").replace(" ", "").replace("-", "")

            teacher.save()

            # 🔥 Yangi ulush (foiz)
            yangi_foiz = teacher.oqituvchi_foizi

            from education.models import Group, Enrollment

            # 🔥 1) O‘qituvchi ishlaydigan guruhlar
            Group.objects.filter(oqituvchi=teacher).update(oqituvchi_foiz=yangi_foiz)

            # 🔥 2) O‘sha guruhlardagi barcha enrollmentlar
            Enrollment.objects.filter(group__oqituvchi=teacher).update(oqituvchi_foiz=yangi_foiz)

            return redirect("core:teacher_list")

    else:
        form = TeacherForm(instance=teacher)

    return render(request, "core/teacher_edit.html", {
        "form": form,
        "teacher": teacher
    })


def _build_stats():
    U = get_user_model()
    return {
        'managers': U.objects.filter(role='manager').count(),
        'teachers': U.objects.filter(role='teacher').count(),
        'students': U.objects.filter(role='student').count(),
        'products': Product.objects.count(),
        'pending_requests': PurchaseRequest.objects.filter(status=PurchaseRequest.PENDING).count(),
        'total_chaqmoq': Ledger.objects.aggregate(s=Sum('ball'))['s'] or 0,
        'sales_today': Sale.objects.filter(sana__date=localdate()).count(),
    }

@login_required
def home(request):
    u = request.user
    role = getattr(u, 'role', None)
    if (not role) and u.is_superuser:
        role = 'director'

    if role == 'director':
        return render(request, 'core/dashboard_director.html', {'stats': _build_stats()})
    if role == 'manager':
        return render(request, 'core/dashboard_manager.html', {'stats': _build_stats()})
    if role == 'teacher':
        return render(request, 'core/dashboard_teacher.html')
    if role == 'student':
        from chaqmoq.models import Ledger
        balance = Ledger.student_balansi(u.id)
        return render(request, 'core/dashboard_student.html', {'balance': balance})

    return redirect('/admin/accounts/user/')


def _staff_only(request):
    u = request.user
    return u.is_superuser or getattr(u, 'role', None) in ('manager','director')

from django.core.paginator import Paginator

@login_required
def stat_managers(request):
    if not _staff_only(request):
        return render(request, 'core/dashboard_guest.html')

    q = request.GET.get('q', '').strip()

    # ❗ Managerda pagination yo‘q → page_size = 10 qat'iy (yoki hammasi)
    page_size = 9999   # shunchaki hammasini chiqarib yuboradi

    rows = U.objects.filter(role='manager')

    if q:
        rows = rows.filter(
            Q(ism__icontains=q) |
            Q(familya__icontains=q) |
            Q(email__icontains=q)
        )

    paginator = Paginator(rows, page_size)
    page_obj = paginator.get_page(1)  # ❗ har doim birinchi sahifa

    start_index = page_obj.start_index()

    return render(request, 'core/stats_users.html', {
        'title': 'Managerlar',
        'rows': rows,
        'page_obj': page_obj,
        'page_size': page_size,
        'start_index': start_index,

        # ❗ paginationni o‘chiradigan flag
        'no_pagination': True,
    })


from education.models import Group, Enrollment
from datetime import date
from django.utils import timezone
from education.models import TuitionMonth

def _first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)

def _parse_month_yyyy_mm(s: str) -> date | None:
    """
    "2026-01" -> date(2026,1,1)
    xato bo'lsa None
    """
    try:
        s = (s or "").strip()
        if not s:
            return None
        y, m = s.split("-")
        y = int(y); m = int(m)
        if m < 1 or m > 12:
            return None
        return date(y, m, 1)
    except Exception:
        return None

@login_required
def user_edit(request, pk):
    user = get_object_or_404(U, id=pk)

    all_groups = Group.objects.all()
    enrollments = Enrollment.objects.filter(student=user).select_related("group")

    # ✅ next_url va month ni oldindan olib qo'yamiz (template ham shundan foydalanadi)
    next_url = request.POST.get("next") or request.GET.get("next") or "/stat/students/"

    month_str = request.POST.get("month") or request.GET.get("month") or ""
    # agar sizda parse_month_str bo'lsa:
    # selected_month = parse_month_str(month_str) if month_str else _first_day_of_month(timezone.localdate())
    selected_month = _parse_month_yyyy_mm(month_str) or _first_day_of_month(timezone.localdate())

    if request.method == "POST":
        # 1) USER MA'LUMOTLARI
        user.ism = (request.POST.get("ism") or "").strip()
        user.familya = (request.POST.get("familya") or "").strip()
        user.otchestvo = (request.POST.get("otchestvo") or "").strip()
        user.email = (request.POST.get("email") or "").strip()
        user.telefon1 = (request.POST.get("telefon1") or "").strip()
        user.telefon2 = (request.POST.get("telefon2") or "").strip()
        user.role = (request.POST.get("role") or "").strip() or user.role

        password = request.POST.get("password")
        if password:
            user.set_password(password)

        user.save()

        # 2) Mavjud enrollmentlar bo‘yicha narxlarni yangilash / o‘chirish
        for enroll in enrollments:
            # checkbox bosilgan bo'lsa — deactivate (modelingizdagi field nomiga moslang)
            if request.POST.get(f"delete_group_{enroll.id}") == "on":
                # ✅ Enrollment’da "active" yo'q ekan. O'zingizdagi field nomiga moslang:
                if hasattr(enroll, "is_active"):
                    enroll.is_active = False
                    enroll.save(update_fields=["is_active"])
                elif hasattr(enroll, "status"):
                    enroll.status = "inactive"
                    enroll.save(update_fields=["status"])
                else:
                    # eng oxirgi variant (xohlamasangiz olib tashlang)
                    enroll.delete()
                continue

            # aks holda narxni yangilaymiz
            field = f"kurs_narhi_{enroll.id}"
            new_price_raw = request.POST.get(field)

            if new_price_raw is not None and str(new_price_raw).strip() != "":
                try:
                    enroll.kurs_narhi = int(new_price_raw)
                    enroll.save(update_fields=["kurs_narhi"])

                    # ✅ MUHIM: aynan USER tanlagan oyga yozamiz (2026-01 bo'lsa shu)
                    TuitionMonth.objects.update_or_create(
                        enrollment=enroll,
                        month=selected_month,
                        defaults={"fee_amount": enroll.kurs_narhi},
                    )
                except ValueError:
                    pass

        # 3) Yangi guruhga qo‘shish (ixtiyoriy)
        yangi_group_id = request.POST.get("yangi_group_id")
        yangi_group_price = request.POST.get("yangi_group_price")

        if yangi_group_id:
            group = Group.objects.get(id=yangi_group_id)
            enroll, created = Enrollment.objects.get_or_create(student=user, group=group)
            if yangi_group_price:
                try:
                    enroll.kurs_narhi = int(yangi_group_price)
                except ValueError:
                    pass
            enroll.save()

            TuitionMonth.objects.update_or_create(
                enrollment=enroll,
                month=selected_month,
                defaults={"fee_amount": enroll.kurs_narhi or 0},
            )

        # ✅ ENG MUHIM: POSTdan keyin doim redirect (PRG) => kesh muammosi yo'q bo'ladi
        return redirect(next_url)

    return render(request, "core/user_edit.html", {
        "user_obj": user,
        "enrollments": enrollments,
        "groups": all_groups,
        "next": next_url,
        "month": month_str,          # ✅ template hidden input uchun
        "selected_month": selected_month,
    })

@login_required
def user_delete(request, pk):
    if not _staff_only(request):
        return render(request, 'core/dashboard_guest.html')

    user = get_object_or_404(U, pk=pk)

    if request.method == "POST":
        user.delete()
        return redirect("core:stat_students")

    return render(request, "core/user_delete.html", {
        "user": user
    })


@login_required
def user_view(request, pk):
    user = get_object_or_404(U, pk=pk)

    return render(request, "core/user_view.html", {
        "user": user
    })

@login_required
def stat_teachers(request):
    if not _staff_only(request):
        return render(request, 'core/dashboard_guest.html')

    q = request.GET.get("q", "").strip()
    page_size = 9999

    rows = (
        U.objects.filter(role="teacher")
        .prefetch_related('enrollment_set__group')
        .order_by("id")
    )
    if q:
        rows = rows.filter(Q(ism__icontains=q) | Q(familya__icontains=q) | Q(email__icontains=q))

    paginator = Paginator(rows, page_size)
    page_obj = paginator.get_page(1)
    start_index = page_obj.start_index()

    return render(request, "core/stats_users.html", {
        "title": "O‘qituvchilar",
        "page_obj": page_obj,
        "start_index": start_index,
        "page_size": page_size,
        "no_pagination": True,
    })

@login_required
def stat_students(request):
    if not _staff_only(request):
        return render(request, 'core/dashboard_guest.html')

    q = request.GET.get("q", "").strip()
    page_size = request.GET.get("size", "10")     # DEFAULT 10
    try:
        page_size = int(page_size)
    except:
        page_size = 10

    rows = (
        U.objects.filter(role='student')
        .prefetch_related('enrollment_set__group')
        .annotate(jami_chaqmoq=Sum("ledger__ball"))
        .order_by("id")
    )

    if q:
        rows = rows.filter(
            Q(ism__icontains=q) |
            Q(familya__icontains=q) |
            Q(email__icontains=q)
        )

    paginator = Paginator(rows, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    start_index = page_obj.start_index()

    return render(request, "core/stats_users.html", {
        "title": "O‘quvchilar",
        "page_obj": page_obj,
        "start_index": start_index,
        "page_size": page_size,
    })

import re
import secrets
import string

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from openpyxl import load_workbook


# ---------------- HELPERS ----------------

def _normalize_header(x: str) -> str:
    return (str(x or "").strip().lower()
            .replace("’", "'").replace("`", "'")
            .replace(" ", "").replace("_", "").replace("-", ""))


def _pick_col(headers_map, *aliases):
    for a in aliases:
        key = _normalize_header(a)
        if key in headers_map:
            return headers_map[key]
    return None


def _cell_to_str(v):
    """Excel cell qiymatini toza stringga aylantiradi (int/float bo‘lsa ham)."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v)).strip()
    return str(v).strip()


def _clean_for_login(text: str) -> str:
    """ism/familyani login uchun tozalash (oddiy translit + faqat a-z0-9)."""
    s = (text or "").strip().lower()

    # Uzbekcha belgilarni soddalashtiramiz
    s = s.replace("o‘", "o").replace("o'", "o")
    s = s.replace("g‘", "g").replace("g'", "g")
    s = s.replace("’", "").replace("'", "")

    # faqat a-z0-9
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _gen_default_password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


def _gen_unique_gmail_like_email(U, ism: str, familya: str) -> str:
    """
    mahmudjon.aminboyev4832@gmail.com
    """
    first = _clean_for_login(ism) or "user"
    last = _clean_for_login(familya)

    base = f"{first}.{last}" if last else first

    for _ in range(80):
        suffix = secrets.randbelow(9000) + 1000  # 4 xonali
        email = f"{base}{suffix}@gmail.com"
        if not U.objects.filter(email=email).exists():
            return email

    token = secrets.token_hex(3)
    return f"{base}{token}@gmail.com"


# ---------------- MAIN IMPORT VIEW ----------------

@login_required
@require_POST
def students_import_excel(request):
    if not _staff_only(request):
        return render(request, 'core/dashboard_guest.html')

    f = request.FILES.get("file")
    if not f:
        messages.error(request, "Excel fayl tanlanmadi.")
        return redirect("core:stat_students")

    if not f.name.lower().endswith(".xlsx"):
        messages.error(request, "Faqat .xlsx format qabul qilinadi (Excel 2007+).")
        return redirect("core:stat_students")

    try:
        wb = load_workbook(filename=f, data_only=True)
        ws = wb.active
    except Exception as e:
        messages.error(request, f"Excel o‘qib bo‘lmadi: {e}")
        return redirect("core:stat_students")

    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        messages.error(request, "Excel bo‘sh yoki sarlavha (header) yo‘q.")
        return redirect("core:stat_students")

    header_row = rows[0]
    headers_map = {}
    for idx, h in enumerate(header_row):
        key = _normalize_header(h)
        if key:
            headers_map[key] = idx

    # Excel ustunlari (email/parol/guruhlar yo‘q!)
    col_ism = _pick_col(headers_map, "ism", "firstname", "name", "first name")
    col_fam = _pick_col(headers_map, "familya", "familiya", "lastname", "surname", "last name")
    col_otch = _pick_col(headers_map, "otchestvo", "middlename", "patronymic", "middle name")
    col_tel1 = _pick_col(headers_map, "telefon", "telefon1", "phone", "tel", "phone1", "tel1")
    col_tel2 = _pick_col(headers_map, "telefon2", "phone2", "tel2")

    # ism & familya bo‘lmasa import qilmaymiz
    if col_ism is None or col_fam is None:
        messages.error(request, "Excel’da 'ism' va 'familya' ustunlari bo‘lishi shart.")
        return redirect("core:stat_students")

    created = 0
    updated = 0
    skipped = 0
    problems = []
    created_credentials = []  # yangi yaratilganlar uchun login/parol ro‘yxat

    with transaction.atomic():
        for r_i, r in enumerate(rows[1:], start=2):
            if not r or all((c is None or str(c).strip() == "") for c in r):
                continue

            ism = _cell_to_str(r[col_ism]) if (col_ism < len(r)) else ""
            fam = _cell_to_str(r[col_fam]) if (col_fam < len(r)) else ""
            otch = _cell_to_str(r[col_otch]) if (col_otch is not None and col_otch < len(r)) else ""

            tel1 = _cell_to_str(r[col_tel1]) if (col_tel1 is not None and col_tel1 < len(r)) else ""
            tel2 = _cell_to_str(r[col_tel2]) if (col_tel2 is not None and col_tel2 < len(r)) else ""

            if not ism or not fam:
                skipped += 1
                problems.append(f"{r_i}-qator: ism yoki familya yo‘q (skip).")
                continue

            try:
                # 1) Telefon bo‘lsa — dublikatni oldini olamiz (update)
                u = None
                if tel1:
                    u = U.objects.filter(role="student", telefon1=tel1).first()

                if u:
                    # UPDATE: email/parolga tegmaymiz
                    u.ism = ism
                    u.familya = fam
                    u.otchestvo = otch
                    if tel1:
                        u.telefon1 = tel1
                    if tel2:
                        u.telefon2 = tel2
                    if getattr(u, "role", None) != "student":
                        u.role = "student"
                    u.save()
                    updated += 1

                else:
                    # 2) CREATE: email+parol avtomatik
                    email = _gen_unique_gmail_like_email(U, ism, fam)
                    password = _gen_default_password()

                    u = U(email=email)
                    u.role = "student"
                    u.ism = ism
                    u.familya = fam
                    u.otchestvo = otch
                    if tel1:
                        u.telefon1 = tel1
                    if tel2:
                        u.telefon2 = tel2

                    u.set_password(password)
                    u.save()

                    created += 1
                    created_credentials.append((ism, fam, email, password))

            except Exception as e:
                skipped += 1
                problems.append(f"{r_i}-qator: xatolik — {e}")

    messages.success(request, f"Import tugadi ✅ Yangi: {created}, Yangilandi: {updated}, Skip: {skipped}")

    # yangi login/parollarni ekranga chiqarib beramiz (faqat 10 tasi)
    if created_credentials:
        preview = created_credentials[:10]
        text = " | ".join([f"{a} {b}: {e} / {p}" for a, b, e, p in preview])
        if len(created_credentials) > 10:
            text += f" | ... (+{len(created_credentials)-10} ta)"
        messages.info(request, f"Yangi login/parollar: {text}")

    if problems:
        preview = " | ".join(problems[:8])
        if len(problems) > 8:
            preview += f" | ... (+{len(problems)-8} ta)"
        messages.warning(request, f"Ogohlantirishlar: {preview}")

    return redirect("core:stat_students")





import openpyxl
from openpyxl.styles import Font, Alignment

from django.http import HttpResponse

@login_required
def stat_students_export_excel(request):
    if not _staff_only(request):
        return HttpResponse("Ruxsat yo‘q", status=403)

    # Studentlarni olamiz
    students = (
        U.objects.filter(role='student')
        .prefetch_related('enrollment_set__group')
        .annotate(jami_chaqmoq=Sum("ledger__ball"))
        .order_by("id")
    )

    # Excel yaratamiz
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Oquvchilar"

    # Header yozamiz
    headers = ["#", "F.I.Sh", "Login", "Telefon", "Guruhlar"]
    ws.append(headers)

    # Header style
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    # Data yozamiz
    for idx, u in enumerate(students, start=1):
        groups = ", ".join([e.group.nom for e in u.enrollment_set.all()])
        phone = u.telefon1 or ""

        ws.append([
            idx,
            f"{u.ism} {u.familya}",
            u.email,
            phone,
            groups
        ])

    # Javob sifatida Excel qaytaramiz
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename="oquvchilar.xlsx"'
    wb.save(response)

    return response


@login_required
def stat_products(request):
    if not _staff_only(request): return render(request, 'core/dashboard_guest.html')
    q = request.GET.get('q','').strip()
    rows = Product.objects.all().order_by('-yaratilgan')
    if q:
        rows = rows.filter(Q(nom__icontains=q)|Q(izoh__icontains=q))
    return render(request, 'core/stats_products.html', {'title': "Mahsulotlar", 'rows': rows})




@login_required
def teacher_delete(request, pk):
    if request.user.role not in ('manager', 'director') and not request.user.is_superuser:
        messages.error(request, "Ruxsat yo‘q.")
        return redirect('core:teacher_list')

    teacher = get_object_or_404(User, pk=pk, role='teacher')

    if request.method == "POST":
        teacher.delete()
        messages.success(request, "O‘qituvchi o‘chirildi ✅")
        return redirect('core:teacher_list')

    return redirect('core:teacher_list')


@login_required
def stat_requests(request):
    if not _staff_only(request): return render(request, 'core/dashboard_guest.html')
    status = request.GET.get('status','')
    rows = PurchaseRequest.objects.select_related('student','product','manager').order_by('-sana')
    if status in ('pending','approved','rejected'):
        rows = rows.filter(status=status)
    return render(request, 'core/stats_requests.html', {'title': "Kutilayotgan so‘rovlar", 'rows': rows, 'status': status})

@login_required
def stat_ledger(request):
    if not _staff_only(request): return render(request, 'core/dashboard_guest.html')
    # default: reyting (jamlanma)
    leaderboard = (Ledger.objects
                   .values('student__id','student__ism','student__familya')
                   .annotate(jami=Sum('ball'))
                   .order_by('-jami'))
    # oxirgi 50 yozuv
    last = Ledger.objects.select_related('student','rule','group').order_by('-sana')[:50]
    jami = Ledger.objects.aggregate(s=Sum('ball'))['s'] or 0
    return render(request, 'core/stats_ledger.html', {'leaderboard': leaderboard, 'last': last, 'sum_all': jami})