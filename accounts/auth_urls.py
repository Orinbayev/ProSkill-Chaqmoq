from django.urls import path
from .auth_views import SecureLoginView
from . import password_reset_views
from . import api_auth
from . import telegram_views

urlpatterns = [
    path('', SecureLoginView.as_view(), name='login'),
    
    # Password Reset
    path('parolni-tiklash/', password_reset_views.forgot_password_init, name='forgot_password_init'),
    path('parolni-tiklash/tanlash/', password_reset_views.forgot_password_verify_choice, name='forgot_password_verify_choice'),
    path('parolni-tiklash/tanlash-tasdiqlash/', password_reset_views.forgot_password_confirm_choice, name='forgot_password_confirm_choice'),
    path('parolni-tiklash/tasdiqlash/', password_reset_views.forgot_password_verify, name='forgot_password_verify'),
    path('parolni-tiklash/yangi/', password_reset_views.forgot_password_set, name='forgot_password_set'),
    
    # Phone Login
    path('phone-kirish/', password_reset_views.phone_login_init, name='phone_login_init'),
    
    # Telegram Link
    path('telegram-boglash/', telegram_views.connect_telegram, name='connect_telegram'),
    
    # Internal Bot API
    path('bot-user-status/', api_auth.get_bot_user_status, name='bot_user_status'),
    path('bot-user-details/', api_auth.get_bot_user_details, name='bot_user_details'),
    path('bot-unlink-telegram/', api_auth.unlink_telegram_api, name='bot_unlink_telegram'),
    
    # Admin Bot API
    path('bot-admin-dashboard/', api_auth.get_bot_admin_dashboard, name='bot_admin_dashboard'),
    path('bot-linked-users/', api_auth.get_bot_linked_users, name='bot_linked_users'),
    path('bot-broadcast-list/', api_auth.get_bot_broadcast_list, name='bot_broadcast_list'),
    path('bot-excel-export/', api_auth.get_bot_excel_export, name='bot_excel_export'),
    path('bot-manage-admins/', api_auth.manage_bot_admins_api, name='bot_manage_admins'),
    path('bot-settings/', api_auth.bot_settings_api, name='bot_settings_api'),
    path('bot-parent-reports-data/', api_auth.get_parent_reports_data, name='bot_parent_reports_data'),
]

