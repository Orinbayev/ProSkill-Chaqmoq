import os
import django
import json
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.api_dashboard import DirectorDashboardAPIView
from accounts.models import User, Center
from education.models import Group, Enrollment, Payment, Attendance
from django.test import RequestFactory
from django.db.models import Sum, Q

def debug():
    user = User.objects.filter(role__in=['director', 'manager', 'admin']).first()
    if not user:
        print("No suitable user found")
        return

    center = user.center
    if not center:
        center = Center.objects.first()

    factory = RequestFactory()
    request = factory.get('/api/director/dashboard/?period=this_month')
    request.user = user
    request.center = center
    
    view = DirectorDashboardAPIView.as_view()
    try:
        response = view(request)
        print(response.content.decode())
    except Exception as e:
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    debug()
