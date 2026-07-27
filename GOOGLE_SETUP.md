# Google orqali ro'yxatdan o'tish

> **Holat: sozlangan va ishlayapti** (2026-07-27).
>
> Google Cloud loyihasi, rozilik ekrani va uchala client ID yaratilgan.
> Quyida nima qilingani va qolgan qadamlar.

## Yaratilgan narsalar

**Loyiha:** `chaqmoqapp-oauth` (number `148087667821`)
**Rozilik ekrani:** App name `ChaqmoqApp` · External · Testing rejimi
**Test user:** `pragrammeruzz@gmail.com`

| Client | Turi | ID |
|---|---|---|
| ChaqmoqApp Server | Web | `148087667821-8p742la98uta3suah4ogutp9dih1nvhn.apps.googleusercontent.com` |
| ChaqmoqApp iOS | iOS (`uz.chaqmoq.chaqmoqMobile`) | `148087667821-abn0rsij76q4su5gt2ecuou36oumh5i2.apps.googleusercontent.com` |
| ChaqmoqApp Android (debug) | Android (`uz.chaqmoq.chaqmoq_mobile`) | `148087667821-fav869onc3fs18up8rfqec5k6bq1ag7c.apps.googleusercontent.com` |

Android debug SHA-1: `95:23:37:0F:4E:8C:70:78:55:7F:C5:8C:31:9A:A4:21:6D:D9:E6:D2`

## Kodga ulangan joylar

- `.env.google.local` — lokal sinov uchun. Repo'da turibdi: bu yerda faqat
  **client ID**'lar bor, ular maxfiy emas (ilova ichiga ham kompilyatsiya
  qilinadi). Client **secret** bu faylga hech qachon yozilmasin.

- `mobile_app/ios/Runner/Info.plist` — `CFBundleURLTypes` ga iOS URL scheme qo'shilgan
- Tekshiruv: `python manage.py google_tekshir`

## Qolgan qadamlar

**1. Render'ga qo'yish** (production uchun majburiy)

Render → ChaqmoqApp servisi → Environment → yangi o'zgaruvchi:

```
GOOGLE_OAUTH_CLIENT_IDS=148087667821-8p742la98uta3suah4ogutp9dih1nvhn.apps.googleusercontent.com,148087667821-abn0rsij76q4su5gt2ecuou36oumh5i2.apps.googleusercontent.com,148087667821-fav869onc3fs18up8rfqec5k6bq1ag7c.apps.googleusercontent.com
```

**2. Play Market uchun ikkinchi SHA-1**

Hozirgi Android client faqat **debug** imzo bilan ishlaydi. Play Market'dan
o'rnatilgan ilovada ishlashi uchun:

- Play Console → ilova → *Setup → App integrity → App signing key certificate → SHA-1*
- Google Cloud → `chaqmoqapp-oauth` → Clients → **yangi Android client** yarating
  (bitta clientga ikkita SHA-1 sig'maydi), nomi: `ChaqmoqApp Android (Play)`
- Yangi ID'ni ham `GOOGLE_OAUTH_CLIENT_IDS` ga qo'shing

**3. Production'ga chiqarish**

Hozir **Testing** rejimida — faqat test users ro'yxatidagilar kira oladi (100 tagacha).
Play Market'ga chiqarishdan oldin: *Audience → Publish app*.

**4. Ilovani yig'ish**

```bash
flutter build ipa \
  --dart-define=GOOGLE_SERVER_CLIENT_ID=148087667821-8p742la98uta3suah4ogutp9dih1nvhn.apps.googleusercontent.com \
  --dart-define=GOOGLE_IOS_CLIENT_ID=148087667821-abn0rsij76q4su5gt2ecuou36oumh5i2.apps.googleusercontent.com

flutter build appbundle \
  --dart-define=GOOGLE_SERVER_CLIENT_ID=148087667821-8p742la98uta3suah4ogutp9dih1nvhn.apps.googleusercontent.com
```

## Xavfsizlik eslatmasi

Web client yaratilganda Google **client secret** ham ko'rsatdi. Bu oqim uni
**ishlatmaydi** (ID token faqat client ID bo'yicha tekshiriladi), shuning uchun
u hech qayerga yozilmadi. Xotirjam bo'lish uchun uni Cloud Console'dan
almashtirib (rotate) qo'ysangiz ham bo'ladi — hech narsa buzilmaydi.

---

## Batafsil qo'llanma (agar qaytadan qilish kerak bo'lsa)

## 1. Google Cloud loyihasi

1. https://console.cloud.google.com → **New Project** → nom: `ChaqmoqApp`
   (yuqoridagi loyiha tanlagichdan yangi loyihaga o'ting!)
2. **APIs & Services → OAuth consent screen** (yangi konsolda: *Google Auth Platform*)
   - User Type: **External**
   - App name: `ChaqmoqApp` ← o'quvchi aynan shuni ko'radi
   - Support email: `pragrammeruzz@gmail.com`
   - Scopes: `email`, `profile` (qo'shimcha hech narsa kerak emas)
   - Test users: o'z Gmail'ingizni qo'shing (nashr qilinmaguncha)
   - Play Market'ga chiqarishdan oldin: **Audience → Publish app** (Production)

## 2. Uchta Client ID

**APIs & Services → Credentials → Create Credentials → OAuth client ID**

| № | Application type | Nima kiritiladi | Nimaga kerak |
|---|---|---|---|
| 1 | **Web application** | nom: `ChaqmoqApp Server` | Server ID tokenni shu ID bo'yicha tekshiradi. **Eng muhimi.** |
| 2 | **iOS** | Bundle ID: `uz.chaqmoq.chaqmoqMobile` | iPhone'da Google oynasi ochilishi uchun |
| 3 | **Android** | Package: `uz.chaqmoq.chaqmoq_mobile` + SHA-1 | Androidda ochilishi uchun |

### Android SHA-1 barmoq izlari

Ikkitasi kerak:

```bash
# 1) Debug (o'z kompyuteringizda sinash uchun)
keytool -list -v -alias androiddebugkey \
  -keystore ~/.android/debug.keystore -storepass android -keypass android

# 2) Play Console imzosi (Play Market uchun MAJBURIY)
#    Play Console → Ilova → Setup → App integrity → App signing key certificate → SHA-1
```

Ikkalasini ham Android client ID'ga qo'shing — aks holda Play Market'dan
o'rnatilgan ilovada Google ishlamaydi.

---

## 3. Serverga qo'yish

Render → Environment → yangi o'zgaruvchi:

```
GOOGLE_OAUTH_CLIENT_IDS=<Web client ID>,<iOS client ID>,<Android client ID>
```

Vergul bilan, bo'shliqsiz. Uchchalasi ham yozilishi kerak.

## 4. Ilovani yig'ish

```bash
flutter build ipa \
  --dart-define=GOOGLE_SERVER_CLIENT_ID=<Web client ID> \
  --dart-define=GOOGLE_IOS_CLIENT_ID=<iOS client ID>

flutter build appbundle \
  --dart-define=GOOGLE_SERVER_CLIENT_ID=<Web client ID>
```

### iOS uchun qo'shimcha qadam

`ios/Runner/Info.plist` ga iOS client ID'ning **teskari** ko'rinishini qo'shing
(Google Cloud'da «iOS URL scheme» deb beriladi):

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>com.googleusercontent.apps.XXXXXXXX-YYYYYYYY</string>
    </array>
  </dict>
</array>
```

---

## 5. Tekshirish

Avval serverda:

```bash
python manage.py google_tekshir
```

U ID'lar to'g'ri ko'rinishdami, nechtasi qo'yilgani va Telegram sozlangan-
sozlanmaganini aytadi. «Sozlamalar joyida» chiqsa — ilovani yig'ing.

Keyin ilovada:

1. Ilovani oching → «Hisobim yo'q — o'yin uchun ro'yxatdan o'tish»
2. Google tugmasi **ko'rinishi** kerak (sozlanmagan xabari o'rniga)
3. Hisob tanlang → ism/familya/yosh formasi → «Boshlash»
4. Faqat **O'yin, Reyting, Profil** bo'limlari bo'lgan panel ochiladi

Xatolik bo'lsa server logida `Google token tekshirilmadi` qatorini qidiring —
odatda sabab `GOOGLE_OAUTH_CLIENT_IDS` da Web client ID yo'qligi bo'ladi.

---

## Eslatma

Google hisobi bilan kirgan foydalanuvchida **parol yo'q** (`set_unusable_password`).
Ular faqat Google orqali kiradi. Agar shu email bilan o'quv markazi hisobi
allaqachon bo'lsa — u o'yin hisobiga aylanmaydi, foydalanuvchi o'z markaz
paneliga tushadi.
