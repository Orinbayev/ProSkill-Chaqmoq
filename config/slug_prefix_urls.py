"""
config/slug_prefix_urls.py

URL patterns for /<center_slug>/ prefix.
No app_name defined to avoid W005 conflicts.
Views resolve identically; request.center is set by TenantMiddleware.
"""
from django.urls import path, include
from billing import click_views as billing_click_views
from education import hr_views as education_hr_views

urlpatterns = [
    path('api/hr/employees/', education_hr_views.employees_api, name='hr_employees_api_prefixed'),
    path('api/hr/employees/<int:employee_id>/', education_hr_views.employee_detail_api, name='hr_employee_detail_api_prefixed'),
    path('api/hr/teachers/available/', education_hr_views.available_teachers_api, name='hr_available_teachers_api_prefixed'),
    path('', include('core.urls')),
    path('', include(('marketing.urls', 'marketing_slug'), namespace='marketing_slug')),
    path('hisob/', include('accounts.urls_tenant')),
    path('hisob/billing/', include('billing.urls')),
    path('chaqmoq/', include('chaqmoq.urls')),
    path('talim/', include('education.urls')),
    path("do'kon/", include('store.urls')),
]
