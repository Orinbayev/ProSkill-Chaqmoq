#!/usr/bin/env bash
# Build natijasini static/downloads/ ga ko'chiradi
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/desktop/dist"
OUT="$ROOT/static/downloads"
mkdir -p "$OUT"

copy_one() {
  local src_glob="$1"
  local dest_name="$2"
  local f
  f="$(ls -1 $src_glob 2>/dev/null | head -1 || true)"
  if [[ -n "${f:-}" && -f "$f" ]]; then
    cp -f "$f" "$OUT/$dest_name"
    echo "OK  $dest_name  ←  $(basename "$f")  ($(du -h "$OUT/$dest_name" | cut -f1))"
  else
    echo "SKIP $dest_name (topilmadi: $src_glob)"
  fi
}

copy_one "$DIST/ChaqmoqApp-Windows-Setup.exe" "ChaqmoqApp-Windows-Setup.exe"
copy_one "$DIST/ChaqmoqApp-Windows-Portable.exe" "ChaqmoqApp-Windows-Portable.exe"
copy_one "$DIST/ChaqmoqApp Setup "*.exe" "ChaqmoqApp-Windows-Setup.exe" 2>/dev/null || true
copy_one "$DIST/"*.exe "ChaqmoqApp-Windows-Setup.exe"
copy_one "$DIST/ChaqmoqApp-Mac.dmg" "ChaqmoqApp-Mac.dmg"
copy_one "$DIST/"*.dmg "ChaqmoqApp-Mac.dmg"

# README for empty state
cat > "$OUT/README.txt" <<'EOF'
ChaqmoqApp Desktop dasturlari

Windows: ChaqmoqApp-Windows-Setup.exe
Mac:     ChaqmoqApp-Mac.dmg

Build:
  cd desktop && npm install && npm run dist && ./publish-to-static.sh
EOF

ls -lah "$OUT"
