#!/usr/bin/env bash
# ─── ensure-emulator-awake.sh ───────────────────────────────────
# Wakes emulator, dismisses keyguard, enables stay-awake, and
# verifies the screen is Awake before ADB interaction.
#
# Usage:  ./scripts/android/ensure-emulator-awake.sh
# Fails with clear message if the screen stays Asleep.
#
# Root cause reference:
#   The "Cobrar" chip was never broken. Prior ADB tap failures
#   were caused by the emulator being Asleep (mWakefulness=Asleep).
#   ADB accepted all commands silently, but touches never reached
#   Flutter. ALWAYS run this script before any UI interaction.
# ──────────────────────────────────────────────────────────────────

set -euo pipefail

echo "🔍 Ensuring emulator is awake..."

# 1. Wake the screen
adb shell input keyevent KEYCODE_WAKEUP 2>/dev/null || true

# 2. Dismiss keyguard (lock screen)
adb shell wm dismiss-keyguard 2>/dev/null || true

# 3. Keep screen on while plugged in
adb shell settings put global stay_on_while_plugged_in 3 2>/dev/null || true

# 4. Verify wakefulness
WAKE=$(adb shell dumpsys power | grep 'mWakefulness=' | head -1 | cut -d= -f2 | tr -d '[:space:]')
echo "📱 mWakefulness=${WAKE}"

if [ "$WAKE" != "Awake" ]; then
  echo ""
  echo "❌ FATAL: Emulator screen is ${WAKE}, not Awake."
  echo "   ADB input tap will fail silently — touches go to the lock screen / black screen."
  echo ""
  echo "   Try:  adb shell input keyevent KEYCODE_WAKEUP"
  echo "         adb shell wm dismiss-keyguard"
  echo "         Then re-run this script."
  exit 1
fi

# 5. Verify MainActivity is focused
FOCUSED=$(adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -1)
echo "🎯 Focus: ${FOCUSED}"

# 6. Show display power state
DISPLAY=$(adb shell dumpsys power | grep 'Display Power' | head -1 | sed 's/^[[:space:]]*//')
echo "🖥️  ${DISPLAY}"

echo "✅ Emulator is awake and ready."
