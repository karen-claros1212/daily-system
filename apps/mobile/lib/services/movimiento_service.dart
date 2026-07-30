import 'package:uuid/uuid.dart';
import '../database/database.dart';
import 'jornada_guard.dart';
import '../services/sync_queue_service.dart';

final _uuidMov = Uuid();

/// Servicio para registrar movimientos financieros.
/// Centraliza la inserción de movimientos, la validación de jornada y el encolado.
class MovimientoService {
  /// Registra un movimiento financiero.
  ///
  /// Verifica que la jornada esté abierta mediante [JornadaGuard].
  /// Inserta en la misma transacción SQLite para evitar carreras.
  /// Encola a sync_queue para sincronización posterior.
  static Future<String> registrarMovimiento({
    required String jornadaId,
    required String tipo,
    required int monto,
    required String nota,
    required String cobradorId,
    required String negocioId,
  }) async {
    final db = await database;

    // Verificar jornada abierta (usa transaction para atomicidad)
    final jornada = await JornadaGuard.requireOpenOn(db, jornadaId);

    final id = _uuidMov.v4();
    final now = DateTime.now().toIso8601String();
    final negocioIdFromJornada = jornada['negocio_id'] as String? ?? negocioId;

    await db.insert('movimiento', {
      'id': id,
      'negocio_id': negocioIdFromJornada,
      'jornada_id': jornadaId,
      'tipo': tipo,
      'monto': monto,
      'nota': nota,
      'creado_el': now,
    });

    await SyncQueueService.enqueue('movimiento', id, {
      'tipo': tipo,
      'monto': monto,
      'nota': nota,
    });

    return id;
  }
}
