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
from django.db.models.functions import ExtractMonth, ExtractYear
from datetime import date

from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
import json

from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localdate, timedelta

from accounts.models import User
from .forms import GroupForm, ITGroupForm, LangGroupForm
from .models import Group, Enrollment, Attendance, Payment 
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
    """
    📘 Guruhlar markaziy sahifasi — barcha kategoriyalar ro‘yxati.
    """
    from .models import Category  # agar alohida model bo‘lsa
    categories = Category.objects.all() if hasattr(Category, "objects") else []
    return render(request, "education/groups_home.html", {
        "categories": categories,
    })

def group_delete_confirm(request, id):
    group = get_object_or_404(Group, id=id)
    if request.method == "POST":
        group.delete()
        return redirect("education:groups_home")
    return render(request, "education/group_delete_confirm.html", {"g": group})



@login_required
def edit_category(request, id):
    cat = get_object_or_404(Category, id=id)
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        image = request.FILES.get("image")

        cat.name = name
        cat.description = description

        # 🔹 Agar yangi rasm tanlangan bo‘lsa, yangisini saqlaymiz
        if image:
            cat.image = image

        cat.save()
        messages.success(request, "Bo‘lim muvaffaqiyatli tahrirlandi ✅")
        return redirect("education:groups_home")

    return render(request, "education/category_edit.html", {"cat": cat})


@login_required
def delete_category(request, id):
    cat = get_object_or_404(Category, id=id)
    if request.method == "POST":
        cat.delete()
        messages.success(request, "Bo‘lim o‘chirildi 🗑️")
        return redirect("education:groups_home")
    return render(request, "education/category_delete_confirm.html", {"cat": cat})


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
@login_required
def create_group_for_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:groups_home")

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)

            # 🟢 To‘g‘ri maydon: ForeignKey bo‘lgan 'category_obj'
            group.category_obj = category

            # Eski 'category' maydoni ham to‘ldirilsa yaxshi
            group.category = Group.IT  # yoki Group.LANG — kerakli turga qarab
            group.save()

            messages.success(request, f"✅ '{group.nom}' guruhi {category.name} bo‘limiga qo‘shildi.")
            return redirect("education:category_detail", category_id=category.id)
    else:
        form = GroupForm()

    return render(request, "education/group_form.html", {"form": form, "category": category})

# @login_required
# def group_create_lang(request):
#     return _create_group(request, Group.LANG)


# @login_required
# def group_create_it(request):
#     return _create_group(request, Group.IT)


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

    # Faqat o‘qituvchi o‘z guruhini ko‘ra oladi
    if request.user.role == "teacher" and g.oqituvchi != request.user:
        return HttpResponseForbidden("Siz bu guruhni ko‘ra olmaysiz.")

    # Sana tanlash
    date_str = request.GET.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()
    if not selected_date:
        selected_date = localdate()

    # Guruhdagi o‘quvchilar
    enrollments = (
        Enrollment.objects
        .filter(group=g)
        .select_related("student")
        .order_by("student__ism", "student__familya")
    )

    student_ids = [e.student_id for e in enrollments]

    # Balanslarni olish
    bal_qs = Ledger.objects.filter(student_id__in=student_ids).values("student_id").annotate(s=Coalesce(Sum("ball"), 0))
    bal_map = {b["student_id"]: b["s"] for b in bal_qs}

    # ✅ Davomatni olish
    try:
        start = make_aware(datetime.combine(selected_date, datetime.min.time()))
        end = make_aware(datetime.combine(selected_date + timedelta(days=1), datetime.min.time()))
        pres_qs = Attendance.objects.filter(group=g, date__gte=start, date__lt=end)
    except Exception:
        pres_qs = Attendance.objects.filter(group=g, date=selected_date)

    pres_map = {a.student_id: a.present for a in pres_qs}

    # Qoida ro‘yxatlari
    rules_plus = Rule.objects.filter(tur=Rule.PLUS).order_by("nom")
    rules_minus = Rule.objects.filter(tur=Rule.MINUS).order_by("nom")

    for e in enrollments:
        s = e.student
        s.balance = int(bal_map.get(s.id, 0))
        s.present_today = bool(pres_map.get(s.id, False))

    can_add_student = request.user.role in ["director", "manager", "teacher"]

    ctx = {
        "g": g,
        "enrollments": enrollments,
        "rules_plus": rules_plus,
        "rules_minus": rules_minus,
        "can_add_student": can_add_student,
        "selected_date": selected_date.isoformat(),
        "today": localdate().isoformat(),
    }

    return render(request, "education/group_detail.html", ctx)



# ---------- AJAX: Davomatni saqlash ----------
@login_required
def attendance_today(request, pk: int):
    """
    Har bir guruh uchun davomatni alohida saqlaydi.
    O‘quvchi bir kunda IT va Ingliz tilida qatnashsa — ikkita alohida Attendance yozuvi yaratiladi.
    Chaqmoqlar esa umumiy hisobda qoladi.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"}, status=405)

    # Guruhni topamiz
    g = get_object_or_404(Group, pk=pk)

    # Foydalanuvchi huquqini tekshiramiz
    if not _teacher_can(request.user, g):
        return JsonResponse({"ok": False, "error": "Ruxsat yo‘q"}, status=403)

    # Ma'lumotlarni olish
    enr_id = request.POST.get("enr_id")
    present_val = request.POST.get("present")
    date_str = request.POST.get("date")

    if not (enr_id and present_val is not None):
        return JsonResponse({"ok": False, "error": "Incomplete data"}, status=400)

    try:
        enrollment = Enrollment.objects.select_related("student").get(pk=int(enr_id), group=g)
    except Enrollment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Enrollment not found"}, status=404)

    student = enrollment.student
    present = str(present_val).lower() in ("1", "true", "yes", "on")

    # ✅ Sanani aniqlash
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            selected_date = localdate()
    else:
        selected_date = localdate()

    # ⚙️ Davomatni alohida guruhga yozamiz
    att, created = Attendance.objects.update_or_create(
        group=g,
        student=student,
        date=selected_date,
        defaults={"present": present, "teacher": request.user},
    )

    # 🔹 Endi chaqmoq tizimi (Ledger) umumiy qoladi, o‘chirmaymiz.
    # Faqat kelmagan bo‘lsa, shu guruhdagi shu kundagi yozuvlarni o‘chiramiz.
    removed_points = 0
    if not present:
        start = make_aware(datetime.combine(selected_date, datetime.min.time()))
        end = make_aware(datetime.combine(selected_date + timedelta(days=1), datetime.min.time()))
        removed_points = Ledger.objects.filter(
            student=student, group=g,
            sana__gte=start, sana__lt=end
        ).count()
        Ledger.objects.filter(
            student=student, group=g,
            sana__gte=start, sana__lt=end
        ).delete()

    return JsonResponse({
        "ok": True,
        "present": present,
        "removed_points": removed_points,
        "created": created
    })


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
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            parsed_date = timezone.localdate()
    else:
        parsed_date = timezone.localdate()

    sana = timezone.make_aware(datetime.combine(parsed_date, datetime.min.time()))

    # ✅ Kunlik chaqmoq limitini tekshirish
    from .models import DailyLightningSetting  # import kerak bo‘ladi
    setting = DailyLightningSetting.objects.filter(date=parsed_date, active=True).first()
    if setting and setting.max_lightning > 0:
        today_sum = Ledger.objects.filter(
            student=student,
            sana__date=parsed_date
        ).aggregate(s=Coalesce(Sum('ball'), 0))['s'] or 0

        if today_sum + amount > setting.max_lightning:
            return JsonResponse({
                "ok": False,
                "error": f"Bugun {setting.max_lightning} tadan ortiq chaqmoq berish mumkin emas."
            }, status=400)

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
def groups_home(request):
    categories = Category.objects.all().order_by("name")
    return render(request, "education/groups_home.html", {"categories": categories})


def category_detail(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    groups = Group.objects.filter(category_obj=category)  # 🟢 shu yerni o‘zgartir
    return render(request, 'education/category_detail.html', {
        'category': category,
        'groups': groups
    })




@login_required
def group_create_by_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.category_obj = category
            group.save()
            return redirect("education:category_detail", category_id=category.id)
    else:
        form = GroupForm()

    return render(request, "education/group_form.html", {
        "form": form,
        "category": category
    })



from .models import Category
from django import forms
from django.contrib import messages

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "image", "description"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Masalan: Dizayn"
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Bo‘lim haqida qisqa izoh"
            }),
        }



@login_required
def groups_home(request):
    """Barcha kategoriyalarni (bo‘limlarni) ko‘rsatish"""
    categories = Category.objects.all().order_by("name")
    return render(request, "education/groups_home.html", {"categories": categories})


@login_required
def add_category(request):
    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Bo‘lim muvaffaqiyatli qo‘shildi ✅")
            return redirect("education:groups_home")
    else:
        form = CategoryForm()
    return render(request, "education/category_add.html", {"form": form})




@login_required
def student_detail(request, student_id: int):
    student = get_object_or_404(User, pk=student_id, role="student")

    MONTH_NAMES = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel", 5: "May",
        6: "Iyun", 7: "Iyul", 8: "Avgust", 9: "Sentabr", 10: "Oktyabr",
        11: "Noyabr", 12: "Dekabr"
    }

    # 🔹 Endi davomatni guruhga qarab ajratamiz
    attendances = Attendance.objects.filter(student=student).select_related("group").annotate(
        year=ExtractYear('date'),
        month=ExtractMonth('date')
    ).order_by('-date')

    # 🔹 Chaqmoqlar ham guruh bo‘yicha hisoblanadi
    ledgers = Ledger.objects.filter(student=student).select_related("group").annotate(
        year=ExtractYear('sana'),
        month=ExtractMonth('sana')
    )

    # 🔹 Har bir guruh bo‘yicha ajratamiz
    grouped_by_group = {}
    for a in attendances:
        grouped_by_group.setdefault(a.group, []).append(a)

    month_summaries = []
    for group, group_attendances in grouped_by_group.items():
        # Guruh bo‘yicha oylik natijalarni tayyorlash
        grouped_by_month = {}
        for a in group_attendances:
            key = (a.year, a.month)
            grouped_by_month.setdefault(key, []).append(a)

        for (year, month), records in grouped_by_month.items():
            total_present = sum(1 for r in records if r.present)
            month_ledgers = ledgers.filter(year=year, month=month, group=group)
            plus_sum = month_ledgers.filter(ball__gt=0).aggregate(total=Sum('ball'))['total'] or 0
            minus_sum = month_ledgers.filter(ball__lt=0).aggregate(total=Sum('ball'))['total'] or 0

            month_summaries.append({
                "group": group.nom,  # 🔹 Guruh nomini qo‘shamiz
                "year": year,
                "month": month,
                "month_name": MONTH_NAMES.get(month, "Noma’lum oy"),
                "present_days": total_present,
                "plus": plus_sum,
                "minus": abs(minus_sum),
                "days": [
                    {
                        "date": r.date,
                        "present": r.present,
                        "plus": ledgers.filter(group=group, sana__date=r.date, ball__gt=0).aggregate(total=Sum('ball'))['total'] or 0,
                        "minus": abs(ledgers.filter(group=group, sana__date=r.date, ball__lt=0).aggregate(total=Sum('ball'))['total'] or 0)
                    }
                    for r in records
                ]
            })

    ctx = {
        "student": student,
        "month_summaries": month_summaries,
    }

    return render(request, "education/student_detail.html", ctx)




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

@login_required
def teacher_salary_list(request):
    teachers = User.objects.filter(role='teacher').order_by('ism')
    return render(request, "education/teacher_salary_list.html", {"teachers": teachers})


# 🔹 2. O‘qituvchining barcha guruhlari
@login_required
def teacher_groups(request, teacher_id):
    teacher = get_object_or_404(User, id=teacher_id, role="teacher")
    groups = Group.objects.filter(oqituvchi=teacher).prefetch_related('enrollments__student', 'attendances')

    teacher_data = []
    for group in groups:
        enrollments = []
        for e in group.enrollments.all():
            attended = group.attendances.filter(student=e.student, present=True).count()
            enrollments.append({
                "student": e.student,
                "kurs_narhi": e.kurs_narhi,
                "foiz": e.oqituvchi_foiz,
                "attended": attended,
                "daromad": e.real_oqituvchi_daromadi(),
            })
        total_income = sum(e["daromad"] for e in enrollments)

        teacher_data.append({
            "group": group,
            "enrollments": enrollments,
            "foiz": group.oqituvchi_foiz,
            "daromad": total_income,
        })

    return render(request, "education/teacher_groups.html", {
        "teacher": teacher,
        "teacher_data": teacher_data,
    })



@login_required
def teacher_salary_report(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    enrollments = group.enrollments.select_related("student")

    total_lessons = Attendance.objects.filter(group=group).values("date").distinct().count()
    per_lesson_income = group.dars_boshiga_tolov()

    student_summaries = []
    for e in enrollments:
        attended = Attendance.objects.filter(group=group, student=e.student, present=True).count()
        teacher_income = attended * per_lesson_income
        student_summaries.append({
            "student": e.student,
            "attended": attended,
            "teacher_income": teacher_income
        })

    teacher_total_income = sum(s["teacher_income"] for s in student_summaries)

    ctx = {
        "group": group,
        "student_summaries": student_summaries,
        "teacher_total_income": teacher_total_income,
        "month": timezone.now().strftime("%B"),
        "year": timezone.now().year,
    }
    return render(request, "education/teacher_salary_report.html", ctx)


# 📊 DIREKTOR HISOBOT PANELI


@login_required
def teacher_salary_summary(request):
    teachers = User.objects.filter(role="teacher")

    selected_month = int(request.GET.get("month", localdate().month))
    current_year = date.today().year

    months = [
        (1, "Yanvar"), (2, "Fevral"), (3, "Mart"), (4, "Aprel"),
        (5, "May"), (6, "Iyun"), (7, "Iyul"), (8, "Avgust"),
        (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr"),
    ]

    teacher_data = []
    chart_labels = [m[1] for m in months]
    chart_teacher_income = [0] * 12
    chart_center_income = [0] * 12

    for teacher in teachers:
        groups = Group.objects.filter(oqituvchi=teacher)
        total_teacher_income = 0
        total_center_income = 0
        total_classes = 0

        for g in groups:
            # === 1. O‘qituvchi o‘tgan darslar soni (davomat asosida)
            attended_lessons = Attendance.objects.filter(
                group=g,
                teacher=teacher,
                present=True,
                date__year=current_year,
                date__month=selected_month
            ).count()

            total_classes += attended_lessons

            # === 2. Har dars uchun to‘lov asosida o‘qituvchi ulushi
            # agar oy_dars_soni yo‘q bo‘lsa nolga bo‘linishni oldini olamiz
            oy_dars_soni = getattr(g, "oy_dars_soni", 12) or 12
            kurs_narxi = getattr(g, "kurs_narxi", 0)
            teacher_share = getattr(g, "oqituvchi_foiz", 40)

            # Har dars uchun o‘qituvchi ulushi
            lesson_payment = (kurs_narxi * teacher_share / 100) / oy_dars_soni
            group_teacher_income = attended_lessons * lesson_payment

            # === 3. Shu oyda tushgan haqiqiy to‘lovlar
            enrollments = Enrollment.objects.filter(group=g)
            payments = Payment.objects.filter(
                enrollment__in=enrollments,
                sana__year=current_year,
                sana__month=selected_month
            )
            group_total = payments.aggregate(total=Sum("summa"))["total"] or 0

            # === 4. Markazga qolgan ulush (agar to‘lovlar kam bo‘lsa, 0 dan oshmaydi)
            center_income = max(group_total - group_teacher_income, 0)

            # === 5. Umumiy yig‘indi
            total_teacher_income += group_teacher_income
            total_center_income += center_income

            # === 6. Grafik uchun
            chart_teacher_income[selected_month - 1] += group_teacher_income
            chart_center_income[selected_month - 1] += center_income

        total_sum = total_teacher_income + total_center_income

        teacher_data.append({
            "teacher": teacher,
            "lessons": total_classes,
            "groups": groups.count(),
            "teacher_income": total_teacher_income,
            "center_profit": total_center_income,
            "total_sum": total_sum,
        })

    # === Oyni nom bilan ko‘rsatish
    month_name = next((m[1] for m in months if m[0] == selected_month), "Noma’lum")

    # === Natija
    context = {
        "teacher_data": teacher_data,
        "chart_labels": chart_labels,
        "chart_teacher_income": chart_teacher_income,
        "chart_center_income": chart_center_income,
        "months": months,
        "selected_month": selected_month,
        "month_name": month_name,
        "year": current_year,
    }

    # Debug uchun terminalda ko‘rsatish
    print(f"=== Hisobot → {month_name}, {current_year}")
    for t in teacher_data:
        print(f"{t['teacher']} | Darslar: {t['lessons']} | Daromad: {t['teacher_income']:.0f} so‘m")

    return render(request, "education/teacher_salary_summary.html", context)


@login_required
def teacher_salary_redirect(request):
    group = None

    # O‘qituvchi bo‘lsa — o‘z guruhini topadi
    if request.user.role == "teacher":
        group = Group.objects.filter(oqituvchi=request.user).first()

    # Direktor yoki superuser bo‘lsa — birinchi mavjud guruhni topadi
    elif request.user.role == "director" or request.user.is_superuser:
        group = Group.objects.first()

    # Agar topilmasa — xabar chiqar va qaytar
    if not group:
        messages.warning(request, "Hech qanday guruh topilmadi!")
        return redirect("education:groups_it")

    # Topilgan guruh bo‘yicha maosh sahifasiga yo‘naltirish
    return redirect("education:teacher_salary_report", group.id)



# ---------- CRUD ----------
@login_required
def group_create(request, category=None):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:guruhlar")

    # Formani kategoriyaga qarab tanlaymiz
    if category == Group.LANG:
        FormCls, title = LangGroupForm, "Tillar bo‘yicha guruh yaratish"
    elif category == Group.IT:
        FormCls, title = ITGroupForm, "IT bo‘yicha guruh yaratish"
    else:
        FormCls, title = GroupForm, "Guruh yaratish"

    form = FormCls(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            g = form.save(commit=False)

            # 🔹 Kategoriya bo‘sh bo‘lsa, avtomatik to‘ldir
            g.category = category or Group.LANG

            # 🔹 Center avtomatik foydalanuvchidan
            if not g.center_id:
                if hasattr(request.user, "center") and request.user.center:
                    g.center = request.user.center
                else:
                    from accounts.models import Center
                    g.center = Center.objects.first()

            # 🔹 Agar kurs narxi yoki foizlar formadan kelmasa — default qiymatlar ber
            if not g.kurs_narxi:
                g.kurs_narxi = 500000
            if not g.oqituvchi_foiz:
                g.oqituvchi_foiz = 40
            if not g.oy_dars_soni:
                g.oy_dars_soni = 12

            g.save()

            messages.success(request, f"✅ {g.nom} guruhi muvaffaqiyatli yaratildi.")
            return redirect("education:group_detail", pk=g.pk)
        else:
            print("❌ Forma xato:", form.errors)

    return render(request, "education/group_form.html", {"form": form, "title": title})


@login_required
def group_edit(request, pk):
    if not request.user.is_superuser and request.user.role not in ["Director", "Manager", "Teacher"]:
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:groups")

    g = get_object_or_404(Group, pk=pk)
    form = GroupForm(request.POST or None, instance=g)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "✅ Guruh yangilandi.")
        return redirect("education:group_detail", pk=g.id)

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "✏️ Guruhni tahrirlash",
    })




@login_required
def group_list(request):
    """
    Barcha guruhlar ro‘yxati.
    """
    rows = Group.objects.select_related("center", "oqituvchi").all()
    can_manage = request.user.is_superuser or request.user.role in ["Director", "Manager", "Teacher"]

    context = {
        "rows": rows,
        "can_manage": can_manage,
    }
    return render(request, "education/groups.html", context)


@login_required
def group_add(request):
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:groups")

    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "✅ Guruh muvaffaqiyatli qo‘shildi.")
        return redirect("education:groups")

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "Yangi guruh qo‘shish",
    })




from django.contrib import messages

@login_required
def group_delete(request, pk):
    """
    Guruhni o‘chirish — tasdiq bilan.
    """
    group = get_object_or_404(Group, pk=pk)

    if request.method == "POST":
        category = getattr(group, "category_obj", None)
        group.delete()
        messages.success(request, "🗑️ Guruh o‘chirildi.")

        if category:
            return redirect("education:category_detail", category_id=category.id)
        return redirect("education:groups")

    return render(request, "education/group_delete_confirm.html", {"group": group})


@login_required
def add_student_to_group(request, pk: int):
    """
    Guruhga yangi o‘quvchi qo‘shish + kurs narxi + o‘qituvchi foizi bilan birga.
    """
    g = get_object_or_404(Group, pk=pk)

    # Faqat ruxsatli rollar
    allowed_roles = ['admin', 'manager', 'teacher', 'director']
    if request.user.role not in allowed_roles:
        return HttpResponseForbidden("Sizda bu amalni bajarish uchun ruxsat yo‘q.")

    # Guruhda yo‘q o‘quvchilar ro‘yxati
    students = (
        User.objects
        .filter(role="student")
        .exclude(enrollment__group=g)
        .order_by("ism", "familya")
    )

    # POST so‘rov — yangi o‘quvchini qo‘shish
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        kurs_narhi = request.POST.get("kurs_narhi")
        oqituvchi_foiz = request.POST.get("oqituvchi_foiz")

        if not student_id:
            return HttpResponse("O‘quvchi tanlanmagan.", status=400)

        try:
            kurs_narhi = int(kurs_narhi or 0)
            oqituvchi_foiz = int(oqituvchi_foiz or 40)
        except ValueError:
            messages.error(request, "Kiritilgan qiymatlar son bo‘lishi kerak.")
            return redirect("education:add_student_to_group", pk=g.id)

        student = get_object_or_404(User, pk=student_id, role="student")

        # 🔹 Yangi Enrollment yozuvi yaratamiz
        Enrollment.objects.create(
            group=g,
            student=student,
            kurs_narhi=kurs_narhi,
            oqituvchi_foiz=oqituvchi_foiz
        )

        messages.success(
            request,
            f"{student.full_name()} guruhga qo‘shildi! "
            f"Kurs narxi: {kurs_narhi:,} so‘m, "
            f"O‘qituvchi ulushi: {oqituvchi_foiz}%"
        )
        return redirect("education:group_detail", pk=g.id)

    ctx = {
        "g": g,
        "students": students,
    }

    return render(request, "education/add_student_to_group.html", ctx)


@login_required
def teacher_groups_view(request, teacher_id):
    teacher = get_object_or_404(User, id=teacher_id, role="teacher")

    groups = (
        teacher.group_set
        .prefetch_related('enrollments__student')
        .all()
    )

    teacher_data = []
    for group in groups:
        enrollments = group.enrollments.all()
        group_income = sum([enr.real_oqituvchi_daromadi() for enr in enrollments])
        group_info = {
            'name': group.name,
            'students': enrollments,
            'foiz': enrollments.first().oqituvchi_foiz if enrollments.exists() else 0,
            'daromad': group_income,
        }
        teacher_data.append(group_info)

    ctx = {
        "teacher": teacher,
        "teacher_data": teacher_data,
    }
    return render(request, "education/teacher_groups.html", ctx)


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
