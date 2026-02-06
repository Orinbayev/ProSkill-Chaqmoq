
import os
import time
import django
from django.conf import settings
from django.urls import reverse, NoReverseMatch

# Setup Django
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

def run_test():
    # 1. Create/Get Superuser for testing
    email = 'smoke_test@chaqmoq.uz'
    password = 'password123'
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        user = User.objects.create_superuser(
            email=email, 
            password=password,
            role='director',
            ism='Smoke',
            familya='Tester'
        )
        print(f"Test user yaratildi: {email}")

    # 2. Define Sidebar items
    # (Label, ViewName or Path)
    pages = [
        ("Boshqaruv (Dashboard)", "core:home"),
        ("Markazlar", "accounts:center_picker"),
        ("O'quvchilar", "core:stat_students"),
        ("Bo'limlar", "education:groups_home"),
        ("Guruhlar", "education:attendance_groups"),
        ("Do'kon", "store:products"),
        ("To'lov", "education:tolovlar_home"),
        ("Hisobot", "education:teacher_salary_summary"),
        ("Reyting", "chaqmoq:reyting"),
        ("Chaqmoq berish", "chaqmoq:berish"),
        ("Admin Panel", "/admin/"),
    ]

    print(f"\n{'BO\'LIM':<30} | {'VAQT':<10} | {'HOLAT'}")
    print("-" * 60)

    client = Client()
    client.force_login(user)

    results = []

    for label, url_name in pages:
        
        # Resolve URL
        try:
            if url_name.startswith("/"):
                path = url_name
            else:
                path = reverse(url_name)
        except NoReverseMatch:
            # Fallback for core:home if not found, usually it's index
            if url_name == 'core:home':
                path = '/'
            else:
                print(f"{label:<30} | {'URL ERROR':<10} | {url_name} topilmadi")
                continue

        start = time.time()
        try:
            response = client.get(path)
            duration = time.time() - start
            status = response.status_code
            
            # Check for redirect (login page?)
            if status == 302:
                status_str = f"302 -> {response.url}"
            else:
                status_str = str(status)

            results.append({
                'label': label,
                'duration': duration,
                'status': status_str,
                'path': path
            })
            
            # Formatting
            dur_str = f"{duration:.4f}s"
            warn = ""
            if duration > 1.5:
                warn = "[!!!] JUDA SEKIN!"
            elif duration > 0.8:
                warn = "[!] Sekin"
            elif duration < 0.1:
                warn = "[OK] Tez"
            
            print(f"{label:<30} | {dur_str:<10} | {status_str} {warn}")
            
        except Exception as e:
            print(f"{label:<30} | ERROR      | {e}")

    print("-" * 60)
    
    # Summary
    if results:
        results.sort(key=lambda x: x['duration'], reverse=True)
        print("\n[SLOW] ENG SEKIN 3 TA BO'LIM:")
        for i, r in enumerate(results[:3], 1):
             print(f"{i}. {r['label']} ({r['path']}): {r['duration']:.4f} sekund")

if __name__ == "__main__":
    run_test()
