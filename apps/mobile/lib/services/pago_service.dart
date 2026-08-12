import 'dart:convert';
import 'package:uuid/uuid.dart';
import 'package:sqflite/sqflite.dart';
import '../database/database.dart';
import '../domain/domain_exceptions.dart';
import '../models/models.dart';
import 'jornada_guard.dart';

final _uuid = Uuid();

/// Servicio de pagos con transacciones reales.
/// Toda operación (guarda + INSERT + cuota + sync_queue) ocurre dentro de db.transaction().
class PagoService {
  /// Registra un pago en la jornada.
  ///
  /// Transacción atómica:
  /// 1. JornadaGuard.requireOpenOn(txn, jornadaId) — dentro del callback
  /// 2. Validar monto > 0
  /// 3. Verificar idempotencia
  /// 4. Insertar PAYMENT mediante txn
  /// 5. Actualizar cuota mediante txn
  /// 6. Insertar sync_queue mediante txn
  ///
  /// Si cualquier paso falla: no queda mutación parcial.
  static Future<Pago> registrarPago(String creditoId, String jornadaId, String cobradorId,
      String negocioId, int monto, String nota, String clienteIdempotenciaClave) async {
    if (monto <= 0) {
      throw MontoInvalidoException(monto);
    }

    final clave = clienteIdempotenciaClave;

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

    final db = await database;
    return db.transaction((txn) async {
      // Guardia DENTRO de la transacción — cero ventana de carrera
      await JornadaGuard.requireOpenOn(txn, jornadaId);

      // Verificar idempotencia dentro de la transacción
      final existentes = await txn.query('pago',
          limit: 1, where: 'clave_idempotencia = ?', whereArgs: [clave]);
      if (existentes.isNotEmpty) {
        final existente = Pago.fromMap(existentes.first);
        final fieldsMatch = existente.creditoId == creditoId
            && existente.jornadaId == jornadaId
            && existente.negocioId == negocioId
            && existente.cobradorId == cobradorId
            && existente.monto == monto
            && existente.tipo == 'PAYMENT';
        if (!fieldsMatch) {
          throw IdempotenciaConflictoException(clave, existente.id, monto, existente.monto);
        }
        return existente;
      }

      // Insertar pago
      await txn.insert('pago', pago.toMap());

      // Marcar primera cuota pendiente como pagada
      final cuotas = await txn.query('cuota_programada',
          where: 'credito_id = ? AND estado = ?',
          whereArgs: [creditoId, 'PENDIENTE'],
          orderBy: 'numero ASC',
          limit: 1);
      if (cuotas.isNotEmpty) {
        await txn.update('cuota_programada',
            {'estado': 'PAGADO'},
            where: 'id = ?',
            whereArgs: [cuotas.first['id']]);
      }

      // Insertar sync_queue dentro de la transacción (S3: payload completo)
      final idempotencyKey = clienteIdempotenciaClave;
      final rutaIdOrigen = await _obtenerRutaIdJornada(txn, jornadaId);
      await _insertSyncQueue(txn, 'pago', pago.id, {
        'tipo': 'PAYMENT',
        'monto': monto,
        'credito_id': creditoId,
        'jornada_id': jornadaId,
        'cobrador_id': cobradorId,
        'negocio_id': negocioId,
        'entidad_id': pago.id,
      }, idempotencyKey: idempotencyKey,
         negocioId: negocioId,
         cobradorIdOrigen: cobradorId,
         jornadaIdOrigen: jornadaId,
         rutaIdOrigen: rutaIdOrigen);

      return pago;
    });
  }

  /// Revierte un pago existente.
  ///
  /// Transacción atómica:
  /// 1. JornadaGuard.requireOpenOn(txn, jornadaId) — dentro del callback
  /// 2. Consultar pago original mediante txn
  /// 3. Comprobar que existe, pertenece a jornada, es PAYMENT, no reversado
  /// 4. Insertar REVERSAL mediante txn
  /// 5. Devolver cuota a PENDIENTE mediante txn
  /// 6. Insertar sync_queue mediante txn
  static Future<Pago> reversarPago(String pagoId, String jornadaId, String cobradorId,
      String negocioId, String motivo) async {
    final db = await database;
    return db.transaction((txn) async {
      // Guardia DENTRO de la transacción
      await JornadaGuard.requireOpenOn(txn, jornadaId);

      // Consultar pago original DENTRO de la transacción
      final pagos = await txn.query('pago', limit: 1, where: 'id = ?', whereArgs: [pagoId]);
      if (pagos.isEmpty) {
        throw PagoNoEncontradoException(pagoId);
      }
      final pagoOriginal = Pago.fromMap(pagos.first);

      // Validar que pertenece a la misma jornada
      if (pagoOriginal.jornadaId != jornadaId) {
        throw PagoInvalidoParaReversionException(pagoId);
      }

      // Validar que es un pago (no otro reversal)
      if (pagoOriginal.tipo != 'PAYMENT') {
        throw PagoInvalidoParaReversionException(pagoId);
      }

      // Validar que no fue reversado ya (protección doble: servicio)
      final reversales = await txn.query('pago',
          limit: 1, where: 'reversal_of_payment_id = ?', whereArgs: [pagoId]);
      if (reversales.isNotEmpty) {
        throw PagoYaReversadoException(pagoId);
      }

      // S2: buscar server_entity_id del pago original para referenciarlo en el servidor
      final pagoInfo = await txn.query('pago',
          columns: ['server_entity_id'],
          where: 'id = ?',
          whereArgs: [pagoId],
          limit: 1);
      final serverPaymentId = pagoInfo.isNotEmpty
          ? (pagoInfo.first['server_entity_id'] as String?)
          : null;
      // Si no hay server_entity_id, usar el ID local (pago no sincronizado aún)
      final paymentIdParaSync = serverPaymentId ?? pagoId;

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

      // Insertar reversal
      await txn.insert('pago', reversal.toMap());

      // Revertir cuota a PENDIENTE
      if (pagoOriginal.creditoId != null) {
        final cuotas = await txn.query('cuota_programada',
            where: 'credito_id = ? AND estado = ?',
            whereArgs: [pagoOriginal.creditoId, 'PAGADO'],
            orderBy: 'numero DESC',
            limit: 1);
        if (cuotas.isNotEmpty) {
          await txn.update('cuota_programada',
              {'estado': 'PENDIENTE'},
              where: 'id = ?',
              whereArgs: [cuotas.first['id']]);
        }
      }

      // Insertar sync_queue dentro de la transacción (S3: payload completo)
      // S2: usar serverPaymentId para que el servidor reconozca el pago original
      final reversalIdempotencyKey = clave;
      final rutaIdOrigen = await _obtenerRutaIdJornada(txn, jornadaId);
      await _insertSyncQueue(txn, 'pago', reversal.id, {
        'tipo': 'REVERSAL',
        'monto': pagoOriginal.monto,
        'reversal_of_payment_id': paymentIdParaSync,
        'jornada_id': jornadaId,
        'cobrador_id': cobradorId,
        'negocio_id': negocioId,
        'motivo': motivo,
      }, idempotencyKey: reversalIdempotencyKey,
         negocioId: negocioId,
         cobradorIdOrigen: cobradorId,
         jornadaIdOrigen: jornadaId,
         rutaIdOrigen: rutaIdOrigen);

      return reversal;
    });
  }

  /// Helper para insertar sync_queue dentro de transacciones.
  /// Evita depender de SyncQueueService.enqueue() que usa database global.
  /// S3: acepta campos adicionales de procedencia.
  static Future<void> _insertSyncQueue(DatabaseExecutor txn, String tipo, String entidadId, Map<String, dynamic> datos,
      {String idempotencyKey = '', String? negocioId, String? cobradorIdOrigen, String? jornadaIdOrigen, String? rutaIdOrigen}) async {
    final now = DateTime.now().toIso8601String();
    await txn.insert('sync_queue', {
      'id': uid(),
      'tipo': tipo,
      'entidad_id': entidadId,
      'datos': jsonEncode(datos),
      'creado_el': now,
      'estado': 'PENDIENTE_DE_SINCRONIZAR',
      'idempotency_key': idempotencyKey,
      'negocio_id': negocioId,
      'cobrador_id_origen': cobradorIdOrigen,
      'jornada_id_origen': jornadaIdOrigen,
      'ruta_id_origen': rutaIdOrigen,
      'intento': 0,
      'ultimo_error': null,
      'ultima_transicion': now,
    });
  }

  /// Busca la ruta_id asociada a una jornada dentro de la transacción.
  static Future<String?> _obtenerRutaIdJornada(DatabaseExecutor txn, String jornadaId) async {
    final resultados = await txn.query(
      'jornada',
      columns: ['ruta_id'],
      where: 'id = ?',
      whereArgs: [jornadaId],
      limit: 1,
    );
    return resultados.isNotEmpty ? (resultados.first['ruta_id'] as String?) : null;
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
