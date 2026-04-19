# RESTORE GUIDE — ChaqmoqApp Backup'dan tiklash bo'yicha to'liq qo'llanma

> Bu hujjat **xotirjam paytda** o'qib, **panik paytda** qadam-baqadam bajarish uchun.
> Oldin tinch paytda **bir marta sinab ko'r** — keyin kerak bo'lganda qo'rqmaysan.

---

## 0. Backup'lar qayerda?

Ikki mustaqil joyda:

| Manzil | Qanday tushadi | Nima uchun kerak |
|---|---|---|
| **Telegram guruh** | Har kuni 17:35 (Asia/Tashkent) | Tez kirish, tarixga qarash |
| **Google Drive** | Har kuni 17:35 (Telegram'dan keyin) | Telegram bloklansa ham qoladi |

**Fayl turlari (har kun):**
- `<slug>_YYYY-MM-DD.json` — har markaz alohida (markazga tegishli qismi)
- `postgres_full_YYYY-MM-DD.sql` — butun DB (barcha markazlar + Django tizim jadvallar)

Drive ichida tartib: `ChaqmoqApp Backups / 2026-04 / 2026-04-19 / <fayllar>`

---

## 1. BIRINCHI SOZLASH — Google Drive'ga ulash (bir martalik)

### 1.1 Google Cloud tomonida

1. https://console.cloud.google.com → **New Project** → nom: `chaqmoqapp-backups`
2. **APIs & Services → Library** → `Google Drive API` qidirib **Enable**
3. **IAM & Admin → Service Accounts → Create Service Account**
   - Nom: `chaqmoqapp-backup-bot`
   - Rol tanlamay Done
4. Yaratilgan service account'ga bos → **Keys → Add Key → Create new key → JSON** → Create
   - JSON fayl yuklanadi — bu senga login parol o'rnini bosadi, **yo'qotma**

### 1.2 Google Drive tomonida

1. https://drive.google.com → **New → Folder** → `ChaqmoqApp Backups`
2. Papkani o'ng tomon → **Share**
3. JSON fayldagi `"client_email"` qiymatini qo'yasan (masalan: `chaqmoqapp-backup-bot@chaqmoqapp-backups.iam.gserviceaccount.com`)
4. Ruxsat: **Editor** → Share (email yubormaslik mumkin)
5. Papkani ochasan, URL'dan ID olasan:
   ```
   https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz_123
                                          └────────── bu yer ID ─────────┘
   ```

### 1.3 Render env vars

Render Dashboard → chaqmoqapp servis → **Environment** → Add:

| Key | Value |
|---|---|
| `GDRIVE_FOLDER_ID` | yuqoridagi papka ID |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | JSON faylning **butun ichini** bitta qatorga (qo'shtirnoqlar, \\n'lar hammasi saqlansin) |

> JSON'ni qanday yopishtirish: fayl ichini butun kop'yalab Render oynasiga qo'yasan. Render saqlaydi. **Tahrir qilma.**

### 1.4 Tekshirish

Render Shell ochib:
```bash
python manage.py test_gdrive_upload
```
Muvaffaqiyat bo'lsa Drive papkasida `_test/gdrive_test_*.txt` paydo bo'ladi. Xato bo'lsa — sabab chiqadi, aylanib tekshir.

---

## 2. TIKLASH — 3 xil holat

### ⚠️ UMUMIY QOIDALAR (har tiklashdan OLDIN)

1. **Xotirjam bo'l.** Xatolarning 50%i panikdan kelib chiqadi.
2. **Hozirgi DB'ni yana backup qilib ol!** Tiklash = ustiga yozish. Agar noto'g'ri tiklasang — qaytarmoqchi bo'lgan holat ham yo'qoladi:
   ```bash
   # Render Shell
   pg_dump $DATABASE_URL > /tmp/pre_restore_$(date +%Y%m%d_%H%M%S).sql
   ```
3. **Staging'da sinab ko'r**, prod'ga tegmay turib. Agar staging yo'q bo'lsa — vaqtincha yangi Render Postgres yaratib shunga tiklab ko'r.
4. **Foydalanuvchilarga ogohlantir** — "10-30 daqiqa texnik ishlar" deb yoz.

---

### HOLAT A — Bitta markazning bir qismi yo'qolgan/buzilgan

**Belgilari:** bitta markaz direktori "talabalarim yo'qolgan" / "ro'yxatdan o'chib ketgan" deydi. Ikkinchi markazda hammasi joyida.

**Qancha vaqt oladi:** 5-10 daqiqa

**Qadamlar:**

1. Telegram guruhdan (yoki Drive'dan) o'sha markazning kerakli kundagi JSON'ini yuklab ol. Masalan: `teacherowski_2026-04-18.json`

2. Faylni Render servisga uzatish — ikki usul:
   - **Oson yo'l:** Drive link'ini `wget` qilish (agar public link bo'lsa), yoki `curl`.
   - **Aniq yo'l:** mahalliy kompyuterda `render ssh` orqali yuklash yoki `scp`. Yoki — Render Shell'da `python manage.py shell` orqali URL fetch.

3. Render Shell:
   ```bash
   # 1. Avval DRY-RUN — hech narsa yozilmaydi, faqat ko'radi
   python manage.py restore_center_backup /tmp/teacherowski_2026-04-18.json \
       --center-slug teacherowski

   # 2. Ro'yxatni ko'r: nechta model, nechta obyekt tiklanadi?
   # Hammasi to'g'ri bo'lsa:

   # 3. Haqiqiy tiklash (--apply bilan)
   python manage.py restore_center_backup /tmp/teacherowski_2026-04-18.json \
       --center-slug teacherowski \
       --apply
   ```

4. Tiklanganidan keyin tekshirish:
   - Saytda o'sha markazga kirib talabalar / to'lovlar ko'rinmoqdami?
   - Ikkinchi markazga TEGILMAGANIni tekshir (uning talabalari eski joyida qolgan bo'lishi kerak).

**⚠️ DIQQAT:**
- `restore_center_backup` — `update_or_create` ishlatadi. Agar markaz ichida backup'dan **keyin** yaratilgan yangi talaba bo'lsa, u JSON'da yo'q — **tiklashdan keyin u o'sha-o'sha saqlanib qoladi** (yo'qolmaydi).
- Lekin backup'dan **keyin yangilangan** ma'lumot (masalan talaba familiyasi tahrirlandi) — backup holatiga **qaytadi**. Bu noxush bo'lishi mumkin.
- Agar sen "faqat o'chirilgan narsalarni qaytarmoqchiman" desang — operatordan **kechadan beri nima o'chgan** ro'yxatini so'ra, shu obyektlarnigina tiklaymiz qo'lda.

---

### HOLAT B — Butun baza yiqildi yoki buzildi

**Belgilari:** sayt ochilmaydi, barcha markaz ma'lumotlari yo'q, `psql` ham ulanmayapti yoki jadvallar bo'sh.

**Qancha vaqt oladi:** 20-40 daqiqa

**Qadamlar:**

1. **Aniqla:** DB'ning o'zi yiqildimi yoki ulanish muammosimi?
   ```bash
   # Render Shell
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM accounts_center;"
   ```
   Javob kelsa — DB ishlayapti, boshqa muammo. Javob kelmasa yoki `relation does not exist` bo'lsa — tiklash kerak.

2. Telegram yoki Drive'dan **eng so'nggi to'g'ri** `postgres_full_YYYY-MM-DD.sql` ni yuklab ol.

3. Ogohlantirish: `.sql` faylning o'lchami kutilganga yaqinmi (~7-20MB)? Juda kichik bo'lsa (100KB'dan kam) — bu **bo'sh yoki buzilgan backup**, oldingi kunning faylini ol.

4. Render Shell (yoki mahalliy kompyuterda `DATABASE_URL` bilan):
   ```bash
   # 1. Hozirgi holatni yana saqlab qo'y (panik backup)
   pg_dump $DATABASE_URL > /tmp/panic_$(date +%Y%m%d_%H%M%S).sql

   # 2. Barcha mavjud jadvallarni tozalash (DB bo'sh holatga keltirish)
   #    EHTIYOT: bu hamma jadvallarni o'chiradi
   psql $DATABASE_URL <<SQL
   DROP SCHEMA public CASCADE;
   CREATE SCHEMA public;
   GRANT ALL ON SCHEMA public TO PUBLIC;
   SQL

   # 3. Backup'dan tiklash
   psql $DATABASE_URL < /tmp/postgres_full_2026-04-18.sql

   # 4. Tekshirish
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM accounts_center;"
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM accounts_user;"
   ```

5. Django'ni qaytadan ishga tushir: Render Dashboard → **Manual Deploy → Deploy latest commit** (yoki `Restart` tugmasi).

6. **Migration holatini tekshir:**
   ```bash
   python manage.py showmigrations
   ```
   Barcha migration'lar `[X]` bilan bo'lishi kerak. Agar bir nechtasi `[ ]` bo'lsa — kod backup olingandan keyin yangi migration qo'shgan. Qaror:
   - **Agar kod o'zgarmagan bo'lsa** — `python manage.py migrate` bilan oldinga.
   - **Agar kod backup'dan keyin migration qo'shgan bo'lsa** — backup'da `meta.migrations` ichiga qarab, backup-vaqtidagi kod holatiga commit ni checkout qilib tiklash, keyin oldinga migrate qilish.

---

### HOLAT C — Zanjirli buzilish (bir necha kun oldin ishlamay qolgan, bugun sezildi)

**Belgilari:** "bir hafta oldin bir narsa ishlamagan shekilli, ma'lumotlar noto'g'ri" — kechagi backup ham xato.

**Strategiya:**

1. Telegram'dan/Drive'dan **bir necha kunlik** backup'larni yuklab ol (masalan: -1, -3, -5, -7 kun).
2. Har birini **alohida staging DB**'ga tiklab sinab ko'r:
   ```bash
   # Render'da yangi Postgres instance yaratasan (vaqtinchalik)
   psql $STAGING_URL < backup_<sana>.sql
   # Django'ni shu DB'ga qaratib ochib, ma'lumotlar "sog'lom" ekanini tekshir
   ```
3. Eng oxirgi "sog'lom" sanani top. Faqat o'shani prod'ga tiklaysan.
4. O'sha kundan beri bo'lgan **sog'lom ma'lumot**larni (yangi talabalar, to'lovlar) operatordan qog'ozdan/daftar'dan qayta kiritish kerak bo'ladi. Bu qiyin qism.

---

## 3. NIMA TIKLANMAYDI (haqiqatni bilgin)

Backup — hamma narsani qaytarmaydi. Bular **alohida** saqlanadi:

| Narsa | Qayerda |
|---|---|
| Yuklangan fayllar / avatar rasmlar | Cloudinary (alohida akkaunt — Cloudinary o'zi backup qiladi) |
| Render env vars (tokenlar, API keys) | Render Dashboard (alohida nusxa ol) |
| Render DB ning servis sozlamalari | Render Dashboard |
| Domain DNS yozuvlari | Registrar (alohida nusxa) |

**Tavsiya:** oyiga bir marta quyidagilarni alohida saqla:
- Render env vars ro'yxati (screenshot yoki `env | sort > env_backup.txt`)
- Cloudinary API kalitlari
- Git repo (GitHub allaqachon saqlaydi, lekin alohida clone ham yaxshi)

---

## 4. Oyiga 1 MARTA — mashq qiling (bu eng muhim qism)

Xotirjam paytda qiladigan ish:

1. Staging DB ga `postgres_full_<kecha>.sql` ni tiklab ko'r. Ishladimi?
2. Bir markazning JSON'ini tiklab ko'r. Ishladimi?
3. Bu qo'llanma hali ham to'g'rimi — URL'lar, buyruqlar?
4. Yangi narsalar (Cloudinary, ENV vars) backup'ga qo'shildimi?

**Agar 6 oy tiklashni sinab ko'rmasang — tizim ishlayotganiga kafolat YO'Q.** Backup faqat yurakni tinchlantiradi, amalda ishlamay qolishi mumkin.

---

## 5. Qidiruv — kimdan yordam so'rash

Agar shu qo'llanmada javob topolmasang:
- `core/services/db_backup_service.py` — backup yaratish logikasi
- `core/services/gdrive_backup.py` — Google Drive yuklash
- `core/management/commands/restore_center_backup.py` — per-center tiklash
- `core/management/commands/test_gdrive_upload.py` — Drive ulanishni sinash
