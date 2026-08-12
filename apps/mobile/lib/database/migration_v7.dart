// Migración v7: reparación de claves idempotencia inventadas por V5 bug.
//
// V5 usaba COALESCE(..., entidad_id) como fallback para idempotency_key.
// Esto "inventaba" una clave que no existía en los datos originales.
//
// V7 corrige instalaciones que ya pasaron por V5:
//   - Filas donde idempotency_key == entidad_id → NULL (no conocemos la real)
//   - Filas donde idempotency_key == entidad_id Y datos.json contiene
//     idempotency_key o clave_idempotencia → re-extract
//
// No cambia esquema. Solo repara datos.

import 'package:sqflite/sqflite.dart';

class MigrationV7 {
  static const int version = 7;

  static Future<void> migrate(Database db) async {
    // 1. Reparar filas donde idempotency_key fue inventado (= entidad_id)
    //    pero los datos JSON sí contienen la clave real
    final jp = String.fromCharCode(36); // $

    await db.execute('''
      UPDATE sync_queue
      SET idempotency_key = COALESCE(
          json_extract(datos, '${jp}.idempotency_key'),
          json_extract(datos, '${jp}.clave_idempotencia')
        )
      WHERE idempotency_key = entidad_id
        AND idempotency_key IS NOT NULL
        AND (
          json_extract(datos, '${jp}.idempotency_key') IS NOT NULL
          OR json_extract(datos, '${jp}.clave_idempotencia') IS NOT NULL
        )
    ''');

    // 2. Filas donde idempotency_key == entidad_id y no hay clave en JSON
    //    → NULL (no inventar)
    await db.execute('''
      UPDATE sync_queue
      SET idempotency_key = NULL
      WHERE idempotency_key = entidad_id
        AND idempotency_key IS NOT NULL
        AND json_extract(datos, '${jp}.idempotency_key') IS NULL
        AND json_extract(datos, '${jp}.clave_idempotencia') IS NULL
    ''');
  }
}
