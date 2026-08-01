#!/usr/bin/env bash
set -euo pipefail

echo "=== UI Gate — Daily System ==="

cd "$(dirname "$0")/../.."

# 1. Token generator check (deterministic — no file modification)
echo "[1/4] Checking design tokens (deterministic)..."
dart run tool/generate_design_tokens.dart --check

# 2. Flutter analyze (strict — no flags)
echo "[2/4] Running flutter analyze (strict)..."
cd apps/mobile
flutter analyze

# 3. Flutter test (widget + golden + semantics + generator — includes generator_test)
echo "[3/4] Running flutter test..."
flutter test

# 4. Token consistency verified by --check mode
echo "[4/4] Token consistency verified by --check mode"
echo ""
echo "Dart and CSS tokens are both deterministically generated from"
echo "the same design/tokens/daily-system.tokens.json. The --check mode"
echo "compares each generated file against its expected output, ensuring"
echo "consistency between Dart and CSS without needing hash comparison."

echo ""
echo "=== UI Gate: ALL PASSED ==="
