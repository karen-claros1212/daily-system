// Migración v2: defensa en profundidad para M3.6 cierre definitivo.
//
// Añade:
// 1. UNIQUE en pago.clave_idempotencia (ya existe en tables.dart, se verifica)
// 2. UNIQUE parcial para una sola reversión por pago original
// 3. UNIQUE en snapshot.jornada_id
// 4. Trigger que rechaza INSERT en pago cuando jornada no está OPEN
// 5. Trigger que rechaza INSERT en movimiento cuando jornada no está OPEN
// 6. Trigger que impide UPDATE del snapshot
// 7. Trigger que impide DELETE del snapshot
// 8. Tabla jornada_snapshot inmutable
import 'package:sqflite/sqflite.dart';

class MigrationV2 {
  static const int version = 2;

  static Future<void> migrate(Database db) async {
    // 1. Tabla snapshot inmutable
    await db.execute('''
      CREATE TABLE jornada_snapshot (
        jornada_id TEXT PRIMARY KEY,
        fecha TEXT NOT NULL,
        cobrador_id TEXT,
        ruta_id TEXT NOT NULL,
        opening_base INTEGER NOT NULL DEFAULT 0,
        opening_carry INTEGER NOT NULL DEFAULT 0,
        recaudo_real INTEGER NOT NULL DEFAULT 0,
        reversales INTEGER NOT NULL DEFAULT 0,
        gastos INTEGER NOT NULL DEFAULT 0,
        ahorro INTEGER NOT NULL DEFAULT 0,
        vales INTEGER NOT NULL DEFAULT 0,
        entregas INTEGER NOT NULL DEFAULT 0,
        recibidos INTEGER NOT NULL DEFAULT 0,
        desembolsos INTEGER NOT NULL DEFAULT 0,
        efectivo_esperado INTEGER NOT NULL DEFAULT 0,
        contado INTEGER NOT NULL DEFAULT 0,
        diferencia INTEGER NOT NULL DEFAULT 0,
        diferencia_motivo TEXT,
        pagos_count INTEGER NOT NULL DEFAULT 0,
        reversales_count INTEGER NOT NULL DEFAULT 0,
        movimientos_count INTEGER NOT NULL DEFAULT 0,
        cerrada_local_el TEXT,
        version_esquema INTEGER NOT NULL DEFAULT 1,
        hash_content TEXT NOT NULL,
        FOREIGN KEY (jornada_id) REFERENCES jornada(id)
      )
    ''');

    // 2. Tabla sync_queue (creada por migración, no por SyncQueueService)
    await db.execute('''
      CREATE TABLE IF NOT EXISTS sync_queue (
        id TEXT PRIMARY KEY,
        tipo TEXT NOT NULL,
        entidad_id TEXT NOT NULL,
        datos TEXT NOT NULL,
        creado_el TEXT NOT NULL,
        estado TEXT DEFAULT 'PENDIENTE_DE_SINCRONIZAR'
      )
    ''');

    // 3. Índice UNIQUE para una sola reversión por pago original
    await db.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_pago_reversal_unique ON pago(reversal_of_payment_id) WHERE reversal_of_payment_id IS NOT NULL');

    // 3-6. Triggers: usar WHEN NOT EXISTS para evitar nested END
    await db.execute('DROP TRIGGER IF EXISTS trg_pago_require_open_jornada');
    await db.execute('DROP TRIGGER IF EXISTS trg_movimiento_require_open_jornada');
    await db.execute('DROP TRIGGER IF EXISTS trg_snapshot_no_update');
    await db.execute('DROP TRIGGER IF EXISTS trg_snapshot_no_delete');

    await db.execute('''
CREATE TRIGGER trg_pago_require_open_jornada
BEFORE INSERT ON pago
FOR EACH ROW
WHEN NOT EXISTS (
  SELECT 1
  FROM jornada
  WHERE id = NEW.jornada_id
    AND estado = 'OPEN'
)
BEGIN
  SELECT RAISE(ABORT, 'DS_JORNADA_NOT_OPEN');
END;
''');

    await db.execute('''
CREATE TRIGGER trg_movimiento_require_open_jornada
BEFORE INSERT ON movimiento
FOR EACH ROW
WHEN NOT EXISTS (
  SELECT 1
  FROM jornada
  WHERE id = NEW.jornada_id
    AND estado = 'OPEN'
)
BEGIN
  SELECT RAISE(ABORT, 'DS_JORNADA_NOT_OPEN');
END;
''');

    await db.execute('''
CREATE TRIGGER trg_snapshot_no_update
BEFORE UPDATE ON jornada_snapshot
FOR EACH ROW
BEGIN
  SELECT RAISE(ABORT, 'DS_SNAPSHOT_IMMUTABLE');
END;
''');

    await db.execute('''
CREATE TRIGGER trg_snapshot_no_delete
BEFORE DELETE ON jornada_snapshot
FOR EACH ROW
BEGIN
  SELECT RAISE(ABORT, 'DS_SNAPSHOT_IMMUTABLE');
END;
''');
  }
}
