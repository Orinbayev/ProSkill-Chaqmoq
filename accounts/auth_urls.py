"""
Authentication URL patterns with secure login view.
"""

from django.urls import path
from .auth_views import SecureLoginView

urlpatterns = [
    path('', SecureLoginView.as_view(), name='login'),
]
