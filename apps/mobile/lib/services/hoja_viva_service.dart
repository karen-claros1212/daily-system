import '../database/database.dart';

class HojaVivaService {
  static Future<List<Map<String, dynamic>>> getHojaViva(
    String rutaId,
    String negocioId, {
    DateTime? reportDate,
  }) async {
    final db = await database;
    final reporte = reportDate ?? DateTime.now();

    // Get active credits for this route
    final creditos = await db.query('credito',
        where: 'ruta_id = ? AND estado = ?',
        whereArgs: [rutaId, 'ACTIVO']);

    final List<Map<String, dynamic>> clientes = [];

    for (final credito in creditos) {
      final creditoId = credito['id'] as String;

      // Get cliente info
      final clientesList = await db.query('cliente',
          where: 'id = ?',
          whereArgs: [credito['cliente_id']]);
      if (clientesList.isEmpty) continue;
      final cliente = clientesList.first;

      // Abono neto = Σ(PAYMENT) − Σ(REVERSAL) por crédito
      final pagosResult = await db.rawQuery('''
        SELECT COALESCE(SUM(
          CASE WHEN tipo = 'REVERSAL' THEN -monto ELSE monto END
        ), 0) as net_pagos
        FROM pago
        WHERE credito_id = ?
      ''', [creditoId]);
      final abonoNeto = (pagosResult.first['net_pagos'] as int?) ?? 0;

      // Saldo = total − abono (canónica)
      final total = credito['total'] as int;
      final saldoPendiente = total - abonoNeto;

      final cuota = credito['cuota'] as int;

      // Cuotas pagadas = abono ÷ cuota (división entera, canónica)
      final cuotasPagadas = abonoNeto ~/ cuota;

      // Pico = abono mód cuota (canónica)
      final pico = abonoNeto % cuota;

      // Mora legacy = (reporte − 1 día − inicio).days − cuotas_pagadas, mínimo 0
      final mora = calcularMoraLegacy(reporte, credito['fecha_inicio'] as String?, cuotasPagadas);

      // Sin score real: el semáforo es siempre GRIS (canónica)
      final semaforo = 'GRIS';

      clientes.add({
        'credito_id': creditoId,
        'cliente_nombre': '${cliente['primer_apellido']} ${cliente['nombres']}',
        'cliente_id': cliente['id'],
        'cuota': credito['cuota'],
        'saldo': saldoPendiente,
        'mora_legacy': mora,
        'pico': pico,
        'cuotas_pagadas': cuotasPagadas,
        'n_cuotas': credito['n_cuotas'],
        'estado_credito': credito['estado'],
        'semaforo': semaforo,
        'total': total,
      });
    }

    return clientes;
  }

  /// Mora legacy: (fecha_reporte − 1 día − inicia).days − cuotas_pagadas, mínimo 0.
  ///
  /// Cuenta días calendario corridos (sin excluir domingos ni festivos) y
  /// descuenta cuotas pagadas, como define el documento maestro (Parte 4.1).
  static int calcularMoraLegacy(DateTime reporte, String? fechaInicioStr, int cuotasPagadas) {
    if (fechaInicioStr == null || fechaInicioStr.isEmpty) return 0;
    final inicio = DateTime.parse(fechaInicioStr);
    final reporteDay = DateTime(reporte.year, reporte.month, reporte.day);
    final inicioDay = DateTime(inicio.year, inicio.month, inicio.day);
    final ancla = reporteDay.subtract(const Duration(days: 1));
    final diasCorridos = ancla.difference(inicioDay).inDays;
    final mora = diasCorridos - cuotasPagadas;
    return mora < 0 ? 0 : mora;
  }
}
