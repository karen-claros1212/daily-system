// Persistencia del sync (SyncRepository) contra SQLite real (FFI).
//
// Cubre las reglas endurecidas del bloque offline sync (S2):
//   - cada dataset se persiste en su PROPIA transaccion (atomico por dataset)
//   - upsert por PK explicito: INSERT ... ON CONFLICT(id) DO UPDATE SET.
//     Jamas INSERT OR REPLACE: un conflicto UNIQUE que no sea el PK
//     (pago.clave_idempotencia) falla de forma controlada y nunca borra la
//     fila local.
//   - proteccion del estado local pendiente: una entidad con trabajo en
//     sync_queue no se sobrescribe; una jornada CLOSED_LOCAL_PENDING_SYNC no
//     regresa a un estado anterior del servidor; la cuota de un credito con
//     pago local pendiente no se revierte.
//   - el import de pagos/movimientos DROP/re-CREATE las guardas de jornada
//     abierta dentro de la transaccion (DDL transaccional): se aceptan
//     jornadas cerradas del servidor, y tras el import (exito O rollback) las
//     guardas quedan activas.
//   - limpiarDatosDeRuta borra lo financiero sin tocar identidad ni
//     sync_queue/snapshot; rechaza con SyncPendienteException si hay outbox
//     pendiente o jornada de cierre local pendiente.

import 'package:daily_system/database/database.dart';
import 'package:daily_system/domain/domain_exceptions.dart';
import 'package:daily_system/services/pago_service.dart';
import 'package:daily_system/sync/sync_models.dart';
import 'package:daily_system/sync/sync_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite/sqflite.dart';

import '../helpers/fixture.dart';

const List<SyncCliente> _clientes = [
  SyncCliente(
    id: 'cl1',
    negocioId: 'n1',
    primerApellido: 'Perez',
    nombres: 'Ana',
    tipoDocumento: 'CC',
    documentoNormalizado: '1234567890',
    telefono1: '3001234567',
    barrio: 'Centro',
    ocupacion: 'Independiente',
  ),
];

const List<SyncCredito> _creditos = [
  SyncCredito(
    id: 'cr1',
    negocioId: 'n1',
    clienteId: 'cl1',
    rutaId: 'r1',
    cuota: 5000,
    nCuotas: 10,
    monto: 5000,
    total: 50000,
    periodicidad: 'DIARIO',
    fechaInicio: '2026-08-01',
    estado: 'ACTIVO',
  ),
];

const List<SyncCuota> _cuotas = [
  SyncCuota(
    id: 'cu1',
    creditoId: 'cr1',
    numero: 1,
    fechaVencimiento: '2026-08-02',
    monto: 5000,
    estado: 'PENDIENTE',
  ),
];

const List<SyncJornada> _jornadas = [
  SyncJornada(
    id: 'j1',
    negocioId: 'n1',
    rutaId: 'r1',
    fecha: '2026-08-08',
    estado: 'CLOSED_SYNCED',
    openingBase: 50000,
    contado: 5000,
    esperado: 5000,
  ),
];

const List<SyncPago> _pagos = [
  SyncPago(
    id: 'p1',
    negocioId: 'n1',
    creditoId: 'cr1',
    jornadaId: 'j1',
    tipo: 'PAYMENT',
    monto: 5000,
    claveIdempotencia: 'sync-pago-1',
    recibidoElServidor: '2026-08-08T18:00:00Z',
  ),
];

const List<SyncMovimiento> _movimientos = [
  SyncMovimiento(
    id: 'm1',
    negocioId: 'n1',
    jornadaId: 'j1',
    tipo: 'GASOLINA',
    naturaleza: 'GASTO',
    monto: 12000,
    nota: 'Combustible',
  ),
];

SyncDataset _datasetCompleto() {
  return SyncDataset(
    negocioId: 'n1',
    cobradorId: 'c1',
    rutaId: 'r1',
    rutaVersion: 2,
    clientes: _clientes,
    creditos: _creditos,
    cuotas: _cuotas,
    jornadas: _jornadas,
    pagos: _pagos,
    movimientos: _movimientos,
  );
}

/// Misma clave_idempotencia que el pago local p1, pero distinto id: el servidor
/// nunca debe reemplazar/eliminar el pago local para resolver el conflicto.
SyncDataset _datasetConPagoConflicto() {
  return SyncDataset(
    negocioId: 'n1',
    cobradorId: 'c1',
    rutaId: 'r1',
    rutaVersion: 2,
    clientes: _clientes,
    creditos: _creditos,
    cuotas: _cuotas,
    jornadas: _jornadas,
    pagos: [
      SyncPago(
        id: 'p-conflicto',
        negocioId: 'n1',
        creditoId: 'cr1',
        jornadaId: 'j1',
        tipo: 'PAYMENT',
        monto: 5000,
        claveIdempotencia: 'sync-pago-1',
        recibidoElServidor: '2026-08-08T18:01:00Z',
      ),
    ],
    movimientos: _movimientos,
  );
}

/// Dataset que incluye un PAYMENT (p1) y su REVERSAL (r1) enlazado vía
/// reversal_of_payment_id: el servidor envía el reversal con el enlace al pago
/// original, y el pull local debe preservarlo para bloquear un doble reverso.
SyncDataset _datasetConPagoYReversal() {
  return SyncDataset(
    negocioId: 'n1',
    cobradorId: 'c1',
    rutaId: 'r1',
    rutaVersion: 2,
    clientes: _clientes,
    creditos: _creditos,
    cuotas: _cuotas,
    jornadas: _jornadas,
    pagos: [
      const SyncPago(
        id: 'p1',
        negocioId: 'n1',
        creditoId: 'cr1',
        jornadaId: 'j1',
        tipo: 'PAYMENT',
        monto: 5000,
        claveIdempotencia: 'sync-pago-1',
        recibidoElServidor: '2026-08-08T18:00:00Z',
      ),
      SyncPago(
        id: 'r1',
        negocioId: 'n1',
        creditoId: 'cr1',
        jornadaId: 'j1',
        cobradorId: 'c1',
        tipo: 'REVERSAL',
        monto: 5000,
        claveIdempotencia: 'sync-reversal-1',
        registradoElDispositivo: '2026-08-08T17:00:00Z',
        recibidoElServidor: '2026-08-08T18:05:00Z',
        nota: 'Reversal de prueba',
        reversalOfPaymentId: 'p1',
      ),
    ],
    movimientos: _movimientos,
  );
}

/// Dataset con la jornada j1 en el estado indicado por el servidor.
SyncDataset _datasetConJornada(String estado) {
  return SyncDataset(
    negocioId: 'n1',
    cobradorId: 'c1',
    rutaId: 'r1',
    rutaVersion: 2,
    jornadas: [
      SyncJornada(
        id: 'j1',
        negocioId: 'n1',
        rutaId: 'r1',
        fecha: '2026-08-08',
        estado: estado,
        openingBase: 50000,
        contado: 5000,
        esperado: 5000,
      ),
    ],
  );
}

/// Dos creditos/cuotas: el servidor aun ve cu1 PENDIENTE y (opcionalmente) ya
/// ve cu2 PAGADO (pago registrado en otro dispositivo).
SyncDataset _datasetDobleCuota({bool cuota2PagadaServidor = false}) {
  return SyncDataset(
    negocioId: 'n1',
    cobradorId: 'c1',
    rutaId: 'r1',
    rutaVersion: 2,
    clientes: _clientes,
    creditos: const [
      SyncCredito(
        id: 'cr1',
        negocioId: 'n1',
        clienteId: 'cl1',
        rutaId: 'r1',
        cuota: 5000,
        nCuotas: 10,
        monto: 5000,
        total: 50000,
        fechaInicio: '2026-08-01',
      ),
      SyncCredito(
        id: 'cr2',
        negocioId: 'n1',
        clienteId: 'cl1',
        rutaId: 'r1',
        cuota: 4000,
        nCuotas: 5,
        monto: 4000,
        total: 20000,
        fechaInicio: '2026-08-05',
      ),
    ],
    cuotas: [
      const SyncCuota(
        id: 'cu1',
        creditoId: 'cr1',
        numero: 1,
        fechaVencimiento: '2026-08-02',
        monto: 5000,
        estado: 'PENDIENTE',
      ),
      SyncCuota(
        id: 'cu2',
        creditoId: 'cr2',
        numero: 1,
        fechaVencimiento: '2026-08-06',
        monto: 4000,
        estado: cuota2PagadaServidor ? 'PAGADO' : 'PENDIENTE',
      ),
    ],
    jornadas: _jornadas,
    pagos: _pagos,
    movimientos: _movimientos,
  );
}

void main() {
  initTestDatabase();

  late Database db;
  late SyncRepository repo;

  setUp(() async {
    await clearDatabase();
    db = await database;
    repo = SyncRepository(db);
  });

  group('SyncRepository — importar dataset completo', () {
    test('persiste identidad y los 6 datasets en el modelo local', () async {
      await repo.importar(_datasetCompleto());

      final negocio = await db.query('negocio', where: 'id = ?', whereArgs: ['n1']);
      final usuario = await db.query('usuario', where: 'id = ?', whereArgs: ['c1']);
      final ruta = await db.query('ruta', where: 'id = ?', whereArgs: ['r1']);
      final clientes = await db.query('cliente', where: 'id = ?', whereArgs: ['cl1']);
      final creditos = await db.query('credito', where: 'id = ?', whereArgs: ['cr1']);
      final cuotas = await db.query('cuota_programada', where: 'id = ?', whereArgs: ['cu1']);
      final jornadas = await db.query('jornada', where: 'id = ?', whereArgs: ['j1']);
      final pagos = await db.query('pago', where: 'id = ?', whereArgs: ['p1']);
      final movimientos = await db.query('movimiento', where: 'id = ?', whereArgs: ['m1']);

      expect(negocio, hasLength(1));
      expect(usuario, hasLength(1));
      expect(usuario.first['rol'], 'COBRADOR');
      expect(ruta, hasLength(1));
      expect(ruta.first['cobrador_id'], 'c1');
      expect(ruta.first['activa'], 1);
      expect(clientes, hasLength(1));
      expect(clientes.first['barrio'], 'Centro');
      expect(creditos, hasLength(1));
      expect(creditos.first['total'], 50000);
      expect(cuotas, hasLength(1));
      expect(jornadas, hasLength(1));
      expect(jornadas.first['estado'], 'CLOSED_SYNCED');
      expect(pagos, hasLength(1));
      expect(pagos.first['monto'], 5000);
      expect(movimientos, hasLength(1));
      expect(movimientos.first['monto'], 12000);
    });

    test('acepta pagos/movimientos de jornadas CERRADAS (guarda suspendida en txn)',
        () async {
      await repo.importar(_datasetCompleto());

      final pagos = await db.query('pago', where: 'jornada_id = ?', whereArgs: ['j1']);
      final movimientos = await db.query('movimiento', where: 'jornada_id = ?', whereArgs: ['j1']);
      expect(pagos, hasLength(1));
      expect(movimientos, hasLength(1));
    });

    test('tras el import las guardas de jornada abierta siguen activas', () async {
      await repo.importar(_datasetCompleto());

      await expectLater(
        db.insert('pago', {
          'id': 'p-forzado',
          'negocio_id': 'n1',
          'jornada_id': 'j1',
          'tipo': 'PAYMENT',
          'monto': 1000,
          'clave_idempotencia': 'forzado-1',
        }),
        throwsA(isA<DatabaseException>()),
      );

      await expectLater(
        db.insert('movimiento', {
          'id': 'm-forzado',
          'negocio_id': 'n1',
          'jornada_id': 'j1',
          'tipo': 'GASOLINA',
          'monto': 1000,
        }),
        throwsA(isA<DatabaseException>()),
      );
    });

    test('es idempotente: importar dos veces no duplica filas (upsert por PK)',
        () async {
      await repo.importar(_datasetCompleto());
      await repo.importar(_datasetCompleto());

      expect(await db.query('cliente', where: 'id = ?', whereArgs: ['cl1']), hasLength(1));
      expect(await db.query('credito', where: 'id = ?', whereArgs: ['cr1']), hasLength(1));
      expect(await db.query('pago', where: 'id = ?', whereArgs: ['p1']), hasLength(1));
    });

    test('con nombres de bootstrap persiste identidad con nombre humano', () async {
      await repo.importar(
        _datasetCompleto(),
        negocioNombre: 'Negocio Demo',
        cobradorNombre: 'Cobrador Uno',
        rutaNombre: 'Ruta Norte',
      );

      final negocio = await db.query('negocio', where: 'id = ?', whereArgs: ['n1']);
      final usuario = await db.query('usuario', where: 'id = ?', whereArgs: ['c1']);
      final ruta = await db.query('ruta', where: 'id = ?', whereArgs: ['r1']);

      expect(negocio.first['nombre'], 'Negocio Demo');
      expect(usuario.first['nombre'], 'Cobrador Uno');
      expect(ruta.first['nombre'], 'Ruta Norte');
    });
  });

  group('SyncRepository — protección del estado local pendiente', () {
    test('A) pago remoto con misma clave y distinto id: conflicto controlado, '
        'no elimina el pago local', () async {
      await repo.importar(_datasetCompleto());

      await expectLater(
        repo.importar(_datasetConPagoConflicto()),
        throwsA(isA<DatabaseException>()),
      );

      final local = await db.query('pago', where: 'id = ?', whereArgs: ['p1']);
      expect(local, hasLength(1));
      expect(local.first['clave_idempotencia'], 'sync-pago-1');
      expect(local.first['monto'], 5000);
      expect(await db.query('pago', where: 'id = ?', whereArgs: ['p-conflicto']),
          isEmpty);
    });

    test('D) tras un import fallido las guardas de jornada siguen activas '
        '(rollback del DROP)', () async {
      await repo.importar(_datasetCompleto());

      await expectLater(
        repo.importar(_datasetConPagoConflicto()),
        throwsA(isA<DatabaseException>()),
      );

      await expectLater(
        db.insert('pago', {
          'id': 'p-fuerza',
          'negocio_id': 'n1',
          'jornada_id': 'j1',
          'tipo': 'PAYMENT',
          'monto': 1000,
          'clave_idempotencia': 'fuerza-1',
        }),
        throwsA(isA<DatabaseException>()),
      );

      await expectLater(
        db.insert('movimiento', {
          'id': 'm-fuerza',
          'negocio_id': 'n1',
          'jornada_id': 'j1',
          'tipo': 'GASOLINA',
          'monto': 1000,
        }),
        throwsA(isA<DatabaseException>()),
      );
    });

    test('B) jornada CLOSED_LOCAL_PENDING_SYNC no regresa a un estado anterior '
        'del servidor', () async {
      await repo.importar(_datasetCompleto());
      await db.update('jornada', {'estado': 'CLOSED_LOCAL_PENDING_SYNC'},
          where: 'id = ?', whereArgs: ['j1']);

      await repo.importar(_datasetConJornada('OPEN'));

      final j1 = (await db.query('jornada', where: 'id = ?', whereArgs: ['j1'])).first;
      expect(j1['estado'], 'CLOSED_LOCAL_PENDING_SYNC');
    });

    test('B) jornada CLOSED_LOCAL_PENDING_SYNC si avanza a CLOSED_SYNCED '
        '(estado posterior)', () async {
      await repo.importar(_datasetCompleto());
      await db.update('jornada', {'estado': 'CLOSED_LOCAL_PENDING_SYNC'},
          where: 'id = ?', whereArgs: ['j1']);

      await repo.importar(_datasetConJornada('CLOSED_SYNCED'));

      final j1 = (await db.query('jornada', where: 'id = ?', whereArgs: ['j1'])).first;
      expect(j1['estado'], 'CLOSED_SYNCED');
    });

    test('B) jornada con trabajo pendiente en sync_queue no se sobrescribe',
        () async {
      await repo.importar(_datasetCompleto());
      await db.update('jornada', {'estado': 'OPEN'},
          where: 'id = ?', whereArgs: ['j1']);
      await db.insert('sync_queue', {
        'id': 'sq-j1',
        'tipo': 'jornada_cierre',
        'entidad_id': 'j1',
        'datos': '{}',
        'creado_el': '2026-08-08T18:00:00Z',
        'estado': 'PENDIENTE_DE_SINCRONIZAR',
      });

      await repo.importar(_datasetConJornada('CLOSED_SYNCED'));

      final j1 = (await db.query('jornada', where: 'id = ?', whereArgs: ['j1'])).first;
      expect(j1['estado'], 'OPEN');
    });

    test('cuota de credito con pago local pendiente no se revierte con el '
        'servidor', () async {
      await repo.importar(_datasetDobleCuota());

      await db.update('jornada', {'estado': 'OPEN'},
          where: 'id = ?', whereArgs: ['j1']);
      await db.insert('pago', {
        'id': 'lp1',
        'negocio_id': 'n1',
        'credito_id': 'cr1',
        'jornada_id': 'j1',
        'tipo': 'PAYMENT',
        'monto': 5000,
        'clave_idempotencia': 'local-pago-1',
      });
      await db.update('cuota_programada', {'estado': 'PAGADO'},
          where: 'id = ?', whereArgs: ['cu1']);
      await db.insert('sync_queue', {
        'id': 'sq-lp1',
        'tipo': 'pago',
        'entidad_id': 'lp1',
        'datos': '{}',
        'creado_el': '2026-08-08T18:30:00Z',
        'estado': 'PENDIENTE_DE_SINCRONIZAR',
      });

      await repo.importar(_datasetDobleCuota(cuota2PagadaServidor: true));

      final cu1 = (await db.query('cuota_programada', where: 'id = ?', whereArgs: ['cu1'])).first;
      final cu2 = (await db.query('cuota_programada', where: 'id = ?', whereArgs: ['cu2'])).first;
      expect(cu1['estado'], 'PAGADO');
      expect(cu2['estado'], 'PAGADO');
      expect(await db.query('pago', where: 'id = ?', whereArgs: ['lp1']), hasLength(1));
    });

    test('S2-H2) reversal del servidor preserva reversal_of_payment_id y bloquea '
        'un doble reverso local', () async {
      await repo.importar(_datasetConPagoYReversal());

      final r1 = (await db.query('pago', where: 'id = ?', whereArgs: ['r1'])).first;
      expect(r1['reversal_of_payment_id'], 'p1');
      expect(r1['nota'], 'Reversal de prueba');

      await db.update('jornada', {'estado': 'OPEN'},
          where: 'id = ?', whereArgs: ['j1']);

      await expectLater(
        PagoService.reversarPago(
          'p1',
          'j1',
          'c1',
          'n1',
          'intento de doble reversal',
        ),
        throwsA(isA<PagoYaReversadoException>()),
      );
    });
  });

  group('SyncRepository — limpiarDatosDeRuta', () {
    test('con la cola sin pendientes limpia lo financiero y conserva identidad '
        'y cola', () async {
      await repo.importar(_datasetCompleto());
      await db.insert('sync_queue', {
        'id': 'sq-ok',
        'tipo': 'pago',
        'entidad_id': 'p1',
        'datos': '{}',
        'creado_el': '2026-08-08T18:00:00Z',
        'estado': 'SINCRONIZADO',
      });

      await repo.limpiarDatosDeRuta();

      expect(await db.query('cliente'), isEmpty);
      expect(await db.query('credito'), isEmpty);
      expect(await db.query('cuota_programada'), isEmpty);
      expect(await db.query('jornada'), isEmpty);
      expect(await db.query('pago'), isEmpty);
      expect(await db.query('movimiento'), isEmpty);
      expect(await db.query('negocio', where: 'id = ?', whereArgs: ['n1']), hasLength(1));
      expect(await db.query('usuario', where: 'id = ?', whereArgs: ['c1']), hasLength(1));
      expect(await db.query('ruta', where: 'id = ?', whereArgs: ['r1']), hasLength(1));
      expect(await db.query('sync_queue'), hasLength(1));
    });

    test('C) con outbox pendiente rechaza la limpieza y no borra nada', () async {
      await repo.importar(_datasetCompleto());
      await db.insert('sync_queue', {
        'id': 'sq-pend',
        'tipo': 'pago',
        'entidad_id': 'p1',
        'datos': '{}',
        'creado_el': '2026-08-08T18:00:00Z',
        'estado': 'PENDIENTE_DE_SINCRONIZAR',
      });

      await expectLater(
        repo.limpiarDatosDeRuta(),
        throwsA(isA<SyncPendienteException>()),
      );

      expect(await db.query('cliente', where: 'id = ?', whereArgs: ['cl1']), hasLength(1));
      expect(await db.query('credito', where: 'id = ?', whereArgs: ['cr1']), hasLength(1));
      expect(await db.query('cuota_programada', where: 'id = ?', whereArgs: ['cu1']), hasLength(1));
      expect(await db.query('jornada', where: 'id = ?', whereArgs: ['j1']), hasLength(1));
      expect(await db.query('pago', where: 'id = ?', whereArgs: ['p1']), hasLength(1));
      expect(await db.query('movimiento', where: 'id = ?', whereArgs: ['m1']), hasLength(1));
      expect(await db.query('sync_queue', where: 'id = ?', whereArgs: ['sq-pend']), hasLength(1));
    });

    test('C) con jornada de cierre local pendiente rechaza la limpieza', () async {
      await repo.importar(_datasetCompleto());
      await db.update('jornada', {'estado': 'CLOSED_LOCAL_PENDING_SYNC'},
          where: 'id = ?', whereArgs: ['j1']);

      await expectLater(
        repo.limpiarDatosDeRuta(),
        throwsA(isA<SyncPendienteException>()),
      );

      expect(await db.query('jornada', where: 'id = ?', whereArgs: ['j1']), hasLength(1));
      expect(await db.query('pago', where: 'id = ?', whereArgs: ['p1']), hasLength(1));
    });
  });
}
