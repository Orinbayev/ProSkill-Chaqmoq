import re

# accounts/forms.py
import json

from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.duplicate_checks import empty_student_duplicate_check, find_student_duplicates
from accounts.models import Center
from accounts.utils import normalize_phone

User = get_user_model()
Group = apps.get_model('education', 'Group')

ROLE_CHOICES = (
    ("director", "Direktor"),
    ("student", "O‘quvchi"),
    ("teacher", "O‘qituvchi"),
    ("manager", "Manager"),
    ("parent", "Ota-ona"),
)

class AddUserForm(forms.ModelForm):
    children_ids = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role="student"),
        required=False,
        label="Farzandlarini tanlang",
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-control uniform-input",
                "id": "id_children_ids",
                "size": 6,
            }
        ),
    )
    center = forms.ModelChoiceField(
        queryset=Center.objects.all(),
        empty_label="---------",
        required=False,
        label="Center"
    )
    group = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        required=False,
        label="Guruhni tanlang"
    )
    kurs_narhi = forms.IntegerField(required=False, label="Kurs narxi")
    group_start_date = forms.DateField(
        required=False,
        label="Boshlash sanasi",
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control uniform-input",
                "id": "id_group_start_date",
            }
        ),
    )
    group_assignments = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_group_assignments"}),
    )
    duplicate_override = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_duplicate_override"}),
    )

    class Meta:
        model = User
        fields = [
            "ism", "familya", "otchestvo",
            "telefon1", "telefon2",
            "center", "role",
            "email", "password",
            "oqituvchi_foizi",
            "birth_date", "gender", "passport_id", "jshr", "telegram_username", "address",
        ]
        widgets = {
            "ism": forms.TextInput(attrs={"placeholder": "Ism", "class": "form-control uniform-input", "id": "id_ism"}),
            "familya": forms.TextInput(attrs={"placeholder": "Familya", "class": "form-control uniform-input", "id": "id_familya"}),
            "otchestvo": forms.TextInput(attrs={"placeholder": "Ota-onaning ismi", "class": "form-control uniform-input", "id": "id_otchestvo"}),
            "telefon1": forms.TextInput(attrs={"placeholder": "+998 99 384 58 54", "class": "form-control uniform-input", "id": "id_telefon1", "inputmode": "numeric", "autocomplete": "off"}),
            "telefon2": forms.TextInput(attrs={"placeholder": "+998 99 384 58 54", "class": "form-control uniform-input", "id": "id_telefon2", "inputmode": "numeric", "autocomplete": "off"}),
            "email": forms.TextInput(attrs={"placeholder": "Gmail avtomatik yaratiladi", "class": "form-control uniform-input", "id": "id_email"}),
            "password": forms.PasswordInput(attrs={"placeholder": "Parol avtomatik yaratiladi", "class": "form-control uniform-input", "id": "id_password"}),
            "role": forms.Select(attrs={"class": "form-control uniform-input", "id": "id_role"}),
            "oqituvchi_foizi": forms.NumberInput(attrs={"placeholder": "40", "class": "form-control uniform-input", "id": "id_oqituvchi_foizi", "min": "0", "max": "100"}),
            "birth_date": forms.DateInput(attrs={"type": "date", "class": "form-control uniform-input"}),
            "gender": forms.RadioSelect(attrs={"class": "gender-radio"}), 
            "passport_id": forms.TextInput(attrs={"placeholder": "AB1234567", "class": "form-control uniform-input", "id": "id_passport_id"}),
            "jshr": forms.TextInput(attrs={"placeholder": "External ID / JSHR", "class": "form-control uniform-input", "maxlength": "14", "id": "id_jshr"}),
            "telegram_username": forms.TextInput(attrs={"placeholder": "@username", "class": "form-control uniform-input", "id": "id_telegram_username"}),
            "address": forms.Textarea(attrs={"placeholder": "Manzil", "class": "form-control uniform-input", "rows": 2, "id": "id_address"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.allowed_roles = kwargs.pop("allowed_roles", None)
        self.allow_initial_group_assignment = bool(kwargs.pop("allow_initial_group_assignment", False))
        self.cleaned_group_assignments = []
        self.student_duplicate_check = empty_student_duplicate_check()
        self._student_duplicate_check_evaluated = False
        super().__init__(*args, **kwargs)

        self.fields["oqituvchi_foizi"].required = False
        self.fields["birth_date"].required = False
        self.fields["gender"].required = False
        self.fields["group"].widget.attrs.update({
            "class": "form-control uniform-input",
            "id": "id_group",
        })
        self.fields["kurs_narhi"].widget.attrs.update({
            "class": "form-control uniform-input",
            "id": "id_kurs_narhi",
            "inputmode": "numeric",
            "min": "0",
        })

        role_labels = dict(User._meta.get_field("role").choices)
        ordered_roles = ["director", "manager", "teacher", "student", "parent"]
        allowed_roles = set(self.allowed_roles or ordered_roles)
        self.fields["role"].choices = [
            (value, role_labels.get(value, label))
            for value, label in User._meta.get_field("role").choices
            if value in allowed_roles and value in ordered_roles
        ]

        u = getattr(self.request, "user", None) if self.request else None

        # ✅ 1) Active center: request.center -> user.center -> POSTed center -> initial center
        active_center = None
        if self.request:
            active_center = getattr(self.request, "center", None)

        if not active_center and u and getattr(u, "center", None):
            active_center = u.center

        # ✅ POST/GET dan center tanlangan bo'lsa ham ishlasin
        center_id = (self.data.get("center") or self.initial.get("center"))
        if center_id:
            try:
                active_center = Center.objects.get(id=center_id)
            except Center.DoesNotExist:
                pass

        # ✅ 2) Center fieldni cheklash (superuser bo'lsa ham)
        if active_center and "center" in self.fields:
            self.fields["center"].queryset = Center.objects.filter(id=active_center.id)
            self.fields["center"].initial = active_center
            self.fields["center"].required = True
            self.fields["center"].empty_label = None

        # ✅ 3) Group field – faqat shu markaz guruhlari chiqsin
        if "group" in self.fields:
            if active_center:
                self.fields["group"].queryset = Group.objects.filter(
                    center=active_center,
                    is_archived=False
                ).order_by("nom")
            else:
                self.fields["group"].queryset = Group.objects.none()

        if "group_start_date" in self.fields and not self.is_bound:
            selected_group = None
            group_id = self.initial.get("group")
            if group_id:
                selected_group = Group.objects.filter(id=group_id).only("course_start_date").first()
            self.fields["group_start_date"].initial = (
                self.initial.get("group_start_date")
                or getattr(selected_group, "course_start_date", None)
                or timezone.localdate()
            )

        if "children_ids" in self.fields:
            if active_center:
                self.fields["children_ids"].queryset = User.objects.filter(
                    role="student",
                    center=active_center,
                    is_archived=False,
                ).order_by("ism", "familya")
            else:
                self.fields["children_ids"].queryset = User.objects.none()

        current_role = (
            (self.data.get("role") if self.is_bound else None)
            or self.initial.get("role")
            or getattr(self.instance, "role", "")
        )
        if current_role == "student" and "telefon1" in self.fields:
            self.fields["telefon1"].required = True

    def duplicate_override_requested(self) -> bool:
        return (self.cleaned_data.get("duplicate_override") or "").strip() == "1"

    def get_student_duplicate_check(self):
        if self._student_duplicate_check_evaluated:
            return self.student_duplicate_check

        self._student_duplicate_check_evaluated = True
        if getattr(self, "cleaned_data", {}).get("role") != "student":
            return self.student_duplicate_check

        request_user = getattr(self.request, "user", None) if self.request else None
        center = (
            self.cleaned_data.get("center")
            or getattr(self.request, "center", None)
            or getattr(request_user, "center", None)
        )
        self.student_duplicate_check = find_student_duplicates(
            center=center,
            ism=self.cleaned_data.get("ism"),
            familya=self.cleaned_data.get("familya"),
            telefon=self.cleaned_data.get("telefon1"),
            birth_date=self.cleaned_data.get("birth_date"),
            exclude_user_id=getattr(self.instance, "pk", None),
        )
        return self.student_duplicate_check


    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        group = cleaned_data.get("group")
        center = cleaned_data.get("center")
        group_start_date = cleaned_data.get("group_start_date")
        group_assignments_raw = (cleaned_data.get("group_assignments") or "").strip()
        self.cleaned_group_assignments = []
        
        if role == "student":
            if not cleaned_data.get("telefon1"):
                self.add_error("telefon1", "O'quvchi uchun telefon raqami majburiy.")

            if self.allow_initial_group_assignment:
                if group_assignments_raw:
                    self.cleaned_group_assignments = self._clean_group_assignments(
                        raw_value=group_assignments_raw,
                        center=center,
                    )
                else:
                    # Security: Verify group center matches user center
                    if group and center and group.center_id != center.id:
                        raise forms.ValidationError("Tanlangan guruh ushbu markazga tegishli emas!")

                    if group and not group_start_date:
                        self.add_error("group_start_date", "Guruh uchun boshlash sanasini tanlang.")
            
            # ===== STUDENT LIMIT CHECK (Warning for Director/Manager ONLY) =====
            # This shows an error message when trying to add students beyond limit
            # It does NOT log anyone out - just prevents adding new students
            if center:
                from accounts.student_limit import check_student_limit
                try:
                    check_student_limit(
                        center,
                        raise_error=True,
                        actor=getattr(self.request, "user", None),
                    )
                except ValidationError as e:
                    # Re-raise the student limit validation error
                    raise e
                except Exception as e:
                    # Handle unexpected errors gracefully
                    raise forms.ValidationError(f"❌ Tizimda kutilmagan xatolik yuz berdi: {str(e)}")
        
        return cleaned_data

    def _clean_group_assignments(self, *, raw_value, center):
        from education.services.tuition import resolve_lesson_schedule

        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Guruhlar ro'yxati noto'g'ri yuborilgan.") from exc

        if not isinstance(payload, list):
            raise forms.ValidationError("Guruhlar ro'yxati noto'g'ri formatda.")

        group_ids = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                group_ids.append(int(item.get("group_id") or 0))
            except (TypeError, ValueError):
                continue

        groups_qs = Group.objects.filter(is_archived=False, id__in=group_ids).select_related("center")
        if center:
            groups_qs = groups_qs.filter(center=center)
        group_map = {group.id: group for group in groups_qs}

        normalized_assignments = []
        seen_group_ids = set()
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise forms.ValidationError(f"{index}-guruh ma'lumoti noto'g'ri.")

            try:
                group_id = int(item.get("group_id") or 0)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f"{index}-guruh tanlanmagan.") from exc

            group = group_map.get(group_id)
            if not group:
                raise forms.ValidationError(f"{index}-guruh topilmadi yoki markazga tegishli emas.")
            if group_id in seen_group_ids:
                raise forms.ValidationError("Bir guruhni ikki marta biriktirib bo'lmaydi.")
            seen_group_ids.add(group_id)

            start_date_raw = (item.get("start_date") or item.get("requested_start_date") or "").strip()
            start_date = parse_date(start_date_raw)
            if not start_date:
                raise forms.ValidationError(f"{group.nom} uchun boshlanish sanasini kiriting.")

            schedule_meta = resolve_lesson_schedule(start_date, item.get("lesson_pattern"))

            course_price_value = item.get("course_price")
            if course_price_value in (None, ""):
                course_price_value = group.kurs_narxi or 0
            try:
                course_price = int(course_price_value)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f"{group.nom} uchun narx noto'g'ri.") from exc

            teacher_percent_value = item.get("teacher_percent")
            if teacher_percent_value in (None, ""):
                teacher_percent_value = group.oqituvchi_foiz or 0
            try:
                teacher_percent = int(teacher_percent_value)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f"{group.nom} uchun o'qituvchi ulushi noto'g'ri.") from exc

            if teacher_percent < 0 or teacher_percent > 100:
                raise forms.ValidationError(f"{group.nom} uchun o'qituvchi ulushi 0 dan 100 gacha bo'lishi kerak.")

            monthly_lessons_value = item.get("monthly_lessons")
            if monthly_lessons_value in (None, ""):
                monthly_lessons_value = group.oy_dars_soni or 12
            try:
                monthly_lessons = int(monthly_lessons_value)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f"{group.nom} uchun oy dars soni noto'g'ri.") from exc

            normalized_assignments.append({
                "group": group,
                "group_id": group.id,
                "group_name": group.nom,
                "start_date": schedule_meta["start_date"],
                "lesson_pattern": schedule_meta["lesson_pattern"],
                "course_price": max(0, course_price),
                "teacher_percent": teacher_percent,
                "monthly_lessons": max(0, monthly_lessons),
            })

        return normalized_assignments

    def _clean_phone_field(self, field_name):
        raw_value = (self.cleaned_data.get(field_name) or "").strip()
        if not raw_value:
            return ""

        raw_digits = re.sub(r"\D", "", raw_value)
        if raw_digits in ("", "998"):
            return ""

        normalized = normalize_phone(raw_value)
        if not re.fullmatch(r"\+998\d{9}", normalized or ""):
            self.add_error(field_name, "Telefon raqam faqat raqamlardan iborat bo'lsin va +998 bilan to'liq formatda kiriting.")
            return raw_value
        return normalized

    def clean_telefon1(self):
        return self._clean_phone_field("telefon1")

    def clean_telefon2(self):
        return self._clean_phone_field("telefon2")

    def clean_passport_id(self):
        value = (self.cleaned_data.get("passport_id") or "").strip().upper()
        if not value:
            return ""
        if not re.fullmatch(r"[A-Z]{2}\d{7}", value):
            raise forms.ValidationError("Passport seriya raqami `AD1231212` ko'rinishida bo'lsin: 2 ta harf va 7 ta raqam.")
        return value

    def save(self, commit=True):
        data = self.cleaned_data
        request = self.request
        req_user = getattr(request, "user", None) if request else None

        center_to_set = None
        if req_user and req_user.is_superuser:
            center_to_set = getattr(request, "center", None) or data.get("center")
        elif req_user and getattr(req_user, "role", None) in ("director", "manager", "teacher"):
            center_to_set = getattr(request, "center", None) or getattr(req_user, "center", None)

        if not center_to_set and req_user and not req_user.is_superuser:
            raise forms.ValidationError("Active center topilmadi.")

        user = super().save(commit=False)
        user.center = center_to_set
        user.is_staff = (user.role in ("manager", "director"))
        if user.is_demo_user is None:
            user.is_demo_user = False
        
        if user.role == "teacher":
            user.oqituvchi_foizi = data.get("oqituvchi_foizi") or 40
        else:
            user.oqituvchi_foizi = 0

        user.set_password(data["password"])

        if commit:
            user.save()
            
            # Handle Enrollment
            if user.role == "student" and self.allow_initial_group_assignment:
                from education.services.enrollment_service import EnrollmentService
                from education.services.tuition import ensure_all_tuition_months_since_start

                if self.cleaned_group_assignments:
                    for assignment in self.cleaned_group_assignments:
                        enrollment = EnrollmentService.enroll_student(
                            student=user,
                            group=assignment["group"],
                            kurs_narxi=assignment["course_price"],
                            oqituvchi_foiz=assignment["teacher_percent"],
                            start_date=assignment["start_date"],
                            lesson_pattern=assignment["lesson_pattern"],
                            monthly_lessons=assignment["monthly_lessons"],
                        )
                        ensure_all_tuition_months_since_start(enrollment, timezone.localdate())
                else:
                    group = data.get("group")
                    if group:
                        start_date = data.get("group_start_date") or timezone.localdate()
                        enrollment = EnrollmentService.enroll_student(
                            student=user,
                            group=group,
                            kurs_narxi=data.get("kurs_narhi") or group.kurs_narxi,
                            oqituvchi_foiz=group.oqituvchi_foiz,
                            start_date=start_date,
                        )
                        ensure_all_tuition_months_since_start(enrollment, timezone.localdate())

            if user.role == "parent":
                user.children.set(data.get("children_ids") or [])

        return user


class TeacherForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['ism', 'familya', 'otchestvo', 'email', 'telefon1', 'center', 'oqituvchi_foizi', 'passport_id', 'jshr', 'birth_date', 'gender', 'telefon2']


class CenterAdminForm(forms.ModelForm):
    """Super Admin uchun markazni yaratish/tahrirlash formasi"""
    expires_at = forms.DateField(
        widget=forms.DateInput(attrs={
            "class": "form-control bg-dark text-white border-secondary",
            "type": "date"
        }, format='%Y-%m-%d'),
        label="Tugash Sanasi (Obuna)",
        required=False
    )

    class Meta:
        model = Center
        fields = [
            "name", "slug", "address",
            "plan",
            "capacity_limit", "expires_at",
            "status", "features"
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "slug": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "address": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "capacity_limit": forms.NumberInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "status": forms.Select(attrs={"class": "form-select bg-dark text-white border-secondary"}),
            "features": forms.HiddenInput(),
        }
        labels = {
            "name": "Markaz Nomi",
            "slug": "Subdomain URL (Slug)",
            "address": "Manzil",
            "plan": "Tarif Rejasi",
            "capacity_limit": "O'quvchilar Limiti (Max Students)",
            "features": "Qo‘shimcha Imkoniyatlar (JSON)",
        }

    def clean_expires_at(self):
        date_val = self.cleaned_data.get('expires_at')
        if date_val:
            from django.utils import timezone
            import datetime
            # Convert date to datetime at start of day
            dt = datetime.datetime.combine(date_val, datetime.time.min)
            return timezone.make_aware(dt)
        return None

    def clean_slug(self):
        from django.utils.text import slugify
        slug = self.cleaned_data.get('slug', '').strip().lower()
        if not slug:
            raise forms.ValidationError("Slug bo'sh bo'lishi mumkin emas.")
        # Normalise
        slug = slugify(slug)
        if not slug:
            raise forms.ValidationError("Slug faqat harf va raqamlardan iborat bo'lishi kerak.")
        # Reject reserved slugs that conflict with URL routing
        RESERVED_SLUGS = {
            'admin', 'platform', 'hisob', 'static', 'media', 'api',
            'health', 'logout', 'c', 'emergency-enter-now', 'chaqmoq',
            'talim', 'store', 'billing', 'favicon',
        }
        if slug in RESERVED_SLUGS:
            raise forms.ValidationError(
                f'"{slug}" tizim tomonidan band qilingan. Boshqa slug tanlang.'
            )
        # Check uniqueness against ALL rows (including soft-deleted),
        # because the DB UNIQUE constraint covers every row.
        qs = Center._default_manager.all().filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f'"{slug}" slugli markaz allaqachon mavjud (yoki o\'chirilgan). '
                f'Boshqa noyob slug tanlang.'
            )
        return slug

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Create sahifasida bu qiymatlar JS orqali sync qilinadi.
        # JS ishlamay qolsa ham brauzer submitni bloklamasligi uchun
        # maydonni server tomonida optional qilib, clean() da to'ldiramiz.
        self.fields["capacity_limit"].required = False
        self.fields["features"].required = False
        
        # ✅ Fix: Ensure date input gets YYYY-MM-DD format
        if self.instance.pk and self.instance.expires_at:
            self.fields['expires_at'].initial = self.instance.expires_at.strftime('%Y-%m-%d')

        from billing.models import SubscriptionPlan
        
        # Populate plan choices dynamically from active plans
        plans = SubscriptionPlan.objects.filter(active=True).order_by('monthly_price')
        choices = [(p.code, f"{p.title} ({p.monthly_price:,} UZS)") for p in plans]
        
        # Add fallback if current instance has a plan not in active list (so it doesn't break edit)
        if self.instance.pk and self.instance.plan:
            if not any(c[0] == self.instance.plan for c in choices):
                choices.insert(0, (self.instance.plan, f"{self.instance.plan} (Arxiv)"))
        
        # Default empty choice
        if not choices:
             choices = [("", "Tariflar mavjud emas")]

        self.fields['plan'] = forms.ChoiceField(
            choices=choices,
            widget=forms.Select(attrs={"class": "form-select bg-dark text-white border-secondary", "id": "id_plan"}),
            label="Tarif Rejasi"
        )

    def clean(self):
        cleaned_data = super().clean()

        from billing.models import SubscriptionPlan
        from core.center_features import CENTER_UI_FEATURE_DEFAULTS

        plan_code = cleaned_data.get("plan")
        plan = SubscriptionPlan.objects.filter(code=plan_code).first() if plan_code else None

        if not cleaned_data.get("capacity_limit"):
            if plan and plan.max_students:
                cleaned_data["capacity_limit"] = plan.max_students
            elif self.instance.pk and self.instance.capacity_limit:
                cleaned_data["capacity_limit"] = self.instance.capacity_limit
            else:
                self.add_error("capacity_limit", "O'quvchilar limiti aniqlanmadi.")

        features = cleaned_data.get("features")
        if not isinstance(features, dict) or not features:
            feature_map = dict(getattr(self.instance, "features", {}) or {})
            if not feature_map:
                feature_map.update({
                    "dashboard": True,
                    "students": True,
                    "attendance": True,
                    "finance": True,
                })
                if plan:
                    for code in plan.plan_features.values_list("code", flat=True):
                        feature_map[code] = True
                for key, enabled in CENTER_UI_FEATURE_DEFAULTS.items():
                    feature_map.setdefault(key, bool(enabled))
            cleaned_data["features"] = feature_map

        return cleaned_data


class DirectorCreationForm(forms.ModelForm):
    """Markaz bilan birga director yaratish formasi"""
    password = forms.CharField(label="Parol", widget=forms.PasswordInput(attrs={"class": "form-control bg-dark text-white border-secondary"}))
    
    class Meta:
        model = User
        fields = ["ism", "familya", "email", "telefon1"]
        widgets = {
            "ism": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary", "placeholder": "Director Ismi"}),
            "familya": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary", "placeholder": "Familiyasi"}),
            "email": forms.EmailInput(attrs={"class": "form-control bg-dark text-white border-secondary", "placeholder": "Login (Email)"}),
            "telefon1": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary", "placeholder": "+998..."}),
        }

    def save(self, center, commit=True):
        user = super().save(commit=False)
        user.role = "director"
        user.center = center
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ParentForm(forms.ModelForm):
    # Field to select children (students) - reverted to multiple selection
    children_ids = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role="student"),
        widget=forms.SelectMultiple(attrs={"class": "form-control select2", "id": "id_children_ids"}),
        required=True,
        label="Farzandlarini tanlang"
    )

    class Meta:
        model = User
        fields = ["ism", "familya", "telefon1", "telefon2", "email", "password"]
        widgets = {
            "ism": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "Ism", "id": "id_ism"}),
            "familya": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "Familya", "id": "id_familya"}),
            "telefon1": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "+998...", "id": "id_telefon1"}),
            "telefon2": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "+998...", "id": "id_telefon2"}),
            "email": forms.EmailInput(attrs={"class": "form-control uniform-input", "placeholder": "Login (email)", "id": "id_email"}),
            "password": forms.PasswordInput(attrs={"class": "form-control uniform-input", "placeholder": "Parol", "id": "id_password"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if self.request:
            center = getattr(self.request, "center", None) or getattr(self.request.user, "center", None)
            if center:
                self.fields["children_ids"].queryset = User.objects.filter(role="student", center=center, is_archived=False)
        
        if self.instance and self.instance.pk:
            self.fields["children_ids"].initial = self.instance.children.all()
            self.fields["password"].required = False # Password not required on edit

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "parent"
        if self.request:
             user.center = getattr(self.request, "center", None) or getattr(self.request.user, "center", None)
        
        pw = self.cleaned_data.get("password")
        if pw:
            user.set_password(pw)
        
        if commit:
            user.save()
            # Set the multiple selected children
            user.children.set(self.cleaned_data.get("children_ids"))
        return user

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["ism", "familya", "avatar"]
        widgets = {
            "ism": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "Ismingiz..."}),
            "familya": forms.TextInput(attrs={"class": "form-control uniform-input", "placeholder": "Familiyangiz..."}),
            "avatar": forms.FileInput(attrs={"class": "form-control uniform-input", "style": "display:none;", "id": "id_avatar_input", "onchange": "previewImage(this)"}),
        }

class PasswordUpdateForm(forms.Form):
    new_password = forms.CharField(
        label="Yangi parol",
        widget=forms.PasswordInput(attrs={"class": "form-control uniform-input", "placeholder": "••••••••"}),
        min_length=8
    )
    confirm_password = forms.CharField(
        label="Yangi parol (takror)",
        widget=forms.PasswordInput(attrs={"class": "form-control uniform-input", "placeholder": "••••••••"}),
        min_length=8
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("new_password")
        p2 = cleaned_data.get("confirm_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Parollar bir-biriga mos kelmadi.")
        return cleaned_data
