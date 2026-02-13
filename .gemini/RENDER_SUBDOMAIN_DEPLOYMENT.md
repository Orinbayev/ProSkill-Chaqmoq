# 🚀 RENDER SUBDOMAIN DEPLOYMENT - COMPLETE GUIDE

**Date:** 2026-02-13  
**Goal:** 100% working subdomains in production (Render.com)

---

## 🎯 ARCHITECTURE OVERVIEW

```
LOCAL:
✅ everbest.localhost:8000  → Tenant: everbest
✅ localhost:8000            → Root/Platform

PRODUCTION (TARGET):
✅ everbest.chaqmoq.uz       → Tenant: everbest
✅ proskill.chaqmoq.uz       → Tenant: proskill
✅ chaqmoq.uz                → Root/Platform
✅ *.chaqmoq.uz              → Any tenant
```

---

## 📝 CHECKLIST

### Phase 1: DNS Configuration (Domain Provider)
- [ ] Add A record for root domain
- [ ] Add wildcard CNAME for subdomains
- [ ] Verify DNS propagation (24-48 hours max)

### Phase 2: Render.com Configuration
- [ ] Add custom domain: chaqmoq.uz
- [ ] Add wildcard domain: *.chaqmoq.uz
- [ ] Enable HTTPS/TLS (auto wildcard cert)
- [ ] Wait for DNS verification

### Phase 3: Django Settings (Production)
- [ ] Update ALLOWED_HOSTS
- [ ] Configure CSRF_TRUSTED_ORIGINS
- [ ] Set SESSION_COOKIE_DOMAIN
- [ ] Enable SSL/HTTPS settings
- [ ] Add USE_X_FORWARDED_HOST

### Phase 4: Middleware Updates
- [ ] Fix host parsing for production
- [ ] Handle Render.com subdomain
- [ ] Test fallback logic

### Phase 5: Testing
- [ ] Test root domain
- [ ] Test known tenant subdomain
- [ ] Test 404 for unknown subdomain
- [ ] Test localhost (dev)

---

## 1️⃣ DNS CONFIGURATION

### Prerequisites:
- Domain: `chaqmoq.uz` (example)
- Render service URL: `your-app.onrender.com`

### DNS Records (at your domain registrar):

#### Option A: If your provider supports ALIAS/ANAME (Cloudflare, DNSimple)

```dns
# Root domain
@   ALIAS   your-app.onrender.com.   TTL 3600

# Wildcard subdomains
*   CNAME   your-app.onrender.com.   TTL 3600
```

#### Option B: If only A records allowed (traditional DNS)

```dns
# Root domain - use Render's A record IP
# Get IP from: dig your-app.onrender.com
@   A       123.456.789.10   TTL 3600

# Wildcard
*   CNAME   your-app.onrender.com.   TTL 3600
```

### Verification:

```bash
# Check root
dig chaqmoq.uz +short
# Expected: IP or CNAME to render

# Check wildcard
dig random.chaqmoq.uz +short
# Expected: IP or CNAME to render

# Check specific tenant
dig everbest.chaqmoq.uz +short
# Expected: Same as wildcard
```

**⏱️ Wait Time:** 5 minutes - 48 hours (usually <1 hour with low TTL)

---

## 2️⃣ RENDER.COM CONFIGURATION

### Step-by-Step in Render Dashboard:

#### 1. Navigate to Your Web Service

```
Dashboard → Your Service → Settings → Custom Domains
```

#### 2. Add Root Domain

```
Click "Add Custom Domain"
Enter: chaqmoq.uz
```

**Render will show DNS instructions:**
```
CNAME: <your-app>.onrender.com
or
A Record: <IP>
```

**Status:** Wait until "Verified" ✅

#### 3. Add Wildcard Domain

```
Click "Add Custom Domain"
Enter: *.chaqmoq.uz
```

**Important Notes:**
- ⚠️ Render FREE tier does NOT support wildcard SSL
- ✅ **Starter tier ($7/mo)** or higher: wildcard SSL included
- Alternative: Use Cloudflare for free wildcard SSL (see below)

**Status:** Wait until "Verified" ✅

#### 4. HTTPS/TLS Configuration

```
Render auto-provisions Let's Encrypt certificates
✅ chaqmoq.uz → SSL cert
✅ *.chaqmoq.uz → Wildcard SSL cert
```

**Verification:**
```bash
curl -I https://chaqmoq.uz
# Expected: HTTP/2 200 (or 301 redirect)

curl -I https://everbest.chaqmoq.uz
# Expected: HTTP/2 200
```

---

## 3️⃣ ALTERNATIVE: CLOUDFLARE PROXY (FREE WILDCARD SSL)

If Render free tier doesn't support wildcard SSL:

### Setup:

1. **Move DNS to Cloudflare** (free plan)
2. **DNS Records in Cloudflare:**

```dns
# Proxied through Cloudflare (orange cloud ☁️)
@   CNAME   your-app.onrender.com   Proxied ✅
*   CNAME   your-app.onrender.com   Proxied ✅
```

3. **Cloudflare SSL Mode:** Full (strict)

**Benefits:**
- ✅ Free wildcard SSL
- ✅ CDN caching
- ✅ DDoS protection
- ✅ Faster DNS propagation

---

## 4️⃣ DJANGO SETTINGS.PY (PRODUCTION)

### Current Issues:

Your settings likely have:
```python
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".localhost", "*"]
```

This works locally but NOT in production.

### ✅ PRODUCTION FIX:

Create or update `config/settings_prod.py`:

```python
# config/settings_prod.py
import os
from .settings import *

# ==================== PRODUCTION OVERRIDES ====================

DEBUG = False

# Your actual domain
ROOT_DOMAIN = os.getenv("ROOT_DOMAIN", "chaqmoq.uz")
RENDER_SERVICE = os.getenv("RENDER_EXTERNAL_URL", "").replace("https://", "").replace("http://", "")

# ✅ ALLOWED_HOSTS - Strict security
ALLOWED_HOSTS = [
    ROOT_DOMAIN,                    # chaqmoq.uz
    f".{ROOT_DOMAIN}",              # *.chaqmoq.uz (wildcard)
    RENDER_SERVICE,                 # your-app.onrender.com
    "localhost",                    # local testing
    "127.0.0.1",
]

# ✅ CSRF Protection
CSRF_TRUSTED_ORIGINS = [
    f"https://{ROOT_DOMAIN}",
    f"https://*.{ROOT_DOMAIN}",     # Wildcard notation
    f"https://{RENDER_SERVICE}",
]

# ✅ Cookie Domain
# Option 1: Shared sessions across subdomains (SSO)
# SESSION_COOKIE_DOMAIN = f".{ROOT_DOMAIN}"  # .chaqmoq.uz
# CSRF_COOKIE_DOMAIN = f".{ROOT_DOMAIN}"

# Option 2: Isolated sessions per subdomain (RECOMMENDED for multi-tenant)
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None

# ✅ Security Headers
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Force HTTPS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# HSTS (only after confirming HTTPS works)
# SECURE_HSTS_SECONDS = 31536000  # 1 year
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True

# ==================== STATIC/MEDIA ====================
# Render static files serving
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media files (use S3/Cloudinary in production)
# MEDIA_URL = "https://your-bucket.s3.amazonaws.com/media/"
```

### Environment Variables on Render:

```bash
# In Render Dashboard → Environment
ROOT_DOMAIN=chaqmoq.uz
MODE=production
DJANGO_SETTINGS_MODULE=config.settings_prod
```

---

## 5️⃣ MIDDLEWARE FIX (HOST PARSING)

### Current Code Analysis:

Your `core/middleware.py` has localhost logic but needs production fixes.

### ✅ UPDATED MIDDLEWARE:

```python
# core/middleware.py
from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden, Http404
from django.conf import settings
from accounts.models import Center
import logging

logger = logging.getLogger(__name__)

class TenantMiddleware:
    """
    Multi-tenant middleware with production-ready subdomain parsing
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ✅ Get clean host (remove port)
        host_port = request.get_host()
        host = host_port.split(':')[0].lower()
        
        # Parse port
        port = None
        if ':' in host_port:
            try:
                port = host_port.split(':')[1]
            except IndexError:
                pass

        subdomain = None
        root_domain = getattr(settings, 'ROOT_DOMAIN', 'localhost')
        
        # ==================== SUBDOMAIN PARSING ====================
        
        # 1. Localhost (Development)
        if "localhost" in host or host in ["127.0.0.1", "0.0.0.0"]:
            # Local: everbest.localhost or everbest.localhost:8000
            parts = host.split('.')
            if len(parts) > 1 and parts[0] not in ["www", "localhost"]:
                subdomain = parts[0]
            root_domain = "localhost"
        
        # 2. Render.com direct URL (fallback)
        elif "onrender.com" in host:
            # your-app.onrender.com or subdomain-your-app.onrender.com
            # Treat as root (no tenant)
            # OR: parse if using <tenant>-<app>.onrender.com pattern
            parts = host.split('-')
            if len(parts) > 1 and not parts[0] == request.META.get('HTTP_HOST', '').split('.')[0]:
                subdomain = parts[0]  # Optional: tenant-app.onrender.com
            root_domain = host
        
        # 3. Production Domain (chaqmoq.uz)
        else:
            # Real domain: everbest.chaqmoq.uz or chaqmoq.uz
            parts = host.split('.')
            
            # Determine root domain from settings or auto-detect
            # Assuming root_domain = "chaqmoq.uz" (2 parts)
            root_parts = root_domain.split('.')
            root_part_count = len(root_parts)
            
            if len(parts) > root_part_count:
                # everbest.chaqmoq.uz → subdomain = "everbest"
                subdomain = parts[0]
                root_domain = ".".join(parts[1:])
            else:
                # chaqmoq.uz → no subdomain
                root_domain = host
        
        # ==================== TENANT RESOLUTION ====================
        
        request.active_center = None
        request.center = None
        
        if subdomain:
            # Try finding center by slug
            center = Center.objects.filter(
                slug=subdomain,
                is_deleted=False
            ).first()
            
            if not center:
                # ✅ Tenant not found → Show 404 (NOT connection refused)
                # Exempt static/media
                if request.path.startswith('/static/') or request.path.startswith('/media/'):
                    return self.get_response(request)
                
                # Superadmin → redirect to platform
                if request.user.is_authenticated and request.user.is_superuser:
                    scheme = request.scheme
                    port_str = f":{port}" if port and port != '443' else ""
                    return redirect(f"{scheme}://{root_domain}{port_str}/platform/centers/")
                
                # Regular user → 404
                return render(request, 'core/center_404.html', {
                    'subdomain': subdomain,
                    'root_domain': root_domain,
                    'host': host_port
                }, status=404)
            
            # Tenant found
            request.active_center = center
            request.center = center
        
        # Fallback: Session-based center (for Render.com direct URL)
        if not request.center:
            active_id = request.session.get("active_center_id")
            if active_id:
                c = Center.objects.filter(id=active_id, is_deleted=False).first()
                if c:
                    request.active_center = c
                    request.center = c
        
        # ==================== ACCESS CONTROL ====================
        
        # Exempt paths
        EXEMPT_PREFIXES = (
            '/hisob/login/',
            '/login/',
            '/logout/',
            '/static/',
            '/media/',
            '/admin/',
            '/platform/',
            '/favicon.ico',
        )
        
        if any(request.path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return self.get_response(request)
        
        # User access logic
        if request.user.is_authenticated:
            if request.user.is_superuser:
                pass  # Superadmin can access anything
            
            elif request.user.center:
                # Regular user: enforce tenant isolation
                if request.active_center and request.active_center != request.user.center:
                    return HttpResponseForbidden(
                        f"Sizga '{request.active_center.name}' markaziga kirish ruxsat etilmagan."
                    )
                
                # Blocked check
                if request.active_center and request.active_center.status == 'BLOCKED':
                    if not request.path.startswith('/hisob/billing/'):
                        return redirect('billing:plans')
            
            else:
                # Orphan user (no center)
                return HttpResponseForbidden("Siz hech qanday markazga biriktirilmagansiz.")
        
        else:
            # Unauthenticated → redirect to login
            login_url = settings.LOGIN_URL
            return redirect(f"{login_url}?next={request.path}")
        
        return self.get_response(request)
```

---

## 6️⃣ ENVIRONMENT DETECTION

Update `config/__init__.py` or use:

```python
# config/settings.py (bottom)

# Auto-detect production
if os.getenv("MODE") == "production" or os.getenv("RENDER"):
    from .settings_prod import *
```

---

## 7️⃣ RENDER DEPLOYMENT

### Build Command:
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

### Start Command:
```bash
gunicorn config.wsgi:application
```

### Environment Variables:
```
MODE=production
ROOT_DOMAIN=chaqmoq.uz
DJANGO_SETTINGS_MODULE=config.settings_prod
SECRET_KEY=<your-secret>
DATABASE_URL=<postgres-url>
```

---

## 🧪 TESTING PLAN

### 1. Root Domain Test
```bash
curl -I https://chaqmoq.uz
# Expected: 200 OK or 30x redirect to /platform/
```

### 2. Known Tenant Test
```bash
curl -I https://everbest.chaqmoq.uz
# Expected: 200 OK (tenant dashboard)
```

### 3. Unknown Tenant Test
```bash
curl -I https://fakeslug.chaqmoq.uz
# Expected: 404 with custom page (NOT connection refused)
```

### 4. Localhost Test
```bash
# Start local server
python manage.py runserver

# Test
curl http://everbest.localhost:8000
# Expected: Tenant dashboard
```

---

## 🚨 TROUBLESHOOTING

### Issue: "ERR_CONNECTION_REFUSED"

**Cause:** DNS not propagated or Render domain not verified

**Fix:**
1. Check DNS: `dig everbest.chaqmoq.uz`
2. Verify Render dashboard shows ✅ Verified
3. Wait 5-60 minutes for propagation

### Issue: "This site can't provide a secure connection"

**Cause:** SSL cert not provisioned

**Fix:**
1. Wait for Render SSL (5-10 min)
2. Check Render dashboard → SSL Status
3. Try HTTP first: `http://everbest.chaqmoq.uz`

### Issue: 404 on all subdomains

**Cause:** Middleware not finding tenants

**Fix:**
1. Check `Center.objects.filter(slug='everbest')` exists
2. Verify `is_deleted=False`
3. Add logging to middleware

### Issue: CSRF verification failed

**Cause:** `CSRF_TRUSTED_ORIGINS` mismatch

**Fix:**
```python
CSRF_TRUSTED_ORIGINS = [
    "https://chaqmoq.uz",
    "https://*.chaqmoq.uz",  # Must have wildcard
]
```

---

## ✅ FINAL CHECKLIST

Before going live:

- [ ] DNS records added (A + wildcard CNAME)
- [ ] DNS propagated (check with dig/nslookup)
- [ ] Render custom domains verified (chaqmoq.uz + *.chaqmoq.uz)
- [ ] Render SSL active (Let's Encrypt)
- [ ] `settings_prod.py` configured
- [ ] `ROOT_DOMAIN` env var set on Render
- [ ] Middleware updated
- [ ] `ALLOWED_HOSTS` correct
- [ ] Test: root domain loads
- [ ] Test: tenant subdomain loads
- [ ] Test: 404 for unknown subdomain
- [ ] Test: login/logout works
- [ ] Test: HTTPS enforced

---

## 📊 EXPECTED TIMELINE

| Task | Time |
|------|------|
| DNS configuration | 5 min |
| DNS propagation | 5 min - 48 hrs |
| Render setup | 10 min |
| Render SSL provision | 5 min |
| Code updates | 30 min |
| Testing | 15 min |
| **TOTAL** | **1-2 hours active work** |

DNS wait time is passive - you can work on code meanwhile.

---

## 🎯 SUCCESS CRITERIA

✅ `https://chaqmoq.uz` → Platform/Center picker  
✅ `https://everbest.chaqmoq.uz` → Everbest center dashboard  
✅ `https://proskill.chaqmoq.uz` → ProSkill center dashboard  
✅ `https://notfound.chaqmoq.uz` → Custom 404 page  
✅ All with HTTPS (green padlock 🔒)  
✅ No "connection refused" errors  
✅ Fast load times (<2s)

---

**END OF GUIDE**
