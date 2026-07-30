import 'package:sqflite/sqflite.dart';
import 'package:intl/intl.dart';
import '../database/database.dart';

class HojaVivaService {
  static Future<List<Map<String, dynamic>>> getHojaViva(String rutaId, String negocioId) async {
    final db = await database;

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

      // Calculate pagos total for this credit
      final pagosResult = await db.rawQuery('''
        SELECT COALESCE(SUM(
          CASE WHEN tipo = 'REVERSAL' THEN -monto ELSE monto END
        ), 0) as net_pagos
        FROM pago
        WHERE credito_id = ?
      ''', [creditoId]);
      final netPagos = (pagosResult.first['net_pagos'] as int?) ?? 0;

      // Calculate saldo pendiente
      final total = credito['total'] as int;
      final saldoPendiente = total - netPagos;

      // Count paid cuotas
      final cuotasPagadas = await _countCuotasPagadas(db, creditoId);

      // Calculate pico (cuota * max(1, n_cuotas - cuotas_pagadas))
      final cuota = credito['cuota'] as int;
      final nCuotas = credito['n_cuotas'] as int;
      final pico = cuota * (nCuotas - cuotasPagadas).clamp(1, nCuotas);

      // Calculate mora legacy
      final mora = await _calcularMoraLegacy(db, creditoId);

      // Determine semaforo based on mora
      final semaforo = _determinarSemaforo(mora, cuotasPagadas, nCuotas);

      clientes.add({
        'credito_id': creditoId,
        'cliente_nombre': '${cliente['primer_apellido']} ${cliente['nombres']}',
        'cliente_id': cliente['id'],
        'cuota': credito['cuota'],
        'saldo': saldoPendiente,
        'mora_legacy': mora,
        'pico': pico,
        'cuotas_pagadas': cuotasPagadas,
        'n_cuotas': nCuotas,
        'estado_credito': credito['estado'],
        'semaforo': semaforo,
        'total': total,
      });
    }

    return clientes;
  }

  static Future<int> _countCuotasPagadas(Database db, String creditoId) async {
    final results = await db.query('cuota_programada',
        columns: ['COUNT(*)'],
        where: 'credito_id = ? AND estado = ?',
        whereArgs: [creditoId, 'PAGADO']);
    return results.first['COUNT(*)'] as int;
  }

  static Future<int> _calcularMoraLegacy(Database db, String creditoId) async {
    // Mora legacy: count overdue unpaid cuotas
    final now = DateFormat('yyyy-MM-dd').format(DateTime.now());
    final results = await db.rawQuery('''
      SELECT COUNT(*) as mora
      FROM cuota_programada
      WHERE credito_id = ? AND estado = 'PENDIENTE' AND fecha_vencimiento < ?
    ''', [creditoId, now]);
    return results.first['mora'] as int;
  }

  static String _determinarSemaforo(int mora, int cuotasPagadas, int nCuotas) {
    if (mora == 0 && cuotasPagadas > 0) return 'VERDE';
    if (mora <= 2) return 'AMARILLO';
    if (mora > 2) return 'ROJO';
    return 'GRIS';
  }
}
