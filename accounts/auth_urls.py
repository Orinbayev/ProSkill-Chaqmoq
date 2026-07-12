from django.urls import path
from .auth_views import SecureLoginView
from . import password_reset_views
from . import api_auth
from . import telegram_views
from core import api_bot

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
    path('bot-parent-connect/', api_auth.connect_parent_by_token_api, name='bot_parent_connect'),
    path('bot-unlink-telegram/', api_auth.unlink_telegram_api, name='bot_unlink_telegram'),
    
    # Admin Bot API
    path('bot-admin-dashboard/', api_auth.get_bot_admin_dashboard, name='bot_admin_dashboard'),
    path('bot-app-adoption/', api_auth.get_bot_app_adoption, name='bot_app_adoption'),
    path('bot-linked-users/', api_auth.get_bot_linked_users, name='bot_linked_users'),
    path('bot-broadcast-list/', api_auth.get_bot_broadcast_list, name='bot_broadcast_list'),
    path('bot-excel-export/', api_auth.get_bot_excel_export, name='bot_excel_export'),
    path('bot-manage-admins/', api_auth.manage_bot_admins_api, name='bot_manage_admins'),
    path('bot-settings/', api_auth.bot_settings_api, name='bot_settings_api'),
    path('bot-parent-reports-data/', api_auth.get_parent_reports_data, name='bot_parent_reports_data'),
    path('bot-dashboard/', api_bot.bot_dashboard, name='bot_dashboard'),
    path('bot-notification-settings/', api_bot.bot_notification_settings, name='bot_notification_settings'),
    path('bot-store-purchase-request/', api_bot.bot_store_purchase_request_create, name='bot_store_purchase_request'),
    path('bot-group-attendance-sheet/', api_bot.bot_group_attendance_sheet, name='bot_group_attendance_sheet'),
    path('bot-group-attendance-mark/', api_bot.bot_group_attendance_mark, name='bot_group_attendance_mark'),
    path('bot-broadcast-audience/', api_bot.bot_broadcast_audience, name='bot_broadcast_audience'),
    path('bot-inline-student-search/', api_bot.bot_inline_student_search, name='bot_inline_student_search'),
    path('bot-deep-link/', api_bot.bot_deep_link, name='bot_deep_link'),
    path('bot-scheduler-payment-reminders/', api_bot.bot_scheduler_payment_reminders, name='bot_scheduler_payment_reminders'),
    path('bot-scheduler-parent-attendance/', api_bot.bot_scheduler_parent_attendance, name='bot_scheduler_parent_attendance'),
    path('bot-scheduler-weekly-reports/', api_bot.bot_scheduler_weekly_reports, name='bot_scheduler_weekly_reports'),
    path('bot-scheduler-month-end-reminders/', api_bot.bot_scheduler_month_end_reminders, name='bot_scheduler_month_end_reminders'),

    # Family bot — telefon orqali avtorizatsiya
    path('bot-family-find-by-phone/', api_auth.family_find_by_phone_api, name='bot_family_find_by_phone'),
    path('bot-family-issue-credentials/', api_auth.family_issue_credentials_api, name='bot_family_issue_credentials'),
    path('bot-family-search-child/', api_auth.family_search_child_api, name='bot_family_search_child'),
    path('bot-family-add-child/', api_auth.family_add_child_api, name='bot_family_add_child'),
    path('bot-family-confirm-link/', api_auth.family_confirm_link_api, name='bot_family_confirm_link'),
    path('bot-family-student-by-name/', api_auth.family_student_by_name_api, name='bot_family_student_by_name'),
]
