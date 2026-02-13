# 🚀 RENDER SUBDOMAIN - QUICK START GUIDE

**5-MINUTE SETUP CHECKLIST**

---

## 📋 BEFORE YOU START

**Prerequisites:**
- ✅ Domain registered (example: `chaqmoq.uz`)
- ✅ Render.com account (free or paid)
- ✅ Code pushed to GitHub
- ✅ Render web service created

---

## STEP 1: DNS CONFIGURATION (5 min)

Go to your domain registrar (GoDaddy, Namecheap, etc.)

### Add These Records:

```dns
Type    Name    Value                           TTL
----    ----    -----                           ---
A       @       <RENDER_IP>                     3600
CNAME   *       your-app.onrender.com.          3600
```

**Get RENDER_IP:**
```bash
dig your-app.onrender.com +short
# OR: Use the IP Render shows in dashboard
```

**Save and wait** 5-60 minutes.

---

## STEP 2: RENDER DASHBOARD (3 min)

### 1. Add Custom Domain

```
Render Dashboard → Your Service → Settings → Custom Domains
```

**Add TWO domains:**
1. `chaqmoq.uz`
2. `*.chaqmoq.uz`

**Wait for "Verified" ✅** (5-10 min)

### 2. Set Environment Variables

```
Environment tab → Add:

ROOT_DOMAIN=chaqmoq.uz
MODE=production
DJANGO_SETTINGS_MODULE=config.settings_prod
SECRET_KEY=<generate-strong-secret>
```

---

## STEP 3: CODE UPDATES (10 min)

### 1. Replace Middleware

**File:** `config/settings.py`

**FIND:**
```python
MIDDLEWARE = [
    ...
    "core.middleware.TenantMiddleware",
]
```

**REPLACE WITH:**
```python
# Use production middleware in prod
if os.getenv("MODE") == "production":
    MIDDLEWARE = [
        "django.middleware.security.SecurityMiddleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        "core.middleware_prod.TenantMiddleware",  # Production version
    ]
```

### 2. Add Production Settings Import

**File:** `config/settings.py` (bottom)

```python
# Auto-load production settings
if os.getenv("MODE") == "production" or os.getenv("RENDER"):
    from .settings_prod import *
    print("✅ Production settings loaded")
```

### 3. Verify Requirements

**File:** `requirements.txt`

```txt
Django>=4.2
psycopg2-binary  # PostgreSQL
gunicorn         # WSGI server
whitenoise       # Static files
dj-database-url  # Database URL parsing
python-dotenv
```

### 4. Update .gitignore

```gitignore
.env
*.sqlite3
staticfiles/
media/
__pycache__/
*.pyc
.DS_Store
```

---

## STEP 4: DEPLOY (2 min)

```bash
# Commit changes
git add .
git commit -m "Add production subdomain support"
git push origin main

# Render will auto-deploy
# Check logs in Render Dashboard
```

---

## STEP 5: VERIFY (3 min)

### Test URLs:

**1. Root Domain:**
```bash
curl -I https://chaqmoq.uz
# Expected: 200 or 302
```

**2. Known Tenant:**
```bash
curl -I https://everbest.chaqmoq.uz
# Expected: 200
```

**3. Unknown Tenant:**
```bash
curl -I https://fakeslug.chaqmoq.uz
# Expected: 404 (custom page)
```

**4. Browser Test:**
- Open: `https://everbest.chaqmoq.uz`
- Should load tenant dashboard (NOT connection refused)

---

## ❌ TROUBLESHOOTING

### Issue: Still getting ERR_CONNECTION_REFUSED

**Check:**
```bash
# 1. DNS propagated?
dig everbest.chaqmoq.uz +short
# Should return: IP or CNAME

# 2. Render verified?
# Dashboard → Custom Domains → Status should be ✅

# 3. Wait 30 minutes after DNS change
```

### Issue: 404 on all subdomains

**Fix:**
```bash
# Check if centers exist
python manage.py shell
>>> from accounts.models import Center
>>> Center.objects.filter(slug='everbest').exists()
True  # Should be True
```

### Issue: HTTPS not working

**Fix:**
```bash
# Wait 5-10 minutes for Render SSL
# Check Render Dashboard → SSL Certificate status

# Try HTTP first:
curl http://everbest.chaqmoq.uz
```

---

## 🎯 SUCCESS CHECKLIST

After deployment, verify:

- [ ] `https://chaqmoq.uz` loads (platform/home)
- [ ] `https://everbest.chaqmoq.uz` loads tenant dashboard
- [ ] `https://xyz.chaqmoq.uz` shows custom 404 (NOT browser error)
- [ ] Green padlock 🔒 (HTTPS working)
- [ ] Login/logout works
- [ ] Can switch between tenants (if SuperAdmin)

---

## 📞 NEED HELP?

**Common Commands:**

```bash
# Check DNS
dig chaqmoq.uz +short
dig everbest.chaqmoq.uz +short

# Check SSL
openssl s_client -connect chaqmoq.uz:443

# View Render logs
# Render Dashboard → Logs tab

# Test locally
python manage.py runserver
# Visit: http://everbest.localhost:8000
```

**Files Created:**
- `config/settings_prod.py` - Production settings
- `core/middleware_prod.py` - Production middleware
- `.gemini/RENDER_SUBDOMAIN_DEPLOYMENT.md` - Full guide

---

## 🚀 GO LIVE!

Once everything works:

1. Point users to: `https://<their-slug>.chaqmoq.uz`
2. Monitor Render logs for errors
3. Set up monitoring (Sentry, etc.)

**Estimated Total Time:** 20-30 minutes (+ DNS wait)

---

**DONE!** 🎉
