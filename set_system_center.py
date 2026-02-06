# Make first center as system center
from accounts.models import Center

# Birinchi markazni tizim markazi qilamiz
center = Center.objects.first()
if center:
    center.is_system = True
    center.save()
    print(f"✅ '{center.name}' tizim markazi qilindi. Bu markazni o'chirib bo'lmaydi!")
else:
    print("❌ Hech qanday markaz topilmadi!")
