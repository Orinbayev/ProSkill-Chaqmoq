from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from chaqmoq.models import Rule, Ledger  # ⬅️ qo'shing

from accounts.models import User
from .forms import GroupForm
from .models import Group, Enrollment, Attendance  # <-- to'g'ri importlar

U = get_user_model()


def _can_manage(user):
    # direktor yoki manager
    return user.is_superuser or getattr(user, "role", None) in ("director", "manager")


# --- Guruhlar ro'yxati (direktor/managerlar uchun umumiy) ---
@login_required
def guruhlar(request):
    rows = (
        Group.objects
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")
    )
    can_manage = _can_manage(request.user)
    return render(request, "education/groups.html", {"rows": rows, "can_manage": can_manage})


# --- Bitta guruh sahifasi ---
@login_required
def group_detail(request, pk):
    g = get_object_or_404(Group, pk=pk)

    # O‘qituvchi faqat o‘z guruhini ko‘ra oladi
    if request.user.role == "teacher" and g.oqituvchi_id != request.user.id and not request.user.is_superuser:
        return HttpResponseForbidden()

    # 1) Mavjud o‘quvchilardan BIR NECHTA qo‘shish
    if request.method == "POST" and request.POST.get("action") == "add-existing-bulk":
        ids = request.POST.getlist("student_ids")
        if not ids:
            messages.warning(request, "O‘quvchi tanlanmadi.")
            return redirect("education:group_detail", pk=g.pk)

        added = 0
        with transaction.atomic():
            for sid in ids:
                try:
                    s = User.objects.get(pk=sid)
                except User.DoesNotExist:
                    continue
                # MUHIM: modelda 'group'!
                Enrollment.objects.get_or_create(group=g, student=s)
                added += 1
        messages.success(request, f"{added} ta o‘quvchi guruhga qo‘shildi.")
        return redirect("education:group_detail", pk=g.pk)

    # 2) Mavjud o‘quvchilardan BITTA qo‘shish (eski tugma uchun)
    if request.method == "POST" and request.POST.get("action") == "add-existing-one":
        sid = request.POST.get("student_id")
        try:
            s = User.objects.get(pk=sid)
            Enrollment.objects.get_or_create(group=g, student=s)  # <-- 'group'
            full = f"{s.ism} {s.familya}".strip()
            messages.success(request, f"{full} guruhga qo‘shildi.")
        except User.DoesNotExist:
            messages.error(request, "O‘quvchi topilmadi.")
        return redirect("education:group_detail", pk=g.pk)

    enrollments = g.enrollments.select_related("student").order_by("student__ism", "student__familya")

    # Guruhga kirmagan foydalanuvchilar (multi-select uchun)
    already_ids = list(enrollments.values_list("student_id", flat=True))
    selectable = User.objects.exclude(id__in=already_ids).order_by("ism", "familya")

    return render(
        request,
        "education/group_detail.html",
        {
            "g": g,
            "enrollments": enrollments,
            "selectable": selectable,
            "can_give_points": (request.user.is_superuser or request.user.role in ("director", "manager", "teacher")),
        },
    )


# --- Guruh ichida o'quvchiga ball (chaqmoq) berish (oddiy variant) ---
@login_required
def group_points(request, pk):
    g = get_object_or_404(Group, pk=pk)

    # o‘qituvchi faqat o‘z guruhiga ball bera oladi
    if request.user.role == "teacher" and g.oqituvchi_id != request.user.id and not request.user.is_superuser:
        return HttpResponseForbidden()

    if request.method != "POST":
        return redirect("education:group_detail", pk=g.pk)

    sid = request.POST.get("student_id")
    amount = int(request.POST.get("amount") or 0)

    student = get_object_or_404(User, pk=sid, role="student")

    # Qo'l bilan berilgan ball uchun default qoida
    tur = Rule.PLUS if amount >= 0 else Rule.MINUS
    rule, _ = Rule.objects.get_or_create(
        nom="Qo'lda berish",
        defaults={"tur": tur, "min_baho": 1, "max_baho": 100},
    )
    # Mavjud qoida boru tur mos kelmasa — moslab qo'yamiz
    if rule.tur != tur:
        rule.tur = tur
        rule.save(update_fields=["tur"])

    # Ledgerga yozuv qo'shamiz
    Ledger.objects.create(
        student=student,
        beruvchi=request.user,
        group=g,
        rule=rule,
        ball=amount,
    )

    sign = "+" if amount >= 0 else ""
    full = f"{student.ism} {student.familya}".strip()
    messages.success(request, f"{full} ga ⚡ {sign}{amount} yozildi.")
    return redirect("education:group_detail", pk=g.pk)

# --- Yaratish / Tahrirlash / O'chirish ---
@login_required
def group_create(request):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:guruhlar")

    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        g = form.save()
        messages.success(request, "Guruh yaratildi.")
        return redirect("education:group_detail", pk=g.pk)
    return render(request, "education/group_form.html", {"form": form, "title": "Guruh yaratish"})


@login_required
def group_edit(request, pk: int):
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
def group_delete(request, pk: int):
    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:guruhlar")

    g = get_object_or_404(Group, pk=pk)
    if request.method == "POST":
        g.delete()
        messages.success(request, "Guruh o‘chirildi.")
        return redirect("education:guruhlar")
    return render(request, "education/group_delete_confirm.html", {"g": g})


# --- O‘quvchini guruhdan chiqarish ---
@login_required
def enrollment_remove(request, pk: int):
    enr = get_object_or_404(Enrollment.objects.select_related("group", "student"), pk=pk)

    if not _can_manage(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("education:group_detail", pk=enr.group_id)

    if request.method == "POST":
        enr.delete()
        messages.success(request, "O‘quvchi guruhdan chiqarildi.")
    return redirect("education:group_detail", pk=enr.group_id)


# --- O'qituvchining «Mening guruhlarim» sahifasi ---
@login_required
def my_groups(request):
    rows = (
        Group.objects
        .filter(oqituvchi=request.user)  # sizning model maydoni
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")
    )
    return render(request, "education/my_groups.html", {"rows": rows})
