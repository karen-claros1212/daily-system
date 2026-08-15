# Documentación — Daily System

> **Verdad primaria:** Este índice organiza la documentación del repositorio.
> Consulte [`STATUS.md`](STATUS.md) para el estado productivo verificado (verdad primaria).
> El handoff operativo vigente es [`DAILY-SYSTEM-CONTEXT-HANDOFF.md`](../DAILY-SYSTEM-CONTEXT-HANDOFF.md).

---

## Índice

| Documento | Tipo | Propósito |
|---|---|---|
| [STATUS.md](STATUS.md) | **Estado vivo** | Estado productivo actual verificado (rama, HEAD, números, gates). Primera lectura obligatoria. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Normativo | Arquitectura vigente: capas, flujos, contratos. |
| [SECURITY.md](SECURITY.md) | Normativo | Auth, device binding, tenant/ruta isolation, idempotencia, revocación. |
| [OFFLINE-SYNC.md](OFFLINE-SYNC.md) | Normativo | Contrato de sync offline S0-S5: estado por bloque. |
| [TESTING.md](TESTING.md) | Estado vivo | Suites, gates, comandos, CI. |
| [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) | Estado vivo | Roadmap por bloques (qué sigue). |
| [ENGRAM-PROTOCOL.md](ENGRAM-PROTOCOL.md) | Normativo | Protocolo Engram (memoria de agentes). |
| [GRAPHIFY-PROTOCOL.md](GRAPHIFY-PROTOCOL.md) | Normativo | Protocolo Graphify (grafo de conocimiento). |
| [GRAPHIFY-CURRENT.md](GRAPHIFY-CURRENT.md) | Referencia | Estado del grafo (regenerable). |
| [ADR-INFRA-NAMING.md](decisions/ADR-INFRA-NAMING.md) | Decisión | Naming de infraestructura. |
| [WEB-UI-BLUEPRINT.md](web/WEB-UI-BLUEPRINT.md) | Histórico | Prototipo web MOCK (no productivo; el panel productivo está en `apps/web/`). |
| [Historical](historical/) | Archivo | Documentos archivados (no son verdad vigente). |
| [ui-audit/](ui-audit/) | Evidencia | Auditoría visual before/after (Android) + manifest SHA-256. |

---

## Clasificación de documentos

| Tipo | Significado | Caducidad |
|---|---|---|
| **Estado vivo** | Refleja el estado verificado del árbol de código actual. Se actualiza con cada verificación. | Al cambio de estado (commit nuevo en `product/web-premium-v1`). |
| **Normativo** | Define cómo debe comportar el sistema. No cambia sin un commit de código que lo justifique. | Al cambio de arquitectura/contracto. |
| **Referencia** | Herramientas o artefactos auxiliares (grafo, protocolo). | Al cambio de herramienta. |
| **Decisión** | Registro de una decisión arquitectónica (ADR). | Aprobada; no caduca salvo reversión. |
| **Histórico** | Capturas de estados anteriores (auditorías, notas de sesión, especificaciones cerradas). Se archivan en `docs/historical/` al reconciliar. | Información histórica; no usar como verdad vigente. |

### Clasificación del inventario documental (2026-08-15)

| Documento | Clase | Acción |
|---|---|---|
| README.md (raíz) | B — vigente pero desactualizado | ✅ Reescrito al estado canónico |
| CHANGELOG.md | B — desactualizado | ✅ Actualizado |
| AGENTS.md | B — desactualizado | ✅ Actualizado |
| SECURITY.md / CONTRIBUTING.md / CODE_OF_CONDUCT.md (raíz) | A — vigente | Sin cambios |
| docs/STATUS.md | B — desactualizado | ✅ Reescrito |
| docs/README.md (este índice) | B — desactualizado | ✅ Reescrito |
| docs/TESTING.md | B — desactualizado | ✅ Actualizado |
| docs/ARCHITECTURE.md | B — desactualizado | ✅ Actualizado |
| docs/SECURITY.md | B — desactualizado | ✅ Actualizado |
| docs/OFFLINE-SYNC.md | B — desactualizado (falta S4/S5) | ✅ Actualizado |
| docs/IMPLEMENTATION-PLAN.md | B — desactualizado | ✅ Actualizado |
| docs/web/WEB-UI-BLUEPRINT.md | B — desactualizado (web ya no es MOCK) | ✅ Marcado histórico |
| docs/ENGRAM-PROTOCOL.md · docs/GRAPHIFY-PROTOCOL.md | A — vigente | Sin cambios |
| docs/GRAPHIFY-CURRENT.md | E — regenerable | Nota de regenerable |
| docs/decisions/ADR-INFRA-NAMING.md | A — decisión vigente | Sin cambios |
| DAILY-SYSTEM-CONTEXT-HANDOFF.md | B — desactualizado | ✅ Regenerado |
| DAILY-SYSTEM-*.md (6 archivos) | C — histórico | ✅ Archivados en `docs/historical/` |
| docs/DOCUMENTO-MAESTRO-*-CERRADO.md · -v1.3.md | C/D — histórico/redundante | ✅ Archivados en `docs/historical/` |
| docs/GRAPHIFY-AUDIT.md | C — histórico | ✅ Archivado en `docs/historical/` |
| docs/ui-audit/* (auditoría + baseline) | C — histórico (evidencia) | ✅ Banner archivado in-place |
| docs/ui-audit/screenshots/ · docs/assets/readme/ | E — regenerable | Web regenerado con panel productivo |

---

## Ruta de trabajo canónica

- **Checkout operativo:** `/home/jesus/proyectos/daily-system`
- **Rama de trabajo:** `product/web-premium-v1` (HEAD: `git rev-parse HEAD`; baseline `bbb3e102`)
- **master:** `486d08b` (legacy — no contiene el hardening)

## Estado actual resumido

| Bloque | Estado |
|---|---|
| M0-M2 (backend financiero) | ✅ PASS |
| M0-M3 base (planes, límites) | ✅ PASS |
| B1-B7 (auth, device, activation) | ✅ PASS |
| S0-S5 (sync/hardening) | ✅ PASS |
| Web Premium (`apps/web/` productivo) | ✅ PASS (Next.js 16, CI 3/3) |
| Backend CI · Web CI · UI Gate | ✅ PASS |
| M4 (OCR) | ⏳ PENDIENTE |
| M5 (score/chatbot) | ⏳ PENDIENTE |
| M6 (producción) | ⏳ PENDIENTE |
