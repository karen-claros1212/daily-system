# Mobile UI Baseline — Daily System

**Fecha:** 2026-07-31
**BASE_SHA:** 57a3336
**Flutter:** 3.44.0 • Dart 3.12.0
**Gato base:** flutter analyze = 0 issues, flutter test = 7/7 passing

---

## Pantalla: Login

**Propósito:** Autenticar cobrador
**Acción primaria:** INICIAR SESIÓN
**Problemas visuales:**
- Logo genérico: `Icons.account_balance_wallet` (billetera)
- Texto técnico visible: "Flutter 3.44 • Material 3"
- "Demo: datos precargados" visible en login principal
- Animación elástica larga (800ms con elasticOut)
- Sombra pesada en logo (blurRadius: 20)
**Problemas de jerarquía:** Subtítulo "Cobro diario offline" opaco, sin tagline de valor
**Problemas de accesibilidad:** Sin `Semantics` en botón principal, sin `Tooltip` en icono
**Estados faltantes:** Ningún estado de carga o error
**Hardcodes:** Colores directos, fontSize hardcodeados
**Duplicaciones:** `compactButton` usada aquí y en otras pantallas
**Riesgo de regresión:** Medio — animación larga afecta UX bajo prisa

## Pantalla: Inicio

**Propósito:** Resumen de jornada y métricas principales
**Acción primaria:** CONTINUAR RUTA / INICIAR JORNADA
**Problemas visuales:** Gradiente sutil en header, métricas sin formato money hero
**Problemas de jerarquía:** Demasiadas métricas simultáneas (>3 protagonistas)
**Problemas de accesibilidad:** Sin `MergeSemantics` en cards de métricas
**Estados faltantes:** Sin indicador de estado offline/online
**Hardcodes:** Colores y tamaños dispersos
**Riesgo de regresión:** Bajo — estructura estable

## Pantalla: Selección de ruta / Cobros

**Propósito:** Lista de clientes y cobros del día
**Acción primaria:** REGISTRAR ABONO
**Problemas visuales:** `CircularProgressIndicator` como único estado de carga
**Problemas de jerarquía:** Tarjetas de cliente sin semáforo claro (color + icono + texto)
**Problemas de accesibilidad:** Chips de filtro sin `Semantics.button`
**Estados faltantes:** Sin estado vacío, sin estado sin conexión
**Hardcodes:** `BorderRadius.circular(16)`, `BorderRadius.circular(8)` dispersos
**Duplicaciones:** Tarjetas de cliente repetidas con lógica similar
**Riesgo de regresión:** Alto — lista grande con `Column` vs `ListView.builder`

## Pantalla: Hoja viva / Cliente

**Propósito:** Detalle del crédito y operaciones
**Acción primaria:** REGISTRAR ABONO
**Problemas visuales:** Sin formato COP en montos, sin money hero
**Problemas de jerarquía:** Información secundaria mezclada con primaria
**Problemas de accesibilidad:** Sin `Tooltip` en botones de icono
**Estados faltantes:** Sin skeleton loading, sin estado de error recuperable
**Hardcodes:** Colores de estado hardcodeados (0xFF2E7D32, 0xFFF57F17)
**Riesgo de regresión:** Medio — cambios en formato de dinero afectan cálculos

## Pantalla: Pago

**Propósito:** Registrar abono/pago
**Acción primaria:** CONFIRMAR PAGO
**Problemas visuales:** Teclado numérico no específico, chips sugeridos ausentes
**Problemas de jerarquía:** Resumen previo a confirmar no prominente
**Problemas de accesibilidad:** Sin `Semantics` en campo de monto
**Estados faltantes:** Sin bloqueo de doble toque durante registro
**Hardcodes:** Colores de confirmación hardcodeados
**Riesgo de regresión:** Alto — idempotencia debe conservarse

## Pantalla: Movimientos

**Propósito:** Registrar movimientos de caja (entrega, gasto, ahorro, etc.)
**Acción primaria:** REGISTRAR MOVIMIENTO
**Problemas visuales:** Selector de tipo sin semáforo visual claro
**Problemas de jerarquía:** Impacto en caja no visible antes de confirmar
**Problemas de accesibilidad:** Sin asociación de error al campo
**Estados faltantes:** Sin estado sin conexión
**Hardcodes:** Tipos de movimiento hardcodeados
**Riesgo de regresión:** Medio — afecta servicio de caja

## Pantalla: Caja

**Propósito:** Conciliación de caja (esperado vs contado)
**Acción primaria:** CONFIRMAR CUADRE
**Problemas visuales:** Diferencia solo con color (verde/rojo), sin icono + texto
**Problemas de jerarquía:** Desglose no progresivo
**Problemas de accesibilidad:** Sin `MergeSemantics` en resumen de caja
**Estados faltantes:** Sin "Caja cuadrada", "Falta dinero", "Sobra dinero" con texto
**Hardcodes:** Colores 0xFF2E7D32, 0xFFFFEBEE, 0xFFC62828
**Riesgo de regresión:** Alto — CajaService no tocar pero UI depende de sus resultados

## Pantalla: Cierre de jornada

**Propósito:** Cerrar jornada con evidencia PDF
**Acción primaria:** CONFIRMAR CIERRE
**Problemas visuales:** Sin bottom sheet/modal de confirmación
**Problemas de jerarquía:** Advertencia post-cierre no prominente
**Problemas de accesibilidad:** Sin `Tooltip` en botones de acción secundaria
**Estados faltantes:** Sin pantalla de éxito post-cierre
**Hardcodes:** Colores y textos hardcodeados
**Riesgo de regresión:** Alto — JornadaGuard y PDFService afectados

## Pantalla: Historial

**Propósito:** Ver jornadas anteriores y documentos
**Acción primaria:** ABRIR PDF de jornada
**Problemas visuales:** Timeline sin skeleton loading
**Problemas de jerarquía:** Estados de sync no claros
**Problemas de accesibilidad:** Sin `Semantics` en items de timeline
**Estados faltantes:** Sin estado vacío
**Hardcodes:** Colores de estado hardcodeados (CLOSED_SYNCED, OPEN, etc.)
**Riesgo de regresión:** Bajo — solo lectura

## Pantalla: Más / Configuración

**Propósito:** Sincronización, documentos, apariencia, acerca de
**Acción primaria:** Variable según sección
**Problemas visuales:** Lista plana sin agrupación visual
**Problemas de jerarquía:** Demo data mezclada con opciones reales
**Problemas de accesibilidad:** Sin orden lógico de foco
**Estados faltantes:** Sin indicador de versión en "Acerca de"
**Hardcodes:** Strings técnicas ("snapshot", "hash", "sync_queue")
**Riesgo de regresión:** Bajo — configuración

---

## Resumen de hallazgos

| Categoría | Cantidad |
|---|---|
| Hardcodes de color | 40+ |
| Textos técnicos en UI | 6 |
| Animaciones largas (>350ms) | 1 |
| Sin estados de carga skeleton | 8 pantallas |
| Sin accesibilidad semántica | 9 pantallas |
| Colores como único indicador | 3 pantallas |
| Duplicaciones de widgets | 4+ |
