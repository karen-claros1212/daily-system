// ─── Navigation Enums — Replaces magic numbers ────────────────────
// Uses ordinal (auto-assigned by Dart) instead of custom index.

/// Main shell tabs (NavigationBar indices)
enum MainSection {
  /// Inicio — home dashboard
  inicio,
  /// Cobros — route + hoja viva + pago + movimientos + caja + cierre
  cobros,
  /// Caja — caja summary
  caja,
  /// Más — historial + settings
  mas,
}

/// Cobros sub-sections (state machine in CobrosShell)
enum CobrosSection {
  /// Select a route (no jornada active)
  seleccionarRuta,
  /// Hoja viva — cartera and semáforo
  hojaViva,
  /// Pago — register payment for a creditor
  pago,
  /// Movimientos — gastos, ahorro, vales
  movimientos,
  /// Caja — efectivo esperado vs contado
  caja,
  /// Cerrar jornada — jornada cierre screen
  cerrarJornada,
}
