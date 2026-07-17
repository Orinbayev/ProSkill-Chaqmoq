# Mobil ilova avtomatik reliz (CI/CD) — sozlash yo'riqnomasi

`main` branch'ga `mobile_app/` ichida o'zgarish **push** qilinganda GitHub Actions
avtomatik ravishda:

- **Android** AAB build qilib **Google Play**'ga (production track) yuklaydi;
- **iOS** IPA build qilib **App Store Connect (TestFlight)**'ga yuklaydi.

Workflow fayli: `.github/workflows/mobile-release.yml`

> ⚠️ **Muhim haqiqat:** yuklashdan keyin har ikki do'kon **review** qiladi
> (Google: soatlar; Apple: ~1-3 kun). "Push → darrov jonli" emas — bu Apple/Google
> qoidasi, hech kim aylanib o'tolmaydi. iOS TestFlight'ga esa review'siz tez tushadi.

---

## 0. Nima qilish kerak (qisqacha)

`GitHub repo → Settings → Secrets and variables → Actions → New repository secret`.

### ✅ HOZIR (do'kon akkauntlari egasidan mustaqil) — faqat 4 ta Android secret
Android CI signed AAB build qilib, **yuklab olinadigan artifact** qiladi (Play'ga
to'g'ridan-to'g'ri yuklamaydi). Buning uchun faqat keystore secret'lari kerak:
`ANDROID_KEYSTORE_BASE64`, `ANDROID_STORE_PASSWORD`, `ANDROID_KEY_PASSWORD`,
`ANDROID_KEY_ALIAS` (1-bo'lim 1.1). Bu 4 tasi qo'shilsa — Android artifact tayyor
bo'ladi, siz uni yuklab olib Play'ga qo'lda joylaysiz.

### ⏳ KEYINROQ (do'kon egasi ruxsati kerak)
- **Play'ga to'liq avtomatik yuklash:** `PLAY_SERVICE_ACCOUNT_JSON` (1.2) — Play Console admin kerak.
- **iOS (TestFlight):** barcha iOS secret'lari (2-bo'lim) + workflow'dagi iOS `if: false` ni o'chirish — App Store Connect egasi/Admin kerak.

Quyidagi jadvallar har bir secret'ni qanday olishni tushuntiradi.

---

## 1. ANDROID uchun secret'lar

| Secret nomi | Nima | Qayerdan olinadi |
|---|---|---|
| `ANDROID_KEYSTORE_BASE64` | keystore fayli (base64) | pastdagi buyruq |
| `ANDROID_STORE_PASSWORD` | keystore paroli | `mobile_app/android/key.properties` dagi `storePassword` |
| `ANDROID_KEY_PASSWORD` | kalit paroli | `key.properties` dagi `keyPassword` |
| `ANDROID_KEY_ALIAS` | kalit alias | `key.properties` dagi `keyAlias` |
| `PLAY_SERVICE_ACCOUNT_JSON` | Play API service account (JSON matni) | 1.2-bo'lim |

### 1.1 Keystore'ni base64 qilish (Mac terminalда)
```bash
base64 -i ~/Desktop/ChaqmoqApp/mobile_app/android/upload-keystore.jks | pbcopy
```
Natija clipboard'ga ko'chiriladi → `ANDROID_KEYSTORE_BASE64` secret'iga qo'ying.

### 1.2 Google Play service account JSON (bir marta)
1. [Google Cloud Console](https://console.cloud.google.com) → yangi/mavjud proyekt → **IAM & Admin → Service Accounts → Create service account**.
2. Yaratilgach → **Keys → Add key → JSON** → fayl yuklab olinadi.
3. [Play Console](https://play.google.com/console) → **Users and permissions → Invite new users** → yuqoridagi service account emailini qo'shing → **App permissions**: ChaqmoqApp uchun *Release* ruxsatlarini bering (Releases: Create/Edit/Publish).
4. Yuklab olingan JSON **faylning butun matnini** `PLAY_SERVICE_ACCOUNT_JSON` secret'iga joylang.

> Track'ni o'zgartirish: workflow'да Android bo'limида `track: production` bor.
> Xavfsizroq boshlash uchun `track: internal` qiling — review'siz, faqat testerlar oladi.

---

## 2. iOS uchun secret'lar

| Secret nomi | Nima | Qayerdan olinadi |
|---|---|---|
| `IOS_DIST_CERT_P12_BASE64` | Apple Distribution sertifikati (.p12, base64) | 2.1 |
| `IOS_DIST_CERT_PASSWORD` | .p12 eksport paroli | 2.1 (o'zingiz o'ylab topasiz) |
| `IOS_PROVISION_PROFILE_BASE64` | App Store provisioning profile (.mobileprovision, base64) | 2.2 |
| `IOS_PROVISION_PROFILE_NAME` | Profilning nomi | 2.2 |
| `IOS_TEAM_ID` | Apple Team ID (10 belgi) | [developer.apple.com](https://developer.apple.com/account) → Membership |
| `IOS_KEYCHAIN_PASSWORD` | CI keychain uchun ixtiyoriy parol | O'zingiz o'ylab topasiz (masalan tasodifiy) |
| `ASC_KEY_ID` | App Store Connect API Key ID | 2.3 |
| `ASC_ISSUER_ID` | App Store Connect Issuer ID | 2.3 |
| `ASC_API_KEY_P8_BASE64` | ASC API kaliti (.p8, base64) | 2.3 |

### 2.1 Distribution sertifikati (.p12)
Agar Mac'ingizда allaqachon "Apple Distribution" sertifikati bo'lsa:
1. **Keychain Access** → **login → My Certificates** → "Apple Distribution: ..." ni toping.
2. Ustiga o'ng tugma → **Export** → `.p12` sifatida saqlang, **parol** qo'ying (bu `IOS_DIST_CERT_PASSWORD`).
3. Base64: `base64 -i dist_cert.p12 | pbcopy` → `IOS_DIST_CERT_P12_BASE64`.

(Sertifikat yo'q bo'lsa: developer.apple.com → Certificates → **Apple Distribution** yarating, yuklab oling, Keychain'ga qo'shing, keyin yuqoridagi eksport.)

### 2.2 App Store provisioning profile
1. [developer.apple.com](https://developer.apple.com/account) → **Profiles → +** → **App Store** (Distribution) → App ID: `uz.chaqmoq.chaqmoqMobile` → sertifikatni tanlang → nom bering (masalan `ChaqmoqApp AppStore`).
2. Yuklab oling (`.mobileprovision`).
3. Base64: `base64 -i ChaqmoqApp_AppStore.mobileprovision | pbcopy` → `IOS_PROVISION_PROFILE_BASE64`.
4. Bergan nomingizni `IOS_PROVISION_PROFILE_NAME` ga yozing (aynan bir xil bo'lsin).

### 2.3 App Store Connect API kaliti
1. [App Store Connect](https://appstoreconnect.apple.com) → **Users and Access → Integrations → App Store Connect API → +**.
2. Rol: **App Manager** (yoki Admin) → yarating.
3. **Key ID** (`ASC_KEY_ID`) va **Issuer ID** (`ASC_ISSUER_ID`) ni ko'chiring.
4. `.p8` faylni yuklab oling (**faqat bir marta yuklab olinadi!**).
5. Base64: `base64 -i AuthKey_XXXX.p8 | pbcopy` → `ASC_API_KEY_P8_BASE64`.

---

## 3. Ishga tushirish va tekshirish

1. Yuqoridagi barcha secret'larni qo'shing.
2. `mobile_app/` ichida biror o'zgarish qilib `main`'ga push qiling —
   YOKI qo'lda: **GitHub repo → Actions → "Mobile Release" → Run workflow**.
3. Actions log'ida android va ios job'lari ishlashini kuzating.

### Versiya raqami
Har run'да build raqami avtomatik oshadi (`BUILD_BASE(5) + run_number`), shuning
uchun do'kon "versionCode allaqachon ishlatilgan" demaydi. `pubspec.yaml` dagi
`1.0.x` nomini o'zgartirsangiz — marketing versiyasi shu bo'ladi.

---

## 4. Ma'lum cheklovlar / ehtimoliy tuzatishlar (halol)

- **iOS imzolash CI'да nozik.** Agar `flutter build ipa` bosqichida imzo xatosi
  chiqsa, ko'pincha sabab: Xcode Runner target'ида "Automatic signing" yoqilgan.
  Yechim: Xcode'да Runner → Signing & Capabilities → **Manual** qilib, yuqoridagi
  App Store profilini tanlab, commit qilish. (Bir marta.) Men buni sizsiz to'liq
  sinab ko'ra olmadim — birinchi run natijasiga qarab moslaymiz.
- **iOS default TestFlight'ga boradi** (review'siz, tez). App Store'да jonli
  chiqarish uchun: App Store Connect'да o'sha build'ni tanlab "Submit for review"
  bosasiz — YOKI xohlasangiz workflow'ga avtomatik App Store submit lane'ini
  qo'shaman (lekin har push'да Apple review'ga jo'natish tavsiya etilmaydi).
- **Android production** review'ga o'zi jo'naydi. `internal` track xavfsizroq.
- **macOS runner** (iOS uchun) GitHub'ning pullik daqiqalarini sarflaydi
  (public repo'да bepul; private repo'да cheklangan bepul limit bor).

---

## 5. Xavfsizlik
- Keystore, `.p12`, `.p8`, `.mobileprovision`, `key.properties` fayllari
  **hech qachon git'ga commit qilinmaydi** (`.gitignore`да bloklangan).
- Ular faqat GitHub Secrets sifatida saqlanadi va CI ichида vaqtincha tiklanadi.
