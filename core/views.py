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
    teacher = get_object_or_404(User, pk=pk, role="teacher")

    if request.method == "POST":
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            teacher = form.save()

            # 🔥 Yangi foiz
            yangi_foiz = teacher.oqituvchi_foizi

            # 🔥 1) O‘qituvchi ishlaydigan barcha guruhlarni yangilash
            from education.models import Group, Enrollment

            Group.objects.filter(oqituvchi=teacher).update(oqituvchi_foiz=yangi_foiz)

            # 🔥 2) O‘qituvchining barcha enrollmentlarini yangilash
            Enrollment.objects.filter(group__oqituvchi=teacher).update(oqituvchi_foiz=yangi_foiz)

            return redirect("core:teacher_list")

    else:
        form = TeacherForm(instance=teacher)

    return render(request, "core/teacher_edit.html", {"form": form, "teacher": teacher})


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

@login_required
def user_edit(request, pk):
    user = get_object_or_404(U, id=pk)

    all_groups = Group.objects.all()
    enrollments = Enrollment.objects.filter(student=user).select_related("group")

    if request.method == "POST":
        # 1) USER MA'LUMOTLARI
        user.ism = request.POST.get("ism")
        user.familya = request.POST.get("familya")
        user.email = request.POST.get("email")
        user.telefon1 = request.POST.get("telefon1")
        user.telefon2 = request.POST.get("telefon2")
        user.role = request.POST.get("role")

        password = request.POST.get("password")
        if password:
            user.set_password(password)

        user.save()

        # 2) Mavjud guruhlar bo‘yicha narxlarni yangilash / o‘chirish
        for enroll in enrollments:
            # agar checkbox bosilgan bo‘lsa – guruhdan chiqaramiz
            if request.POST.get(f"delete_group_{enroll.id}") == "on":
                enroll.active = False          # ❌ delete emas
                enroll.save()
                continue


            # aks holda narxni yangilaymiz
            field = f"kurs_narhi_{enroll.id}"
            new_price = request.POST.get(field)
            if new_price:
                try:
                    enroll.kurs_narhi = int(new_price)
                    enroll.save()
                except ValueError:
                    pass

        # 3) Yangi guruhga qo‘shish (ixtiyoriy)
        yangi_group_id = request.POST.get("yangi_group_id")
        yangi_group_price = request.POST.get("yangi_group_price")

        if yangi_group_id:
            group = Group.objects.get(id=yangi_group_id)
            enroll, created = Enrollment.objects.get_or_create(
                student=user,
                group=group
            )
            if yangi_group_price:
                try:
                    enroll.kurs_narhi = int(yangi_group_price)
                except ValueError:
                    pass
            enroll.save()

        return redirect("/stat/students/")

    return render(request, "core/user_edit.html", {
        "user_obj": user,
        "enrollments": enrollments,
        "groups": all_groups,
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
    if not _staff_only(request): return render(request, 'core/dashboard_guest.html')
    q = request.GET.get('q','').strip()
    rows = U.objects.filter(role='teacher')
    if q:
        rows = rows.filter(Q(ism__icontains=q)|Q(familya__icontains=q)|Q(email__icontains=q))
    return render(request, 'core/stats_users.html', {'title': "O‘qituvchilar", 'rows': rows})

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