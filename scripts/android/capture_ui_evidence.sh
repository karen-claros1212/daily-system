#!/usr/bin/env bash
# ─── capture_ui_evidence.sh — Parametrized UI Evidence Capture ──────
# Captures real screenshots of the Daily System mobile app (Android
# emulator) and the static web prototype, for the UX/UI premium audit.
#
# The script drives the app through real navigation (login → select
# route → open jornada → each screen) using ADB taps resolved from the
# Flutter semantics tree (uiautomator dump), so it works across phone /
# tablet / light / dark without hardcoded pixel coordinates. Every
# capture is recorded in a manifest.json with SHA-256 + commit metadata.
#
# REQUIREMENTS
#   - Android emulator/device visible via adb (default emulator-5554)
#   - Flutter-built debug APKs (see --build-apks):
#       apps/mobile/build/app/outputs/flutter-apk/app-daily-demo-debug.apk
#       apps/mobile/build/app/outputs/flutter-apk/app-default-debug.apk
#   - chromium (snap chromium or google-chrome) for --web captures
#
# USAGE
#   ./scripts/android/capture_ui_evidence.sh [OPTIONS]
#
# OPTIONS
#   --mode after|before     Capture stage (default: after)
#   --variant default|demo  APK variant to install (default: demo)
#   --profile phone|tablet  Screen profile (default: phone)
#   --theme light|dark      Theme (default: light)
#   --web                   Capture the web prototype instead of Android
#   --screen all|<name>     Capture only the named screen(s) (default: all)
#   --apk PATH              Override APK path
#   --out-dir DIR           Override output directory
#   --no-install            Skip pm clear + APK install (reuse running app)
#   --build-apks            Build default + demo APKs first
#   --device SERIAL         adb device (default: emulator-5554)
#   --verbose               Print the uiautomator tree while navigating
#   -h|--help               Show help
#
# OUTPUT
#   docs/ui-audit/screenshots/<stage>/<profile>-<theme>/NN-name.png
#   docs/ui-audit/screenshots/manifest.json
# ────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── defaults ───────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ADB_DEVICE="${ADB_DEVICE:-emulator-5554}"
STAGE="after"
VARIANT="demo"
PROFILE="phone"
THEME="light"
WEB_MODE=false
SCREEN_FILTER="all"
APK_OVERRIDE=""
OUT_DIR_OVERRIDE=""
NO_INSTALL=false
BUILD_APKS=false
VERBOSE=false

PHONE_SIZE="412x915"
TABLET_SIZE="840x900"
DENSITY="160"
PKG="com.dailysystem.mobile"
ACTIVITY="$PKG/.MainActivity"

# screen order (prefix used for stable filenames)
SCREENS=(login inicio cobros pago movimientos caja cierre historial)
SCREEN_PREFIX=(01 02 03 04 05 06 07 08)

# ─── helpers ────────────────────────────────────────────────────────
log()  { echo "  $*"; }
info() { echo "== $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

adb() { command adb -s "$ADB_DEVICE" "$@"; }

# adb_push <local> <remote>  — exec-out avoids /sdcard round trip
adb_screencap() { adb exec-out screencap -p; }

UI_TMP="/tmp/opencode/ui-dump.xml"

dump_tree() {
  adb shell uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 || true
  adb pull /sdcard/ui.xml "$UI_TMP" > /dev/null 2>&1 || true
}

node_text() { # prints "desc|text|cx cy" per labeled node
  python3 - "$UI_TMP" <<'PY'
import re, sys
try:
    xml = open(sys.argv[1]).read()
except Exception:
    sys.exit(0)
for n in re.findall(r'<node[^>]*/>', xml):
    m = re.search(r'content-desc="([^"]*)"', n)
    t = re.search(r'text="([^"]*)"', n)
    b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
    cd = m.group(1).replace('&#10;', ' ') if m else ''
    tx = t.group(1).replace('&#10;', ' ') if t else ''
    label = cd or tx
    if label:
        x = (int(b.group(1)) + int(b.group(3))) // 2 if b else -1
        y = (int(b.group(2)) + int(b.group(4))) // 2 if b else -1
        print(f"{label}\t{x}\t{y}")
PY
}

tap_label() { # tap_label <substring> [max-y]
  local needle="$1" maxy="${2:-99999}"
  dump_tree
  local target
  target=$(node_text | awk -F'\t' -v needle="$needle" -v my="$maxy" \
    'index($1, needle) && $3 <= my { print $0; exit }')
  if [ -z "${target:-}" ]; then
    return 1
  fi
  local x y
  x=$(echo "$target" | cut -f2)
  y=$(echo "$target" | cut -f3)
  log "tap '$needle' → ($x, $y)"
  adb shell input tap "$x" "$y" > /dev/null
  return 0
}

wait_label() { # wait_label <substring> [timeout_s]
  local needle="$1" timeout="${2:-20}" waited=0
  while [ "$waited" -lt "$timeout" ]; do
    dump_tree
    if node_text | grep -q -F "$needle"; then
      return 0
    fi
    sleep 2
    waited=$((waited + 2))
  done
  return 1
}

swipe_up() {
  adb shell input swipe 206 700 206 350 300 > /dev/null
}

relaunch_app() {
  adb shell am force-stop "$PKG" > /dev/null
  sleep 1
  adb shell am start -n "$ACTIVITY" > /dev/null
  sleep 8
}

# ─── capture + manifest accumulation ────────────────────────────────
RUN_LOG=""
declare -a MANIFEST_JSON=()

verify_screen() { # verify_screen <name> <signature-label>
  local name="$1" sig="$2"
  dump_tree
  node_text | grep -q -F "$sig" ||
    die "'$name' no contiene la firma '$sig' — captura inválida"
  log "verify '$name' → ok ('$sig' present)"
}

capture() { # capture <screen-name>
  local name="$1" ok=false
  if [ "$SCREEN_FILTER" != "all" ] && [ "$SCREEN_FILTER" != "$name" ]; then
    return 0
  fi
  local idx=-1
  for i in "${!SCREENS[@]}"; do
    if [ "${SCREENS[$i]}" = "$name" ]; then idx=$i; fi
  done
  local prefix
  if [ "$idx" -ge 0 ]; then prefix="${SCREEN_PREFIX[$idx]}-"; else prefix=""; fi
  local outdir stage_dir
  if [ -n "$OUT_DIR_OVERRIDE" ]; then
    stage_dir="$OUT_DIR_OVERRIDE"
  else
    stage_dir="$REPO_ROOT/docs/ui-audit/screenshots/$STAGE/$PROFILE-$THEME"
  fi
  outdir="$stage_dir"
  mkdir -p "$outdir"
  local file="$outdir/$prefix$name.png"
  adb_screencap > "$file"
  if [ -s "$file" ]; then
    local size sha resolution
    size=$(stat -c%s "$file")
    sha=$(sha256sum "$file" | cut -d' ' -f1)
    resolution=$(adb shell wm size | grep -o '[0-9]*x[0-9]*' | head -1)
    log "capture '$name' → $file (${size} bytes)"
    if [ -n "$RUN_LOG" ]; then
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$name" "$file" "$size" "$sha" "$resolution" "$STAGE" "$VARIANT" "$THEME" >> "$RUN_LOG"
    fi
  else
    die "capture '$name' vacía — captura inválida"
  fi
}

# ─── device preparation ─────────────────────────────────────────────
prepare_device() {
  info "Preparing device ($ADB_DEVICE) profile=$PROFILE theme=$THEME"
  adb get-state > /dev/null 2>&1 || die "no device at $ADB_DEVICE"
  adb shell input keyevent KEYCODE_WAKEUP > /dev/null 2>&1 || true
  adb shell wm dismiss-keyguard > /dev/null 2>&1 || true
  adb shell settings put global stay_on_while_plugged_in 3 > /dev/null 2>&1 || true
  local wake
  wake=$(adb shell dumpsys power | grep 'mWakefulness=' | head -1 | cut -d= -f2 | tr -d '[:space:]')
  [ "$wake" = "Awake" ] || die "emulator screen is $wake, not Awake"

  # resolution profile
  if [ "$PROFILE" = "tablet" ]; then
    adb shell wm size "$TABLET_SIZE" > /dev/null
  else
    adb shell wm size "$PHONE_SIZE" > /dev/null
  fi
  adb shell wm density "$DENSITY" > /dev/null

  # theme (system night mode) — fallo aquí aborta la captura
  if [ "$THEME" = "dark" ]; then
    adb shell cmd uimode night yes > /dev/null 2>&1 || die "no se pudo activar night mode"
  else
    adb shell cmd uimode night no > /dev/null 2>&1 || die "no se pudo desactivar night mode"
  fi

  # accessibility bridge so Flutter exposes semantics to uiautomator
  # (AccessibilityMenu service does NOT intercept taps, unlike TalkBack)
  adb shell settings put secure enabled_accessibility_services \
    com.android.systemui.accessibility.accessibilitymenu/.AccessibilityMenuService > /dev/null
  adb shell settings put secure accessibility_enabled 1 > /dev/null
}

install_apk() {
  if [ "$NO_INSTALL" = true ]; then
    log "Skipping install (--no-install)"
    return 0
  fi
  local apk
  if [ -n "$APK_OVERRIDE" ]; then
    apk="$APK_OVERRIDE"
  elif [ "$VARIANT" = "demo" ]; then
    apk="$REPO_ROOT/apps/mobile/build/app/outputs/flutter-apk/app-daily-demo-debug.apk"
  else
    apk="$REPO_ROOT/apps/mobile/build/app/outputs/flutter-apk/app-default-debug.apk"
  fi
  [ -f "$apk" ] || die "APK not found: $apk (use --build-apks first)"
  info "Clearing app data + installing $VARIANT variant"
  adb shell pm clear "$PKG" > /dev/null 2>&1 || true
  adb install -r "$apk" > /dev/null 2>&1 || die "APK install failed: $apk"
  adb shell am start -n "$ACTIVITY" > /dev/null
  sleep 8
}

# ─── navigation + capture flow ──────────────────────────────────────
capture_android() {
  info "Capturing Android screens (mode=$STAGE variant=$VARIANT profile=$PROFILE theme=$THEME)"

  # 1. login screen
  wait_label "INICIAR SESIÓN" 30 || die "login screen not found"
  capture "login"
  verify_screen "login" "INICIAR SESIÓN"
  tap_label "INICIAR SESIÓN" || die "cannot tap login"
  sleep 4

  # 2. offline inicio → route selection
  wait_label "SELECCIONAR RUTA" 20 || die "inicio (offline) not found"
  tap_label "SELECCIONAR RUTA" || die "cannot tap route selector"
  sleep 4

  # 3. pick first route → opens the jornada → hoja viva
  wait_label "Ruta activa" 20 || die "no routes available"
  tap_label "Ruta activa" || die "cannot tap route"
  sleep 5

  # 4. hoja viva
  wait_label "VERDE" 20 || die "hoja viva not found"
  capture "cobros"
  verify_screen "cobros" "VERDE"

  # 5. relaunch so Inicio reloads with the open jornada (MainShell chrome
  #    visible en cada captura — no se captura mainshell como evidencia
  #    separada porque es idéntico a inicio sin estado distinto)
  relaunch_app
  wait_label "JORNADA ACTIVA" 30 || die "inicio (active) not found"
  capture "inicio"
  verify_screen "inicio" "JORNADA ACTIVA"

  # 6. pago (Cobrar tile on Inicio)
  tap_label "Seleccionar cliente y abono" || die "Cobrar tile not found"
  sleep 4
  wait_label "REGISTRAR PAGO" 20 || die "pago screen not found"
  capture "pago"
  verify_screen "pago" "REGISTRAR PAGO"

  # 7. movimientos
  tap_label "Tab 1 of 4" 900 || die "Inicio tab not found"
  sleep 3
  tap_label "Gastos, ahorro" || die "Movimientos tile not found"
  sleep 4
  wait_label "Nuevo movimiento" 20 || die "movimientos screen not found"
  capture "movimientos"
  verify_screen "movimientos" "Nuevo movimiento"

  # 8. caja
  tap_label "Tab 1 of 4" 900 || die "Inicio tab not found"
  sleep 3
  tap_label "Efectivo esperado vs contado" || die "Caja tile not found"
  sleep 4
  wait_label "Apertura" 20 || die "caja screen not found"
  capture "caja"
  verify_screen "caja" "Apertura"

  # 9. cierre (scroll Inicio, tap TERMINAR JORNADA card)
  tap_label "Tab 1 of 4" 900 || die "Inicio tab not found"
  sleep 3
  swipe_up
  sleep 2
  tap_label "TERMINAR JORNADA" || die "TERMINAR JORNADA card not found"
  sleep 4
  wait_label "JORNADA ABIERTA" 20 || die "cierre screen not found"
  capture "cierre"
  verify_screen "cierre" "JORNADA ABIERTA"

  # 10. historial (Más tab → Historial de Jornadas)
  tap_label "Tab 1 of 4" 900 || die "Inicio tab not found"
  sleep 2
  tap_label "Tab 4 of 4" 900 || die "Más tab not found"
  sleep 3
  tap_label "Historial de Jornadas" || die "historial card not found"
  sleep 4
  capture "historial"
  verify_screen "historial" "Historial de Jornadas"
}

# ─── web prototype captures ─────────────────────────────────────────
capture_web() {
  local chromium
  chromium="$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)"
  [ -n "$chromium" ] || die "chromium not found (needed for --web)"
  local proto="$REPO_ROOT/design/prototypes/web"
  local outdir stage_dir
  if [ -n "$OUT_DIR_OVERRIDE" ]; then
    stage_dir="$OUT_DIR_OVERRIDE"
  else
    stage_dir="$REPO_ROOT/docs/ui-audit/screenshots/$STAGE/web"
  fi
  mkdir -p "$stage_dir"

  local size
  if [ "$PROFILE" = "tablet" ]; then
    size="840x900"
  else
    size="412x915"
  fi

  info "Capturing web prototype (chromium, ${size})"
  local pages=(index cartera caja reportes)
  local n=1
  for page in "${pages[@]}"; do
    local file="$stage_dir/0$n-$page.png"
    "$chromium" --headless=new --disable-gpu --hide-scrollbars \
      --window-size="$size" \
      --screenshot="$file" \
      "file://$proto/$page.html" > /dev/null 2>&1 || die "web capture '$page' failed"
    if [ -s "$file" ]; then
      local sha sz
      sz=$(stat -c%s "$file")
      sha=$(sha256sum "$file" | cut -d' ' -f1)
      log "capture '$page' → $file (${sz} bytes)"
      if [ -n "$RUN_LOG" ]; then
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
          "web-$page" "$file" "$sz" "$sha" "$size" "$STAGE" "web" "$THEME" >> "$RUN_LOG"
      fi
    fi
    n=$((n + 1))
  done
}

# ─── manifest ───────────────────────────────────────────────────────
write_manifest() {
  [ -n "$RUN_LOG" ] || return 0
  local manifest
  if [ -n "$OUT_DIR_OVERRIDE" ]; then
    manifest="$OUT_DIR_OVERRIDE/../manifest.json"
  else
    manifest="$REPO_ROOT/docs/ui-audit/screenshots/manifest.json"
  fi
  manifest="$(realpath "$manifest")"
  mkdir -p "$(dirname "$manifest")"

  local commit devmodel devapi ts
  if [ "$STAGE" = "before" ] && [ -d "$REPO_ROOT-before/.git" ]; then
    commit=$(git -C "$REPO_ROOT-before" rev-parse HEAD 2>/dev/null || echo "unknown")
  else
    commit=$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown")
  fi
  devmodel=$(adb shell getprop ro.product.model 2>/dev/null | tr -d '\r' || echo "unknown")
  devapi=$(adb shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r' || echo "unknown")
  ts=$(date +%Y%m%d-%H%M%S)

  python3 - "$manifest" "$commit" "$devmodel" "$devapi" "$ts" "$RUN_LOG" <<'PY'
import json, os, sys
manifest, commit, model, api, ts, runlog = sys.argv[1:7]
entries = {}
if os.path.exists(manifest):
    try:
        existing = json.load(open(manifest))
        for e in existing.get("captures", []):
            entries[e.get("path")] = e
    except Exception:
        pass
for line in open(runlog):
    p = line.rstrip('\n').split('\t')
    if len(p) < 8:
        continue
    name, path, size, sha, res, stage, variant, theme = p[:8]
    rel = os.path.relpath(path, os.path.dirname(manifest))
    entries[rel] = {
        "screen": name,
        "stage": stage,
        "variant": variant,
        "theme": theme,
        "path": rel,
        "size_bytes": int(size),
        "sha256": sha,
        "resolution": res,
        "device": model,
        "api": api,
        "commit": commit,
        "timestamp": ts,
    }
with open(manifest, "w") as f:
    json.dump({"generated": ts, "commit": commit, "captures": list(entries.values())}, f, indent=2)
print(f"manifest → {manifest} ({len(entries)} captures)")
PY
}

# ─── main ───────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --mode) STAGE="$2"; shift 2 ;;
    --variant) VARIANT="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --theme) THEME="$2"; shift 2 ;;
    --web) WEB_MODE=true; shift ;;
    --screen) SCREEN_FILTER="$2"; shift 2 ;;
    --apk) APK_OVERRIDE="$2"; shift 2 ;;
    --out-dir) OUT_DIR_OVERRIDE="$2"; shift 2 ;;
    --no-install) NO_INSTALL=true; shift ;;
    --build-apks) BUILD_APKS=true; shift ;;
    --device) ADB_DEVICE="$2"; shift 2 ;;
    --verbose) VERBOSE=true; shift ;;
    -h|--help) grep '^#' "$0" | head -60; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

case "$STAGE" in after|before) ;; *) die "invalid --mode (after|before)" ;; esac
case "$VARIANT" in default|demo) ;; *) die "invalid --variant (default|demo)" ;; esac
case "$PROFILE" in phone|tablet) ;; *) die "invalid --profile (phone|tablet)" ;; esac
case "$THEME" in light|dark) ;; *) die "invalid --theme (light|dark)" ;; esac

mkdir -p /tmp/opencode
RUN_LOG="/tmp/opencode/capture-run-$$.tsv"

if [ "$BUILD_APKS" = true ]; then
  info "Building APKs"
  local outdir="$REPO_ROOT/apps/mobile/build/app/outputs/flutter-apk"
  (cd "$REPO_ROOT/apps/mobile" && source ~/.bashrc 2>/dev/null; \
   flutter build apk --debug --dart-define=DAILY_DEMO=true \
   && cp build/app/outputs/flutter-apk/app-debug.apk "$outdir/app-daily-demo-debug.apk" \
   && flutter build apk --debug --dart-define=DAILY_DEMO=false \
   && cp build/app/outputs/flutter-apk/app-debug.apk "$outdir/app-default-debug.apk")
fi

if [ "$WEB_MODE" = true ]; then
  capture_web
  write_manifest
  info "Done."
  exit 0
fi

prepare_device
install_apk
capture_android
write_manifest

info "Capture complete."
[ -f "$RUN_LOG" ] && rm -f "$RUN_LOG"
