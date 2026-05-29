"""
config/slug_prefix_urls.py

URL patterns for /<center_slug>/ prefix.
No app_name defined to avoid W005 conflicts.
Views resolve identically; request.center is set by TenantMiddleware.
"""
from django.urls import path, include
from billing import click_views as billing_click_views
from education import hr_views as education_hr_views

# Import urlpatterns directly (as a list) so Django does NOT auto-assign the
# accounts app_name from the module, avoiding the W005 duplicate-namespace warning
# and ensuring {% url 'accounts:...' %} always resolves to the canonical
# 'accounts' namespace defined in config/urls.py.
from accounts.urls_tenant import urlpatterns as _accounts_tenant_urls
from billing.urls import urlpatterns as _billing_urls
from chaqmoq.urls import urlpatterns as _chaqmoq_urls
from education.urls import urlpatterns as _education_urls
from store.urls import urlpatterns as _store_urls

urlpatterns = [
    path('api/hr/employees/', education_hr_views.employees_api, name='hr_employees_api_prefixed'),
    path('api/hr/employees/<int:employee_id>/', education_hr_views.employee_detail_api, name='hr_employee_detail_api_prefixed'),
    path('api/hr/teachers/available/', education_hr_views.available_teachers_api, name='hr_available_teachers_api_prefixed'),
    path('', include('core.urls')),
    path('', include(('marketing.urls', 'marketing_slug'), namespace='marketing_slug')),
    path('hisob/', include(_accounts_tenant_urls)),
    path('hisob/billing/', include(_billing_urls)),
    path('chaqmoq/', include(_chaqmoq_urls)),
    path('talim/', include(_education_urls)),
    path("do'kon/", include(_store_urls)),
]
