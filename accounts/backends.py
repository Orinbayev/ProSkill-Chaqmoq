from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrPhoneBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in using either
    their email or phone number.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        from accounts.utils import normalize_phone
        
        try:
            # Try by email first
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            try:
                # Try by normalized phone
                norm_phone = normalize_phone(username)
                user = User.objects.get(phone_number=norm_phone)
            except User.DoesNotExist:
                # Run the default password hasher once to reduce the vulnerability
                # to timing attacks.
                User().set_password(password)
                return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

