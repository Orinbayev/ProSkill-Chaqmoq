from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

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
    qoldiq = models.PositiveIntegerField(default=0, help_text="Ombordagi mahsulot soni")
    sotilgan_soni = models.PositiveIntegerField(default=0, help_text="Jami sotilgan mahsulotlar soni")
    izoh = models.TextField(blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mahsulot'
        verbose_name_plural = 'Mahsulotlar'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.nom} ({self.qoldiq} dona)"

    @property
    def mavjud(self):
        """Mahsulot mavjudmi?"""
        return self.qoldiq > 0


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
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS = (
        (PENDING, 'Kutilmoqda'),
        (APPROVED, 'Tasdiqlandi'),
        (REJECTED, 'Rad etildi'),
    )

    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUS, default=PENDING)
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasdiqlovchi', limit_choices_to={'role': 'manager'}
    )
    sana = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Xarid so‘rovi'
        verbose_name_plural = 'Xarid so‘rovlari'
        ordering = ['-sana']

    def __str__(self):
        s = f"{self.student.first_name} {self.student.last_name}" if self.student else "—"
        return f"{s} → {self.product.nom} x{self.qty} ({self.get_status_display()})"


# ===================================
# 4️⃣ SOTUV MODELI
# ===================================
class Sale(models.Model):
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
def create_sale_on_approve(sender, instance, created, **kwargs):
    """
    Manager tasdiqlaganda avtomatik sotuv yaratiladi,
    student chaqmoqdan to‘lov yechiladi,
    mahsulot qoldig‘i kamayadi.
    """
    if not created and instance.status == PurchaseRequest.APPROVED:
        product = instance.product
        student = instance.student

        # Studentda yetarli chaqmoq bo‘lsa
        if hasattr(student, 'chaqmoq') and student.chaqmoq >= product.narx_chaqmoq * instance.qty:
            # 1️⃣ Chaqmoqni yechish
            student.chaqmoq -= product.narx_chaqmoq * instance.qty
            student.save()

            # 2️⃣ Mahsulot qoldig‘ini kamaytirish
            if product.qoldiq >= instance.qty:
                product.qoldiq -= instance.qty
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


from django.db import models

class Yonalish(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nom


class Manba(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nom


class LeadStatus(models.Model):
    nom = models.CharField(max_length=100)

    def __str__(self):
        return self.nom


class Lead(models.Model):
    ism = models.CharField(max_length=100)
    familya = models.CharField(max_length=100, blank=True)
    telefon1 = models.CharField(max_length=20)
    telefon2 = models.CharField(max_length=20, blank=True)
    yosh = models.PositiveIntegerField()
    address = models.CharField(max_length=255, blank=True, verbose_name="Yashash manzili")

    manba = models.ForeignKey(Manba, on_delete=models.SET_NULL, null=True, blank=True)
    yonalish = models.ForeignKey(Yonalish, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey('LeadStatus', on_delete=models.SET_NULL, null=True, blank=True)

    # 🟢 Yangi maydon – izoh
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh (comment)")

    qoshilgan_sana = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ism} {self.familya or ''}".strip()
