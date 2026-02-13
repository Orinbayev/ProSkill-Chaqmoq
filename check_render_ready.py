# 🔍 RENDER DIAGNOSTIC SCRIPT
"""
Run this to verify all Render deployment requirements
"""
import sys
import os

print("=" * 60)
print("🔍 RENDER DEPLOYMENT DIAGNOSTIC CHECK")
print("=" * 60)

errors = []
warnings = []
success = []

# 1. Check Python version
print("\n1️⃣ Checking Python version...")
py_version = sys.version_info
print(f"   Python {py_version.major}.{py_version.minor}.{py_version.micro}")
if py_version.major == 3 and py_version.minor >= 9:
    success.append("✅ Python version OK (3.9+)")
else:
    errors.append("❌ Python version too old (need 3.9+)")

# 2. Check Django
print("\n2️⃣ Checking Django...")
try:
    import django
    print(f"   Django {django.VERSION[0]}.{django.VERSION[1]}.{django.VERSION[2]}")
    success.append("✅ Django installed")
except ImportError:
    errors.append("❌ Django not installed")

# 3. Check gunicorn
print("\n3️⃣ Checking gunicorn...")
try:
    import gunicorn
    print(f"   gunicorn installed")
    success.append("✅ gunicorn installed")
except ImportError:
    errors.append("❌ gunicorn not installed (required for Render)")

# 4. Check psycopg2 (PostgreSQL driver)
print("\n4️⃣ Checking psycopg2...")
try:
    import psycopg2
    print(f"   psycopg2 installed")
    success.append("✅ psycopg2-binary installed")
except ImportError:
    errors.append("❌ psycopg2-binary not installed (required for PostgreSQL)")

# 5. Check dj-database-url
print("\n5️⃣ Checking dj-database-url...")
try:
    import dj_database_url
    print(f"   dj-database-url installed")
    success.append("✅ dj-database-url installed")
except ImportError:
    errors.append("❌ dj-database-url not installed (required for Render DATABASE_URL)")

# 6. Check whitenoise
print("\n6️⃣ Checking whitenoise...")
try:
    import whitenoise
    print(f"   whitenoise installed")
    success.append("✅ whitenoise installed")
except ImportError:
    errors.append("❌ whitenoise not installed (required for static files)")

# 7. Check wsgi.py exists
print("\n7️⃣ Checking wsgi.py...")
wsgi_path = "config/wsgi.py"
if os.path.exists(wsgi_path):
    print(f"   {wsgi_path} found")
    success.append("✅ config/wsgi.py exists")
else:
    errors.append(f"❌ {wsgi_path} not found")

# 8. Check render.yaml
print("\n8️⃣ Checking render.yaml...")
if os.path.exists("render.yaml"):
    print(f"   render.yaml found")
    try:
        with open("render.yaml", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "startCommand:" in content:
                success.append("✅ render.yaml has startCommand")
            else:
                errors.append("❌ render.yaml missing startCommand")
            
            if "$PORT" in content:
                success.append("✅ render.yaml uses $PORT")
            else:
                errors.append("❌ render.yaml doesn't use $PORT")
    except Exception as e:
        warnings.append(f"⚠️ Could not read render.yaml: {e}")
else:
    errors.append("❌ render.yaml not found")

# 9. Check settings files
print("\n9️⃣ Checking settings files...")
if os.path.exists("config/settings.py"):
    success.append("✅ config/settings.py exists")
else:
    errors.append("❌ config/settings.py not found")

if os.path.exists("config/settings_prod.py"):
    success.append("✅ config/settings_prod.py exists")
else:
    warnings.append("⚠️ config/settings_prod.py not found (optional)")

# 10. Check requirements.txt
print("\n🔟 Checking requirements.txt...")
if os.path.exists("requirements.txt"):
    try:
        with open("requirements.txt", "r", encoding="utf-8", errors="ignore") as f:
            reqs = f.read()
            required = ["Django", "gunicorn", "psycopg2-binary", "whitenoise"]
            for req in required:
                if req in reqs:
                    print(f"   ✅ {req}")
                else:
                    errors.append(f"❌ {req} missing from requirements.txt")
        
        # Check for the old typo
        if "reportlabdj-database-url" in reqs:
            errors.append("❌ TYPO FOUND: 'reportlabdj-database-url' should be two lines")
        else:
            success.append("✅ No typo in requirements.txt")
    except Exception as e:
        errors.append(f"❌ Could not read requirements.txt: {e}")
else:
    errors.append("❌ requirements.txt not found")

# Summary
print("\n" + "=" * 60)
print("📊 DIAGNOSTIC SUMMARY")
print("=" * 60)

print(f"\n✅ SUCCESS ({len(success)}):")
for s in success:
    print(f"  {s}")

if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  {w}")

if errors:
    print(f"\n❌ ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  {e}")
    print("\n🚨 FIX THESE ERRORS BEFORE DEPLOYING TO RENDER!")
    sys.exit(1)
else:
    print("\n🎉 ALL CHECKS PASSED! Ready for Render deployment.")
    sys.exit(0)
