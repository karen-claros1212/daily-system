# Documentación — Daily System

> **Verdad primaria:** Este índice organiza la documentación del repositorio.
> Consulte [`STATUS.md`](STATUS.md) para el estado productivo verificado.
> Consulte [DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md](../DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md) para la continuidad entre sesiones de agente.

---

## Índice

| Documento | Tipo | Propósito |
|---|---|---|
| [STATUS.md](STATUS.md) | **Estado vivo** | Estado productivo actual verificado (números, rama, HEAD, gates). Primera lectura obligatoria. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Normativo | Arquitectura vigente: capas, flujos, contratos. |
| [SECURITY.md](SECURITY.md) | Normativo | Auth, device binding, tenant/ruta isolation, idempotencia, revocación. |
| [OFFLINE-SYNC.md](OFFLINE-SYNC.md) | Normativo | Contrato de sync offline S0-S3: estado por bloque. |
| [TESTING.md](TESTING.md) | Estado vivo | Suites, gates, comandos, CI. |
| [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) | Estado vivo | Roadmap por bloques (qué sigue). |
| [ENGRAM-PROTOCOL.md](ENGRAM-PROTOCOL.md) | Normativo | Protocolo Engram (memoria de agentes). |
| [GRAPHIFY-*](GRAPHIFY-CURRENT.md) | Referencia | Grafo de conocimiento. |
| [ADR-INFRA-NAMING.md](decisions/ADR-INFRA-NAMING.md) | Decisión | Naming de infraestructura. |
| [WEB-UI-BLUEPRINT.md](web/WEB-UI-BLUEPRINT.md) | Normativo | Prototipo web MOCK (no productivo). |
| [DOCUMENTO-MAESTRO-v1.3-CERRADO.md](DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md) | Normativo | Especificaciones originales. |

---

## Clasificación de documentos

| Tipo | Significado | Caducidad |
|---|---|---|
| **Estado vivo** | Refleja el estado verificado del árbol de código actual. Se actualiza con cada verificación. | Al cambio de estado (commit nuevo en hardening). |
| **Normativo** | Define cómo debe comportar el sistema. No cambia sin un commit de código que lo justifique. | Al cambio de arquitectura/contracto. |
| **Referencia** | Herramientas o artefactos auxiliares (grafo, protocolo). | Al cambio de herramienta. |
| **Decisión** | Registro de una decisión arquitectónica (ADR). | Aprobada; no caduca salvo reversión. |
| **Histórico** | Capturas de estados anteriores (handoff de auditoría, notas de sesión). Se archivan en `docs/historical/` al reconciliar. | Información histórica; no usar como verdad vigente. |

---

## Ruta de trabajo canónica

- **Checkout operativo:** `/home/jesus/proyectos/daily-system`
- **Rama de trabajo:** `hardening/b1-b7-audit` (HEAD verificado: `c0a3a9c`)
- **master:** `486d08b` (no contiene el hardening B1-B7)

## Estado actual resumido

| Bloque | Estado |
|---|---|
| M0-M2 (backend financiero) | ✅ PASS |
| B1-B7 (auth, device, activation) | ✅ PASS (c0a3a9c) |
| S0 (session maintenance) | ✅ PASS |
| S1 (route isolation) | ✅ PASS |
| S2 (server→mobile pull + persist) | ✅ PASS |
| S3 (mobile→server outbox/ACK/retry) | ⏳ PENDIENTE |
| Web productivo (`apps/web/`) | ⏳ PENDIENTE (MOCK solo) |
| M4 (OCR) | ⏳ PENDIENTE |
| M5 (score/chatbot) | ⏳ PENDIENTE |
| M6 (producción) | ⏳ PENDIENTE |
