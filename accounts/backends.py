from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailOrPhoneBackend(ModelBackend):
    """
    Custom authentication backend — email yoki telefon raqami bilan login.

    PERF v2:
    - select_related('center') qo'shildi: User topilgandan keyin middleware
      va context processor center ga murojaat qiladi. select_related shu
      qo'shimcha DB query ni yo'q qiladi (login paytida 1 query tejaydi).
    - only() bilan faqat kerakli fieldlar yuklanyapti — katta User modeli uchun muhim.
    """

    # Login uchun kerakli fieldlar — barchasi emas
    _SELECT_FIELDS = (
        "id", "email", "phone_number", "password",
        "is_active", "is_staff", "is_superuser",
        "role", "ism", "familya", "center_id",
        "telegram_id", "is_telegram_linked", "is_demo_user",
    )

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        from accounts.utils import normalize_phone

        user = None
        try:
            # ✅ PERF: select_related('center') — middleware uchun oldindan yuklash
            user = (
                User.objects
                .select_related("center")
                .only(*self._SELECT_FIELDS)
                .get(email__iexact=username)
            )
        except User.DoesNotExist:
            norm_phone = normalize_phone(username)
            phone_matches = list(
                User.objects
                .select_related("center")
                .only(*self._SELECT_FIELDS)
                .filter(phone_number=norm_phone)
                .order_by("id")[:2]
            )
            if len(phone_matches) == 1:
                user = phone_matches[0]
            else:
                # Timing attack oldini olish
                User().set_password(password)
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
