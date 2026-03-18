"""
core/slug_tenant_urls.py

All tenant-scoped URL patterns.
Included under BOTH:
  - path('', ...)           → /stat/students/
  - path('<slug>/', ...)    → /proskill/stat/students/
"""
from django.urls import path, include

urlpatterns = [
    path('', include(('core.urls', 'core'), namespace='core')),
    path('hisob/', include(('accounts.urls_tenant', 'accounts'), namespace='accounts')),
    path('hisob/billing/', include(('billing.urls', 'billing'), namespace='billing')),
    path('chaqmoq/', include(('chaqmoq.urls', 'chaqmoq'), namespace='chaqmoq')),
    path('talim/', include(('education.urls', 'education'), namespace='education')),
    path("do'kon/", include(('store.urls', 'store'), namespace='store')),
]
