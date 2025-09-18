from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from chaqmoq.models import Rule, Ledger  # ⬅️ qo'shing
from .forms import GroupForm, LangGroupForm, ITGroupForm
from accounts.models import User
from .forms import GroupForm
from .models import Group, Enrollment, Attendance  # <-- to'g'ri importlar
from django.http import HttpResponseForbidden, Http404

U = get_user_model()


def _can_manage(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")

@login_required
def groups_hub(request):
    return render(request, "education/groups_hub.html")


@login_required
def groups_by_category(request, category):
    if category not in ("lang", "it"):
        raise Http404("Noto‘g‘ri kategoriya")

    rows = (Group.objects
            .filter(category=category)
            .select_related("center", "oqituvchi")
            .annotate(student_count=Count("enrollments"))
            .order_by("nom"))

    ctx = {
        "rows": rows,
        "category": category,
        "can_manage": _can_manage(request.user),
    }
    return render(request, "education/groups_by_category.html", ctx)

# DRY: umumiy yaratuvchi
def _create_group(request, category):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:groups_hub")

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            g = form.save(commit=False)
            g.category = category
            g.save()
            messages.success(request, "Guruh yaratildi.")
            return redirect("education:groups_lang" if category == "lang" else "education:groups_it")
    else:
        form = GroupForm()

    title = ("Tillar" if category == "lang" else "IT") + " bo‘yicha guruh yaratish"
    return render(request, "education/group_form.html", {"form": form, "title": title, "category": category})



def _group_create_with_category(request, category_value):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:groups_hub")

    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            g = form.save(commit=False)
            g.category = category_value   # formda bo‘lmasa majburiy
            g.save()
            messages.success(request, "Guruh yaratildi.")
            return redirect("education:group_detail", pk=g.pk)
    else:
        form = GroupForm(initial={"category": category_value})

    return render(request, "education/group_form.html", {
        "form": form,
        "title": "Tillar bo‘yicha guruh yaratish" if category_value == Group.LANG else "IT bo‘yicha guruh yaratish",
    })



@login_required
def group_create_lang(request):
    return _create_group(request, "lang")

@login_required
def group_create_it(request):
    return _create_group(request, "it")

# --- Guruhlar ro'yxati (direktor/managerlar uchun umumiy) ---
@login_required
def guruhlar(request):
    rows = Group.objects.select_related('center', 'oqituvchi').annotate(student_count=Count('enrollments'))
    return render(request, "education/groups.html", {"rows": rows, "can_manage": _can_manage(request.user)})


@login_required
def guruhlar_tillar(request):
    return groups_by_category(request, Group.LANG)

@login_required
def guruhlar_it(request):
    return groups_by_category(request, Group.IT)




# --- Bitta guruh sahifasi ---
@login_required
def group_detail(request, pk):
    g = get_object_or_404(Group, pk=pk)

    if request.user.role == "teacher" and not (request.user.is_superuser or g.oqituvchi_id == request.user.id):
        return HttpResponseForbidden()

    # multi-select orqali bir nechta mavjud talabani qo‘shish
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
                Enrollment.objects.get_or_create(group=g, student=s)
                added += 1
        messages.success(request, f"{added} ta o‘quvchi guruhga qo‘shildi.")
        return redirect("education:group_detail", pk=g.pk)

    enrollments = g.enrollments.select_related("student").order_by("student__ism")
    already_ids = enrollments.values_list("student_id", flat=True)
    selectable = User.objects.exclude(id__in=already_ids).order_by("ism", "familya")

    return render(request, "education/group_detail.html", {
        "g": g,
        "enrollments": enrollments,
        "selectable": selectable,
        "can_give_points": (request.user.is_superuser or request.user.role in ("director", "manager", "teacher")),
    })


# --- Guruh ichida o'quvchiga ball (chaqmoq) berish (oddiy variant) ---

@login_required
def group_points(request, pk):
    g = get_object_or_404(Group, pk=pk)
    if request.user.role == "teacher" and not (request.user.is_superuser or g.oqituvchi_id == request.user.id):
        return HttpResponseForbidden()
    if request.method != "POST":
        return redirect("education:group_detail", pk=g.pk)

    sid = request.POST.get("student_id")
    amount = int(request.POST.get("amount", "0") or 0)
    student = get_object_or_404(User, pk=sid)

    # ⚡ Ledgerga yozish (tavsiya)
    from chaqmoq.models import Ledger, Rule
    # bu yerda qoidani o'zingiz tanlang yoki "free" qoida yarating
    rule = Rule.objects.first()
    Ledger.objects.create(student=student, beruvchi=request.user, group=g, rule=rule, ball=amount)

    sign = "+" if amount >= 0 else ""
    messages.success(request, f"{student.get_full_name()} ga ⚡ {sign}{amount} berildi.")
    return redirect("education:group_detail", pk=g.pk)

# --- Yaratish / Tahrirlash / O'chirish ---
@login_required
def group_create(request, category=None):
    if not _can_manage(request.user):
        messages.error(request, "Sizda guruh yaratish huquqi yo‘q.")
        return redirect("education:guruhlar")

    # kategoriya bo‘yicha mos forma
    if category == Group.LANG:
        FormCls = LangGroupForm
        title = "Tillar bo‘yicha guruh yaratish"
    elif category == Group.IT:
        FormCls = ITGroupForm
        title = "IT bo‘yicha guruh yaratish"
    else:
        FormCls = GroupForm
        title = "Guruh yaratish"

    if request.method == "POST":
        form = FormCls(request.POST)
        if form.is_valid():
            g = form.save()
            messages.success(request, "Guruh yaratildi.")
            return redirect("education:group_detail", pk=g.pk)
    else:
        form = FormCls(initial={"category": category} if category else None)

    return render(request, "education/group_form.html", {"form": form, "title": title})

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
    rows = (Group.objects
            .filter(oqituvchi=request.user)
            .select_related('center', 'oqituvchi')
            .annotate(student_count=Count('enrollments'))
            .order_by('nom'))
    return render(request, "education/my_groups.html", {"rows": rows})
