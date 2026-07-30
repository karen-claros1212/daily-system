import 'dart:convert';
import 'package:uuid/uuid.dart';
import '../database/database.dart';
import '../domain/domain_exceptions.dart';
import 'jornada_guard.dart';

final _uuidMov = Uuid();

/// Servicio transaccional para registrar movimientos financieros.
/// Toda la operación (guarda + inserción + sync_queue) ocurre dentro de db.transaction().
class MovimientoService {
  /// Registra un movimiento financiero.
  ///
  /// Transacción atómica:
  /// 1. JornadaGuard.requireOpenOn(txn, jornadaId) — dentro del callback
  /// 2. Validar tipo permitido
  /// 3. Validar monto > 0
  /// 4. Insertar movimiento mediante txn
  /// 5. Insertar sync_queue mediante txn
  ///
  /// Si cualquier paso falla: no queda mutación parcial.
  static Future<String> registrarMovimiento({
    required String jornadaId,
    required String tipo,
    required int monto,
    required String nota,
    required String cobradorId,
    required String negocioId,
  }) async {
    if (monto <= 0) {
      throw MontoInvalidoException(monto);
    }

    final db = await database;
    return db.transaction((txn) async {
      // Guardia DENTRO de la transacción — cero ventana de carrera
      final jornada = await JornadaGuard.requireOpenOn(txn, jornadaId);

      final id = _uuidMov.v4();
      final now = DateTime.now().toIso8601String();
      final negocioIdFromJornada = jornada['negocio_id'] as String? ?? negocioId;

      // Insertar movimiento dentro de la transacción
      await txn.insert('movimiento', {
        'id': id,
        'negocio_id': negocioIdFromJornada,
        'jornada_id': jornadaId,
        'tipo': tipo,
        'monto': monto,
        'nota': nota,
        'creado_el': now,
      });

      // Insertar sync_queue dentro de la transacción
      await txn.insert('sync_queue', {
        'id': uid(),
        'tipo': 'movimiento',
        'entidad_id': id,
        'datos': jsonEncode({'tipo': tipo, 'monto': monto, 'nota': nota}),
        'creado_el': now,
        'estado': 'PENDIENTE_DE_SINCRONIZAR',
      });

      return id;
    });
  }
}

/// Genera un UID reutilizable dentro de transacciones.
String uid() => const Uuid().v4();
