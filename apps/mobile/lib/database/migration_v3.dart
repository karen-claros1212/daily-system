// Migración v3: jornada_documento — recuperación documental completa.
//
// Añade:
// 1. Tabla jornada_documento para rastreo de PDFs generados
// 2. Índice UNIQUE jornada_id + tipo para un documento por tipo por jornada
// 3. Restricciones FOREIGN KEY para integridad referencial
import 'package:sqflite/sqflite.dart';

class MigrationV3 {
  static const int version = 3;

  static Future<void> migrate(Database db) async {
    // 1. Tabla jornada_documento — recuperación documental
    await db.execute('''
      CREATE TABLE IF NOT EXISTS jornada_documento (
        id TEXT PRIMARY KEY,
        jornada_id TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('PDF_CIERRE', 'PDF_ORIGEN', 'FOTO', 'OTRO')),
        estado TEXT NOT NULL DEFAULT 'PENDING' CHECK(estado IN ('PENDING', 'GENERATED', 'FAILED_RETRYABLE', 'FAILED_PERMANENT')),
        ruta TEXT,
        snapshot_hash TEXT,
        pdf_hash_sha256 TEXT,
        bytes_b64 TEXT,
        error TEXT,
        creado_el TEXT NOT NULL,
        generado_el TEXT,
        FOREIGN KEY (jornada_id) REFERENCES jornada(id)
      )
    ''');

    // 2. Índice UNIQUE: un documento por tipo por jornada
    await db.execute(
      'CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_jornada_tipo '
      'ON jornada_documento(jornada_id, tipo)',
    );

    // 3. Trigger: rechaza INSERT en jornada_documento si jornada no existe
    await db.execute('DROP TRIGGER IF EXISTS trg_doc_require_valid_jornada');
    await db.execute('''
CREATE TRIGGER trg_doc_require_valid_jornada
BEFORE INSERT ON jornada_documento
FOR EACH ROW
WHEN NOT EXISTS (
  SELECT 1 FROM jornada WHERE id = NEW.jornada_id
)
BEGIN
  SELECT RAISE(ABORT, 'DS_JORNADA_NOT_FOUND');
END;
''');
  }
}
