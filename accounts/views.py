# accounts/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import get_user_model, logout
from django.views.decorators.http import require_http_methods
from django import forms
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from .forms import AddUserForm, TeacherForm
from accounts.models import User                     # kerak bo‘lsa
from education.models import Group, Enrollment, Attendance  # ✅ to‘g‘ri joydan import


U = get_user_model()

# --- ruxsat yordamchilari ---
def _can_add(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")

def _is_staff_like(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")

# --- Foydalanuvchi qo‘shish (o'zgarmagan) ---
from education.models import Enrollment, Group

@login_required
def add_user(request):
    if not _can_add(request.user):
        messages.error(request, "Sizda foydalanuvchi qo‘shish huquqi yo‘q.")
        return redirect("core:home")

    if request.method == "POST":
        form = AddUserForm(request.POST)
        group_id = request.POST.get("group_id")
        kurs_narhi = request.POST.get("kurs_narhi")

        if form.is_valid():
            user = form.save()

            # === STUDENT BO‘LSA ===
            if user.role == "student" and group_id:
                try:
                    group = Group.objects.get(id=group_id)

                    # Kurs narxi
                    if kurs_narhi:
                        kurs_narhi = int(kurs_narhi)
                    else:
                        kurs_narhi = getattr(group, "kurs_narhi", 0)

                    # 🔥 O‘qituvchi foizi → guruhdagi o‘qituvchini olib beramiz
                    oqituvchi_foiz = group.oqituvchi.oqituvchi_foizi

                    Enrollment.objects.create(
                        student=user,
                        group=group,
                        kurs_narhi=kurs_narhi,
                        oqituvchi_foiz=oqituvchi_foiz
                    )

                except Group.DoesNotExist:
                    pass

            messages.success(request, f"{user.ism} {user.familya} muvaffaqiyatli qo‘shildi.")
            return redirect("core:home")

        else:
            print("FORM ERRORS:", form.errors)

    else:
        form = AddUserForm()

    groups = Group.objects.all().order_by("nom")

    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "title": "Foydalanuvchi qo‘shish", "groups": groups}
    )



@login_required
def add_teacher(request):
    if request.method == "POST":
        form = TeacherForm(request.POST)
        if form.is_valid():
            teacher = form.save(commit=False)

            teacher.role = "teacher"

            # 🔥 Formdan kelgan foizni majburan yozamiz
            teacher.oqituvchi_foizi = form.cleaned_data.get("oqituvchi_foizi")

            teacher.save()
            return redirect("core:teacher_list")
    else:
        form = TeacherForm()

    return render(request, "accounts/add_teacher.html", {"form": form})


# --- Tahrirlash formasi (o'zgarmagan) ---
class UserEditForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Yangi parol", widget=forms.PasswordInput, required=False,
        help_text="Bo‘sh qoldirsangiz parol o‘zgarmaydi."
    )
    password2 = forms.CharField(label="Parolni tasdiqlash", widget=forms.PasswordInput, required=False)

    class Meta:
        model = U
        fields = ["ism", "familya", "telefon1", "telefon2", "center", "email", "gmail", "role"]
        widgets = {"role": forms.Select()}

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 or p2:
            if not p1 or not p2 or p1 != p2:
                self.add_error("password2", "Parollar mos kelmadi.")
            elif len(p1) < 6:
                self.add_error("password1", "Parol uzunligi kamida 6 bo‘lsin.")
        return data

@login_required
def user_edit(request, pk: int):
    if not _is_staff_like(request.user):
        messages.error(request, "Sizda ruxsat yo‘q.")
        return redirect("core:home")

    obj = get_object_or_404(U, pk=pk)
    form = UserEditForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        u = form.save()
        p1 = form.cleaned_data.get("password1")
        if p1:
            u.set_password(p1)
            u.save()
        messages.success(request, "Foydalanuvchi ma’lumotlari yangilandi.")
        return redirect("accounts:user_edit", pk=obj.id)

    return render(request, "accounts/user_edit.html", {"form": form, "obj": obj})

from django.views.decorators.http import require_GET

@login_required
@require_GET
def logout_now(request):
    logout(request)
    return redirect("login")  # sizda login url name "login" bo‘lsa


@login_required
@require_http_methods(["GET", "POST"])
def logout_view(request):
    # GET -> tasdiqlash sahifasi
    if request.method == "GET":
        return render(request, "accounts/logout_confirm.html")

    # POST -> logout
    logout(request)
    messages.success(request, "Tizimdan chiqdingiz.")
    return redirect("login")

# === YANGI: O‘qituvchi sahifasi -> Guruhlar ro‘yxati ===
@login_required
@user_passes_test(_is_staff_like)
def teacher_detail(request, user_id):
    teacher = get_object_or_404(User, pk=user_id, role="teacher")
    groups = (
        Group.objects
        .filter(oqituvchi=teacher)                      # ⬅️ teacher emas, oqituvchi
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))
        .order_by("nom")                                # ⬅️ name emas, nom
    )
    return render(request, "accounts/teacher_detail.html", {
        "teacher": teacher,
        "groups": groups,
    })

# === YANGI: Talaba profili -> Chaqmoq + Davomat ===
@login_required
@user_passes_test(lambda u: u.is_superuser or u.role in ("director", "manager", "teacher"))
def student_detail(request, user_id: int):
    student = get_object_or_404(User, pk=user_id, role="student")

    # ⚡ Chaqmoq (Ledger)
    from chaqmoq.models import Ledger
    tx = (
        Ledger.objects
        .filter(student=student)
        .select_related("rule", "group", "beruvchi")
        .order_by("-sana")[:50]
    )
    total = Ledger.student_balansi(student.id)

    # 📅 Davomat
    from education.models import Attendance
    attendance = (
        Attendance.objects
        .filter(student=student)
        .select_related("group")
        .order_by("-date")[:50]
    )

    groups = (
        Group.objects
        .filter(enrollments__student=student)
        .select_related("center", "oqituvchi")
        .distinct()
    )

    return render(request, "accounts/student_detail.html", {
        "student": student,
        "groups": groups,
        "tx": tx,
        "total": total,
        "attendance": attendance,
    })


@login_required
@user_passes_test(lambda u: getattr(u, "role", None) == "teacher")
def my_groups(request):
    rows = (
        Group.objects
        .filter(oqituvchi=request.user)                 # o‘qituvchining o‘z guruhlari
        .select_related("center", "oqituvchi")
        .annotate(student_count=Count("enrollments"))   # talabalar soni
        .order_by("nom")
    )
    return render(request, "education/groups.html", {"rows": rows})
