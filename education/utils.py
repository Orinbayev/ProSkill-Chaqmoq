# education/utils.py
from education.models import Payment

def calculate_student_balance(student, group):
    """
    O‘quvchi to‘lovlarini to‘g‘ri hisoblaydi.
    Overpayment bo‘lsa → keyingi oyga o‘tadi.
    """
    kurs_narhi = group.kurs_narxi

    # Barcha to‘lovlar yig‘indisi
    payments = Payment.objects.filter(student=student, group=group)
    total_paid = sum(p.summa for p in payments)

    # Necha oy to‘liq to‘langan?
    full_months = total_paid // kurs_narhi

    # O‘tgan oylar tugagandan keyin qolgan pul
    remain = total_paid % kurs_narhi

    # Agar remain > 0 bo‘lsa → keyingi oy uchun avans
    # Agar remain == 0 bo‘lsa → 0
    qoldiq_keyingi_oy = kurs_narhi - remain if remain > 0 else 0

    return {
        "kurs_narhi": kurs_narhi,
        "total_paid": total_paid,
        "full_months": full_months,
        "remain": remain,  # keyingi oyga o‘tgan pul
        "qoldiq": qoldiq_keyingi_oy,
        "is_full": remain == 0,
    }
