# Daily System — Context Handoff

## Estado Canónico Actual (2026-08-15)

```
S0–S5: PASS · Web Premium: PRODUCTIVO
BASELINE: bbb3e1024cd0380cf48288c486565a4411c602c3
RAMA: product/web-premium-v1
WORKTREE: DIRTY (reconciliación documental en curso — sin commit aún)
MASTER: INTACTO (remote: 486d08b)
CI: 3 workflows PASS (backend-ci · web-ci · ui-gate)
```

## Bloque activo — Reconciliación documental (docs + evidencia visual)

- Estado verificado: Backend **367 passed/8 skipped** (SQLite) · alembic head `m8_negocio_nit`
- Mobile **177/177** · flutter analyze 14 infos preexistentes/0 nuevos
- Web E2E: mock **107** + real **26** · `npm audit` 0 · ruff 127 (deuda conocida)
- 8 docs históricos archivados en `docs/historical/` (banner ARCHIVADO)
- README, docs/STATUS, docs/README, docs/TESTING, docs/ARCHITECTURE, docs/SECURITY,
  docs/OFFLINE-SYNC, docs/IMPLEMENTATION-PLAN, docs/web/WEB-UI-BLUEPRINT, CHANGELOG, AGENTS actualizados

## Backend — Baseline certificado

**Baseline:** `bbb3e1024cd0380cf48288c486565a4411c602c3`

**Alembic head:** `m8_negocio_nit` — invariante NIT garantizada por BD (ONBOARDING FINAL).
Cadena: init → m2_apertura_idempotency → m2_jornada_caja → m3_dispositivo → m4_ruta_cobrador_fk →
m5_dispositivo_activacion → m6_dispositivo_version → m7_desafio_auth → m8_negocio_nit.

**Routers (15):** negocio, onboarding, ruta, cliente, credito, pago, hoja_viva, jornada,
movimiento, dispositivo, activacion, mobile, device, auth, inversionista.

**S5:** `conflict_service.py` — 6 verificadores (pago, movimiento, jornada, apertura, reversal,
ruta) · 48 tests. PRE-CHECK layer (no reemplaza validaciones inline).

## Web Premium — Productivo

- `apps/web/` — Next.js 16.3.1 · React 19.2.8 · TS 5.9.3 · Tailwind
- Login en `src/app/page.tsx`; sesión httpOnly `daily_admin_token` → `GET /api/auth/me`
- RBAC server-side (`src/lib/rbac.ts`): COBRADOR / INVERSIONISTA / ADMINISTRADOR
- Superficies: dashboard, rutas, caja, reportes, dispositivos, suscripción, onboarding
- E2E Playwright: 19 specs (14 mock + 5 real)

## S4 Baseline (histórico)
`b75f2c482d5b3f42d60cdbb0f384195c1df73ffc` · S5 `877f24d70dc43246f968e32e50e1bcc8e450191b`

## Protocolo de Recuperación de Sesión

Antes de iniciar cualquier trabajo nuevo:

1. **Engram:** `mem_context` project: daily-system
2. **Handoff local:** leer `DAILY-SYSTEM-CONTEXT-HANDOFF.md`
3. **Graphify:** consultar si disponible
4. **Git:**
   ```
   cd /home/jesus/proyectos/daily-system
   git branch --show-current   # → product/web-premium-v1
   git rev-parse HEAD          # → bbb3e1024cd0380cf48288c486565a4411c602c3
   git status --short          # → reconciliación documental pendiente de commit
   ```
5. **Estado canónico:** leer `docs/STATUS.md` (fuente oficial)
6. **Regresión:** reabrir S0-S5 o Web Premium solo si regresión demostrable

## Restricciones (bloque actual)
- NO push sin verificar todos los gates locales
- NO merge · NO rebase · NO tag
- NO tocar `master` · NO force push
- NO nuevo vertical funcional · NO reglas de negocio · NO auth · NO DB/migrations

## Historial de Baselines
- S4: b75f2c482d5b3f42d60cdbb0f384195c1df73ffc
- S5: 877f24d70dc43246f968e32e50e1bcc8e450191b
- Web Premium baseline: bbb3e1024cd0380cf48288c486565a4411c602c3
