import 'package:sqflite/sqflite.dart';
import 'package:uuid/uuid.dart';
import '../database/database.dart';
import '../models/models.dart';

final _uuid = Uuid();

class PagoService {
  static Future<Pago> registrarPago(String creditoId, String jornadaId, String cobradorId,
      String negocioId, int monto, String nota) async {
    final db = await database;
    final clave = _uuid.v4();

    final pago = Pago(
      id: uid(),
      negocioId: negocioId,
      creditoId: creditoId,
      jornadaId: jornadaId,
      cobradorId: cobradorId,
      tipo: 'PAYMENT',
      monto: monto,
      claveIdempotencia: clave,
      nota: nota,
      registradoElDispositivo: DateTime.now().toIso8601String(),
    );

    await db.insert('pago', pago.toMap());

    // Update related cuota_programada to PAGADO
    final credito = await db.query('credito', limit: 1, where: 'id = ?', whereArgs: [creditoId]);
    if (credito.isNotEmpty) {
      final creditoMap = credito.first;
      final nCuotas = creditoMap['n_cuotas'] as int;
      // Mark first unpaid cuota as paid
      final cuotas = await db.query('cuota_programada',
          where: 'credito_id = ? AND estado = ?',
          whereArgs: [creditoId, 'PENDIENTE'],
          orderBy: 'numero ASC',
          limit: 1);
      if (cuotas.isNotEmpty) {
        await db.update('cuota_programada',
            {'estado': 'PAGADO'},
            where: 'id = ?',
            whereArgs: [cuotas.first['id']]);
      }
    }

    return pago;
  }

  static Future<Pago> reversarPago(String pagoId, String jornadaId, String cobradorId,
      String negocioId, String motivo) async {
    final db = await database;

    // Get original payment
    final pagos = await db.query('pago', limit: 1, where: 'id = ?', whereArgs: [pagoId]);
    if (pagos.isEmpty) throw Exception('Pago no encontrado');
    final pagoOriginal = Pago.fromMap(pagos.first);

    final clave = _uuid.v4();
    final reversal = Pago(
      id: uid(),
      negocioId: negocioId,
      creditoId: pagoOriginal.creditoId,
      jornadaId: jornadaId,
      cobradorId: cobradorId,
      tipo: 'REVERSAL',
      monto: pagoOriginal.monto,
      claveIdempotencia: clave,
      nota: 'Reversal: $motivo',
      registradoElDispositivo: DateTime.now().toIso8601String(),
      reversalOfPaymentId: pagoId,
    );

    await db.insert('pago', reversal.toMap());

    // Revert cuota to PENDIENTE
    if (pagoOriginal.creditoId != null) {
      final cuotas = await db.query('cuota_programada',
          where: 'credito_id = ? AND estado = ?',
          whereArgs: [pagoOriginal.creditoId, 'PAGADO'],
          orderBy: 'numero DESC',
          limit: 1);
      if (cuotas.isNotEmpty) {
        await db.update('cuota_programada',
            {'estado': 'PENDIENTE'},
            where: 'id = ?',
            whereArgs: [cuotas.first['id']]);
      }
    }

    return reversal;
  }

  static Future<List<Pago>> getPagosJornada(String jornadaId) async {
    final db = await database;
    final results = await db.query('pago',
        where: 'jornada_id = ?',
        whereArgs: [jornadaId],
        orderBy: 'registrado_el_dispositivo DESC');
    return results.map((m) => Pago.fromMap(m)).toList();
  }

  static Future<int> totalPagosJornada(String jornadaId) async {
    final db = await database;
    final results = await db.query('pago',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'PAYMENT']);
    return (results.first['SUM(monto)'] as int?) ?? 0;
  }

  static Future<int> totalReversalesJornada(String jornadaId) async {
    final db = await database;
    final results = await db.query('pago',
        columns: ['SUM(monto)'],
        where: 'jornada_id = ? AND tipo = ?',
        whereArgs: [jornadaId, 'REVERSAL']);
    return (results.first['SUM(monto)'] as int?) ?? 0;
  }
}
