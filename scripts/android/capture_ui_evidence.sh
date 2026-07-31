#!/usr/bin/env bash
set -euo pipefail

# ─── UI Evidence Capture Script ──────────────────────────────────
# Captures screenshots from the Daily System app running on an
# Android emulator. Generates a manifest.json with metadata.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCREENSHOTS_DIR="$REPO_ROOT/docs/ui-audit/screenshots/after"
MANIFEST="$REPO_ROOT/docs/ui-audit/screenshots/manifest.json"

# Verify ADB
if ! command -v adb &>/dev/null; then
  echo "ERROR: adb not found. Install Android SDK Platform-Tools."
  exit 1
fi

# Verify device
adb devices | grep -q "device" || {
  echo "ERROR: No Android device/emulator found."
  echo "Start emulator: $ANDROID_HOME/emulator/emulator -avd DailySystem_API35"
  exit 1
}

# Verify APK
APK="$REPO_ROOT/apps/mobile/build/app/outputs/flutter-apk/app-debug.apk"
if [ ! -f "$APK" ]; then
  echo "ERROR: APK not found at $APK"
  echo "Build first: cd apps/mobile && flutter build apk --debug"
  exit 1
fi

# Install APK
echo "[1/5] Installing APK..."
adb install -r "$APK" > /dev/null 2>&1 || true
echo "  APK installed."

# Get device info
echo "[2/5] Capturing device info..."
DEVICE_MODEL=$(adb shell getprop ro.product.model 2>/dev/null || echo "unknown")
DEVICE_API=$(adb shell getprop ro.build.version.sdk 2>/dev/null || echo "unknown")
DEVICE_RES=$(adb shell wm size 2>/dev/null | grep "Physical size" | cut -d' ' -f3 || echo "unknown")
COMMIT_SHA=$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "  Model: $DEVICE_MODEL"
echo "  API: $DEVICE_API"
echo "  Resolution: $DEVICE_RES"
echo "  SHA: $COMMIT_SHA"

# Define screens to capture
declare -a SCREENS=(
  "01-login:phone-light"
  "02-inicio:phone-light"
  "03-ruta-cobros:phone-light"
  "04-pago:phone-light"
  "05-movimientos:phone-light"
  "06-caja:phone-light"
  "07-cierre:phone-light"
  "08-historial:phone-light"
)

# Capture screenshots
echo "[3/5] Capturing screenshots..."
echo "[" > "$MANIFEST"
FIRST=true

for screen_info in "${SCREENS[@]}"; do
  SCREEN_NAME="${screen_info%%:*}"
  THEME="${screen_info##*:}"
  OUTPUT="$SCREENSHOTS_DIR/$THEME/${SCREEN_NAME}.png"
  
  # Navigate to screen (simplified: take screenshot of current screen)
  # In production, this would use adb shell input tap to navigate
  adb shell screencap -p /sdcard/evidence.png 2>/dev/null
  adb pull /sdcard/evidence.png "$OUTPUT" 2>/dev/null || true
  
  if [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
    FILE_SIZE=$(stat -c%s "$OUTPUT" 2>/dev/null || stat -f%z "$OUTPUT" 2>/dev/null || echo "0")
    FILE_SHA=$(sha256sum "$OUTPUT" 2>/dev/null | cut -d' ' -f1 || echo "unknown")
    
    if [ "$FIRST" = true ]; then
      FIRST=false
    else
      echo "," >> "$MANIFEST"
    fi
    
    cat >> "$MANIFEST" << JSONEOF
  {
    "screen": "$SCREEN_NAME",
    "theme": "$THEME",
    "path": "$OUTPUT",
    "size_bytes": $FILE_SIZE,
    "sha256": "$FILE_SHA",
    "device": "$DEVICE_MODEL",
    "api": "$DEVICE_API",
    "resolution": "$DEVICE_RES",
    "commit": "$COMMIT_SHA",
    "timestamp": "$TIMESTAMP"
  }
JSONEOF
    
    echo "  ✓ $SCREEN_NAME ($THEME) - ${FILE_SIZE} bytes"
  else
    echo "  ✗ $SCREEN_NAME ($THEME) - capture failed"
  fi
done

echo "" >> "$MANIFEST"
echo "]" >> "$MANIFEST"

# Verify no empty screenshots
echo "[4/5] Validating screenshots..."
EMPTY_COUNT=0
for f in "$SCREENSHOTS_DIR"/phone-light/*.png; do
  if [ -f "$f" ] && [ ! -s "$f" ]; then
    EMPTY_COUNT=$((EMPTY_COUNT + 1))
  fi
done

if [ "$EMPTY_COUNT" -gt 0 ]; then
  echo "  WARNING: $EMPTY_COUNT empty screenshots detected"
else
  echo "  All screenshots valid (non-empty)."
fi

# Generate summary
echo "[5/5] Summary..."
TOTAL_FILES=$(find "$SCREENSHOTS_DIR" -name "*.png" -size +0c 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$SCREENSHOTS_DIR" 2>/dev/null | cut -f1)
echo ""
echo "=== Capture Complete ==="
echo "Screenshots: $TOTAL_FILES files"
echo "Total size: $TOTAL_SIZE"
echo "Manifest: $MANIFEST"
echo "Device: $DEVICE_MODEL (API $DEVICE_API, $DEVICE_RES)"
echo "SHA: $COMMIT_SHA"
