
import os
import django
from django.conf import settings
from datetime import date

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from accounts.models import Center
from education.models import Group, Payment, Enrollment, Attendance
from education.views import tolovlar_home
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware

User = get_user_model()

def run_smoke_test():
    print("🚀 Starting Smoke Test for Center Isolation...")

    # 1. Create Data
    # Center 1
    c1, _ = Center.objects.get_or_create(name="Center 1", slug="c1")
    u1 = User.objects.create_user(username="director1", password="p", role="director", center=c1)
    
    # Center 2
    c2, _ = Center.objects.get_or_create(name="Center 2", slug="c2")
    u2 = User.objects.create_user(username="director2", password="p", role="director", center=c2)

    # Groups
    g1 = Group.objects.create(nom="G1 (C1)", center=c1, kurs_narxi=100_000, oqituvchi_foiz=50)
    g2 = Group.objects.create(nom="G2 (C2)", center=c2, kurs_narxi=200_000, oqituvchi_foiz=50)

    # Students
    s1 = User.objects.create_user(username="student1", role="student", center=c1)
    s2 = User.objects.create_user(username="student2", role="student", center=c2)

    # Enrollments
    Enrollment.objects.create(group=g1, student=s1, center=c1, kurs_narhi=100_000, oqituvchi_foiz=50)
    Enrollment.objects.create(group=g2, student=s2, center=c2, kurs_narhi=200_000, oqituvchi_foiz=50)

    # Payments
    Payment.objects.create(student=s1, group=g1, summa=50_000, center=c1, created_by=u1)
    Payment.objects.create(student=s2, group=g2, summa=100_000, center=c2, created_by=u2)
    
    # Attendance (for income calculation)
    Attendance.objects.create(group=g1, student=s1, date=date.today(), present=True)
    Attendance.objects.create(group=g2, student=s2, date=date.today(), present=True)

    print("✅ Test Data Created successfully.")

    # 2. Simulate Request as Director 1
    factory = RequestFactory()
    request = factory.get('/education/tolovlar/')
    request.user = u1
    request.center = c1 # Middleware usually sets this
    
    # Add session/message support
    middleware = SessionMiddleware(lambda x: None)
    middleware.process_request(request)
    request.session.save()
    
    msg_middleware = MessageMiddleware(lambda x: None)
    msg_middleware.process_request(request)

    # 3. Call View
    print("\n🔍 Calling tolovlar_home as Director 1...")
    response = tolovlar_home(request)
    
    # Check context in response (if it was a TemplateResponse, which render() produces)
    # Since render() returns HttpResponse with content, we can't easily access context directly 
    # unless we mock render or parse HTML.
    # However, to explicitly check isolation logic, let's look at the HTML content for leakage.
    
    content = response.content.decode('utf-8')
    
    # 4. Assertions
    print("\n🧐 Verifying Isolation:")
    
    # Check for G1 (Should exist)
    if "G1 (C1)" in content:
        print("✅ G1 (Center 1) found in response.")
    else:
        print("❌ G1 (Center 1) NOT found! (Unexpected)")

    # Check for G2 (Should NOT exist)
    if "G2 (C2)" in content:
        print("❌ CRITICAL FAIL: G2 (Center 2) found in response! Data leakage detected.")
    else:
        print("✅ G2 (Center 2) NOT found. Group isolation passed.")

    # Check for student 2
    if "student2" in content:
         print("❌ CRITICAL FAIL: student2 (Center 2) found! Data leakage detected.")
    else:
         print("✅ student2 NOT found. Student check passed.")

    # Cleanup
    u1.delete()
    u2.delete()
    c1.delete()
    c2.delete()
    s1.delete()
    s2.delete()
    
    print("\n🎉 Smoke Test Completed.")

if __name__ == "__main__":
    try:
        run_smoke_test()
    except Exception as e:
        print(f"❌ Test Failed with error: {e}")
