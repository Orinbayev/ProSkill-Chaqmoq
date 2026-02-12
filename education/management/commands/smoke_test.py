
from django.core.management.base import BaseCommand
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

class Command(BaseCommand):
    help = 'Runs smoke test for center isolation'

    def handle(self, *args, **options):
        print("🚀 Starting Smoke Test inside Management Command...")

        # 1. Create Data
        # Center 1
        c1, _ = Center.objects.get_or_create(name="Center 1", slug="c1")
        u1, created = User.objects.get_or_create(email="director1@example.com", defaults={"password":"p", "role":"director", "center":c1})
        if not created and u1.center != c1:
             u1.center = c1
             u1.save()
        
        # Center 2
        c2, _ = Center.objects.get_or_create(name="Center 2", slug="c2")
        u2, created = User.objects.get_or_create(email="director2@example.com", defaults={"password":"p", "role":"director", "center":c2})
        if not created and u2.center != c2:
             u2.center = c2
             u2.save()

        # Groups
        g1, _ = Group.objects.get_or_create(nom="G1 (C1)", defaults={"center":c1, "kurs_narxi":100_000, "oqituvchi_foiz":50})
        g2, _ = Group.objects.get_or_create(nom="G2 (C2)", defaults={"center":c2, "kurs_narxi":200_000, "oqituvchi_foiz":50})
        
        if g1.center != c1: g1.center = c1; g1.save()
        if g2.center != c2: g2.center = c2; g2.save()

        # Students
        s1, _ = User.objects.get_or_create(email="student1@example.com", defaults={"role":"student", "center":c1, "password":"p"})
        s2, _ = User.objects.get_or_create(email="student2@example.com", defaults={"role":"student", "center":c2, "password":"p"})
        
        if s1.center != c1: s1.center = c1; s1.save()
        if s2.center != c2: s2.center = c2; s2.save()

        # Enrollments
        Enrollment.objects.get_or_create(group=g1, student=s1, defaults={"center":c1, "kurs_narhi":100_000, "oqituvchi_foiz":50})
        Enrollment.objects.get_or_create(group=g2, student=s2, defaults={"center":c2, "kurs_narhi":200_000, "oqituvchi_foiz":50})

        # Payments
        Payment.objects.get_or_create(student=s1, group=g1, defaults={"summa":50_000, "center":c1, "created_by":u1})
        Payment.objects.get_or_create(student=s2, group=g2, defaults={"summa":100_000, "center":c2, "created_by":u2})
        
        # Attendance (for income calculation)
        Attendance.objects.get_or_create(group=g1, student=s1, date=date.today(), defaults={"present":True})
        Attendance.objects.get_or_create(group=g2, student=s2, date=date.today(), defaults={"present":True})

        print("✅ Test Data Verified successfully.")

        # 2. Simulate Request as Director 1
        factory = RequestFactory()
        request = factory.get('/education/tolovlar/')
        request.user = u1
        request.center = c1 
        
        middleware = SessionMiddleware(lambda x: None) # Mock
        middleware.process_request(request)
        request.session.save()
        
        msg_middleware = MessageMiddleware(lambda x: None) # Mock
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
            self.stdout.write(self.style.SUCCESS("\n🎉 SMOKE TEST PASSED: ISOLATION CONFIRMED."))
            with open("smoke_test_result.txt", "w") as f: f.write("PASSED")
        else:
            self.stdout.write(self.style.ERROR("\n💥 SMOKE TEST FAILED: DATA LEAKAGE DETECTED."))
            with open("smoke_test_result.txt", "w") as f: f.write("FAILED")
