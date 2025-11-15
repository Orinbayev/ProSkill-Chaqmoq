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

@login_required
def stat_managers(request):
    if not _staff_only(request): return render(request, 'core/dashboard_guest.html')
    q = request.GET.get('q','').strip()
    rows = U.objects.filter(role='manager')
    if q:
        rows = rows.filter(Q(ism__icontains=q)|Q(familya__icontains=q)|Q(email__icontains=q))
    return render(request, 'core/stats_users.html', {'title': 'Managerlar', 'rows': rows})

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
    if not _staff_only(request): return render(request, 'core/dashboard_guest.html')
    q = request.GET.get('q','').strip()
    rows = U.objects.filter(role='student')
    if q:
        rows = rows.filter(Q(ism__icontains=q)|Q(familya__icontains=q)|Q(email__icontains=q))
    return render(request, 'core/stats_users.html', {'title': "O‘quvchilar", 'rows': rows})

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