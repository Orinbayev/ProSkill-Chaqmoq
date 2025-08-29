from django.db import transaction
from .models import PurchaseRequest, Sale
from chaqmoq.models import Ledger, Rule

@transaction.atomic
def approve_purchase(pr: PurchaseRequest, manager):
    if pr.status != PurchaseRequest.PENDING:
        return False, 'Allaqachon ko‘rilgan.'
    # talab qilingan Chaqmoq
    kerak = pr.product.narx_chaqmoq * pr.qty
    balans = Ledger.student_balansi(pr.student_id)
    if balans < kerak:
        return False, 'Chaqmoq yetarli emas.'
    if pr.product.qoldiq < pr.qty:
        return False, 'Mahsulot qoldig‘i yetarli emas.'

    # Chaqmoq yechish (minus yozuv)
    minus_rule, _ = Rule.objects.get_or_create(nom='Do‘kondan xarid', tur=Rule.MINUS, defaults={'min_baho':1,'max_baho':1000000})
    Ledger.objects.create(student=pr.student, beruvchi=manager, rule=minus_rule, ball=-kerak)

    # qoldiq kamaytirish
    p = pr.product
    p.qoldiq -= pr.qty
    p.save(update_fields=['qoldiq'])

    # Sotuv yozish
    Sale.objects.create(student=pr.student, product=pr.product, qty=pr.qty, narx_chaqmoq=pr.product.narx_chaqmoq, manager=manager)

    pr.status = PurchaseRequest.APPROVED
    pr.manager = manager
    pr.save(update_fields=['status','manager'])
    return True, 'Tasdiqlandi.'
