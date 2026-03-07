# ✅ RENDER PRODUCTION DEPLOYMENT - FINAL CHECKLIST

**Project:** ChaqmoqApp Multi-Tenant SaaS  
**Date:** 2026-02-13  
**Status:** ✅ CODE READY - AWAITING DEPLOYMENT

---

## 📋 PRE-DEPLOYMENT CHECKLIST

### ✅ Code Changes (COMPLETED)

- [x] Created `config/settings_prod.py` - Production settings
- [x] Created `core/middleware_prod.py` - Production middleware
- [x] Modified `config/settings.py` - Auto-load production config
- [x] Updated `requirements.txt` - Added `dj-database-url`
- [x] Created deployment documentation (3 guides)
- [x] Generated architecture diagram

### ⏳ DNS Configuration (TO DO)

**Domain:** `chaqmoq.uz` (your actual domain)

**Go to:** Your domain registrar (GoDaddy, Namecheap, etc.)

**Add these DNS records:**

```dns
Type    Name    Value                           TTL     Status
----    ----    -----                           ---     ------
A       @       <GET_FROM_RENDER_DASHBOARD>     3600    [ ]
CNAME   *       your-app.onrender.com.          3600    [ ]
```

**How to get values:**

1. **Render IP (for A record):**
   - Option A: Render Dashboard → Custom Domains → Shows IP
   - Option B: Run: `dig your-app.onrender.com +short`

2. **Render service URL:**
   - Your app URL in Render (ends with `.onrender.com`)

**Verification Command:**
```bash
# After adding DNS records, wait 5-30 min, then:
dig chaqmoq.uz +short          # Should return IP
dig test.chaqmoq.uz +short     # Should return IP or CNAME
```

---

### ⏳ Render.com Configuration (TO DO)

**Login to:** https://render.com

#### Step 1: Add Custom Domains

Navigate: `Dashboard → Your Service → Settings → Custom Domains`

**Click "Add Custom Domain"** and enter:

1. **Root domain:**
   ```
   chaqmoq.uz
   ```
   Status: Wait for ✅ Verified

2. **Wildcard subdomain:**
   ```
   *.chaqmoq.uz
   ```
   Status: Wait for ✅ Verified

**Note:** 
- Free tier may NOT support wildcard SSL
- Use **Starter tier ($7/mo)** or Cloudflare proxy for wildcard SSL

#### Step 2: Set Environment Variables

Navigate: `Dashboard → Your Service → Environment`

**Add these variables:**

```env
NAME                        VALUE
----                        -----
ROOT_DOMAIN                 chaqmoq.uz
MODE                        production
SECRET_KEY                  <GENERATE_NEW_SECRET>
DJANGO_SETTINGS_MODULE      config.settings_prod
```

**Generate SECRET_KEY:**
```python
# Run locally:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Other variables** (auto-set by Render):
- `DATABASE_URL` - PostgreSQL connection string
- `RENDER` - `true`
- `RENDER_EXTERNAL_URL` - Your app URL

#### Step 3: Verify Build Settings

Navigate: `Dashboard → Your Service → Settings`

**Build Command:**
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

**Start Command:**
```bash
gunicorn config.wsgi:application
```

**Region:** Choose closest to users (e.g., Frankfurt for Europe/Asia)

---

### ⏳ Code Deployment (TO DO)

**Commit and push:**

```bash
cd c:\Users\user\Desktop\chaqmoq_academy

# Check status
git status

# Add all changes
git add .

# Commit
git commit -m "Add Render production subdomain support

- Production settings with ALLOWED_HOSTS wildcard
- Production middleware with robust subdomain parsing
- Auto-detect production environment
- Added dj-database-url dependency
- Full deployment documentation"

# Push to main
git push origin main
```

**Watch deployment:**
- Go to Render Dashboard → **Logs** tab
- Wait for: `Deploy live` message
- Should see: `✅ Production settings loaded successfully`

**Estimated time:** 5-10 minutes

---

## 🧪 POST-DEPLOYMENT TESTING

### Test 1: Root Domain

```bash
curl -I https://chaqmoq.uz
```

**Expected:**
```
HTTP/2 200 
# OR
HTTP/2 302  (redirect to platform)
```

**Browser:** 
- Open: `https://chaqmoq.uz`
- Should show: Platform homepage or center picker

---

### Test 2: Known Tenant (everbest)

```bash
curl -I https://everbest.chaqmoq.uz
```

**Expected:**
```
HTTP/2 200
```

**Browser:**
- Open: `https://everbest.chaqmoq.uz`
- Should show: Everbest center dashboard
- **NOT:** "ERR_CONNECTION_REFUSED"

---

### Test 3: Another Tenant (proskill)

```bash
curl -I https://proskill.chaqmoq.uz
```

**Expected:**
```
HTTP/2 200
```

**Browser:**
- Open: `https://proskill.chaqmoq.uz`
- Should show: ProSkill center dashboard

---

### Test 4: Non-Existent Tenant (404)

```bash
curl -I https://fakeslug.chaqmoq.uz
```

**Expected:**
```
HTTP/2 404
```

**Browser:**
- Open: `https://fakeslug.chaqmoq.uz`
- Should show: Custom 404 page ("Markaz topilmadi")
- **NOT:** Browser connection error

---

### Test 5: HTTPS Security

**Browser check:**
- All URLs should have 🔒 green padlock
- Click padlock → Certificate valid
- Issued by: Let's Encrypt

**Command line:**
```bash
openssl s_client -connect chaqmoq.uz:443
# Should show valid certificate
```

---

### Test 6: Login/Logout

1. Go to: `https://everbest.chaqmoq.uz`
2. Login with director credentials
3. Should access dashboard
4. Logout
5. Should redirect to login page

**No errors during this flow**

---

### Test 7: Tenant Isolation

1. Login as director of **everbest**
2. Try accessing: `https://proskill.chaqmoq.uz`
3. **Expected:** 403 Forbidden ("Sizga kirish ruxsat etilmagan")

**Security verified** ✅

---

### Test 8: SuperAdmin Access

1. Login as SuperAdmin
2. Go to: `https://chaqmoq.uz/platform/centers/`
3. Should see: List of all centers
4. Click center card
5. Should access tenant dashboard

---

## 🚨 TROUBLESHOOTING

### Issue: DNS Not Working

**Symptoms:**
```bash
dig chaqmoq.uz
# Returns: empty or wrong value
```

**Solutions:**
1. **Wait longer:** DNS can take up to 48 hours (usually <1 hour)
2. **Check TTL:** Lower TTL = faster propagation
3. **Clear cache:**
   ```bash
   # Windows
   ipconfig /flushdns
   
   # Mac/Linux
   sudo dscacheutil -flushcache
   ```
4. **Use online tool:** https://dnschecker.org

---

### Issue: Render Domain Not Verified

**Symptoms:**
Render dashboard shows "Pending" or "Verification Failed"

**Solutions:**
1. **Wait 10-30 minutes** after DNS change
2. **Check DNS records** match Render instructions EXACTLY
3. **Click "Retry Verification"** in Render dashboard
4. **Check for typos:** Ensure no extra spaces, correct domain

---

### Issue: 500 Internal Server Error

**Symptoms:**
All pages show 500 error

**Solutions:**
1. **Check Render logs:**
   ```
   Dashboard → Logs tab
   Look for Python errors
   ```

2. **Common causes:**
   - `SECRET_KEY` missing
   - Database migration failed
   - Static files not collected

3. **Fix migrations:**
   ```bash
   # In Render shell (Dashboard → Shell)
   python manage.py migrate
   ```

---

### Issue: Static Files Not Loading (CSS/JS missing)

**Symptoms:**
Page loads but no styling

**Solutions:**
1. **Verify WhiteNoise** in `MIDDLEWARE`
2. **Check build logs** for `collectstatic` success
3. **Run manually:**
   ```bash
   # In Render shell
   python manage.py collectstatic --noinput
   ```

---

### Issue: Database Connection Error

**Symptoms:**
"Could not connect to database"

**Solutions:**
1. **Check `DATABASE_URL`** env var exists in Render
2. **Verify PostgreSQL** instance is running
3. **Check connection limit** (free tier: 97 connections)

---

### Issue: CSRF Verification Failed

**Symptoms:**
Forms don't submit, CSRF error

**Solutions:**
1. **Check `CSRF_TRUSTED_ORIGINS`** includes your domain:
   ```python
   CSRF_TRUSTED_ORIGINS = [
       "https://chaqmoq.uz",
       "https://*.chaqmoq.uz",
   ]
   ```

2. **Update settings_prod.py** if needed

3. **Redeploy**

---

## 📊 SUCCESS CRITERIA

Mark as complete when ALL tests pass:

- [ ] `https://chaqmoq.uz` loads (200 or 302)
- [ ] `https://everbest.chaqmoq.uz` loads tenant dashboard (200)
- [ ] `https://fakeslug.chaqmoq.uz` shows 404 (not connection error)
- [ ] HTTPS green padlock visible on all URLs
- [ ] Login/logout works correctly
- [ ] Tenant isolation enforced (403 for wrong tenant)
- [ ] SuperAdmin can access all tenants
- [ ] Static files load (CSS, JS, images)
- [ ] No errors in Render logs
- [ ] DNS propagated globally (check https://dnschecker.org)

---

## 📁 DOCUMENTATION FILES

All documentation in `.gemini/` folder:

1. **`RENDER_FINAL_SUMMARY.md`** - This file (checklist + troubleshooting)
2. **`RENDER_SUBDOMAIN_DEPLOYMENT.md`** - Complete technical guide
3. **`QUICK_START_RENDER.md`** - 5-step quick setup
4. **Architecture Diagram** - Visual flow chart

---

## 🔄 ROLLBACK PLAN

If production fails:

### Option 1: Disable Production Settings

**In Render Environment:**
```
Remove: MODE=production
```

**Redeploy** - will use base settings.py

### Option 2: Emergency Fix

```bash
# Quick fix in settings_prod.py
DEBUG = True  # Temporarily for debugging
ALLOWED_HOSTS = ["*"]  # Allow all (NOT for long-term!)
```

**Push and redeploy**

### Option 3: Full Rollback

```bash
git revert HEAD
git push origin main
```

---

## 🎯 EXPECTED TIMELINE

| Task | Time |
|------|------|
| DNS setup | 5 min |
| DNS propagation | 5 min - 48 hrs* |
| Render config | 5 min |
| Code deployment | 5 min |
| Render build | 5-10 min |
| SSL provisioning | 5 min |
| Testing | 10 min |
| **TOTAL ACTIVE WORK** | **30-40 min** |

*DNS usually propagates in 5-60 minutes despite 48hr max

---

## ✅ FINAL VALIDATION

Before marking as "DONE":

```bash
# Run all these commands and verify output:

# 1. DNS check
dig chaqmoq.uz +short
dig everbest.chaqmoq.uz +short

# 2. HTTP checks
curl -I https://chaqmoq.uz
curl -I https://everbest.chaqmoq.uz
curl -I https://fakeslug.chaqmoq.uz

# 3. SSL check
echo | openssl s_client -connect chaqmoq.uz:443 2>/dev/null | grep -i "verify return code"
# Should show: verify return code: 0 (ok)
```

**All should return expected values**

---

## 🚀 GO LIVE PROCEDURE

1. **[DONE]** Code changes committed
2. **[TODO]** DNS records added
3. **[TODO]** Render custom domains configured
4. **[TODO]** Environment variables set
5. **[TODO]** Code deployed to Render
6. **[TODO]** DNS propagation verified
7. **[TODO]** SSL certificate active
8. **[TODO]** All 8 tests passed
9. **[FINAL]** Announce to users: Use `https://<slug>.chaqmoq.uz`

---

## 📞 SUPPORT

If issues persist after following troubleshooting:

1. **Check Render Status:** https://status.render.com
2. **View Render logs:** Dashboard → Logs (errors in red)
3. **Review Django errors:** Look for Python traceback
4. **Check settings:** Ensure all env vars set correctly

---

**Status:** ✅ **READY FOR PRODUCTION DEPLOYMENT**

**Next Action:** Follow "DNS Configuration" section above

---

**END OF CHECKLIST**
