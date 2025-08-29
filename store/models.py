from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Product(models.Model):
    nom = models.CharField(max_length=150)
    narx_chaqmoq = models.PositiveIntegerField()
    qoldiq = models.PositiveIntegerField(default=0)
    izoh = models.TextField(blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mahsulot'
        verbose_name_plural = 'Mahsulotlar'

    def __str__(self):
        return self.nom

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='rasmlar')
    rasm = models.ImageField(upload_to='products/')

    class Meta:
        verbose_name = 'Mahsulot rasmi'
        verbose_name_plural = 'Mahsulot rasmlari'

class PurchaseRequest(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS = (
        (PENDING, 'Kutilmoqda'),
        (APPROVED, 'Tasdiqlandi'),
        (REJECTED, 'Rad etildi'),
    )

    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role':'student'})
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUS, default=PENDING)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasdiqlovchi', limit_choices_to={'role':'manager'})
    sana = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Xarid so‘rovi'
        verbose_name_plural = 'Xarid so‘rovlari'

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
