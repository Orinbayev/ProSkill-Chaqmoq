from django.db import transaction
from .models import PurchaseRequest, Sale, Expense
from chaqmoq.models import Ledger, Rule
from .lead_services import convert_lead_to_student_safe

@transaction.atomic
def approve_purchase(pr: PurchaseRequest, manager):
    """Manager yoki direktor so‘rovni tasdiqlaydi"""
    product = pr.product
    student = pr.student

    # ✅ 1. Balansni tekshirish
    balans = Ledger.student_balansi(student.id, center=pr.center)
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

    from chaqmoq.models import LightningHistory
    from education.models import Student as EdStudent
    st_model, _ = EdStudent.objects.get_or_create(user=student)
    LightningHistory.objects.create(
        student=st_model,
        points=-umumiy_narx,
        reason=f"Do'kondan xarid: {product.nom}",
        source="manual",
        teacher=manager
    )

    # ✅ 4. Sotuv yozuvini yaratish
    Sale.objects.create(
        student=student,
        product=product,
        qty=pr.qty,
        narx_chaqmoq=product.narx_chaqmoq,
        narx_som=product.narx_som,
        manager=manager
    )

    # ✅ 6. Xarajat yozish (agar narx_som > 0 bo'lsa)
    if product.narx_som > 0:
        from .models import ExpenseCategory
        cat, _ = ExpenseCategory.objects.get_or_create(
            nom="Do'kon", 
            center=manager.center if manager.center else product.center
        )
        
        Expense.objects.create(
            center=manager.center if manager.center else product.center,
            summa=product.narx_som * pr.qty,
            izoh=f"{product.nom} (x{pr.qty})",
            product=product,
            category=cat,
            receiver=f"{student.ism} {student.familya}".strip(),
            worker=manager,
            payment_method='naqd' # Default
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
def convert_lead_to_student(lead, converted_by=None, target_center=None):
    """
    Backward-compatible wrapper.
    New implementation lives in `store.lead_services.convert_lead_to_student_safe`.
    """
    return convert_lead_to_student_safe(
        lead=lead,
        converted_by=converted_by,
        target_center=target_center,
    )
