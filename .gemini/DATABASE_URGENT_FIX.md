# 🚨 RENDER DATABASE SETUP - URGENT FIX

**Issue:** Users can't login because database resets on every deploy
**Cause:** No PostgreSQL configured, using SQLite (ephemeral)
**Solution:** Add PostgreSQL database to Render

---

## 🎯 IMMEDIATE ACTION REQUIRED

### **STEP 1: Create PostgreSQL Database on Render**

1. **Go to:** https://dashboard.render.com

2. **Click:** "New +" (top right)

3. **Select:** "PostgreSQL"

4. **Configure:**
   ```
   Name: proskill-db
   Database: chaqmoq_academy
   User: chaqmoq_user
   Region: Frankfurt (same as web service)
   Plan: FREE
   ```

5. **Click:** "Create Database"

6. **Wait:** 2-3 minutes for provisioning

---

### **STEP 2: Connect Database to Web Service**

1. **Go to:** Dashboard → PostgreSQL → proskill-db

2. **Copy:** "Internal Database URL" (starts with `postgres://`)
   ```
   Example:
   postgres://chaqmoq_user:password@dpg-xxxxx/chaqmoq_academy
   ```

3. **Go to:** Dashboard → Web Service (ProSkill-Chaqmoq)

4. **Navigate to:** Environment tab

5. **Add Environment Variable:**
   ```
   Key: DATABASE_URL
   Value: <paste the Internal Database URL>
   ```

6. **Click:** "Save Changes"

---

### **STEP 3: Re-deploy**

Deploy will auto-trigger. Watch logs:

```log
==> Running migrations
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying accounts.0001_initial... OK
  ...
  
==> Migrations completed successfully
```

---

### **STEP 4: Create Superuser**

After deploy succeeds:

1. **Go to:** Dashboard → ProSkill-Chaqmoq → Shell

2. **Click:** "Shell" tab

3. **Run these commands:**

```bash
python manage.py createsuperuser
```

**Enter:**
```
Email: amirxondev@gmail.com
Password: <your-password>
Password (again): <your-password>
```

**Success:**
```
Superuser created successfully.
```

---

### **STEP 5: Verify Login**

1. **Open:** https://proskill-chaqmoq.onrender.com/hisob/login/

2. **Login with:**
   ```
   Email: amirxondev@gmail.com
   Password: <your-password>
   ```

3. **Should work!** ✅

---

## 🔧 ALTERNATIVE: Quick Render Setup Via Dashboard

**If Render has auto-PostgreSQL:**

1. Dashboard → PostgreSQL → "Add PostgreSQL"
2. Render will auto-create and link it
3. Redeploy
4. Create superuser in Shell

---

## ⚠️ WHY THIS HAPPENED

**Your current setup:**

```python
# settings.py
if "DATABASE_URL" in os.environ:
    # Use PostgreSQL
    DATABASES = {...}
else:
    # Use SQLite (EPHEMERAL!)
    DATABASES = {"default": {"ENGINE": "sqlite3", ...}}
```

**Problem:**
- No `DATABASE_URL` in Render environment
- Falls back to SQLite
- SQLite file is **temporary** on Render
- Each deploy = new container = **new SQLite** = **data lost!**

---

## ✅ AFTER FIX

**With PostgreSQL:**
```
Deploy → PostgreSQL persists → Users remain → Login works! ✅
```

---

## 📋 QUICK CHECKLIST

- [ ] Create PostgreSQL on Render
- [ ] Copy DATABASE_URL
- [ ] Add to Environment variables
- [ ] Wait for auto-redeploy
- [ ] Run migrations (auto)
- [ ] Create superuser in Shell
- [ ] Test login

**ETA:** 10 minutes

---

## 🚨 IF YOU NEED DATA BACK

**If you have local data:**

1. **Export from local:**
   ```bash
   python manage.py dumpdata > backup.json
   ```

2. **After Render PostgreSQL setup:**
   ```bash
   # In Render Shell:
   python manage.py loaddata backup.json
   ```

---

**STATUS:** 🔴 CRITICAL - Database not persistent  
**ACTION:** Follow steps above NOW  
**RESULT:** Login will work after PostgreSQL setup

---

**NEXT:** Report back when PostgreSQL is created!
