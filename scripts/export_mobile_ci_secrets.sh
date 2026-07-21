#!/usr/bin/env bash
# GitHub Actions secret'larini tayyorlash yordamchisi.
# Parollarni ekranga CHOP ETMAYDI — faqat base64 va yo'riqnoma.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOBILE="$ROOT/mobile_app"
KEYSTORE="$MOBILE/android/upload-keystore.jks"
KEYPROPS="$MOBILE/android/key.properties"

echo "════════════════════════════════════════════════════════"
echo " ChaqmoqApp — CI secret tayyorlash"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Repo: Settings → Secrets and variables → Actions → New repository secret"
echo ""

if [[ -f "$KEYSTORE" ]]; then
  echo "── ANDROID_KEYSTORE_BASE64 (clipboard ga nusxa) ──"
  if command -v pbcopy >/dev/null 2>&1; then
    base64 -i "$KEYSTORE" | tr -d '\n' | pbcopy
    echo "✅ base64 clipboard ga ko'chirildi → ANDROID_KEYSTORE_BASE64 secretiga joylang"
  else
    base64 -i "$KEYSTORE" | tr -d '\n' > /tmp/chaqmoq_keystore.b64
    echo "✅ /tmp/chaqmoq_keystore.b64 ga yozildi"
  fi
else
  echo "⚠️  Keystore topilmadi: $KEYSTORE"
fi

if [[ -f "$KEYPROPS" ]]; then
  echo ""
  echo "── key.properties dan (qo'lda secret qiling) ──"
  # Faqat nomlarni ko'rsatamiz, parolni emas
  ALIAS=$(grep -E '^keyAlias=' "$KEYPROPS" | cut -d= -f2- || true)
  echo "ANDROID_KEY_ALIAS      = ${ALIAS:-upload}"
  echo "ANDROID_STORE_PASSWORD = (key.properties dagi storePassword)"
  echo "ANDROID_KEY_PASSWORD   = (key.properties dagi keyPassword)"
else
  echo "⚠️  key.properties topilmadi"
fi

echo ""
echo "── iOS (keyinroq) ──"
echo "1) Variables: ENABLE_IOS_CI = true"
echo "2) Secrets: MOBILE_DEPLOY_SETUP.md 2-bo'lim"
echo ""
echo "── Play avtomatik yuklash (ixtiyoriy) ──"
echo "PLAY_SERVICE_ACCOUNT_JSON = Play Console service account JSON matni"
echo ""
echo "To'liq yo'riqnoma: MOBILE_DEPLOY_SETUP.md"
echo "════════════════════════════════════════════════════════"
