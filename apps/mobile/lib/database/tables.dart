class Tables {
  static const String createNegocio = '''
    CREATE TABLE negocio (
      id TEXT PRIMARY KEY,
      nombre TEXT NOT NULL,
      nit TEXT,
      pais TEXT DEFAULT 'CO',
      moneda TEXT DEFAULT 'COP',
      zona_horaria TEXT DEFAULT 'America/Bogota'
    )
  ''';

  static const String createUsuario = '''
    CREATE TABLE usuario (
      id TEXT PRIMARY KEY,
      negocio_id TEXT NOT NULL REFERENCES negocio(id),
      rol TEXT NOT NULL CHECK(rol IN ('ADMINISTRADOR', 'COBRADOR', 'INVERSIONISTA')),
      nombre TEXT NOT NULL,
      documento TEXT,
      activo INTEGER DEFAULT 1
    )
  ''';

  static const String createRuta = '''
    CREATE TABLE ruta (
      id TEXT PRIMARY KEY,
      negocio_id TEXT NOT NULL REFERENCES negocio(id),
      nombre TEXT NOT NULL,
      cobrador_id TEXT REFERENCES usuario(id),
      activa INTEGER DEFAULT 1
    )
  ''';

  static const String createCliente = '''
    CREATE TABLE cliente (
      id TEXT PRIMARY KEY,
      negocio_id TEXT NOT NULL REFERENCES negocio(id),
      primer_apellido TEXT NOT NULL,
      nombres TEXT NOT NULL,
      tipo_documento TEXT,
      documento_normalizado TEXT,
      telefono_1 TEXT,
      direccion TEXT,
      barrio TEXT,
      ciudad TEXT,
      ocupacion TEXT,
      identity_status TEXT DEFAULT 'PROVISIONAL'
    )
  ''';

  static const String createCredito = '''
    CREATE TABLE credito (
      id TEXT PRIMARY KEY,
      negocio_id TEXT NOT NULL REFERENCES negocio(id),
      cliente_id TEXT NOT NULL REFERENCES cliente(id),
      ruta_id TEXT NOT NULL REFERENCES ruta(id),
      cuota INTEGER NOT NULL,
      n_cuotas INTEGER NOT NULL,
      monto INTEGER NOT NULL,
      total INTEGER NOT NULL CHECK(total = cuota * n_cuotas),
      periodicidad TEXT DEFAULT 'DIARIO',
      fecha_inicio TEXT NOT NULL,
      estado TEXT DEFAULT 'ACTIVO' CHECK(estado IN ('ACTIVO', 'PAGADO', 'REFINANCIADO', 'CANCELADO'))
    )
  ''';

  static const String createCuotaProgramada = '''
    CREATE TABLE cuota_programada (
      id TEXT PRIMARY KEY,
      credito_id TEXT NOT NULL REFERENCES credito(id),
      numero INTEGER NOT NULL,
      fecha_vencimiento TEXT NOT NULL,
      monto INTEGER NOT NULL,
      estado TEXT DEFAULT 'PENDIENTE' CHECK(estado IN ('PENDIENTE', 'PAGADO', 'VENCIDO', 'RENANCIADO'))
    )
  ''';

  static const String createJornada = '''
    CREATE TABLE jornada (
      id TEXT PRIMARY KEY,
      negocio_id TEXT NOT NULL REFERENCES negocio(id),
      ruta_id TEXT NOT NULL REFERENCES ruta(id),
      cobrador_id TEXT REFERENCES usuario(id),
      fecha TEXT NOT NULL,
      estado TEXT DEFAULT 'OPEN' CHECK(estado IN ('OPEN', 'CLOSING', 'CLOSED_LOCAL_PENDING_SYNC', 'CLOSED_SYNCED')),
      opening_base INTEGER DEFAULT 0,
      opening_carry INTEGER DEFAULT 0,
      esperado INTEGER DEFAULT 0,
      contado INTEGER DEFAULT 0,
      diferencia INTEGER DEFAULT 0,
      diferencia_motivo TEXT,
      sobrante_manana INTEGER DEFAULT 0,
      cerrada_local_el TEXT,
      recibida_servidor_el TEXT,
      sincronizada_el TEXT
    )
  ''';

  static const String createPago = '''
    CREATE TABLE pago (
      id TEXT PRIMARY KEY,
      negocio_id TEXT NOT NULL REFERENCES negocio(id),
      credito_id TEXT REFERENCES credito(id),
      jornada_id TEXT REFERENCES jornada(id),
      cobrador_id TEXT REFERENCES usuario(id),
      tipo TEXT NOT NULL CHECK(tipo IN ('PAYMENT', 'REVERSAL')),
      monto INTEGER NOT NULL,
      clave_idempotencia TEXT NOT NULL UNIQUE,
      nota TEXT,
      registrado_el_dispositivo TEXT,
      recibido_el_servidor TEXT,
      reversal_of_payment_id TEXT
    )
  ''';

  static const String createMovimiento = '''
    CREATE TABLE movimiento (
      id TEXT PRIMARY KEY,
      negocio_id TEXT NOT NULL REFERENCES negocio(id),
      jornada_id TEXT REFERENCES jornada(id),
      tipo TEXT NOT NULL CHECK(tipo IN ('GASOLINA', 'OFICINA', 'AHORRO', 'VALE', 'ENTREGA', 'RECIBIDO', 'DESEMBOLSO', 'AJUSTE', 'OTRO')),
      naturaleza TEXT CHECK(naturaleza IN ('GASTO', 'CUSTODIA', 'CUENTA_POR_COBRAR', 'TRASLADO_ENTRADA', 'TRASLADO_SALIDA', 'DESEMBOLSO', 'AJUSTE')),
      monto INTEGER NOT NULL,
      nota TEXT,
      clave_idempotencia TEXT,
      creado_por TEXT,
      creado_el TEXT
    )
  ''';

  static const List<String> all = [
    createNegocio,
    createUsuario,
    createRuta,
    createCliente,
    createCredito,
    createCuotaProgramada,
    createJornada,
    createPago,
    createMovimiento,
  ];
}
