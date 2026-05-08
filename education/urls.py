from django.urls import path
from . import views
from . import hr_views
from .models import Group  # 🔹 kerak bo‘ladi category uchun

app_name = "education"

urlpatterns = [
    # === 📚 HUB / RO‘YXATLAR ===
    path("hr/", hr_views.hr_dashboard, name="hr_dashboard"),
    path("guruhlar/ro‘yxat/", views.group_list, name="group_list"),
    path("tolovlar/", views.tolovlar_home, name="tolovlar_home"),
    path("tolovlar/export/", views.payment_export_xlsx, name="payment_export_xlsx"),
    path("tolovlar/details/", views.get_payment_details, name="get_payment_details"),
    path("tolovlar/pdf-summary/", views.student_payments_pdf, name="student_payments_pdf"),
    path("tolovlar/oqituvchilar/", views.tolov_oqituvchilar, name="tolov_oqituvchilar"),
    path("api/calculate-lessons/", views.calculate_lessons_api, name="calculate_lessons_api"),
    path("xarajatlar/add/", views.expense_create, name="expense_create"),
    path("qarzdorlar/", views.qarzdorlar_home, name="qarzdorlar_home"),
    # path("payment/create/", views.create_payment, name="create_payment"),
    path("tolovlar/tarix/<int:student_id>/", views.payment_history, name="payment_history"),
    path("points-details/", views.points_details, name="points_details"),
    path("group-price/<int:pk>/", views.get_group_price, name="group_price"),
    path("groups/<int:pk>/bulk_remove/", views.group_bulk_remove, name="group_bulk_remove"),
    path('guruh/<int:g_id>/attend-all/', views.attend_all_students, name='group_attend_all'),
   path(
    "guruh/<int:group_id>/attendance/export/",
    views.group_month_attendance_export,
    name="group_month_attendance_export"
),
    path("tolov/create/", views.create_payment, name="create_payment"),

    path("tolovlar/tarix/enrollment/<int:enrollment_id>/", views.payment_history_enrollment, name="payment_history_enrollment"),
    path("tolov/chek/<int:payment_id>/", views.payment_receipt_pdf, name="payment_receipt_pdf"),
    path("tolovlar/enrollment/<int:enrollment_id>/edit/", views.enrollment_edit, name="enrollment_edit"),
    path("tolovlar/enrollment/<int:enrollment_id>/delete/", views.enrollment_delete, name="enrollment_delete"),
    path("tolov/update/<int:payment_id>/", views.payment_update, name="payment_update"),
    path("tolovlar/payment/<int:payment_id>/delete/", views.payment_delete, name="payment_delete"),
    path("tolovlar/student/<int:student_id>/groups/", views.student_groups_api, name="student_groups_api"),
    path("tolovlar/students/with-debt/", views.students_with_debt_api, name="students_with_debt_api"),
    # 🔹 Guruhlar kategoriyasi bo‘yicha
    path("guruhlar/", views.groups_home, name="groups_home"),
    path("guruhlar/hammasi/", views.all_groups_overview, name="all_groups"),
    path("guruhlar/add/", views.add_category, name="add_category"),
    path("guruhlar/tillar/", views.groups_by_category, {"category": Group.LANG}, name="groups_lang"),
    path("guruhlar/it/", views.groups_by_category, {"category": Group.IT}, name="groups_it"),
    
    # === ➕ YARATISH / TAHRIRLASH / O‘CHIRISH ===
    # 🔹 To‘g‘ridan-to‘g‘ri group_create view chaqiradi, lekin category qiymati uzatilgan holda
    path("guruh/yaratish/tillar/", views.group_create, {"category": Group.LANG}, name="group_create_lang"),
    path("guruh/yaratish/it/", views.group_create, {"category": Group.IT}, name="group_create_it"),

    path("guruh/<int:pk>/tahrirlash/", views.group_edit, name="group_edit"),
    path("guruh/<int:pk>/o‘chirish/", views.group_delete, name="group_delete"),
    path('guruhlar/', views.groups_hub, name='groups_hub'),

    # === 👥 GURUHLAR ===
    path("guruh/<int:pk>/", views.group_detail, name="group_detail"),
    path("groups/<int:group_id>/schedule/", views.group_schedule_manage, name="group_schedule_manage"),
    path("guruh/<int:pk>/add-student/", views.add_student_to_group, name="add_student_to_group"),
    path("guruh/<int:pk>/davomat/", views.group_rollcall, name="group_rollcall"),
    path('category/<int:id>/edit/', views.edit_category, name='edit_category'),
    path('category/<int:id>/delete/', views.delete_category, name='delete_category'),
    path('guruh/<int:id>/delete/', views.group_delete_confirm, name='group_delete_confirm'),
    path('guruh/<int:pk>/archive/', views.group_toggle_archive, name='group_toggle_archive'),
    path('guruh/<int:pk>/pause/', views.group_toggle_close, name='group_toggle_close'),
    path("groups/", views.group_list, name="groups"),
    path("groups/add/", views.group_add, name="group_add"),
    path("groups/<int:pk>/edit/", views.group_edit, name="group_edit"),
    path("groups/<int:pk>/delete/", views.group_delete, name="group_delete"),

    # === 📅 DAVOMAT va BALLAR ===
    path("guruh/<int:pk>/attendance_today/", views.attendance_today, name="attendance_today"),
    path("guruh/<int:pk>/points/", views.group_points, name="group_points"),
    path("attendance/toggle/", views.toggle_attendance, name="toggle_attendance"),
    path("schedule/conflict-check/", views.schedule_conflict_check, name="schedule_conflict_check"),
    path("schedule/weekly/", views.weekly_schedule_view, name="weekly_schedule"),
    path("schedule/my/", views.teacher_schedule_view, name="teacher_schedule"),

    # === 🧪 Imtihon moduli ===
    path("exam/settings/", views.exam_settings_view, name="exam_settings"),
    path("exam/reminder/<int:group_id>/action/", views.exam_reminder_action, name="exam_reminder_action"),
    path("exam/list/", views.exam_list, name="exam_list"),
    path("exam/create/", views.exam_create, name="exam_create"),
    path("exam/create/<int:group_id>/", views.exam_create, name="exam_create_for_group"),
    path("exam/sessions/<int:session_id>/", views.exam_session_entry, name="exam_session_entry"),
    path("exam/sessions/<int:session_id>/detail/", views.exam_session_detail, name="exam_session_detail"),
    path("exam/groups/<int:group_id>/history/", views.group_exam_history, name="group_exam_history"),
    path("exam/groups/<int:group_id>/internal-ranking/", views.group_internal_ranking, name="group_internal_ranking"),
    path(
        "exam/groups/<int:group_id>/completion-recommendations/",
        views.group_completion_recommendations,
        name="group_completion_recommendations",
    ),
    path("exam/groups/<int:group_id>/closure/action/", views.group_closure_action, name="group_closure_action"),
    path("exam/teacher-history/", views.teacher_exam_history, name="teacher_exam_history"),
    path("exam/failed-students/", views.failed_students_list, name="failed_students_list"),

    # === 🎓 Certificate / Diploma moduli ===
    path("certificates/templates/", views.certificate_templates_view, name="certificate_templates"),
    path(
        "certificates/templates/<int:template_id>/activate/",
        views.certificate_template_activate,
        name="certificate_template_activate",
    ),
    path(
        "certificates/groups/<int:group_id>/candidates/",
        views.group_certificate_candidates,
        name="group_certificate_candidates",
    ),
    path(
        "certificates/groups/<int:group_id>/students/<int:student_id>/issue/",
        views.issue_certificate_action,
        name="issue_certificate_action",
    ),
    path("certificates/<int:certificate_id>/", views.certificate_detail, name="certificate_detail"),
    path(
        "certificates/<int:certificate_id>/pdf/",
        views.certificate_download_pdf,
        name="certificate_download_pdf",
    ),
    path("certificates/verify/<str:certificate_number>/", views.certificate_verify, name="certificate_verify"),

    # === 💰 O‘QITUVCHI HISOBLARI ===
    path("teacher-salary/", views.teacher_salary_list, name="teacher_salary_list"),
    path("teacher-salary/export/", views.teacher_salary_export, name="teacher_salary_export"),
    path("teacher-salary/<int:teacher_id>/", views.teacher_groups, name="teacher_groups"),
    path("teacher-salary/group/<int:group_id>/", views.teacher_salary_report, name="teacher_salary_report"),
    path("teacher-salary/summary/", views.teacher_salary_summary, name="teacher_salary_summary"),
    path("teacher-salary/auto/", views.teacher_salary_redirect, name="teacher_salary_auto"),

    # === 👨‍🏫 O‘QITUVCHI UCHUN ===
    path("mening-guruhlarim/", views.my_groups, name="my_groups"),
    path("guruhlar/meniki/", views.my_groups, name="men_guruhlarim"),
    path("mening_guruhlarim/", views.my_groups, name="mening_guruhlarim"),
    path("daromadim/", views.teacher_income_dashboard, name="teacher_income_dashboard"),
    path("finance/close-month/", views.close_finance_month_view, name="close_finance_month"),
    path("finance/month-preview/", views.month_preview, name="month_preview"),
    path("fix-incomes/", views.fix_all_incomes, name="fix_all_incomes"),

    # === 🧍‍♂️ O‘QUVCHILAR ===
    path("student/<int:student_id>/", views.student_detail, name="student_detail"),
    path("student/<int:student_id>/exam-report/", views.student_exam_report, name="student_exam_report"),
    path("kiritish/<int:enrollment_id>/transfer/", views.transfer_student_view, name="transfer_student"),
    path("kiritish/<int:pk>/olib-tashlash/", views.enrollment_remove, name="enrollment_remove"),
    path("kiritish/<int:pk>/chiqish/", views.enrollment_leave, name="enrollment_leave"),
    path("kiritish/<int:pk>/kechiktir/", views.enrollment_toggle_deferred, name="enrollment_toggle_deferred"),
    path('guruhlar/<int:category_id>/', views.category_detail, name='category_detail'),
    # Guruh yaratish bo‘lim asosida
    path("guruh/yaratish/<int:category_id>/", views.group_create_by_category, name="group_create_category"),
    path(
        "attendance/force/",
        views.attendance_force,
        name="attendance_force"
    ),
    path(
        "attendance/groups/",
        views.attendance_groups,
        name="attendance_groups",
    ),

    path(
        "attendance/groups/<int:group_id>/",
        views.group_month_attendance,
        name="group_month_attendance",),

    path(
        "attendance/groups/<int:group_id>/toggle/",
        views.attendance_toggle_cell,
        name="attendance_toggle_cell",
    ),


]
from .api import teacher_expected_income_api
urlpatterns += [
    path("api/finance/teacher-expected-income/", teacher_expected_income_api, name="teacher_expected_income_api"),
]
