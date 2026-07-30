import 'package:uuid/uuid.dart';
import '../database/database.dart';
import '../domain/domain_exceptions.dart';
import '../models/models.dart';
import 'jornada_guard.dart';

final _uuid = Uuid();

class PagoService {
  /// Registra un pago en la jornada.
  ///
  /// Transacción atómica:
  /// 1. Verifica jornada abierta (JornadaGuard)
  /// 2. Inserta el pago
  /// 3. Marca la cuota_programada como PAGADO
  ///
  /// Si falla paso 3, se revierte paso 2.
  static Future<Pago> registrarPago(String creditoId, String jornadaId, String cobradorId,
      String negocioId, int monto, String nota) async {
    final db = await database;

    // Verificar jornada abierta
    await JornadaGuard.requireOpen(jornadaId);

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

    // Transacción atómica: pago + cuota
    await db.transaction((txn) async {
      final txnDb = txn;
      await txnDb.insert('pago', pago.toMap());

      // Marcar primera cuota pendiente como pagada
      final cuotas = await txnDb.query('cuota_programada',
          where: 'credito_id = ? AND estado = ?',
          whereArgs: [creditoId, 'PENDIENTE'],
          orderBy: 'numero ASC',
          limit: 1);
      if (cuotas.isNotEmpty) {
        await txnDb.update('cuota_programada',
            {'estado': 'PAGADO'},
            where: 'id = ?',
            whereArgs: [cuotas.first['id']]);
      }
    });

    return pago;
  }

  /// Revierte un pago existente.
  ///
  /// Transacción atómica:
  /// 1. Verifica jornada abierta
  /// 2. Verifica que el pago original existe
  /// 3. Inserta el reversal
  /// 4. Revierte la cuota_programada a PENDIENTE
  static Future<Pago> reversarPago(String pagoId, String jornadaId, String cobradorId,
      String negocioId, String motivo) async {
    final db = await database;

    // Verificar jornada abierta
    await JornadaGuard.requireOpen(jornadaId);

    // Obtener pago original
    final pagos = await db.query('pago', limit: 1, where: 'id = ?', whereArgs: [pagoId]);
    if (pagos.isEmpty) {
      throw PagoNoEncontradoException(pagoId);
    }
    final pagoOriginal = Pago.fromMap(pagos.first);

    // Validar que es un pago (no otro reversal)
    if (pagoOriginal.tipo != 'PAYMENT') {
      throw PagoInvalidoParaReversionException(pagoId);
    }

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

    // Transacción atómica: reversal + cuota
    await db.transaction((txn) async {
      final txnDb = txn;
      await txnDb.insert('pago', reversal.toMap());

      // Revertir cuota a PENDIENTE
      if (pagoOriginal.creditoId != null) {
        final cuotas = await txnDb.query('cuota_programada',
            where: 'credito_id = ? AND estado = ?',
            whereArgs: [pagoOriginal.creditoId, 'PAGADO'],
            orderBy: 'numero DESC',
            limit: 1);
        if (cuotas.isNotEmpty) {
          await txnDb.update('cuota_programada',
              {'estado': 'PENDIENTE'},
              where: 'id = ?',
              whereArgs: [cuotas.first['id']]);
        }
      }
    });

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
