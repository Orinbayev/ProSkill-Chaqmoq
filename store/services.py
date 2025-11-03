from django.db import transaction
from .models import PurchaseRequest, Sale
from chaqmoq.models import Ledger, Rule

@transaction.atomic
def approve_purchase(pr: PurchaseRequest, manager):
    """Manager yoki direktor so‘rovni tasdiqlaydi"""
    product = pr.product
    student = pr.student

    # ✅ 1. Balansni tekshirish
    balans = Ledger.student_balansi(student.id)
    umumiy_narx = product.narx_chaqmoq * pr.qty

    if balans < umumiy_narx:
        return False, f"{student.ism} uchun balans yetarli emas ({balans} / {umumiy_narx})"

    # ✅ 2. So‘rovni tasdiqlash
    pr.status = PurchaseRequest.APPROVED
    pr.manager = manager
    pr.save()

    # ✅ 3. Ledgerga yozuv qo‘shish (chaqmoq yechish)
    rule = Rule.objects.filter(nom__icontains="Sotib olish").first()
    if not rule:
        rule = Rule.objects.create(nom="Mahsulot sotib olish", tur="-", min_baho=0, max_baho=0)

    Ledger.objects.create(
        student=student,
        beruvchi=manager,
        rule=rule,
        ball=-umumiy_narx
    )

    # ✅ 4. Sotuv yozuvini yaratish
    Sale.objects.create(
        student=student,
        product=product,
        qty=pr.qty,
        narx_chaqmoq=product.narx_chaqmoq,
        manager=manager
    )

    # ✅ 5. Mahsulot statistikasi
    if hasattr(product, 'sotilgan_soni'):
        product.sotilgan_soni += pr.qty
        product.save(update_fields=['sotilgan_soni'])

    return True, f"{product.nom} mahsulot uchun so‘rov tasdiqlandi ✅"


def reject_purchase(pr: PurchaseRequest, manager):
    if pr.status != PurchaseRequest.PENDING:
        return False, 'Allaqachon ko‘rilgan.'
    pr.status = PurchaseRequest.REJECTED
    pr.manager = manager
    pr.save(update_fields=['status','manager'])
    return True, 'Rad etildi.'
