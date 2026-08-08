# DAILY SYSTEM — BLOQUE 5 · MATRIZ DE PARIDAD FINANCIERA BACKEND–MÓVIL

> Documento de trabajo del Bloque 5 (autorizado por dictamen 2026-08-06).
> **Estado: PASS (2026-08-06).** Backend = **autoridad financiera**. El móvil puede calcular offline, pero sus resultados deben ser deterministas y equivalentes al backend.
> Este documento define una única definición documentada por regla, los casos sintéticos, los valores esperados y la clasificación de cada diferencia.
> Gates finales: paridad móvil 14/14 · móvil completo 82/82 · backend 166/166 · `flutter analyze` limpio · UI Gate PASS · `git diff --check` OK (detalle en §10).

---

## 1. Reglas canónicas (fuente única)

Fuente: `docs/DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md` §§4.1–4.3, 4.6–4.7.

| Regla | Definición canónica | Implementación backend |
|---|---|---|
| abono_neto | `Σ(PAYMENT) − Σ(REVERSAL)` por crédito | `payment_service.get_net_paid` |
| saldo | `total_contractual − abono_neto` | `payment_service.get_saldo` |
| cuotas_pagadas | `abono_neto // cuota` (división entera) | `payment_service.get_cuotas_pagadas`, `hoja_viva_service` |
| pico | `abono_neto % cuota` (residuo) | `payment_service.get_pico_amount`, `hoja_viva_service` |
| mora_legacy | `max((fecha_reporte − 1 día − fecha_inicio).days − cuotas_pagadas, 0)` | `calculation_service.calcular_mora_legacy`, `hoja_viva_service` |
| mora_real | derivada del calendario contractual (cuotas vencidas) | `get_vence_hoy_count` (parcial) |
| semáforo | `GRIS` mientras no exista score real | `hoja_viva_service` (siempre `GRIS`) |
| dc_legacy | `Σ cuota` de todos los créditos `ACTIVO` | `hoja_viva_service` |
| vence_hoy | `Σ monto` de cuotas `PENDIENTE` con `fecha_vencimiento = fecha_reporte` | `hoja_viva_service` / `payment_service.get_vence_hoy_count` |
| efectivo_esperado | `opening_base + opening_carry + (Σ PAYMENT − Σ REVERSAL) + otros_entrada − desembolsos − vales − gastos − ahorro − entregas` | `caja_service.calcular_cadena_caja` |
| diferencia | `contado − efectivo_esperado` | `jornada_service.cerrar_jornada` |
| opening_carry(D) | `sobrante_manana(D−1)` = contado de la jornada anterior | `jornada_service.get_carry_for_date` |
| sobrante_manana(D) | `contado(D)` | `jornada_service.cerrar_jornada` |
| renovación | `saldo_refinanciado = saldo_anterior − pago_efectivo`; `dinero_nuevo_entregado = monto_nuevo − saldo_refinanciado`; `monto_final_con_recargo = monto_nuevo + (monto_nuevo × recargo_pct // 100)` | `calculation_service.calcular_renovacion`, `renewal_service` |

Reglas de impresión (documento §4.1): **cero se imprime como blanco**; aplica a `Mora`, `Pico` y `#_C`.

---

## 2. Método de comparación

- El backend es la referencia: `resultado_backend` es el valor esperado.
- `resultado_móvil` se obtiene ejecutando los servicios reales del móvil contra SQLite real (FFI) con los mismos datos.
- Cada diferencia se clasifica como:

| Clasificación | Significado |
|---|---|
| BUG BACKEND | El backend no cumple la regla canónica |
| BUG MÓVIL | El móvil no cumple la regla canónica |
| DIFERENCIA DE REPRESENTACIÓN | Misma magnitud, formato o campo distinto |
| REGLA NO DEFINIDA | No existe definición canónica (se documenta, no se corrige sin autorización) |
| SIN DIVERGENCIA | Ambos lados producen el mismo resultado |

---

## 3. Casos de la matriz

Convenciones de los casos:
- `cuota` en COP, `n` número de cuotas, `total = cuota × n`, `monto` = principal.
- `fecha_inicio` y `fecha_reporte` fijas por caso (el móvil las recibe como parámetro opcional de prueba).
- Pago y reverso se registran con los servicios reales de cada lado.

### C-01 Pago exacto de una cuota

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| total | 200.000 |
| abono (1 pago) | 5.000 |

| Regla | Backend (esperado) |
|---|---|
| abono_neto | 5.000 |
| saldo | 195.000 |
| cuotas_pagadas | 1 |
| pico | 0 |
| mora_legacy (reporte = inicio + 10d) | (10 − 1 − 1) = 8 |

### C-02 Pago parcial menor que una cuota

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| total | 200.000 |
| abono (1 pago) | 1.500 |

| Regla | Backend (esperado) |
|---|---|
| abono_neto | 1.500 |
| saldo | 198.500 |
| cuotas_pagadas | 0 |
| pico | 1.500 |

### C-03 Pago de varias cuotas exactas

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| total | 200.000 |
| abono (1 pago) | 10.000 |

| Regla | Backend (esperado) |
|---|---|
| abono_neto | 10.000 |
| saldo | 190.000 |
| cuotas_pagadas | 2 |
| pico | 0 |

### C-04 Pago superior a una cuota con pico

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| total | 200.000 |
| abono (1 pago) | 12.000 |

| Regla | Backend (esperado) |
|---|---|
| abono_neto | 12.000 |
| saldo | 188.000 |
| cuotas_pagadas | 2 |
| pico | 2.000 |

### C-05 Pago total del crédito

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| total | 200.000 |
| abono (1 pago) | 200.000 |

| Regla | Backend (esperado) |
|---|---|
| abono_neto | 200.000 |
| saldo | 0 |
| cuotas_pagadas | 40 |
| pico | 0 |

### C-06 Reverso parcial (pago 10.000, reverso 5.000)

> **REGLA NO DEFINIDA (documentado, no implementado):** ni el backend
> (`reverse_payment`, reverso = monto del pago original) ni el móvil
> (`reversarPago`, `monto: pagoOriginal.monto`) soportan reverso parcial.
> El caso se documenta para la regla, pero no hay divergencia que corregir.

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| total | 200.000 |
| pago | 10.000 |
| reverso | 5.000 |

| Regla | Backend (esperado) |
|---|---|
| abono_neto | 5.000 |
| saldo | 195.000 |
| cuotas_pagadas | 1 |
| pico | 0 |

### C-07 Reverso total (pago 5.000, reverso 5.000)

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| total | 200.000 |
| pago | 5.000 |
| reverso | 5.000 |

| Regla | Backend (esperado) |
|---|---|
| abono_neto | 0 |
| saldo | 200.000 |
| cuotas_pagadas | 0 |
| pico | 0 |

### C-08 Mora legacy (15 días sin abono)

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| total | 200.000 |
| fecha_inicio | `R−15` |
| fecha_reporte (R) | fija |
| abono | 0 |

| Regla | Backend (esperado) |
|---|---|
| cuotas_pagadas | 0 |
| mora_legacy | (15 − 1 − 0) = **14** |

### C-09 Vence hoy

| Campo | Valor |
|---|---|
| cuota | 5.000 |
| n | 40 |
| fecha_inicio | `R−10` |
| cuota programada con vencimiento `= R` | 1 × PENDIENTE |
| cuota programada con vencimiento `< R` | 2 × PENDIENTE |

| Regla | Backend (esperado) |
|---|---|
| vence_hoy (count) | 1 |
| vence_hoy_monto | 5.000 |
| mora_legacy | (10 − 1 − 0) = 9 |

### C-10 Caja con todos los flujos físicos

> Reverso TOTAL (único soportado en ambas plataformas). El REVERSAL queda
> ligado a la jornada del pago original (ver BUG BACKEND en §6).

| Flujo | Monto |
|---|---|
| opening_base | 100.000 |
| opening_carry | 0 |
| recaudo (PAYMENT) | 50.000 + 20.000 |
| reversos (REVERSAL) | 50.000 (reverso total del pago de 50.000) |
| gastos (GASOLINA+OFICINA) | 15.000 |
| ahorro | 5.000 |
| vales | 3.000 |
| entregas | 2.000 |
| recibidos (otros_entrada) | 4.000 |
| desembolsos | 1.000 |

| Regla | Backend (esperado) |
|---|---|
| recaudo_real (neto) | 20.000 |
| efectivo_esperado | 100.000 + 0 + 20.000 + 4.000 − 15.000 − 5.000 − 3.000 − 2.000 − 1.000 = **98.000** |

### C-11 Cierre con diferencia

| Campo | Valor |
|---|---|
| efectivo_esperado | 118.000 |
| efectivo_contado | 120.000 |

| Regla | Backend (esperado) |
|---|---|
| diferencia | 2.000 (exige motivo) |
| sobrante_manana | 120.000 |

### C-12 Carry de la jornada siguiente

| Campo | Valor |
|---|---|
| jornada D cierre | contado = 120.000 → sobrante_manana = 120.000 |
| jornada D+1 apertura | opening_carry |

| Regla | Backend (esperado) |
|---|---|
| opening_carry(D+1) | 120.000 |

### C-13 Renovación (fixture del documento)

| Campo | Valor |
|---|---|
| saldo_anterior | 2.740 |
| pago_efectivo | 0 |
| monto_nuevo | 3.000 |
| recargo_pct | 20 |

| Regla | Backend (esperado) |
|---|---|
| saldo_refinanciado | 2.740 |
| dinero_nuevo_entregado | 260 |
| monto_final_con_recargo | 3.600 |

### C-14 Semáforo sin score real

| Regla | Backend (esperado) |
|---|---|
| semaforo (todo crédito) | `GRIS` |

### C-15 DC legacy y vence hoy a nivel ruta

Créditos ACTIVOS de la ruta (cuotas): `[5000, 3000, 7000, 4000, 6000]`.

| Regla | Backend (esperado) |
|---|---|
| dc_legacy | 25.000 |
| vence_hoy | cuotas PENDIENTE con vencimiento = reporte (0 en el caso base) |

### C-16 Snapshot financiero de cierre

| Regla | Backend (esperado) |
|---|---|
| snapshot incluye | opening_base, opening_carry, recaudo_real, desembolsos, vales, gastos, ahorro, entregas, otros_entrada, efectivo_esperado, efectivo_contado, diferencia, diferencia_motivo, pagos_count, movimientos_count, renovaciones_count |
| hash | `_canonical_json_hash(snapshot)` (backend) / `JornadaSnapshot.computeHash` (móvil), JSON ordenado |

---

## 4. Resultado backend (autoridad)

Generado por `apps/api/src/tests/test_b5_paridad.py` (nuevo). Cada caso parametrizado usa las funciones canónicas del backend y el servicio real de pago/cierre. PASS = el backend cumple la regla.

```
pytest src/tests/test_b5_paridad.py -q
18 passed  (2026-08-06)
Suite completa: 166 passed
```

## 5. Resultado móvil

Generado por `apps/mobile/test/paridad_b5_test.dart` (nuevo) sobre los servicios reales (`HojaVivaService`, `CajaService`, `PagoService`, `JornadaService`) y SQLite real.

```
flutter test test/paridad_b5_test.dart -q
14 tests, all passed  (2026-08-06)
Suite móvil completa: 79 passed, 3 goldens hoja viva pendientes de regenerar (ver §8)
```

## 6. Divergencias iniciales

| Caso | Regla | Backend | Móvil (antes) | Clasificación |
|---|---|---|---|---|
| C-01..C-05 | pico | `abono % cuota` | `cuota × max(1, n − pagadas)` | BUG MÓVIL → **corregido** (`hoja_viva_service.dart`) |
| C-01..C-05 | cuotas_pagadas | `abono // cuota` | `COUNT(cuota PAGADO)` | BUG MÓVIL → **corregido** (`hoja_viva_service.dart`) |
| C-08 | mora_legacy | `(reporte−1−inicio).days − #_C` | `COUNT(PENDIENTE vencida)` (es mora_real) | BUG MÓVIL → **corregido** (`hoja_viva_service.dart`) |
| C-14 | semáforo | `GRIS` | heurística VERDE/AMARILLO/ROJO | BUG MÓVIL → **corregido** (`hoja_viva_service.dart`) |
| C-12 | opening_carry | `sobrante_manana(D−1)` | siempre 0 (no se persiste carry) | BUG MÓVIL → **corregido** (`jornada_service.dart`: carry en apertura, `sobrante_manana` en cierre) |
| C-10 | efectivo_esperado | fórmula flujos físicos | fórmula equivalente con signo expandido | SIN DIVERGENCIA |
| C-10 | recaudo_real con reverso | **BUG BACKEND (corregido):** el REVERSAL no heredaba `jornada_id` del pago original y nunca restaba del recaudo de la jornada | el REVERSAL se crea con `jornada_id` (exige misma jornada) y resta de `recaudo_real` | BUG BACKEND → corregido en `payment_service.reverse_payment` |
| C-10 | fórmula caja | **duplicación contradictoria (corregido):** el helper puro `calcular_caja` omitía `entregas`/`recibidos` | — | BUG BACKEND → alineado con la fórmula canónica (Parágrafo PASS: sin duplicación contradictoria) |
| C-06 | reverso parcial | no soportado (`monto = original.monto`) | no soportado (`monto: pagoOriginal.monto`) | REGLA NO DEFINIDA (documentado, no implementado) |
| C-16 | hash snapshot | `_canonical_json_hash` | `JornadaSnapshot.computeHash` | DIFERENCIA DE REPRESENTACIÓN (ver §7) |
| C-15 | vence_hoy / dc_legacy | presente en API | no emitido por servicios móviles | REGLA NO DEFINIDA (móvil no lo muestra) |
| C-13 | renovación | `renewal_service` completo | no existe en servicios móviles | REGLA NO DEFINIDA (fuera de alcance móvil actual) |

## 7. Notas de clasificación

- **C-10 SIN DIVERGENCIA (fórmula):** el backend calcula `recaudo_real = PAYMENT − REVERSAL` y suma `otros_entrada`; el móvil suma `PAYMENT` por separado y resta `REVERSAL` y suma `recibidos`. Ambas formas producen el mismo `efectivo_esperado`. Es la misma fórmula con el signo expandido.
- **BUG BACKEND (recaudo_real):** el REVERSAL no heredaba `jornada_id` del pago original, por lo que `calcular_cadena_caja` (filtra por `jornada_id`) nunca lo restaba del recaudo de la jornada → efectivo sobrecontado en 50.000. **Corregido:** `reverse_payment` ahora copia `jornada_id=original.jornada_id`, igualando la semántica móvil (`reversarPago` exige la misma jornada y crea el REVERSAL con ella). Verificado por `test_calcular_cadena_caja_integracion`.
- **BUG BACKEND (duplicación contradictoria):** el helper puro `calcular_caja` (solo pruebas) omitía `entregas` y `recibidos`, contradiciendo la fórmula canónica. **Corregido:** ahora acepta `entregas`/`recibidos` (defaults `[]`, retrocompatible con `test_calculations.py`). Prohibido por el criterio PASS "una única definición por regla".
- **C-06 REGLA NO DEFINIDA:** el reverso parcial no existe en ninguna plataforma (el reverso siempre copia el monto del pago original). Se documenta el valor esperado por la regla, pero no se implementa en Bloque 5.
- **C-16 DIFERENCIA DE REPRESENTACIÓN:** el hash canónico de cierre no es una cifra financiera; la paridad exige que ambas partes validen contra un snapshot canónico común. El backend ya valida en `sincronizar_cierre`; el móvil genera su propio hash. La convergencia de formato pertenece al Bloque 6 (sincronización real), no al Bloque 5.
- **C-15 / C-13 REGLA NO DEFINIDA (móvil):** el móvil no expone DC/vence hoy/renovación en sus servicios ni en su UI. No se inventa una implementación en este bloque; se documenta como deuda para cuando la sincronización/renovación móvil exista.

## 8. Criterio PASS del Bloque 5

- cero divergencias en la matriz para las reglas que el móvil implementa;
- una única definición documentada por regla (§1);
- pruebas unitarias y de integración (backend `test_b5_paridad.py`, móvil `paridad_b5_test.dart`);
- no duplicación contradictoria de fórmulas.

## 9. Pendientes de autorización (resueltos 2026-08-06)

- **Goldens regenerados (autorización concedida):** únicamente `screen_cobros.png`, `screen_cobros_dark.png` y `screen_cobros_tablet.png` (CobrosShell/Hoja Viva). Verificado por análisis de píxeles que la diferencia se limita a: resumen GRIS (3 chips → 1 chip) y cifras financieras (saldo, cuotas_pagadas, pico, mora). Sin cambios de navegación, estructura, tipografía, tema, espaciado o tamaños; ninguna otra pantalla alterada.
- **Decisión de UI (opción b):** el resumen de hoja viva muestra un único chip gris con el conteo real de clientes sin score, etiqueta `GRIS: N`. Se retiraron los chips fijos VERDE/AMARILLO/ROJO en cero (`hoja_viva_screen.dart`). Cada cliente conserva la representación gris y la etiqueta "Sin historial". No se implementa clasificación VERDE/AMARILLO/ROJO ni score hasta existir `score_snapshot` real y regla empresarial aprobada.

## 10. Cierre del Bloque 5 (PASS)

```
paridad móvil     apps/mobile/test/paridad_b5_test.dart   14/14 PASS
móvil completo    flutter test                            82/82 PASS
backend           pytest src/tests/ -q                    166/166 PASS
flutter analyze   apps/mobile                             No issues found
UI Gate           scripts/ci/ui_gate.sh                   ALL PASSED
git diff --check                                          OK
```

Solo se modificaron los 3 goldens de CobrosShell/Hoja Viva, justificado por corrección financiera legítima (cifras corregidas + resumen GRIS). Sin commit, push, merge, deploy ni regeneración adicional de goldens.
