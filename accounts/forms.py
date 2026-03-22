# accounts/forms.py
from django import forms
from django.contrib.auth import get_user_model
from accounts.models import Center
from django.apps import apps
from django.core.exceptions import ValidationError

User = get_user_model()
Group = apps.get_model('education', 'Group')

ROLE_CHOICES = (
    ("student", "O‘quvchi"),
    ("teacher", "O‘qituvchi"),
    ("manager", "Manager"),
    ("parent", "Ota-ona"),
)

class AddUserForm(forms.ModelForm):
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

    class Meta:
        model = User
        fields = [
            "ism", "familya", "otchestvo",
            "telefon1", "telefon2",
            "center", "role",
            "email", "password",
            "oqituvchi_foizi",
            "birth_date", "gender", "passport_id", "jshr", "address",
        ]
        widgets = {
            "ism": forms.TextInput(attrs={"placeholder": "Ism", "class": "form-control uniform-input", "id": "id_ism"}),
            "familya": forms.TextInput(attrs={"placeholder": "Familya", "class": "form-control uniform-input", "id": "id_familya"}),
            "otchestvo": forms.TextInput(attrs={"placeholder": "Otasining ismi (ixtiyoriy)", "class": "form-control uniform-input", "id": "id_otchestvo"}),
            "telefon1": forms.TextInput(attrs={"placeholder": "+998XXXXXXXXX", "class": "form-control uniform-input"}),
            "telefon2": forms.TextInput(attrs={"placeholder": "+998XXXXXXXXX", "class": "form-control uniform-input"}),
            "email": forms.TextInput(attrs={"placeholder": "Login (email)", "class": "form-control uniform-input", "id": "id_email"}),
            "password": forms.PasswordInput(attrs={"placeholder": "Parol", "class": "form-control uniform-input", "id": "id_password"}),
            "birth_date": forms.DateInput(attrs={"type": "date", "class": "form-control uniform-input"}),
            "gender": forms.RadioSelect(attrs={"class": "gender-radio"}), 
            "passport_id": forms.TextInput(attrs={"placeholder": "AB1234567", "class": "form-control uniform-input"}),
            "jshr": forms.TextInput(attrs={"placeholder": "14 ta raqam", "class": "form-control uniform-input", "maxlength": "14"}),
            "address": forms.Textarea(attrs={"placeholder": "Manzil...", "class": "form-control uniform-input", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        self.fields["oqituvchi_foizi"].required = False

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



    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        group = cleaned_data.get("group")
        center = cleaned_data.get("center")
        
        if role == "student":
            if not cleaned_data.get("birth_date"):
                self.add_error("birth_date", "O‘quvchi uchun tug‘ilgan sana majburiy!")
            if not cleaned_data.get("gender"):
                self.add_error("gender", "O‘quvchi uchun jins tanlanishi shart!")
            
            # Security: Verify group center matches user center
            if group and center and group.center_id != center.id:
                raise forms.ValidationError("Tanlangan guruh ushbu markazga tegishli emas!")
            
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

    def save(self, commit=True):
        data = self.cleaned_data
        request = self.request
        req_user = getattr(request, "user", None) if request else None

        center_to_set = None
        if req_user and req_user.is_superuser:
            center_to_set = getattr(request, "center", None) or data.get("center")
        elif req_user and getattr(req_user, "role", None) in ("director", "manager"):
            center_to_set = getattr(req_user, "center", None)

        if not center_to_set and req_user and not req_user.is_superuser:
            raise forms.ValidationError("Active center topilmadi.")

        user = super().save(commit=False)
        user.center = center_to_set
        user.is_staff = (user.role in ("manager", "director"))
        
        if user.role == "teacher":
            user.oqituvchi_foizi = data.get("oqituvchi_foizi") or 40
        else:
            user.oqituvchi_foizi = 0

        user.set_password(data["password"])

        if commit:
            user.save()
            
            # Handle Enrollment
            group = data.get("group")
            if user.role == "student" and group:
                from education.models import Enrollment
                from education.services.tuition import ensure_tuition_month
                from django.utils import timezone
                
                enr, created = Enrollment.objects.get_or_create(
                    group=group,
                    student=user,
                    defaults={
                        'kurs_narhi': data.get("kurs_narhi") or group.kurs_narxi,
                        'oqituvchi_foiz': group.oqituvchi_foiz,
                        'center': group.center
                    }
                )
                
                # Agar o'quvchi birinchi marta shu guruhga qo'shilayotgan bo'lsa,
                # darhol joriy oy uchun TuitionMonth (qarz) yaratamiz
                if created:
                    ensure_tuition_month(enr, timezone.localdate())

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
            "db_name", "db_user", "db_password", "db_host", "db_port",
            "plan",
            "capacity_limit", "expires_at",
            "status", "features"
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "slug": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "address": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "db_name": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "db_user": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "db_password": forms.PasswordInput(attrs={"class": "form-control bg-dark text-white border-secondary"}, render_value=True),
            "db_host": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
            "db_port": forms.TextInput(attrs={"class": "form-control bg-dark text-white border-secondary"}),
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
