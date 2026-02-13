import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_prod")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
print("\n" + "="*60)
print(f"🔍 DIAGNOSTIKA VA PAROL TIKLASH (User Model: {User.__name__})")
print("="*60)

# 1. Jami userlar
count = User.objects.count()
print(f"\n📊 Bazada jami userlar soni: {count} ta")

if count == 0:
    print("❌ BAZA BO'SH KO'RINYAPTI! (Flush qilingan yoki loaddata ishlamagan)")
    print("   Iltimos, qaytadan: python manage.py loaddata data.json qiling")
    sys.exit()

# 2. Target userlarni qidirish
emails_to_check = ["amirxondev@gmail.com", "yangi_admin@gmail.com"]
found_user = None

for email in emails_to_check:
    print(f"\n🔎 {email} qidirilmoqda...")
    # Case-insensitive search
    user = User.objects.filter(email__iexact=email).first()
    
    if user:
        print(f"   ✅ TOPILDI! ID: {user.id}, Asl Email: '{user.email}'")
        found_user = user
        break
    else:
        print(f"   ❌ Topilmadi.")

# 3. Parolni yangilash
if found_user:
    new_pass = "admin123"
    print(f"\n🛠️  Parol o'zgartirilmoqda: {found_user.email} -> '{new_pass}'")
    
    found_user.set_password(new_pass)
    found_user.is_active = True
    found_user.is_staff = True
    found_user.is_superuser = True
    found_user.save()
    
    print(f"✅ MUVAFFAQIYATLI! Yangi parol: {new_pass}")
    print(f"👉 Kirish uchun: {found_user.email} va parol: {new_pass}")

else:
    # Agar hech kim topilmasa, majburiy yangi admin yaratamiz
    print("\n⚠️  Eski adminlar topilmadi. Yangi 'rescue_admin' yaratamiz...")
    try:
        email = "rescue_admin@gmail.com"
        password = "admin123"
        if User.objects.filter(email=email).exists():
             u = User.objects.get(email=email)
             u.delete()
        
        User.objects.create_superuser(email=email, password=password)
        print(f"✅ YANGI ADMIN YARATILDI: {email}")
        print(f"👉 Parol: {password}")
    except Exception as e:
        print(f"❌ Xatolik yuz berdi: {e}")

print("\n" + "="*60)
