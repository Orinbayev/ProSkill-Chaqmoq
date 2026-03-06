from django.urls import path
from .auth_views import SecureLoginView
from . import password_reset_views
from . import api_auth
from . import telegram_views

urlpatterns = [
    path('', SecureLoginView.as_view(), name='login'),
    
    # Password Reset
    path('parolni-tiklash/', password_reset_views.forgot_password_init, name='forgot_password_init'),
    path('parolni-tiklash/tasdiqlash/', password_reset_views.forgot_password_verify, name='forgot_password_verify'),
    path('parolni-tiklash/yangi/', password_reset_views.forgot_password_set, name='forgot_password_set'),
    
    # Phone Login
    path('phone-kirish/', password_reset_views.phone_login_init, name='phone_login_init'),
    
    # Telegram Link
    path('telegram-boglash/', telegram_views.connect_telegram, name='connect_telegram'),
    
    # Internal Bot API
    path('bot-user-status/', api_auth.get_bot_user_status, name='bot_user_status'),
    path('bot-user-details/', api_auth.get_bot_user_details, name='bot_user_details'),
    
]

