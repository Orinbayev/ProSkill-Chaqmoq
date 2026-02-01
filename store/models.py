from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()

# ===================================
# 1️⃣ MAHSULOT MODELI
# ===================================
class Product(models.Model):
    nom = models.CharField(max_length=150)
    narx_chaqmoq = models.PositiveIntegerField(help_text="Mahsulot narxi (chaqmoqda)")
    sotilgan_soni = models.PositiveIntegerField(default=0, help_text="Jami sotilgan mahsulotlar soni")
    izoh = models.TextField(blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)
    
    # ✅ Tenant isolation
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)

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
# 7️⃣ LEAD MODELLARI
# ===================================
class Yonalish(models.Model):
    nom = models.CharField(max_length=100)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ('nom', 'center')
        
    def __str__(self):
        return self.nom


class Manba(models.Model):
    nom = models.CharField(max_length=100)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ('nom', 'center')

    def __str__(self):
        return self.nom


class LeadStatus(models.Model):
    nom = models.CharField(max_length=100)
    center = models.ForeignKey('accounts.Center', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ('nom', 'center')

    def __str__(self):
        return self.nom




class Lead(models.Model):
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
    yosh = models.PositiveIntegerField()
    address = models.CharField(max_length=255, blank=True, verbose_name="Yashash manzili")
    manba = models.ForeignKey(Manba, on_delete=models.SET_NULL, null=True, blank=True)
    yonalish = models.ForeignKey(Yonalish, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey('LeadStatus', on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh (comment)")
    qoshilgan_sana = models.DateTimeField(auto_now_add=True)

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

    def __str__(self):
        return f"{self.ism} {self.familya or ''}".strip()
