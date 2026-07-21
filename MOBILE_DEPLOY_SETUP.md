# Mobil CI/CD — GitHub push → Android + iOS

**Expo emas.** Bu loyiha **Flutter**. Eng yaxshi yo‘l: **GitHub Actions**.

Workflow: `.github/workflows/mobile-release.yml`

```text
git push origin main   (mobile_app/ o'zgarganda)
        │
        ├─► Android: signed AAB → Actions artifact
        │         └─ (secret bo'lsa) Google Play internal
        │
        └─► iOS: (ENABLE_IOS_CI=true) IPA → TestFlight
```

> Push **darrov Production** qilmaydi. Apple/Google **review** bor.  
> iOS avval **TestFlight**; Android default **internal** track.

---

## 1) Hozir ishga tushirish (Android — 5 daqiqa)

### 1.1 Secret’larni yaratish

Terminal:

```bash
cd ~/Desktop/ChaqmoqApp
bash scripts/export_mobile_ci_secrets.sh
```

Keyin GitHub:

**Repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Qiymat |
|--------|--------|
| `ANDROID_KEYSTORE_BASE64` | skript clipboard qilgan base64 |
| `ANDROID_STORE_PASSWORD` | `mobile_app/android/key.properties` dagi `storePassword` |
| `ANDROID_KEY_PASSWORD` | `keyPassword` (odatda bir xil) |
| `ANDROID_KEY_ALIAS` | `keyAlias` (odatda `upload`) |

### 1.2 Ishga tushirish

```bash
# mobile_app o'zgarishi + push
git add .github/workflows/mobile-release.yml MOBILE_DEPLOY_SETUP.md scripts/export_mobile_ci_secrets.sh
git commit -m "ci: mobile release workflow for Android + iOS"
git push origin main
```

Yoki: **Actions → Mobile Release → Run workflow**

### 1.3 Natija

1. **Actions** → oxirgi run → yashil ✅  
2. **Artifacts** → `ChaqmoqApp-x.y.z-N-aab` ni yuklab oling  
3. Play Console ga AAB joylang (hozircha qo‘lda)

---

## 2) Play ga to‘liq avtomatik (ixtiyoriy)

1. Google Cloud → Service Account + JSON key  
2. Play Console → Users → shu emailga **Release** ruxsati  
3. Secret: `PLAY_SERVICE_ACCOUNT_JSON` = butun JSON matni  
4. Variable: `ENABLE_PLAY_UPLOAD` = `true`  

Keyingi push da AAB **internal** track ga yuklanadi.

Production uchun: **Run workflow** da `play_track: production` yoki workflow dagi default ni o‘zgartiring.

---

## 3) iOS avtomatik (TestFlight)

### 3.1 Variable

**Settings → Secrets and variables → Actions → Variables → New**

| Variable | Qiymat |
|----------|--------|
| `ENABLE_IOS_CI` | `true` |

### 3.2 Secrets

| Secret | Qanday |
|--------|--------|
| `IOS_DIST_CERT_P12_BASE64` | Keychain → Apple Distribution → Export .p12 → `base64 -i cert.p12 \| pbcopy` |
| `IOS_DIST_CERT_PASSWORD` | .p12 paroli |
| `IOS_PROVISION_PROFILE_BASE64` | App Store profile .mobileprovision → base64 |
| `IOS_PROVISION_PROFILE_NAME` | Profil nomi (aynan) |
| `IOS_TEAM_ID` | `95JJKTKNR9` (Membership) |
| `IOS_KEYCHAIN_PASSWORD` | ixtiyoriy (masalan `ci-temp-pass`) |
| `ASC_KEY_ID` | App Store Connect API Key ID |
| `ASC_ISSUER_ID` | Issuer ID |
| `ASC_API_KEY_P8_BASE64` | `.p8` fayl base64 |

**API Key:** App Store Connect → Users and Access → Integrations → App Store Connect API → **+** (App Manager) → `.p8` ni bir marta yuklab saqlang.

### 3.3 Natija

Push → macOS runner → IPA → **TestFlight**.  
App Store Production review ga baribir **qo‘lda** “Submit for Review” kerak (yoki Fastlane lane kengaytiriladi).

---

## 4) Versiya raqamlari

- Marketing: `mobile_app/pubspec.yaml` → `version: 1.0.2+7` dagi `1.0.2`  
- Build number: CI da `BUILD_BASE + run_number` (do‘kon monoton o‘sish)

---

## 5) Expo?

**Yo‘q.** Bu Flutter. Expo ishlatilmaydi.

---

## 6) Checklist

```text
☐ ANDROID_* 4 ta secret
☐ git push main
☐ Actions yashil + AAB artifact
☐ (ixtiyoriy) PLAY_SERVICE_ACCOUNT_JSON
☐ (ixtiyoriy) ENABLE_IOS_CI=true + iOS secrets
```

Savollar bo‘lsa: Actions log skrinini yuboring.
