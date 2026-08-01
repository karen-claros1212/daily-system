# Evidencia: integration test — Jornada de Cierre

- **Fecha:** 2026-07-31
- **Dispositivo:** emulator-5554 (API 34, x86_64)
- **Comando:** `flutter test integration_test/jornada_cierre_test.dart -d emulator-5554 --dart-define=DAILY_DEMO=true`
- **Resultado:** 17/17 PASS
- **Log completo:** `jornada_cierre_integration_test_2026-07-31.log` (no versionado, `*.log` en .gitignore)

## Grupos

| Grupo | Tests | Resultado |
|---|---|---|
| A. SERVICE TEST — `CajaService.calcularCaja()` + `cerrarJornada` | 3 | PASS |
| B. UI TEST — `JornadaCierreScreen` flujo real (input + botón + confirmación) | 4 | PASS |
| C. PERSISTENCIA — Verificación DB + idempotencia + hash + PDF | 10 | PASS |

## Cobertura verificada

- Cálculo canónico `esperado = 100000` (opening_base + carry + recaudo − reversales − gastos − ahorro − entregas + recibidos).
- Cierre real desde UI: input `contado`, tap `TERMINAR JORNADA`, confirmación `JORNADA CERRADA`.
- Persistencia: `CLOSED_LOCAL_PENDING_SYNC`, `esperado`, `contado`, `diferencia`, `cerrada_local_el`.
- PDF generado tras cierre: existe, tamaño > 0, encabezado `%PDF`, hash validado contra snapshot.
- PDF corrupto se regenera (escritura de bytes basura → regeneración válida).
- Snapshot inmutable: `trg_snapshot_no_update` / `trg_snapshot_no_delete` bloquean UPDATE/DELETE (`DS_SNAPSHOT_IMMUTABLE`).
- Idempotencia: misma clave + mismos datos → un solo pago; clave distinta → dos pagos legítimos; misma clave + monto distinto → `IdempotenciaConflictoException`.
- Pagos/movimientos posteriores al cierre bloqueados (`JornadaCerradaException`, trigger `DS_JORNADA_NOT_OPEN`).
- Migración V3: tabla `jornada_documento`, trigger `trg_doc_require_valid_jornada`, índice `idx_doc_jornada_tipo`.

## Hallazgo corregido

`PdfService._recomputeSnapshotHash` calculaba el hash con `jornadaId: ''`, mientras que
`JornadaService.cerrarJornada` lo almacena con el `jornada_id` real. Todo
`generarPdfDesdeSnapshot` fallaba con `Snapshot corrupto: hash mismatch`, por lo que el PDF
de cierre nunca se escribía. Corregido pasando el `jornadaId` real.
