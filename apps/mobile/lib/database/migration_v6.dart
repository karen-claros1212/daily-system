// Migración v6: pago.server_entity_id + reparación de mappings.
//
// Añade columna server_entity_id a la tabla pago para guardar el UUID
// que asigna el servidor a cada PAYMENT/REVERSAL.
//
// Reparación de datos:
//   - Las filas de sync_queue que ya tienen server_entity_id pero cuyo pago
//     local no lo tiene se propagan a pago.server_entity_id.
//   - Esto permite que el Pull reconcilie server_entity_id → local_id
//     incluso en instalaciones que ya tenían datos S3.
//
// No reescribe migraciones v2-v5.
// No cambia el esquema de sync_queue, jornada, movimiento.

import 'package:sqflite/sqflite.dart';

class MigrationV6 {
  static const int version = 6;

  static Future<void> migrate(Database db) async {
    // 1. Verificar columnas existentes
    final columns = await db.rawQuery('PRAGMA table_info(pago)');
    final columnNames = columns
        .map((col) => col['name'] as String)
        .whereType<String>()
        .toSet();

    // 2. Agregar server_entity_id a pago si no existe
    if (!columnNames.contains('server_entity_id')) {
      await db.execute('ALTER TABLE pago ADD COLUMN server_entity_id TEXT');
    }

    // 3. Reparación: propagar server_entity_id de sync_queue → pago
    //    para instalaciones que ya tenían datos S3 en V5.
    await db.execute('''
      UPDATE pago
      SET server_entity_id = (
        SELECT sq.server_entity_id
        FROM sync_queue sq
        WHERE sq.entidad_id = pago.id
          AND sq.server_entity_id IS NOT NULL
          AND sq.server_entity_id != ''
      )
      WHERE server_entity_id IS NULL
        AND EXISTS (
          SELECT 1 FROM sync_queue sq
          WHERE sq.entidad_id = pago.id
            AND sq.server_entity_id IS NOT NULL
            AND sq.server_entity_id != ''
        )
    ''');
  }
}
