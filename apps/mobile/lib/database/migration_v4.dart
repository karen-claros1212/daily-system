// Migración v4: reparación de jornada_documento para dispositivos con V3 anterior.
//
// En 6f568e2, Migration V3 se publicó con:
//   hash_sha256 TEXT
//
// En cb5d525, se modificó para tener:
//   snapshot_hash TEXT
//   pdf_hash_sha256 TEXT
//
// Pero oldVersion < 3 es FALSE en dispositivos que ya ejecutaron V3.
// Migration V4 detecta columnas con PRAGMA y agrega las faltantes.
import 'package:sqflite/sqflite.dart';

class MigrationV4 {
  static const int version = 4;

  static Future<void> migrate(Database db) async {
    // 1. Verificar columnas existentes en jornada_documento
    final columns = await db.rawQuery('PRAGMA table_info(jornada_documento)');
    final columnNames = columns
        .map((col) => col['name'] as String)
        .whereType<String>()
        .toSet();

    // 2. Agregar columnas faltantes
    if (!columnNames.contains('snapshot_hash')) {
      await db.execute('ALTER TABLE jornada_documento ADD COLUMN snapshot_hash TEXT');
    }

    if (!columnNames.contains('pdf_hash_sha256')) {
      await db.execute('ALTER TABLE jornada_documento ADD COLUMN pdf_hash_sha256 TEXT');
    }

    // 3. Migrar datos de hash_sha256 → pdf_hash_sha256 si existe
    if (columnNames.contains('hash_sha256') && !columnNames.contains('pdf_hash_sha256')) {
      // Migrar valores existentes: hash_sha256 → pdf_hash_sha256
      await db.execute('''
        UPDATE jornada_documento
        SET pdf_hash_sha256 = hash_sha256
        WHERE hash_sha256 IS NOT NULL AND pdf_hash_sha256 IS NULL
      ''');
    }

    // 4. Migrar snapshot_hash desde jornada_snapshot si está vacío
    if (columnNames.contains('snapshot_hash')) {
      // Para cada documento sin snapshot_hash, intentar obtenerlo del snapshot correspondiente
      final docs = await db.query('jornada_documento',
          where: 'snapshot_hash IS NULL',
          columns: ['id', 'jornada_id']);

      for (final doc in docs) {
        final jornadaId = doc['jornada_id'] as String?;
        if (jornadaId == null) continue;

        final snapshots = await db.query('jornada_snapshot',
            where: 'jornada_id = ?', whereArgs: [jornadaId], limit: 1);

        if (snapshots.isNotEmpty) {
          final snapshotHash = snapshots.first['hash_content'] as String?;
          if (snapshotHash != null) {
            await db.update('jornada_documento',
                {'snapshot_hash': snapshotHash},
                where: 'id = ?', whereArgs: [doc['id']]);
          }
        }
      }
    }
  }
}
