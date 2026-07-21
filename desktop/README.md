# ChaqmoqApp Desktop

To'liq ChaqmoqApp saytini Windows va Mac dastur sifatida ochadi.

## Ishga tushirish (dev)

```bash
cd desktop
npm install
CHAQMOQ_URL=http://127.0.0.1:8000 npm start
```

## Build

```bash
# Mac + Windows
npm run dist

# Faqat Mac
npm run dist:mac

# Faqat Windows (.exe)
npm run dist:win
```

Natija: `desktop/dist/`

- Windows: `ChaqmoqApp-Setup-1.0.0.exe`, `ChaqmoqApp-Portable-1.0.0.exe`
- Mac: `ChaqmoqApp-Mac-1.0.0-arm64.dmg`, `ChaqmoqApp-Mac-1.0.0-x64.dmg`

Tayyor fayllarni `static/downloads/` ga ko'chiring — saytdan yuklab olinadi.
