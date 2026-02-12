
from django.conf import settings
from datetime import date
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from accounts.models import Center
from education.models import Group, Payment, Enrollment, Attendance
from education.views import tolovlar_home
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware

User = get_user_model()

try:
    print("🚀 Starting Smoke Test inside Shell...")

    # 1. Create Data
    # Center 1
    c1, _ = Center.objects.get_or_create(name="Center 1", slug="c1")
    u1, _ = User.objects.get_or_create(username="director1", defaults={"password":"p", "role":"director", "center":c1})
    
    # Center 2
    c2, _ = Center.objects.get_or_create(name="Center 2", slug="c2")
    u2, _ = User.objects.get_or_create(username="director2", defaults={"password":"p", "role":"director", "center":c2})

    # Groups
    g1, _ = Group.objects.get_or_create(nom="G1 (C1)", defaults={"center":c1, "kurs_narxi":100_000, "oqituvchi_foiz":50})
    g2, _ = Group.objects.get_or_create(nom="G2 (C2)", defaults={"center":c2, "kurs_narxi":200_000, "oqituvchi_foiz":50})

    # Students
    s1, _ = User.objects.get_or_create(username="student1", defaults={"role":"student", "center":c1})
    s2, _ = User.objects.get_or_create(username="student2", defaults={"role":"student", "center":c2})

    # Enrollments
    Enrollment.objects.get_or_create(group=g1, student=s1, defaults={"center":c1, "kurs_narhi":100_000, "oqituvchi_foiz":50})
    Enrollment.objects.get_or_create(group=g2, student=s2, defaults={"center":c2, "kurs_narhi":200_000, "oqituvchi_foiz":50})

    # Payments
    Payment.objects.get_or_create(student=s1, group=g1, defaults={"summa":50_000, "center":c1, "created_by":u1})
    Payment.objects.get_or_create(student=s2, group=g2, defaults={"summa":100_000, "center":c2, "created_by":u2})
    
    # Attendance (for income calculation)
    Attendance.objects.get_or_create(group=g1, student=s1, date=date.today(), defaults={"present":True})
    Attendance.objects.get_or_create(group=g2, student=s2, date=date.today(), defaults={"present":True})

    print("✅ Test Data Created successfully.")

    # 2. Simulate Request as Director 1
    factory = RequestFactory()
    request = factory.get('/education/tolovlar/')
    request.user = u1
    request.center = c1 
    
    middleware = SessionMiddleware(lambda x: None)
    middleware.process_request(request)
    request.session.save()
    
    msg_middleware = MessageMiddleware(lambda x: None)
    msg_middleware.process_request(request)

    # 3. Call View
    print("\n🔍 Calling tolovlar_home as Director 1...")
    response = tolovlar_home(request)
    
    content = response.content.decode('utf-8')
    
    # 4. Assertions
    print("\n🧐 Verifying Isolation:")
    
    leak_detected = False
    
    # Check for G1 (Should exist)
    if "G1 (C1)" in content:
        print("✅ G1 (Center 1) found.")
    else:
        print("❌ G1 (Center 1) NOT found!")
        leak_detected = True

    # Check for G2 (Should NOT exist)
    if "G2 (C2)" in content:
        print("❌ CRITICAL FAIL: G2 (Center 2) found! LEAK!")
        leak_detected = True
    else:
        print("✅ G2 (Center 2) NOT found. passed.")

    # Check for student 2
    if "student2" in content:
         print("❌ CRITICAL FAIL: student2 (Center 2) found! LEAK!")
         leak_detected = True
    else:
         print("✅ student2 NOT found. passed.")

    if not leak_detected:
        print("\n🎉 SMOKE TEST PASSED: ISOLATION CONFIRMED.")
    else:
        print("\n💥 SMOKE TEST FAILED: DATA LEAKAGE DETECTED.")

except Exception as e:
    print(f"❌ Test Error: {e}")
