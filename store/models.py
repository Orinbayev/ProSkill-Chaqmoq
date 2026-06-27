from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.soft_delete import SoftDeleteMixin

User = get_user_model()

# ===================================
# 1️⃣ MAHSULOT MODELI
# ===================================
class Product(SoftDeleteMixin, models.Model):
    nom = models.CharField(max_length=150)
    narx_chaqmoq = models.PositiveIntegerField(help_text="Mahsulot narxi (chaqmoqda)")
    narx_som = models.PositiveIntegerField(default=0, help_text="Mahsulot narxi (so‘mda)")
    sotilgan_soni = models.PositiveIntegerField(default=0, help_text="Jami sotilgan mahsulotlar soni")
    izoh = models.TextField(blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)
    
    # ✅ Tenant isolation
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)

    # Bo'lim cheklovi: bo'sh = hammaga ko'rinadi, belgilansa faqat o'sha bo'limdagilarga
    allowed_categories = models.ManyToManyField(
        'education.Category',
        blank=True,
        related_name='restricted_products',
        verbose_name="Ko'rinadigan bo'limlar (bo'sh = hammaga)",
    )

    class Meta:
        verbose_name = 'Mahsulot'
        verbose_name_plural = 'Mahsulotlar'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.nom} — {self.sotilgan_soni} dona sotilgan"

    @property
    def mavjud(self):
        """Har doim True qaytaradi, chunki mahsulot doim mavjud hisoblanadi"""
        return True

    @property
    def sotib_olganlar(self):
        from store.models import Sale
        return Sale.objects.filter(product=self).count()



# ===================================
# 2️⃣ MAHSULOT RASMI
# ===================================
class ProductImage(models.Model):
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='rasmlar')
    rasm = models.ImageField(upload_to='products/')

    class Meta:
        verbose_name = 'Mahsulot rasmi'
        verbose_name_plural = 'Mahsulot rasmlari'

    def __str__(self):
        return f"Rasm: {self.product.nom}"


# ===================================
# 3️⃣ XARID SO‘ROVI
# ===================================
class PurchaseRequest(models.Model):
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    # ======== STATUS CHOICES ========
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS = (
        (PENDING, 'Kutilmoqda'),
        (APPROVED, 'Tasdiqlandi'),
        (REJECTED, 'Rad etildi'),
    )

    # ======== FIELDS ========
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'student'},
        verbose_name='O‘quvchi'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,  # 🔥 Mahsulot o‘chirilsa, bu joy NULL bo‘ladi
        null=True,
        blank=True,
        related_name='purchase_requests',
        verbose_name='Mahsulot'
    )

    qty = models.PositiveIntegerField(default=1, verbose_name='Soni')
    status = models.CharField(
        max_length=10,
        choices=STATUS,
        default=PENDING,
        verbose_name='Holat'
    )

    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasdiqlovchi',
        limit_choices_to={'role': 'manager'},
        verbose_name='Tasdiqlovchi'
    )

    sana = models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan sana')

    # ======== META ========
    class Meta:
        verbose_name = 'Xarid so‘rovi'
        verbose_name_plural = 'Xarid so‘rovlari'
        ordering = ['-sana']

    # ======== STRING REPRESENTATION ========
    def __str__(self):
        student_name = (
            f"{self.student.first_name} {self.student.last_name}"
            if self.student else "Noma'lum o‘quvchi"
        )
        product_name = (
            self.product.nom if self.product else "O‘chirilgan mahsulot"
        )
        return f"{student_name} → {product_name} ×{self.qty} ({self.get_status_display()})"


# ===================================
# 4️⃣ SOTUV MODELI
# ===================================
class Sale(models.Model):
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    qty = models.PositiveIntegerField(default=1)
    narx_chaqmoq = models.PositiveIntegerField()
    narx_som = models.PositiveIntegerField(default=0)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sotuv_manager')
    sana = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sotuv'
        verbose_name_plural = 'Sotuvlar'
        ordering = ['-sana']

    def __str__(self):
        s = f"{self.student.first_name} {self.student.last_name}" if self.student else "—"
        p = self.product.nom if self.product else "—"
        return f"{s} — {p} x{self.qty}"


# ===================================
# 5️⃣ SIGNAL — MANAGER TASDIQLAGANDA SOTUV YARATISH
# ===================================
@receiver(post_save, sender=PurchaseRequest)
def handle_purchase_request(sender, instance, created, **kwargs):
    """
    Manager tasdiqlaganda:
      - Studentdan chaqmoq yechiladi
      - Mahsulotning sotilgan_soni oshiriladi
      - Sotuv yozuvi yaratiladi
    """
    product = instance.product
    student = instance.student

    # Tasdiqlangan holat
    if not created and instance.status == PurchaseRequest.APPROVED:
        if hasattr(student, 'chaqmoq') and student.chaqmoq >= product.narx_chaqmoq * instance.qty:
            # 1️⃣ Chaqmoqni yechish
            student.chaqmoq -= product.narx_chaqmoq * instance.qty
            student.save()

            # 2️⃣ Sotilgan sonni oshirish
            product.sotilgan_soni += instance.qty
            product.save()

            # 3️⃣ Sotuv yozuvini yaratish
            Sale.objects.create(
                student=student,
                product=product,
                qty=instance.qty,
                narx_chaqmoq=product.narx_chaqmoq,
                manager=instance.manager
            )


# ===================================
# 6️⃣ IZOH MODELI
# ===================================
class Comment(models.Model):
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Izoh'
        verbose_name_plural = 'Izohlar'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} → {self.product.nom}"


# ===================================
# 6.1️⃣ XARAJATLAR (EXPENSE) - TEST UCHUN
# ===================================
class ExpenseCategory(models.Model):
    nom = models.CharField(max_length=100)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('nom', 'center')
        verbose_name = "Xarajat toifasi"
        verbose_name_plural = "Xarajat toifalari"
    
    def __str__(self):
        return self.nom


class PaymentMethod(models.Model):
    """
    Markaz tomonidan qo'shilgan to'lov usullari (NAQD, CLICK, PAYME, ...).
    Filtrlar va to'lov modallarida dropdown sifatida ishlatiladi.
    """
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True, related_name='payment_methods')
    nom = models.CharField(max_length=80, verbose_name="To'lov usuli nomi")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "To'lov usuli"
        verbose_name_plural = "To'lov usullari"
        ordering = ['-is_active', 'nom']
        unique_together = ('center', 'nom')

    def save(self, *args, **kwargs):
        if self.nom:
            self.nom = self.nom.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nom


class Expense(models.Model):
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    summa = models.PositiveIntegerField(verbose_name="Summa (so'm)")
    izoh = models.CharField(max_length=255, verbose_name="Izoh")
    sana = models.DateTimeField(default=timezone.now)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)

    # ✅ Yangi maydonlar
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Toifa")
    payment_method = models.CharField(
        max_length=20, 
        choices=[('naqd', 'Naqd'), ('plastik', 'Plastik'), ('otkazma', 'O‘tkazma')],
        default='naqd',
        verbose_name="To‘lov usuli"
    )
    receiver = models.CharField(max_length=150, blank=True, null=True, verbose_name="Qabul qiluvchi")
    worker = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Hodim")

    class Meta:
        verbose_name = "Xarajat"
        verbose_name_plural = "Xarajatlar"
        ordering = ['-sana']

    def __str__(self):
        return f"{self.summa} so'm - {self.izoh}"


# ===================================
# 7️⃣ LEAD MODELLARI
# ===================================
class Yonalish(models.Model):
    nom = models.CharField(max_length=100)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    color = models.CharField(max_length=20, blank=True, default="#64748b")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    class Meta:
        unique_together = ('nom', 'center')
        ordering = ("nom",)
        
    def __str__(self):
        return self.nom

    @property
    def display_color(self) -> str:
        return self.color or "#64748b"


class Manba(models.Model):
    nom = models.CharField(max_length=100)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ('nom', 'center')

    def __str__(self):
        return self.nom


class LeadStatus(models.Model):
    class Code(models.TextChoices):
        NEW = "new", "Yangi"
        CONTACTED = "contacted", "Bog'lanildi"
        NO_ANSWER = "no_answer", "Javob bermadi"
        TRIAL_SCHEDULED = "trial_scheduled", "Sinovga yozildi"
        TRIAL_ATTENDED = "trial_attended", "Sinov darsda qatnashdi"
        REGISTERED = "registered", "Tasdiqlandi"
        LOST = "lost", "Bekor qilingan"

    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=32, choices=Code.choices, blank=True, default="", db_index=True)
    order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ('nom', 'center')
        ordering = ("order", "nom")

    def __str__(self):
        return self.nom





class LeadGroup(models.Model):
    class Status(models.TextChoices):
        COLLECTING = "collecting", "Yig'ilmoqda"
        READY = "ready", "Tayyor"
        CONVERTED = "converted", "Guruhga aylantirilgan"

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=150)
    subject = models.ForeignKey(
        Yonalish,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_groups",
    )
    department = models.ForeignKey(
        "education.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_groups",
    )
    min_students = models.PositiveSmallIntegerField(default=1)
    note = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.COLLECTING,
        db_index=True,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_lead_groups",
    )
    converted_group = models.ForeignKey(
        "education.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_lead_groups",
    )
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archived_lead_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["center", "status"]),
            models.Index(fields=["center", "is_archived"]),
            models.Index(fields=["center", "subject"]),
            models.Index(fields=["center", "department"]),
        ]

    def __str__(self):
        return self.name

    @property
    def lead_count(self) -> int:
        return self.leads.filter(is_archived=False).count()

    @property
    def confirmed_lead_count(self) -> int:
        return self.leads.filter(is_archived=False).filter(
            models.Q(is_confirmed=True) | models.Q(converted_to_student=True)
        ).count()

    def mark_archived(self, by_user=None):
        self.is_archived = True
        self.archived_at = timezone.now()
        if by_user:
            self.archived_by = by_user
        self.save(update_fields=["is_archived", "archived_at", "archived_by", "updated_at"])

    def restore(self):
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.save(update_fields=["is_archived", "archived_at", "archived_by", "updated_at"])


class Lead(models.Model):
    class Subject(models.TextChoices):
        IELTS = "ielts", "IELTS"
        GENERAL_ENGLISH = "general_english", "General English"
        MATH = "math", "Matematika"
        RUSSIAN = "russian", "Rus tili"
        OTHER = "other", "Boshqa"

    class PipelineStatus(models.TextChoices):
        NEW = "new", "Yangi"
        CONTACTED = "contacted", "Bog'lanildi"
        TRIAL = "trial", "Sinovga yozildi"
        CONFIRMED = "confirmed", "Tasdiqlandi"
        CONVERTED = "converted", "O'quvchiga aylangan"
        CANCELED = "canceled", "Bekor qilingan"

    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    ism = models.CharField(max_length=100)
    familya = models.CharField(max_length=100, blank=True)
    otchestvo = models.CharField(max_length=150, blank=True, null=True, verbose_name="Otasining ismi")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    gender = models.CharField(max_length=10, choices=[('male', 'Erkak'), ('female', 'Ayol')], null=True, blank=True, verbose_name="Jinsi")
    passport_id = models.CharField(max_length=20, blank=True, null=True, verbose_name="Passport ID")
    jshr = models.CharField(max_length=14, blank=True, null=True, verbose_name="JSHR")
    telefon1 = models.CharField(max_length=20)
    telefon2 = models.CharField(max_length=20, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True, default="")
    parent_name = models.CharField(max_length=150, blank=True, default="", verbose_name="Ota-onasining ismi")
    yosh = models.PositiveIntegerField()
    address = models.CharField(max_length=255, blank=True, verbose_name="Yashash manzili")
    bilim_darajasi = models.CharField(max_length=100, blank=True, default="", verbose_name="Bilim darajasi / Sinfi")
    manba = models.ForeignKey(Manba, on_delete=models.SET_NULL, null=True, blank=True)
    yonalish = models.ForeignKey(Yonalish, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey('LeadStatus', on_delete=models.SET_NULL, null=True, blank=True)
    assigned_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_leads",
        limit_choices_to={"role": "manager"},
    )
    lead_group = models.ForeignKey(
        "LeadGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    added_to_group_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh (comment)")
    lost_reason = models.CharField(max_length=255, blank=True, default="")
    next_follow_up_date = models.DateField(null=True, blank=True, db_index=True)
    qoshilgan_sana = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_leads",
    )

    # ✅ NEW: lead → student conversion info
    converted_user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="converted_leads",
        verbose_name="O‘quvchi (student)"
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    converted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="converted_leads_by",
        verbose_name="Kim o‘tkazdi"
    )
    converted_to_student = models.BooleanField(default=False, db_index=True)
    is_confirmed = models.BooleanField(default=False, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_leads",
        verbose_name="Kim tasdiqladi",
    )

    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archived_leads",
    )

    class Meta:
        indexes = [
            models.Index(fields=["center", "qoshilgan_sana"]),
            models.Index(fields=["center", "status"]),
            models.Index(fields=["center", "assigned_manager"]),
            models.Index(fields=["center", "lead_group"]),
            models.Index(fields=["center", "manba"]),
            models.Index(fields=["center", "is_archived"]),
            models.Index(fields=["center", "is_confirmed"]),
            models.Index(fields=["center", "converted_to_student"]),
            models.Index(fields=["next_follow_up_date"]),
        ]

    def __str__(self):
        return f"{self.ism} {self.familya or ''}".strip()

    @property
    def full_name(self) -> str:
        return " ".join(part for part in [self.ism, self.familya, self.otchestvo] if part).strip()

    @property
    def note(self) -> str:
        return self.comment or ""

    @property
    def name(self) -> str:
        return self.full_name

    @property
    def phone(self) -> str:
        return self.telefon1 or self.telefon2 or self.parent_phone or ""

    @property
    def source(self):
        return self.manba

    @property
    def interested_course(self):
        return self.yonalish

    @property
    def manager(self):
        return self.assigned_manager

    @property
    def subject_name(self) -> str:
        return getattr(self.yonalish, "nom", "") or self.Subject.OTHER.label

    @property
    def subject_color(self) -> str:
        return getattr(self.yonalish, "display_color", "#64748b") or "#64748b"

    @property
    def pipeline_status(self) -> str:
        if self.converted_to_student:
            return self.PipelineStatus.CONVERTED

        status_code = (getattr(self.status, "code", "") or "").strip().lower()
        status_name = (getattr(self.status, "nom", "") or "").strip().lower()

        if status_code == LeadStatus.Code.LOST or "yo'qot" in status_name or "bekor" in status_name:
            return self.PipelineStatus.CANCELED
        if status_code in {LeadStatus.Code.TRIAL_SCHEDULED, LeadStatus.Code.TRIAL_ATTENDED} or "trial" in status_name or "sinov" in status_name:
            return self.PipelineStatus.TRIAL
        if status_code in {LeadStatus.Code.CONTACTED, LeadStatus.Code.NO_ANSWER} or "bog" in status_name or "aloqa" in status_name or "javob" in status_name:
            return self.PipelineStatus.CONTACTED
        if self.is_confirmed or status_code == LeadStatus.Code.REGISTERED or "tasdiq" in status_name or "register" in status_name:
            return self.PipelineStatus.CONFIRMED
        return self.PipelineStatus.NEW

    @property
    def pipeline_status_label(self) -> str:
        return dict(self.PipelineStatus.choices).get(self.pipeline_status, self.pipeline_status)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        normalized_update_fields = set(update_fields or [])
        previous_group_id = None
        previous_added_at = None
        should_track_group_change = self._state.adding or update_fields is None or bool(
            {"lead_group", "lead_group_id", "added_to_group_at"} & normalized_update_fields
        )

        if should_track_group_change and self.pk:
            previous_group_id, previous_added_at = (
                type(self).objects.filter(pk=self.pk)
                .values_list("lead_group_id", "added_to_group_at")
                .first()
                or (None, None)
            )

        if self.lead_group_id:
            if self._state.adding and not self.added_to_group_at:
                self.added_to_group_at = timezone.now()
            elif previous_group_id != self.lead_group_id:
                self.added_to_group_at = timezone.now()
            elif not self.added_to_group_at:
                self.added_to_group_at = previous_added_at or timezone.now()
        else:
            self.added_to_group_at = None

        if update_fields is not None:
            normalized_fields = set(update_fields)
            if "lead_group" in normalized_fields or "lead_group_id" in normalized_fields or "added_to_group_at" in normalized_fields:
                normalized_fields.add("added_to_group_at")
                kwargs["update_fields"] = list(normalized_fields)

        return super().save(*args, **kwargs)

    def mark_archived(self, by_user=None):
        self.is_archived = True
        self.archived_at = timezone.now()
        if by_user:
            self.archived_by = by_user
        self.save(update_fields=["is_archived", "archived_at", "archived_by", "updated_at"])

    def restore(self):
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.save(update_fields=["is_archived", "archived_at", "archived_by", "updated_at"])

    def mark_confirmed(self, by_user=None, save=True):
        self.is_confirmed = True
        if not self.confirmed_at:
            self.confirmed_at = timezone.now()
        if by_user:
            self.confirmed_by = by_user
        if save:
            self.save(update_fields=["is_confirmed", "confirmed_at", "confirmed_by", "updated_at"])

    def mark_converted(self, converted_user=None, converted_by=None):
        self.is_confirmed = True
        self.converted_to_student = True
        if converted_user:
            self.converted_user = converted_user
        if converted_by:
            self.converted_by = converted_by
            if not self.confirmed_by_id:
                self.confirmed_by = converted_by
        if not self.converted_at:
            self.converted_at = timezone.now()
        if not self.confirmed_at:
            self.confirmed_at = self.converted_at
        self.is_archived = True
        if converted_by:
            self.archived_by = converted_by
        if not self.archived_at:
            self.archived_at = timezone.now()
        self.save(
            update_fields=[
                "is_confirmed",
                "confirmed_at",
                "confirmed_by",
                "converted_to_student",
                "converted_user",
                "converted_by",
                "converted_at",
                "is_archived",
                "archived_by",
                "archived_at",
                "updated_at",
            ]
        )


class LeadActivity(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Yaratildi"
        UPDATED = "updated", "Yangilandi"
        STATUS_CHANGED = "status_changed", "Status o'zgardi"
        FOLLOW_UP_SET = "follow_up_set", "Qayta aloqa belgilandi"
        CONVERTED = "converted", "Studentga o'tkazildi"
        ARCHIVED = "archived", "Arxivlandi"
        TRIAL_SCHEDULED = "trial_scheduled", "Sinov dars belgilandi"
        TRIAL_RESULT_CHANGED = "trial_result_changed", "Sinov dars natijasi o'zgardi"

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=40, choices=Action.choices)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_activities",
    )
    from_value = models.CharField(max_length=255, blank=True, default="")
    to_value = models.CharField(max_length=255, blank=True, default="")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["center", "action", "created_at"]),
            models.Index(fields=["lead", "created_at"]),
        ]

    def __str__(self):
        return f"Lead#{self.lead_id} {self.action}"


class TrialLesson(models.Model):
    class ResultStatus(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        ATTENDED = "attended", "Qatnashdi"
        ABSENT = "absent", "Kelmagan"
        CONVERTED = "converted", "Ro'yxatdan o'tdi"
        NOT_INTERESTED = "not_interested", "Qiziqmadi"
        FOLLOW_UP_NEEDED = "follow_up_needed", "Qayta aloqa kerak"

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="trial_lessons")
    group = models.ForeignKey("education.Group", on_delete=models.SET_NULL, null=True, blank=True, related_name="trial_lessons")
    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trial_lessons",
        limit_choices_to={"role": "teacher"},
    )
    scheduled_at = models.DateTimeField()
    attended = models.BooleanField(null=True, blank=True)
    result_status = models.CharField(max_length=24, choices=ResultStatus.choices, default=ResultStatus.PENDING, db_index=True)
    notes = models.TextField(blank=True, default="")
    registered_after_trial = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_trial_lessons",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_trial_lessons",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-scheduled_at", "-id")
        indexes = [
            models.Index(fields=["center", "scheduled_at"]),
            models.Index(fields=["center", "result_status"]),
            models.Index(fields=["teacher", "scheduled_at"]),
            models.Index(fields=["lead", "scheduled_at"]),
        ]

    def __str__(self):
        return f"{self.lead.full_name} sinov dars @ {self.scheduled_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if not self.center_id:
            if self.lead_id and self.lead.center_id:
                self.center_id = self.lead.center_id
            elif self.group_id and self.group.center_id:
                self.center_id = self.group.center_id
        super().save(*args, **kwargs)


class TrialLessonActivity(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Yaratildi"
        UPDATED = "updated", "Yangilandi"
        RESULT_CHANGED = "result_changed", "Natija o'zgardi"
        CONVERTED = "converted", "Studentga o'tdi"

    center = models.ForeignKey("accounts.Center", on_delete=models.CASCADE, null=True, blank=True)
    trial_lesson = models.ForeignKey(TrialLesson, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=32, choices=Action.choices)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trial_lesson_activities",
    )
    from_value = models.CharField(max_length=255, blank=True, default="")
    to_value = models.CharField(max_length=255, blank=True, default="")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["center", "action", "created_at"]),
            models.Index(fields=["trial_lesson", "created_at"]),
        ]

    def __str__(self):
        return f"SinovDars#{self.trial_lesson_id} {self.action}"
