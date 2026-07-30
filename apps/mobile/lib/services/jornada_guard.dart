import 'package:sqflite/sqflite.dart';
import '../database/database.dart';
import '../domain/domain_exceptions.dart';
import '../domain/jornada_state.dart';

/// Guarda centralizada de jornada.
/// Todas las mutaciones financieras pasan por aquí para evitar
/// duplicación de consultas y mensajes de error inconsistentes.
class JornadaGuard {
  /// Verifica que la jornada exista y esté en estado OPEN.
  /// Devuelve la fila validada para evitar una segunda consulta innecesaria.
  ///
  /// Lanza:
  /// - [JornadaNoEncontradaException] si no existe.
  /// - [JornadaCerradaException] si está cerrada.
  static Future<Map<String, dynamic>> requireOpen(String jornadaId) async {
    final db = await database;
    return requireOpenOn(db, jornadaId);
  }

  /// Versión que acepta un executor existente (para usar dentro de transacciones).
  static Future<Map<String, dynamic>> requireOpenOn(DatabaseExecutor executor, String jornadaId) async {
    final jornadas = await executor.query('jornada',
        limit: 1, where: 'id = ?', whereArgs: [jornadaId]);
    if (jornadas.isEmpty) {
      throw JornadaNoEncontradaException(jornadaId);
    }
    final estado = jornadas.first['estado'] as String;
    final state = JornadaStateExtension.fromSql(estado);
    if (!state.isMutatable) {
      throw JornadaCerradaException(jornadaId, estado);
    }
    return jornadas.first;
  }
}
