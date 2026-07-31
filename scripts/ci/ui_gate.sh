#!/usr/bin/env bash
set -euo pipefail

echo "=== UI Gate — Daily System ==="

cd "$(dirname "$0")/../.."

# 1. Token check
echo "[1/4] Checking design tokens..."
dart run tool/generate_design_tokens.dart --check

# 2. Flutter analyze (strict — no warnings or infos allowed)
echo "[2/4] Running flutter analyze..."
cd apps/mobile
flutter analyze

# 3. Flutter test
echo "[3/4] Running flutter test..."
flutter test

# 4. Token consistency (Dart vs CSS)
echo "[4/4] Checking token consistency..."
cd ../..
DART_HASH=$(dart run tool/generate_design_tokens.dart 2>&1 | sha256sum)
cd apps/mobile
CSS_HASH=$(cat ../../design/tokens/generated/daily-system.css | sha256sum)

if [ "$DART_HASH" = "$CSS_HASH" ]; then
  echo "Tokens consistent: PASS"
else
  echo "Tokens mismatch: FAIL"
  exit 1
fi

echo "=== UI Gate: ALL PASSED ==="
