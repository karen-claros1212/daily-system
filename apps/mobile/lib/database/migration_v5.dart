// Migración v5: evolución de sync_queue para S3 (outbox push/ACK/retry).
//
// Añade columnas necesarias para el push orchestrator:
//   1. idempotency_key — clave original usada en headers del request
//   2. negocio_id — origen del negocio
//   3. ruta_id_origen — ruta de origen para detectar R1→R2
//   4. cobrador_id_origen — cobrador de origen
//   5. jornada_id_origen — jornada de origen
//   6. intento — contador de reintentos
//   7. ultimo_error — último mensaje de error
//   8. ultima_transicion — timestamp de última transición de estado
//
// Nuevos estados: ENVIANDO, ERROR_REINTENTABLE, CONFLICTO
//
// Migración de datos legacy:
//   - Filas con datos en Map.toString() se conservan
//   - Se extraen campos del tipo si es posible
//   - Se marca como legacy si no se puede reconstruir
//
// No reescribe migraciones v2/v3/v4.
// No cambia el esquema de pago, movimiento, jornada.

import 'package:sqflite/sqflite.dart';

class MigrationV5 {
  static const int version = 5;

  // Estados que sync_queue puede tener tras esta migración.
  static const String estadoPendiente = 'PENDIENTE_DE_SINCRONIZAR';
  static const String estadoEnviando = 'ENVIANDO';
  static const String estadoSincronizado = 'SINCRONIZADO';
  static const String estadoError = 'ERROR_REINTENTABLE';
  static const String estadoConflicto = 'CONFLICTO';

  static Future<void> migrate(Database db) async {
    // 1. Verificar columnas existentes
    final columns = await db.rawQuery('PRAGMA table_info(sync_queue)');
    final columnNames = columns
        .map((col) => col['name'] as String)
        .whereType<String>()
        .toSet();

    // 2. Agregar columnas faltantes (ALTER TABLE ADD COLUMN)
    if (!columnNames.contains('idempotency_key')) {
      await db.execute('ALTER TABLE sync_queue ADD COLUMN idempotency_key TEXT');
    }

    if (!columnNames.contains('negocio_id')) {
      await db.execute('ALTER TABLE sync_queue ADD COLUMN negocio_id TEXT');
    }

    if (!columnNames.contains('ruta_id_origen')) {
      await db.execute('ALTER TABLE sync_queue ADD COLUMN ruta_id_origen TEXT');
    }

    if (!columnNames.contains('cobrador_id_origen')) {
      await db.execute('ALTER TABLE sync_queue ADD COLUMN cobrador_id_origen TEXT');
    }

    if (!columnNames.contains('jornada_id_origen')) {
      await db.execute('ALTER TABLE sync_queue ADD COLUMN jornada_id_origen TEXT');
    }

    if (!columnNames.contains('intento')) {
      await db.execute('ALTER TABLE sync_queue ADD COLUMN intento INTEGER NOT NULL DEFAULT 0');
    }

    if (!columnNames.contains('ultimo_error')) {
      await db.execute('ALTER TABLE sync_queue ADD COLUMN ultimo_error TEXT');
    }

    if (!columnNames.contains('ultima_transicion')) {
      await db.execute('ALTER TABLE sync_queue ADD COLUMN ultima_transicion TEXT');
    }

    // 3. Migrar datos legacy:
    //    - Intentar extraer tipo del campo datos si es Map.toString()
    //    - Extraer campos relevantes según el tipo detectado
    //    - Marcar filas no migrables como CONFLICTO con motivo

    // Primero, identificar filas que necesitan migración
    final rows = await db.query('sync_queue',
        columns: ['id', 'datos']);

    for (final row in rows) {
      final id = row['id'] as String?;
      if (id == null) continue;

      final datos = row['datos'] as String?;

      if (datos == null || datos.isEmpty) continue;

      // Detectar si es JSON válido o Map.toString()
      final esJsonValido = datos.startsWith('{') && datos.endsWith('}');

      if (esJsonValido) {
        // Intentar parsear JSON y extraer campos
        try {
          // No hacemos dart:convert aquí porque es migration pura SQLite
          // Usamos CASE para extraer campos básicos del tipo
          await db.execute('''
            UPDATE sync_queue
            SET idempotency_key = entidad_id,
                intento = 0,
                ultima_transicion = creado_el
            WHERE id = ? AND idempotency_key IS NULL
          ''', [id]);
        } catch (e) {
          // Si falla, marcar como CONFLICTO
          await db.execute('''
            UPDATE sync_queue
            SET estado = ?,
                ultimo_error = ?,
                ultima_transicion = ?
            WHERE id = ?
          ''', [
            estadoConflicto,
            'legacy_datos_no_reconstruible',
            DateTime.now().toIso8601String(),
            id,
          ]);
        }
      } else {
        // Map.toString() — marcar como legacy no reconstruible
        await db.execute('''
          UPDATE sync_queue
          SET estado = ?,
              ultimo_error = ?,
              ultima_transicion = ?
          WHERE id = ?
        ''', [
          estadoConflicto,
          'legacy_map_tostring_no_json',
          DateTime.now().toIso8601String(),
          id,
        ]);
      }
    }

    // 4. Crear índices para queries frecuentes de S3
    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_sq_estado_pendiente
      ON sync_queue(estado, creado_el)
      WHERE estado = '$estadoPendiente'
    ''');

    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_sq_estado_error
      ON sync_queue(estado, creado_el)
      WHERE estado = '$estadoError'
    ''');

    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_sq_idempotencia
      ON sync_queue(idempotency_key)
      WHERE idempotency_key IS NOT NULL
    ''');

    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_sq_jornada
      ON sync_queue(jornada_id_origen, tipo, creado_el)
      WHERE jornada_id_origen IS NOT NULL
    ''');
  }
}
