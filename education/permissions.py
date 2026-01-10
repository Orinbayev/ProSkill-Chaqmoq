# education/permissions.py
from django.conf import settings


def user_can_manage_payments(user) -> bool:
    """
    To'lov bo'limini boshqarish ruxsati.
    Default: superuser/staff -> True
    Qo'shimcha: ruxsat (has_perm) yoki group nomlari orqali.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return False

    # 1) Eng kuchli: adminlar
    if user.is_superuser or user.is_staff:
        return True

    # 2) Django permission orqali (agar mavjud bo'lsa)
    perm_candidates = [
        "education.manage_payments",   # agar siz custom permission qo'shgan bo'lsangiz
        "education.add_payment",
        "education.change_payment",
        "education.view_payment",
        "education.change_enrollment",
        "education.view_enrollment",
    ]
    for perm in perm_candidates:
        try:
            if user.has_perm(perm):
                return True
        except Exception:
            pass

    # 3) Guruh nomlari orqali (xohlasangiz settings'dan boshqarasiz)
    default_groups = [
        "Admin",
        "Boshqaruv",
        "Direktor",
        "Moliya",
        "Buxgalteriya",
        "Kassa",
        "Manager",
    ]
    allowed_groups = getattr(settings, "PAYMENT_MANAGER_GROUPS", default_groups)

    try:
        user_groups = set(user.groups.values_list("name", flat=True))
        if user_groups.intersection(set(allowed_groups)):
            return True
    except Exception:
        pass

    # 4) Agar sizda user.profile.role yoki user.role bo'lsa (ixtiyoriy)
    role = None
    try:
        role = getattr(getattr(user, "profile", None), "role", None) or getattr(user, "role", None)
    except Exception:
        role = None

    if role:
        role_s = str(role).lower()
        if role_s in {"admin", "director", "manager", "cashier", "accountant", "finance"}:
            return True

    return False