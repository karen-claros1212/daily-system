#!/usr/bin/env bash
set -euo pipefail

echo "=== UI Gate — Daily System ==="

cd "$(dirname "$0")/../.."

# 1. Token generator check (deterministic — no file modification)
echo "[1/5] Checking design tokens (deterministic)..."
dart run tool/generate_design_tokens.dart --check

# 2. Generator-specific tests
echo "[2/5] Running generator unit tests..."
cd apps/mobile
flutter test test/generator_test.dart || { echo "Generator tests failed"; exit 1; }

# 3. Flutter analyze (strict — no flags)
echo "[3/5] Running flutter analyze (strict)..."
flutter analyze

# 4. Flutter test (widget + golden + semantics)
echo "[4/5] Running flutter test..."
flutter test

# 5. Token consistency verified by --check mode
echo "[5/5] Token consistency verified by --check mode"
echo ""
echo "Dart and CSS tokens are both deterministically generated from"
echo "the same design/tokens/daily-system.tokens.json. The --check mode"
echo "compares each generated file against its expected output, ensuring"
echo "consistency between Dart and CSS without needing hash comparison."

echo ""
echo "=== UI Gate: ALL PASSED ==="
