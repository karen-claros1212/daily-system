// ─── Persistencia local del sync (bloque offline sync, S2) ──────────────────
//
// Recibe un SyncDataset (GET /api/mobile/sync) y lo refleja en el modelo
// financiero local EXISTENTE (lib/database/tables.dart), sin crear un segundo
// modelo. Reglas del bloque (endurecidas para no destruir estado local):
//   - UPSERT por PK explicito: INSERT ... ON CONFLICT(id) DO UPDATE SET <cols>.
//     JAMAS se usa INSERT OR REPLACE: resolver un conflicto UNIQUE que no sea
//     el PK borrando la fila local esta prohibido (en especial pago: mismo id
//     -> update permitido; distinto id + misma clave_idempotencia -> CONFLICTO
//     controlado, nunca se borra el pago local para insertar el remoto).
//   - Proteccion del estado local pendiente: si una entidad tiene trabajo
//     pendiente en sync_queue, el pull no la sobrescribe (ni su cuota). Una
//     jornada CLOSED_LOCAL_PENDING_SYNC no regresa a un estado anterior del
//     servidor; el conflicto queda conservado para S3/reconciliacion.
//   - Cada dataset se persiste en SU PROPIA transaccion (atomico por dataset).
//   - Orden de persistencia por dependencia: identidad -> clientes -> creditos
//     -> cuotas -> jornadas -> pagos -> movimientos.
//   - Los triggers de guarda de jornada abierta (MigrationV2) se DROP/re-CREATE
//     dentro de la transaccion de pagos/movimientos: el import del servidor
//     incluye jornadas CLOSED/CLOSED_SYNCED, que la guarda rechazaria. Como el
//     DDL es transaccional, un fallo revierte el DROP y deja las guardas
//     intactas.

import 'package:sqflite/sqflite.dart';

import '../database/migration_v2.dart';
import 'sync_models.dart';

/// Hay trabajo local pendiente de sincronizar y una operacion destructiva
/// (limpiarDatosDeRuta) fue rechazada para no perderlo.
class SyncPendienteException implements Exception {
  final String message;
  const SyncPendienteException(this.message);

  @override
  String toString() => 'SyncPendienteException: $message';
}

/// Orden del ciclo de vida de la jornada para detectar "estado anterior".
const List<String> _ordenEstadosJornada = [
  'OPEN',
  'CLOSING',
  'CLOSED_LOCAL_PENDING_SYNC',
  'CLOSED_SYNCED',
];

class SyncRepository {
  final Database db;

  SyncRepository(this.db);

  /// Refleja todo el dataset del servidor en el modelo local.
  ///
  /// [negocioNombre], [cobradorNombre] y [rutaNombre] vienen del bootstrap
  /// (el SyncDataset solo trae ids); si se omiten se conservan los valores
  /// locales ya existentes (o el id como nombre si no existen).
  Future<void> importar(
    SyncDataset dataset, {
    String? negocioNombre,
    String? cobradorNombre,
    String? rutaNombre,
  }) async {
    final pendientes = await _entidadesPendientes(db);
    final creditosProtegidos = await _creditosConPagoPendiente(db);
    final serverToLocal = await _mapearServerALocal(db);

    await _importarIdentidad(dataset, negocioNombre, cobradorNombre, rutaNombre);
    await _importarDataset('cliente', dataset.clientes);
    await _importarDataset('credito', dataset.creditos);
    await _importarCuotas(dataset.cuotas, creditosProtegidos);
    await _importarJornadas(dataset, pendientes);
    await _importarPagosConMapeo(dataset.pagos, pendientes, serverToLocal);
    await _importarMovimientosConMapeo(dataset.movimientos, pendientes, serverToLocal);
  }

  /// Construye mapeo server_entity_id → local_id desde sync_queue.
  /// Permite que el pull reconcilie filas del servidor con IDs locales.
  Future<Map<String, String>> _mapearServerALocal(DatabaseExecutor txn) async {
    final rows = await txn.query(
      'sync_queue',
      columns: ['entidad_id', 'server_entity_id'],
      where: 'server_entity_id IS NOT NULL AND server_entity_id != \'\'',
    );
    final map = <String, String>{};
    for (final row in rows) {
      final serverId = row['server_entity_id'] as String?;
      final localId = row['entidad_id'] as String?;
      if (serverId != null && localId != null) {
        map[serverId] = localId;
      }
    }
    return map;
  }

  /// Importa pagos mapeando server ID → local ID antes del UPSERT.
  /// Suspende triggers de guarda de jornada abierta DENTRO de la transaccion.
  Future<void> _importarPagosConMapeo(
    List<SyncFila> filas,
    Set<String> pendientes,
    Map<String, String> serverToLocal,
  ) async {
    if (filas.isEmpty) return;
    await db.transaction((txn) async {
      await txn.execute('DROP TRIGGER IF EXISTS trg_pago_require_open_jornada');
      try {
        for (final fila in filas) {
          if (pendientes.contains(fila.id)) continue;

          // S3: mapear server_entity_id → local_id para UPSERT correcto
          final localId = serverToLocal[fila.id] ?? fila.id;
          final mapa = fila.toMap();
          mapa['id'] = localId;

          await _upsertPorPk(txn, 'pago', mapa);
        }
      } finally {
        await txn.execute(TriggerGuardasJornada.pago);
      }
    });
  }

  /// Importa movimientos mapeando server ID → local ID antes del UPSERT.
  /// Suspende triggers de guarda de jornada abierta DENTRO de la transaccion.
  Future<void> _importarMovimientosConMapeo(
    List<SyncFila> filas,
    Set<String> pendientes,
    Map<String, String> serverToLocal,
  ) async {
    if (filas.isEmpty) return;
    await db.transaction((txn) async {
      await txn.execute('DROP TRIGGER IF EXISTS trg_movimiento_require_open_jornada');
      try {
        for (final fila in filas) {
          if (pendientes.contains(fila.id)) continue;

          // S3: mapear server_entity_id → local_id para UPSERT correcto
          final localId = serverToLocal[fila.id] ?? fila.id;
          final mapa = fila.toMap();
          mapa['id'] = localId;

          await _upsertPorPk(txn, 'movimiento', mapa);
        }
      } finally {
        await txn.execute(TriggerGuardasJornada.movimiento);
      }
    });
  }

  /// Limpia el modelo local de la ruta (clientes, creditos, cuotas, jornadas,
  /// pagos y movimientos) para que el proximo sync sea un reflejo fiel del
  /// servidor.
  ///
  /// SIEMPRE preserva: identidad (negocio/usuario/ruta), sync_queue,
  /// jornada_snapshot y jornada_documento (historia auditable). Si existe
  /// outbox pendiente o jornadas con cierre local pendiente, la limpieza se
  /// RECHAZA con [SyncPendienteException] y no se borra nada (R1 no se limpia
  /// destructivamente; el conflicto se resuelve en S3/S4).
  Future<void> limpiarDatosDeRuta() async {
    await db.transaction((txn) async {
      final pendientes = await txn.query(
        'sync_queue',
        columns: ['id'],
        where: 'estado = ?',
        whereArgs: ['PENDIENTE_DE_SINCRONIZAR'],
      );
      if (pendientes.isNotEmpty) {
        throw SyncPendienteException(
          'Hay ${pendientes.length} operacion(es) pendientes de sincronizar; '
          'no se limpia la ruta.',
        );
      }

      final jornadasPendientes = await txn.query(
        'jornada',
        columns: ['id'],
        where: 'estado = ?',
        whereArgs: ['CLOSED_LOCAL_PENDING_SYNC'],
      );
      if (jornadasPendientes.isNotEmpty) {
        throw SyncPendienteException(
          'Hay ${jornadasPendientes.length} jornada(s) con cierre local '
          'pendiente; no se limpia la ruta.',
        );
      }

      // Orden hijos-antes-que-padres. jornada_snapshot y jornada_documento no
      // se tocan: son historia auditable inmutable.
      for (final tabla in [
        'movimiento',
        'pago',
        'jornada',
        'cuota_programada',
        'credito',
        'cliente',
      ]) {
        await txn.delete(tabla);
      }
    });
  }

  Future<void> _importarIdentidad(
    SyncDataset dataset,
    String? negocioNombre,
    String? cobradorNombre,
    String? rutaNombre,
  ) async {
    await db.transaction((txn) async {
      final negocio = await txn.query(
        'negocio',
        where: 'id = ?',
        whereArgs: [dataset.negocioId],
        limit: 1,
      );
      await _upsertPorPk(txn, 'negocio', {
        'id': dataset.negocioId,
        'nombre': negocioNombre ??
            (negocio.isNotEmpty
                ? negocio.first['nombre'] as String
                : dataset.negocioId),
      });

      final cobrador = await txn.query(
        'usuario',
        where: 'id = ?',
        whereArgs: [dataset.cobradorId],
        limit: 1,
      );
      await _upsertPorPk(txn, 'usuario', {
        'id': dataset.cobradorId,
        'negocio_id': dataset.negocioId,
        'rol': 'COBRADOR',
        'nombre': cobradorNombre ??
            (cobrador.isNotEmpty
                ? cobrador.first['nombre'] as String
                : dataset.cobradorId),
      });

      final ruta = await txn.query(
        'ruta',
        where: 'id = ?',
        whereArgs: [dataset.rutaId],
        limit: 1,
      );
      await _upsertPorPk(txn, 'ruta', {
        'id': dataset.rutaId,
        'negocio_id': dataset.negocioId,
        'nombre': rutaNombre ??
            (ruta.isNotEmpty ? ruta.first['nombre'] as String : dataset.rutaId),
        'cobrador_id': dataset.cobradorId,
        'activa': 1,
      });
    });
  }

  Future<void> _importarDataset(
    String tabla,
    List<SyncFila> filas,
  ) async {
    if (filas.isEmpty) return;
    await db.transaction((txn) async {
      for (final fila in filas) {
        await _upsertPorPk(txn, tabla, fila.toMap());
      }
    });
  }

  /// Importa cuotas protegiendo el estado local de creditos con pagos
  /// pendientes: si el credito tiene trabajo en sync_queue, su cuota local
  /// (p.ej. marcada PAGADO por un pago sin sincronizar) no se revierte con el
  /// estado anterior que aun tiene el servidor.
  Future<void> _importarCuotas(
    List<SyncCuota> cuotas,
    Set<String> creditosProtegidos,
  ) async {
    if (cuotas.isEmpty) return;
    await db.transaction((txn) async {
      for (final cuota in cuotas) {
        if (creditosProtegidos.contains(cuota.creditoId)) continue;
        await _upsertPorPk(txn, 'cuota_programada', cuota.toMap());
      }
    });
  }

  /// Importa jornadas con dos protecciones:
  ///   1. Si la jornada tiene trabajo pendiente en sync_queue, no se toca.
  ///   2. Si la jornada local esta CLOSED_LOCAL_PENDING_SYNC y el servidor
  ///      devuelve un estado anterior, no regresa (conflicto para S3).
  Future<void> _importarJornadas(
    SyncDataset dataset,
    Set<String> pendientes,
  ) async {
    if (dataset.jornadas.isEmpty) return;
    await db.transaction((txn) async {
      for (final jornada in dataset.jornadas) {
        if (pendientes.contains(jornada.id)) continue;

        final local = await txn.query(
          'jornada',
          columns: ['estado'],
          where: 'id = ?',
          whereArgs: [jornada.id],
          limit: 1,
        );
        final estadoLocal =
            local.isNotEmpty ? local.first['estado'] as String : null;
        if (estadoLocal == 'CLOSED_LOCAL_PENDING_SYNC' &&
            _esEstadoAnterior(jornada.estado, estadoLocal)) {
          continue;
        }

        await _upsertPorPk(
          txn,
          'jornada',
          jornada.toMap(cobradorId: dataset.cobradorId),
        );
      }
    });
  }

  /// Importa pagos o movimientos suspendiendo los triggers de guarda de
  /// jornada abierta DENTRO de la transaccion: el servidor envia jornadas
  /// cerradas y la guarda rechazaria el insert. DDL es transaccional en
  /// SQLite, asi que un fallo revierte tambien el DROP y deja las guardas
  /// intactas.
  ///
  /// Entidades con trabajo pendiente en sync_queue no se sobrescriben.
  Future<void> _importarGuardadoConJornadaAbierta(
    String tabla,
    List<SyncFila> filas,
    Set<String> pendientes,
  ) async {
    if (filas.isEmpty) return;
    await db.transaction((txn) async {
      await txn.execute('DROP TRIGGER IF EXISTS trg_pago_require_open_jornada');
      await txn.execute(
          'DROP TRIGGER IF EXISTS trg_movimiento_require_open_jornada');
      try {
        for (final fila in filas) {
          if (pendientes.contains(fila.id)) continue;
          await _upsertPorPk(txn, tabla, fila.toMap());
        }
      } finally {
        await txn.execute(TriggerGuardasJornada.pago);
        await txn.execute(TriggerGuardasJornada.movimiento);
      }
    });
  }

  /// Upsert por PK explicito. Solo se actualizan las columnas presentes en la
  /// fila (nunca el id). Un conflicto UNIQUE distinto del PK (p.ej.
  /// clave_idempotencia) propaga la excepcion de la base: fallo controlado,
  /// sin borrar la fila local.
  Future<void> _upsertPorPk(
    DatabaseExecutor txn,
    String tabla,
    Map<String, dynamic> fila,
  ) async {
    final columnas = fila.keys.toList();
    final sets = columnas
        .where((c) => c != 'id')
        .map((c) => '$c = excluded.$c')
        .join(', ');
    final placeholders = List.filled(columnas.length, '?').join(', ');

    final sql = 'INSERT INTO $tabla (${columnas.join(', ')}) '
        'VALUES ($placeholders) '
        'ON CONFLICT(id) DO UPDATE SET $sets';

    await txn.rawInsert(sql, columnas.map((c) => fila[c]).toList());
  }

  /// Entidades con outbox pendiente (sync_queue estado PENDIENTE_DE_SINCRONIZAR).
  Future<Set<String>> _entidadesPendientes(DatabaseExecutor txn) async {
    final rows = await txn.query(
      'sync_queue',
      columns: ['entidad_id'],
      where: 'estado = ?',
      whereArgs: ['PENDIENTE_DE_SINCRONIZAR'],
    );
    return rows.map((r) => r['entidad_id'] as String).toSet();
  }

  /// Creditos con pagos locales pendientes de sincronizar. Sus cuotas no se
  /// revierten con el estado del servidor durante el pull.
  Future<Set<String>> _creditosConPagoPendiente(DatabaseExecutor txn) async {
    final rows = await txn.rawQuery('''
      SELECT DISTINCT p.credito_id AS credito_id
      FROM sync_queue sq
      JOIN pago p ON p.id = sq.entidad_id
      WHERE sq.estado = 'PENDIENTE_DE_SINCRONIZAR'
        AND p.credito_id IS NOT NULL
    ''');
    return rows
        .map((r) => r['credito_id'] as String)
        .toSet();
  }

  /// true si [candidato] es un estado anterior a [referencia] en el ciclo de
  /// vida de la jornada (OPEN < CLOSING < CLOSED_LOCAL_PENDING_SYNC <
  /// CLOSED_SYNCED). Sin jornada local (null) nunca es "anterior".
  bool _esEstadoAnterior(String candidato, String? referencia) {
    if (referencia == null) return false;
    final i = _ordenEstadosJornada.indexOf(candidato);
    final j = _ordenEstadosJornada.indexOf(referencia);
    if (i < 0 || j < 0) return false;
    return i < j;
  }
}
