#!/usr/bin/env bash
# ─── capture_web_evidence.sh — Evidencia visual del panel web productivo ──
# Arranca el stack de la Web Premium (mock-api con el contrato REAL del
# backend en :8100 + Next.js dev en :3000), captura las 8 pantallas del panel
# con Playwright (login real por código de activación) y escribe un
# manifest.json con SHA-256 + commit + timestamp.
#
# OUTPUT
#   docs/assets/readme/web/01-login.png … 08-registro.png
#   docs/assets/readme/web/manifest.json
#
# REQUIREMENTS
#   - node + apps/web/node_modules (npm ci) + browsers de Playwright instalados
#   - Libre el puerto 3000/8100 o servidores ya levantados (se reutilizan)
#
# USAGE
#   ./scripts/web/capture_web_evidence.sh [--keep-servers]
# ────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WEB_DIR="$REPO_ROOT/apps/web"
OUT_DIR="$REPO_ROOT/docs/assets/readme/web"
KEEP=false

log()  { echo "== $*"; }
info() { echo "  $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --keep-servers) KEEP=true; shift ;;
    -h|--help) grep '^#' "$0" | head -20; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

command -v node >/dev/null 2>&1 || die "node no encontrado"
[ -d "$WEB_DIR/node_modules/@playwright/test" ] || die "faltan deps web: (cd apps/web && npm ci)"
[ -n "${PLAYWRIGHT_BROWSERS_PATH:-}" ] || [ -d "$HOME/.cache/ms-playwright" ] || \
  die "browsers de Playwright no instalados (npx playwright install chromium)"

# ─── servidores (reutiliza los que ya respondan) ───────────────────────────
MOCK_PID=""
WEB_PID=""

is_up() { curl -sf -o /dev/null "$1"; }

if is_up "http://localhost:8100/api/inversionista/resumen"; then
  info "mock-api ya responde en :8100 — se reutiliza"
else
  log "Arrancando mock-api (:8100)"
  (cd "$WEB_DIR" && MOCK_API_PORT=8100 node e2e/mock-api.mjs > /tmp/opencode/capture-mock.log 2>&1) &
  MOCK_PID=$!
  for i in $(seq 1 30); do is_up "http://localhost:8100/api/inversionista/resumen" && break; sleep 1; done
  is_up "http://localhost:8100/api/inversionista/resumen" || die "mock-api no levantó"
fi

if is_up "http://localhost:3000"; then
  info "Next dev ya responde en :3000 — se reutiliza"
else
  log "Arrancando Next dev (:3000)"
  (cd "$WEB_DIR" && API_BASE=http://localhost:8100 DAILY_ENV=test npm run dev > /tmp/opencode/capture-web.log 2>&1) &
  WEB_PID=$!
  for i in $(seq 1 60); do is_up "http://localhost:3000" && break; sleep 1; done
  is_up "http://localhost:3000" || die "Next dev no levantó (ver /tmp/opencode/capture-web.log)"
fi

# ─── captura ────────────────────────────────────────────────────────────────
mkdir -p "$OUT_DIR"
trap 'if [ "$KEEP" != true ]; then
  [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null || true
  [ -n "$MOCK_PID" ] && kill "$MOCK_PID" 2>/dev/null || true
fi' EXIT

log "Capturando 8 pantallas de la Web Premium"
node "$REPO_ROOT/scripts/web/capture_web_evidence.mjs"

info "Evidencia → $OUT_DIR"
ls -1 "$OUT_DIR"/*.png | sed "s|$REPO_ROOT/||"
