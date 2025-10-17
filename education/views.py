# education/views.py
from datetime import datetime
from tokenize import group
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Value, F
from .models import  Group,  User
from django.utils.dateparse import parse_date
from django.utils.timezone import localdate, make_aware

from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
import json

from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localdate

from accounts.models import User
from .forms import GroupForm, ITGroupForm, LangGroupForm
from .models import Group, Enrollment, Attendance
from chaqmoq.models import Ledger, Rule
from django.db.models.functions import Abs, Coalesce

U = get_user_model()

DAILY_LIMIT = 50  # har bir o‘qituvchi → har bir o‘quvchi uchun, bugungi kun limiti

# ---------- Ruxsat helperlari ----------
def _can_manage(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _can_give_points(user, g: Group):
    return (
        user.is_superuser
        or user.role in ("director", "manager")
        or (user.role == "teacher" and g.oqituvchi_id == user.id)
    )

def _teacher_can(user, g: Group) -> bool:
    return user.is_superuser or user.role in ("director", "manager") or (
        user.role == "teacher" and g.oqituvchi_id == user.id
    )

# ---------- HUB va ro'yxatlar ----------
@login_required
def groups_hub(request):
    return render(request, "education/groups_hub.html")


@login_required
def groups_by_category(request, category):
    if category not in ("lang", "it"):
        raise Http404("Noto‘g‘ri kategoriya")

    rows = (
        Group.objects.filter(category=category)
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")
    )
    return render(
        request,
        "education/groups_by_category.html",
        {"rows": rows, "category": category, "can_manage": _can_manage(request.user)},
    )


# DRY: guruh yaratish
def _create_group(request, category_value):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:groups_hub")

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            g = form.save(commit=False)
            g.category = category_value
            g.save()
            messages.success(request, "Guruh yaratildi.")
            return redirect("education:group_detail", pk=g.pk)
    else:
        form = GroupForm(initial={"category": category_value})

    title = "Tillar bo‘yicha guruh yaratish" if category_value == Group.LANG else "IT bo‘yicha guruh yaratish"
    return render(request, "education/group_form.html", {"form": form, "title": title})


@login_required
def group_create_lang(request):
    return _create_group(request, Group.LANG)


@login_required
def group_create_it(request):
    return _create_group(request, Group.IT)


# (eski ro'yxatlar kerak bo'lsa)
@login_required
def guruhlar(request):
    rows = (
        Group.objects.select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")
    )
    return render(request, "education/groups.html", {"rows": rows, "can_manage": _can_manage(request.user)})


@login_required
def guruhlar_tillar(request):
    return groups_by_category(request, Group.LANG)


@login_required
def guruhlar_it(request):
    return groups_by_category(request, Group.IT)


# ---------- Bitta guruh (bitta sahifada hamma narsa) ----------
@login_required
def group_detail(request, pk: int):
    g = get_object_or_404(Group, pk=pk)

    # O'qituvchilar faqat o'z guruhini ko'ra olishi
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return HttpResponseForbidden("Siz bu guruhni ko‘ra olmaysiz.")

    # GET param orqali sana (YYYY-MM-DD) — agar yo'q bo'lsa bugun
    date_str = request.GET.get('date')
    if date_str:
        sel = parse_date(date_str)
        if sel is None:
            selected_date = localdate()
        else:
            selected_date = sel
    else:
        selected_date = localdate()

    # Guruh a'zolari
    enrollments = (
        Enrollment.objects
        .filter(group=g)
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )

    # Ball (balans) map
    student_ids = [e.student_id for e in enrollments]
    bal_qs = Ledger.objects.filter(student_id__in=student_ids).values('student_id').annotate(s=Coalesce(Sum('ball'), 0))
    bal_map = {item['student_id']: item['s'] for item in bal_qs}

    # Tanlangan sanadagi davomat
    pres_qs = Attendance.objects.filter(group=g, date=selected_date)
    pres_map = {a.student_id: a.present for a in pres_qs}

    # Qoida ro'yxatlari
    rules_plus = Rule.objects.filter(tur=Rule.PLUS).order_by("nom")
    rules_minus = Rule.objects.filter(tur=Rule.MINUS).order_by("nom")

    # Front uchun atributlar
    for e in enrollments:
        s = e.student
        s.balance = int(bal_map.get(s.id, 0))
        # present_today nomini saqlab qolamiz (template shu nomdan foydalanadi)
        s.present_today = bool(pres_map.get(s.id, False))

    can_add_student = request.user.role in ['director', 'manager', 'teacher']

    ctx = {
        "g": g,
        "enrollments": enrollments,
        "rules_plus": rules_plus,
        "rules_minus": rules_minus,
        "can_add_student": can_add_student,
        # template uchun sana (string)
        "selected_date": selected_date.isoformat(),
        "today": localdate().isoformat(),
    }
    return render(request, "education/group_detail.html", ctx)





# ---------- AJAX: Davomatni saqlash ----------
@login_required
def attendance_today(request, pk: int):
    """
    Davomatni saqlaydi: form-data yoki JSON qabul qiladi.
    Kutilgan maydonlar: enr_id yoki student_id (int), present (1/0/true/false), date (YYYY-MM-DD) - ixtiyoriy.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"}, status=405)

    # data olinishi (JSON yoki form)
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            data = json.loads(request.body.decode())
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    else:
        data = request.POST

    g = get_object_or_404(Group, pk=pk)
    if request.user.role == "teacher" and g.oqituvchi != request.user and not _teacher_can(request.user, g):
        return HttpResponseForbidden()

    enr_id = (data.get("enr_id") or "").strip()
    student_id = (data.get("student_id") or "").strip()
    date_str = (data.get("date") or "").strip()

    # sana
    if date_str:
        the_date = parse_date(date_str)
        if not the_date:
            return JsonResponse({"ok": False, "error": "Invalid date"}, status=400)
    else:
        the_date = localdate()

    # o'quvchini aniqlash
    if enr_id and str(enr_id).isdigit():
        enr = get_object_or_404(Enrollment, pk=int(enr_id), group=g)
        student = enr.student
    elif student_id and str(student_id).isdigit():
        student = get_object_or_404(User, pk=int(student_id), role="student")
    else:
        return JsonResponse({"ok": False, "error": "ID not provided"}, status=400)

    present_raw = data.get("present")
    present = str(present_raw).lower() in ("1", "true", "yes", "on")

    attendance, created = Attendance.objects.update_or_create(
        group=g,
        student=student,
        date=the_date,
        defaults={
            "present": present,
            "teacher": request.user if request.user.role == "teacher" else request.user if request.user.role in ("director", "manager") else None
        }
    )

    return JsonResponse({"ok": True, "present": attendance.present})



# ---------- AJAX: Chaqmoq yozish/ayirish ----------
@login_required
def group_points(request, pk: int):
    # Faqat POST
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"}, status=405)

    # JSON yoki form-data
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode())
        except Exception:
            data = {}
    else:
        data = request.POST

    # Guruhni tekshirish
    g = get_object_or_404(Group, pk=pk)
    if request.user.role == "teacher" and g.oqituvchi != request.user and not _teacher_can(request.user, g):
        return HttpResponseForbidden()

    # Ma'lumotlarni olish
    student_id = (data.get("student_id") or "").strip()
    rule_id = (data.get("rule_id") or "").strip()
    amount_raw = (data.get("amount") or "0").strip()
    date_str = (data.get("date") or "").strip()

    # Ballni parse qilish
    try:
        amount = int(amount_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Noto‘g‘ri ball kiritildi"}, status=400)

    if amount == 0:
        return JsonResponse({"ok": False, "error": "0 ball yozilmaydi"}, status=400)

    # Studentni olish
    student = get_object_or_404(User, pk=int(student_id), role="student")

    # Qoida olish
    if rule_id and rule_id.isdigit():
        rule = get_object_or_404(Rule, pk=int(rule_id))
    else:
        rule = Rule.objects.filter(nom="Erkin ball").first() or Rule.objects.create(
            nom="Erkin ball", tur=Rule.PLUS, min_baho=1, max_baho=1000000
        )

    # ✅ SANANI ANIQLASH
    if date_str:
        try:
            # foydalanuvchi tanlagan sana (faqat YYYY-MM-DD)
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            parsed_date = timezone.localdate()
    else:
        parsed_date = timezone.localdate()

    # Datetimega aylantirish (timezone bilan)
    sana = timezone.make_aware(datetime.combine(parsed_date, datetime.min.time()))

    # ⚡ Ledger yozuvini yaratish
    record = Ledger.objects.create(
        student=student,
        beruvchi=request.user,
        group=g,
        rule=rule,
        ball=amount,
        sana=sana,
    )

    # Balansni qayta hisoblash
    balance_agg = Ledger.objects.filter(student=student).aggregate(s=Coalesce(Sum("ball"), 0))
    balance = int(balance_agg.get("s") or 0)

    return JsonResponse({
        "ok": True,
        "amount": amount,
        "balance": balance,
        "saved_date": parsed_date.strftime("%Y-%m-%d"),
        "id": record.id
    })


@login_required
def student_detail(request, student_id: int):
    """
    Foydalanuvchining davomat va chaqmoq tarixini ko‘rsatadi.
    """
    student = get_object_or_404(User, pk=student_id, role="student")

    att_dates = Attendance.objects.filter(student=student).values_list('date', flat=True)
    ledger_dates = Ledger.objects.filter(student=student).values_list('sana', flat=True)

    # har ikkala sanani toza date formatga o‘tkazamiz
    all_dates = []
    for d in att_dates:
        if hasattr(d, 'date'):
            d = d.date()
        all_dates.append(d)
    for d in ledger_dates:
        if hasattr(d, 'date'):
            d = d.date()
        all_dates.append(d)

    dates = sorted(set(all_dates), reverse=True)[:30]

    history = []
    for d in dates:
        # ✅ Davomat
        present_qs = Attendance.objects.filter(student=student, date=d)
        present = present_qs.exists() and any(a.present for a in present_qs)

        # ✅ Ledgerdan o‘sha sanaga tegishli plus/minus yig‘indi
        plus_sum = Ledger.objects.filter(
            student=student, sana__date=d, ball__gt=0
        ).aggregate(s=Coalesce(Sum('ball'), 0))['s'] or 0

        minus_sum = Ledger.objects.filter(
            student=student, sana__date=d, ball__lt=0
        ).aggregate(s=Coalesce(Sum('ball'), 0))['s'] or 0

        history.append({
            'date': d,
            'is_present': bool(present),
            'plus_coin': int(plus_sum),
            'minus_coin': int(abs(minus_sum)),
        })

    return render(request, 'education/student_detail.html', {
        'student': student,
        'history': history
    })




# ---------- (ixtiyoriy) alohida Davomat/Chaqmoq sahifasi ----------
@login_required
def group_rollcall(request, pk):
    g = get_object_or_404(Group, pk=pk)
    if not _can_give_points(request.user, g):
        return HttpResponseForbidden()

    # sana
    date_str = request.GET.get("date") or request.POST.get("date")
    try:
        the_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else localdate()
    except Exception:
        the_date = localdate()

    students = [
        e.student for e in g.enrollments.select_related("student").order_by("student__ism", "student__familya")
    ]

    pres_map = {
        a.student_id: a.present for a in Attendance.objects.filter(group=g, date=the_date)
    }
    bal_map = {
        row["student_id"]: (row["total"] or 0)
        for row in (
            Ledger.objects.filter(student_id__in=[s.id for s in students])
            .values("student_id").annotate(total=Sum("ball"))
        )
    }

    for s in students:
        s.present = pres_map.get(s.id, False)
        s.balance = bal_map.get(s.id, 0)

    rules = Rule.objects.order_by("nom")

    if request.method == "POST" and request.POST.get("save") == "1":
        saved = 0
        for s in students:
            present = bool(request.POST.get(f"present_{s.id}"))
            Attendance.objects.update_or_create(
                group=g,
                student=s,
                date=the_date,
                defaults={"present": present, "teacher": request.user if request.user.role == "teacher" else None},
            )
            rule_id = request.POST.get(f"rule_{s.id}")
            amount_raw = request.POST.get(f"ball_{s.id}") or "0"
            try:
                amount = int(amount_raw)
            except ValueError:
                amount = 0
            if rule_id and amount:
                rule = get_object_or_404(Rule, pk=int(rule_id))
                abs_ball = abs(amount)
                if rule.min_baho <= abs_ball <= rule.max_baho:
                    signed = abs_ball if rule.tur == Rule.PLUS else -abs_ball
                    Ledger.objects.create(student=s, beruvchi=request.user, group=g, rule=rule, ball=signed)
                    saved += 1
        messages.success(request, f"Saqlash tugadi. {saved} ta chaqmoq yozildi.")
        return redirect(f"{request.path}?date={the_date.isoformat()}")

    return render(
        request,
        "education/group_rollcall.html",
        {"g": g, "date": the_date.isoformat(), "students": students, "rules": rules},
    )


# ---------- CRUD ----------
@login_required
def group_create(request, category=None):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:guruhlar")

    if category == Group.LANG:
        FormCls, title = LangGroupForm, "Tillar bo‘yicha guruh yaratish"
    elif category == Group.IT:
        FormCls, title = ITGroupForm, "IT bo‘yicha guruh yaratish"
    else:
        FormCls, title = GroupForm, "Guruh yaratish"

    form = FormCls(request.POST or None)
    if request.method == "POST" and form.is_valid():
        g = form.save()
        messages.success(request, "Guruh yaratildi.")
        return redirect("education:group_detail", pk=g.pk)

    return render(request, "education/group_form.html", {"form": form, "title": title})


@login_required
def group_edit(request, pk):
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:guruhlar")
    g = get_object_or_404(Group, pk=pk)
    form = GroupForm(request.POST or None, instance=g)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guruh yangilandi.")
        return redirect("education:group_detail", pk=g.id)
    return render(request, "education/group_form.html", {"form": form, "title": "Guruhni tahrirlash"})


@login_required
def group_list(request):
    # Guruhlarni olish
    category = request.GET.get("category")
    rows = Group.objects.all().select_related("center", "oqituvchi")

    # Kimlar guruh yaratishi va tahrirlashi mumkinligini aniqlaymiz
    can_manage = request.user.is_superuser or request.user.role in ["Director", "Manager", "Teacher"]

    # Template'ga yuboriladigan kontekst
    ctx = {
        "rows": rows,
        "category": category,
        "can_manage": can_manage,
        "filter_title": "Guruhlar",
    }

    return render(request, "education/groups.html", ctx)


from django.contrib import messages

@login_required
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    category = group.category  # Faraz qilamiz: groupda category degan maydon bor ("lang" yoki "it")
    group.delete()

    # 🔁 Shu yerda qayerga qaytarishni tekshiramiz
    if category == "lang":
        return redirect("education:groups_lang")
    elif category == "it":
        return redirect("education:groups_it")
    else:
        return redirect("education:groups_hub")  # default holat



@login_required
def add_student_to_group(request, pk: int):
    g = get_object_or_404(Group, pk=pk)

    # Faqat ruxsatli rollar qo‘shishi mumkin
    allowed_roles = ['admin', 'manager', 'teacher', 'director']
    if request.user.role not in allowed_roles:
        return HttpResponseForbidden("Sizda bu amalni bajarish uchun ruxsat yo‘q.")

    # O‘quvchilarni olish (ilgari enrollments__group bo‘lgandi)
    # To‘g‘risi: enrollment__group
    students = (
        User.objects
        .filter(role="student")
        .exclude(enrollment__group=g)
        .order_by("ism", "familya")
    )

    # POST so‘rov bilan yuborilsa — o‘quvchini qo‘shamiz
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        if not student_id:
            return HttpResponse("O‘quvchi tanlanmagan.", status=400)

        student = get_object_or_404(User, pk=student_id, role="student")

        # Yangi Enrollment yaratamiz
        Enrollment.objects.create(group=g, student=student)
        messages.success(request, f"{student.ism} guruhga qo‘shildi.")
        return redirect("education:group_detail", pk=g.id)

    ctx = {
        "g": g,
        "students": students,
    }

    return render(request, "education/add_student_to_group.html", ctx)


@require_POST
def toggle_attendance(request):
    student_id = request.POST.get("student_id")
    group_id = request.POST.get("group_id")
    date_str = request.POST.get("date")

    if not (student_id and group_id):
        return JsonResponse({"error": "Invalid data"}, status=400)

    date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timezone.localdate()

    att, created = Attendance.objects.get_or_create(
        group_id=group_id,
        student_id=student_id,
        date=date,
        defaults={"teacher": request.user}
    )

    # Belgini o‘zgartiramiz (agar bor bo‘lsa)
    att.present = not att.present
    att.teacher = request.user
    att.save()

    return JsonResponse({
        "success": True,
        "present": att.present,
        "date": att.date.strftime("%Y-%m-%d"),
    })




# ---------- A'zolik va o'qituvchi sahifasi ----------
@login_required
def enrollment_remove(request, pk):
    enr = get_object_or_404(Enrollment.objects.select_related("group", "student"), pk=pk)
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:group_detail", pk=enr.group_id)
    if request.method == "POST":
        enr.delete()
        messages.success(request, "O‘quvchi guruhdan chiqarildi.")
    return redirect("education:group_detail", pk=enr.group_id)


@login_required
def my_groups(request):
    rows = (
        Group.objects.filter(oqituvchi=request.user)
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")
    )
    return render(request, "education/my_groups.html", {"rows": rows})
