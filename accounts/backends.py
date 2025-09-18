# accounts/backends.py
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailOrUsernameBackend(ModelBackend):
    """
    Username bo'yicha aniq topishga urinamiz (username unikal bo'lishi kerak).
    Agar topilmasa, email/gmail bo'yicha qidiramiz. Duplikat bo'lsa birinchi
    mos kelgan (faol) foydalanuvchini olamiz. Parol tekshiriladi.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        ident = username or kwargs.get(User.USERNAME_FIELD)
        if not ident or not password:
            return None

        user = None

        # 1) Avvalo username bo'yicha (case-insensitive) — u odatda unique
        try:
            user = User.objects.get(**{f"{User.USERNAME_FIELD}__iexact": ident})
        except User.DoesNotExist:
            user = None
        except User.MultipleObjectsReturned:
            # Username duplicat bo'lishi kerak emas, lekin shunchaki himoya
            user = None

        # 2) Username topilmasa — email/gmail bo'yicha qidiramiz
        if user is None:
            qs = User.objects.filter(
                Q(email__iexact=ident) | Q(gmail__iexact=ident)
            ).order_by('-is_active', '-last_login')  # eng mosini olamiz
            user = qs.first()

        if user and self.user_can_authenticate(user) and user.check_password(password):
            return user
        return None
