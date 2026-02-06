# Role-Based Access Control (RBAC) - Xavfsizlik Arxitekturasi

## Muammo

Ilgari tizimda katta xavfsizlik muammosi mavjud edi:
- Foydalanuvchi qaysi URL orqali kirmasin, login qilgandan keyin o'sha URL'ga redirect bo'lardi
- O'quvchi admin panel URL'ini olsa, login qilgandan keyin admin panelga kirib ketardi
- `?next=` parametri orqali permission bypass qilish mumkin edi

## Yechim: 3 Qatlamli Xavfsizlik

### 1. Secure Login View

**Fayl:** `accounts/auth_views.py`

Login view `?next` parametrini **butunlay ignore** qiladi va har doim foydalanuvchini o'z roliga mos dashboardga yo'naltiradi:

```python
class SecureLoginView(auth_views.LoginView):
    def get_success_url(self):
        user = self.request.user
        role = getattr(user, 'role', None)
        
        # Role-based mapping
        dashboard_map = {
            'student': 'core:home',
            'parent': 'core:dashboard_parent',
            'teacher': 'core:home',
            'manager': 'core:home',
            'admin': 'core:home',
        }
        
        return reverse(dashboard_map.get(role, 'core:home'))
```

**Natija:**
- ✅ Login qilgandan keyin HAR DOIM to'g'ri dashboardga boradi
- ✅ `?next=/admin/staff/users/` - bu link IGNORE qilinadi
- ✅ Hech qanday URL injection ish bermaydi

### 2. Role-Based Access Middleware

**Fayl:** `core/middleware_rbac.py`

Har bir request'da foydalanuvchi rolini va URL'ni tekshiradi:

```python
class RoleBasedAccessMiddleware:
    # Har bir rol uchun ruxsat berilgan URL'lar ro'yxati
    role_permissions = {
        'student': ['core:home', 'core:user_view', 'store:*', ...],
        'parent': ['core:dashboard_parent', 'core:user_view', ...],
        'teacher': ['core:home', 'education:*', 'chaqmoq:*', ...],
        'manager': ['core:*', 'education:*', 'billing:*', ...],
        'admin': ['*'],  # Admin hamma joyga kirishi mumkin
    }
```

**Ishlash mexanizmi:**

1. **Request keladi** → Middleware tekshiradi
2. **Foydalanuvchi roli aniqlanadi** → `request.user.role`
3. **Current URL resolve qilinadi** → `resolve(request.path)`
4. **Permission check** → Rol uchun ruxsat bormi?
5. **Agar ruxsat yo'q** → O'z dashboardiga redirect
6. **Agar ruxsat bor** → So'rov davom etadi

**Misol:**

```
Student login qilgan
URL: /stat/users/ (manager/admin uchun)
Middleware: ❌ Ruxsat yo'q!
Action: → redirect('core:home') (student dashboard)
```

**Wildcard support:**

- `'core:*'` - core app'ning barcha URL'lariga ruxsat
- `'*'` - barcha URL'larga ruxsat (faqat admin uchun)

### 3. View-Level Permission Checks

Mavjud view'lardagi `@login_required` va custom permission check'lar ham ishlaydi. Endi ular **double protection** beradi.

## O'rnatish

### 1. Middleware'ni yoqish

`settings.py`:

```python
MIDDLEWARE = [
    # ... boshqa middleware'lar
    "core.middleware.TenantMiddleware",
    "billing.middleware.SubscriptionMiddleware",
    "core.middleware_rbac.RoleBasedAccessMiddleware",  # ✅ Shu yerda
]
```

**MUHIM:** `RoleBasedAccessMiddleware` **DOIM** `AuthenticationMiddleware`'dan **KEYIN** bo'lishi kerak!

### 2. Login URL'ni yangilash

`config/urls.py`:

```python
urlpatterns = [
    # ❌ ESki (xavfli):
    # path('hisob/login/', auth_views.LoginView.as_view(...), name='login'),
    
    # ✅ YANGI (xavfsiz):
    path('hisob/login/', include('accounts.auth_urls')),
]
```

### 3. Permission'larni sozlash

`middleware_rbac.py`'dagi `role_permissions` dict'ni o'zgartiring:

```python
self.role_permissions = {
    'student': [
        'core:home',
        'core:user_view',
        'store:*',  # Do'kon
        'chaqmoq:*',  # Ballar
    ],
    # ... boshqa rollar
}
```

## Sinash

### Test 1: Direct URL Access (ASOSIY TEST!)

1. **Student** sifatida login qiling
2. Browser'da qo'lda yozing: `http://127.0.0.1:8000/stat/users/`
3. **Kutilgan natija:** Avtomatik `core:home` (student dashboard)'ga redirect
4. **Xato natija:** Agar sahifa ochilsa - middleware ishlamayapti!

### Test 2: Login with ?next Parameter

1. Logout qiling
2. URL: `http://127.0.0.1:8000/hisob/login/?next=/stat/teacher/`
3. **Student** sifatida login qiling
4. **Kutilgan natija:** Student dashboard'ga boradi (next ignore)
5. **Xato natija:** Teacher sahifasiga borsa - SecureLoginView ishlamayapti!

### Test 3: Role Switching

Har bir rol uchun sinash:

| Rol | Login keyin borishi kerak |
|-----|---------------------------|
| student | `core:home` → student dashboard |
| parent | `core:dashboard_parent` |
| teacher | `core:home` → teacher dashboard |
| manager | `core:home` → manager dashboard |
| admin | `core:home` yoki `accounts:superadmin_dashboard` |

## Xavfsizlik modellari

### Model 1: Whitelisting (qo'llanilmoqda)

✅ **Faqat ruxsat berilgan URL'lar ochiladi**

```python
# Student faqat ro'yxatdagi URL'larga kirishi mumkin
'student': ['core:home', 'core:user_view', 'store:*']
```

**Afzalligi:** Eng xavfsiz. Yangi sahifa qo'shsangiz, ruxsat bermaguningizcha hech kim kira olmaydi.

### Model 2: Blacklisting (tavsiya ETILMAYDI!)

❌ **Taqiqlangan URL'lar ro'yxati**

```python
# YOMON yondashuv - ishlatmang!
forbidden_for_student = ['/admin/', '/stat/', '/staff/']
```

**Nega yomon?**
- Bitta URL unutsangiz - xavfsizlik muammo
- Har doim yangilash kerak
- Default = xavfsiz emas

## Qo'shimcha xavfsizlik choralar

### 1. CSRF Protection

Django'ning default CSRF middleware'i yoqilgan:

```python
MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',
]
```

### 2. Center Isolation

`TenantMiddleware` har bir foydalanuvchi faqat o'z markazi ma'lumotlarini ko'rishini ta'minlaydi.

### 3. Subscription Check

`SubscriptionMiddleware` - markaz bloklanganida admin/manager'dan boshqa hech kim ishlay olmaydi.

## Muammolarni hall qilish

### Muammo: "Middleware ishlamayapti"

**Tekshirish:**

1. `settings.py`'da middleware to'g'ri qo'shilganini tekshiring
2. Server restart qiling: `Ctrl+C` → `python manage.py runserver`
3. Browser cache tozalang: `Ctrl+Shift+Delete`

### Muammo: "Login qilganimda 404 xato"

**Sabab:** `auth_urls.py` file yaratilmagan yoki import xato

**Yechim:**

```python
# accounts/auth_urls.py mavjudligini tekshiring
# accounts/auth_views.py mavjudligini tekshiring
```

### Muammo: "Login infinite loop"

**Sabab:** `LOGIN_URL` va login view conflict qilmoqda

**Yechim:**

```python
# settings.py
LOGIN_URL = "login"  # to'g'ri

# urls.py
path('hisob/login/', ..., name='login')  # name bir xil bo'lishi kerak
```

## Best Practices

### ✅ DO (Qiling):

1. **Har bir yangi sahifa qo'shganingizda** - `role_permissions`'ga qo'shing
2. **View'larda ham permission check** - double protection
3. **Test yozing** - har bir rol uchun alohida
4. **Logs qo'shing** - kim qayerga kirishga uringanini ko'ring

```python
# middleware_rbac.py'ga logging qo'shing:
import logging
logger = logging.getLogger(__name__)

def __call__(self, request):
    # ...
    if not self._has_permission(...):
        logger.warning(
            f"Access denied: {request.user.username} ({user_role}) "
            f"tried to access {full_url_name}"
        )
```

### ❌ DON'T (Qilmang):

1. **Middleware'ni o'chirish** - "tezroq ishlaydi" deb
2. **`role='admin'` hard-code** - user model'dan oling
3. **Blacklisting ishlatish** - faqat whitelist
4. **Exception catch qilib ignore** - xatolarni log qiling

## Performance

**Overhead:** ~0.5-1ms har bir request uchun

**Optimizatsiya:**

1. Static/media file'lar uchun skipla ✅ (qilingan)
2. Admin panel uchun skipla ✅ (qilingan)
3. URL pattern caching (katta loyihalar uchun)

```python
# Agar 10,000+ request/sec bo'lsa:
from functools import lru_cache

@lru_cache(maxsize=128)
def _check_permission_cached(self, role, url_name):
    # Cache permission check results
    pass
```

## Yangilanishlar

Kelajakda qo'shish mumkin bo'lgan feature'lar:

1. **Dynamic permissions** - database'dan o'qish
2. **IP whitelist** - muayyan IP'lardan faqat
3. **Time-based access** - faqat ish vaqtida
4. **Audit logs** - kim qachon qayerga kirgan
5. **Rate limiting** - brute force hujumlarni oldini olish

## Xulosa

Bu 3-qatlamli xavfsizlik arxitekturasi:

1. ✅ **SecureLoginView** - ?next ni ignore qiladi
2. ✅ **RoleBasedAccessMiddleware** - har bir request'ni tekshiradi
3. ✅ **View permissions** - qo'shimcha himoya

**Natija:**
- 🔒 O'quvchi hech qachon admin panelga kira olmaydi
- 🔒 URL injection ishlamaydi
- 🔒 Har bir foydalanuvchi faqat o'z sahifalarida ishlaydi
- 🔒 Xavfsizlik default - ruxsat explicit

**Test qiling va ishlatishdan zavqlaning!** 🚀
