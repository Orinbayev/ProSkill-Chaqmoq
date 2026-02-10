from django.db import transaction
from .models import PurchaseRequest, Sale, Expense
from chaqmoq.models import Ledger, Rule
import re
import secrets
import string
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.db import transaction

U = get_user_model()

User = get_user_model()
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

# store/services.py


def _normalize_phone(phone: str) -> str:
    """
    Lead telefonlari ba'zan '993845854' ko'rinishida bo'ladi.
    Biz buni +998993845854 ga aylantiramiz.
    """
    s = (phone or "").strip()
    if not s:
        return ""

    # faqat raqamlarni qoldiramiz
    digits = re.sub(r"\D+", "", s)

    # Agar 9 xonali bo'lsa (UZ local) => +998 qo'shamiz
    if len(digits) == 9:
        return "+998" + digits

    # Agar 12 xonali bo'lsa (998xxxxxxxxx) => + qo'shamiz
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits

    # Agar allaqachon +998... bo'lsa
    if s.startswith("+998"):
        return s

    # fallback
    return s


def _clean_for_login(text: str) -> str:
    s = (text or "").strip().lower()
    s = s.replace("o‘", "o").replace("o'", "o")
    s = s.replace("g‘", "g").replace("g'", "g")
    s = s.replace("’", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _gen_default_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


def _gen_unique_gmail_like_email(ism: str, familya: str) -> str:
    first_char = _clean_for_login(ism)[:1] or "s"
    last_part = _clean_for_login(familya)[:8]
    base = f"{first_char}.{last_part}" if last_part else first_char

    # 1. Asl holatda tekshirish (random raqamsiz)
    email = f"{base}@gmail.com"
    if not U.objects.filter(email=email).exists():
        return email

    # 2. Ketma-ket raqam qo'shish
    for i in range(1, 1000):
        email = f"{base}{i}@gmail.com"
        if not U.objects.filter(email=email).exists():
            return email

    # 3. Juda kam holatda random
    token = secrets.token_hex(3)
    return f"{base}{token}@gmail.com"


def convert_lead_to_student(lead, converted_by=None, target_center=None):
    """
    Lead status 'Tasdiqlandi' bo'lsa studentga o'tkazadi.

    Qoidalar:
    - Agar lead.converted_user bor bo'lsa: qayta yaratmaydi.
    - Telefon1 bo'yicha student topilsa: o'shani bog'laydi (update qiladi).
    - Aks holda: yangi student yaratadi (email+parol auto).
    - lead.converted_user / converted_by / converted_at to'ldiriladi.

    Return: (user, password, created)
      - created=True bo'lsa password qaytadi
      - existing bo'lsa password=None
    """
    if getattr(lead, "converted_user_id", None):
        return lead.converted_user, None, False

    tel1 = _normalize_phone(getattr(lead, "telefon1", ""))
    tel2 = _normalize_phone(getattr(lead, "telefon2", ""))

    with transaction.atomic():
        # 1) NEW: Always create a new student as requested.
        # 2) Yangi student yaratamiz
        email = _gen_unique_gmail_like_email(lead.ism, lead.familya)
        password = _gen_default_password()

        user = U(email=email)
        user.role = "student"
        user.center = target_center or lead.center
        user.ism = lead.ism
        user.familya = lead.familya

        if hasattr(user, "telefon1") and tel1:
            user.telefon1 = tel1
        if hasattr(user, "telefon2") and tel2:
            user.telefon2 = tel2
        
        # ✅ Extended fields
        user.otchestvo = getattr(lead, "otchestvo", "")
        user.birth_date = getattr(lead, "birth_date", None)
        user.gender = getattr(lead, "gender", "")
        user.passport_id = getattr(lead, "passport_id", "")
        user.jshr = getattr(lead, "jshr", "")
        user.address = getattr(lead, "address", "")

        user.set_password(password)
        user.save()
        created = True

        # 3) Lead bilan bog'laymiz
        lead.converted_user = user
        lead.converted_at = timezone.now()
        if converted_by is not None:
            lead.converted_by = converted_by
        lead.save(update_fields=["converted_user", "converted_at", "converted_by"])

    return user, password, created
