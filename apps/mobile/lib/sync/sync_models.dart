// ─── DTOs del sync del movil (Bloque offline sync, S2) ──────────────────────
//
// Mapean el contrato GET /api/mobile/sync del backend (SyncResponse en
// src/schemas/__init__.py): el dataset COMPLETO de la ruta activa unica del
// cobrador. El scope lo deriva el servidor; el movil solo refleja y persiste.
//
// Cada clase expone toMap() con las columnas EXACTAS de la tabla local
// (lib/database/tables.dart): se reutiliza el modelo financiero local, no se
// crea un segundo modelo. Los campos que el servidor no expone (cobrador_id,
// nota, etc.) quedan null en el insert, como en el modelo local.

/// Una fila del sync que se puede persistir en el modelo local.
abstract class SyncFila {
  String get id;

  Map<String, dynamic> toMap();
}

class SyncCliente implements SyncFila {
  @override
  final String id;
  final String negocioId;
  final String primerApellido;
  final String nombres;
  final String? tipoDocumento;
  final String? documentoNormalizado;
  final String? telefono1;
  final String? direccion;
  final String? barrio;
  final String? ciudad;
  final String? ocupacion;
  final String identityStatus;

  const SyncCliente({
    required this.id,
    required this.negocioId,
    required this.primerApellido,
    required this.nombres,
    this.tipoDocumento,
    this.documentoNormalizado,
    this.telefono1,
    this.direccion,
    this.barrio,
    this.ciudad,
    this.ocupacion,
    this.identityStatus = 'PROVISIONAL',
  });

  factory SyncCliente.fromJson(Map<String, dynamic> json) {
    return SyncCliente(
      id: json['id'] as String,
      negocioId: json['negocio_id'] as String,
      primerApellido: json['primer_apellido'] as String,
      nombres: json['nombres'] as String,
      tipoDocumento: json['tipo_documento'] as String?,
      documentoNormalizado: json['documento_normalizado'] as String?,
      telefono1: json['telefono_1'] as String?,
      direccion: json['direccion'] as String?,
      barrio: json['barrio'] as String?,
      ciudad: json['ciudad'] as String?,
      ocupacion: json['ocupacion'] as String?,
      identityStatus: json['identity_status'] as String? ?? 'PROVISIONAL',
    );
  }

  @override
  Map<String, dynamic> toMap() => {
        'id': id,
        'negocio_id': negocioId,
        'primer_apellido': primerApellido,
        'nombres': nombres,
        'tipo_documento': tipoDocumento,
        'documento_normalizado': documentoNormalizado,
        'telefono_1': telefono1,
        'direccion': direccion,
        'barrio': barrio,
        'ciudad': ciudad,
        'ocupacion': ocupacion,
        'identity_status': identityStatus,
      };
}

class SyncCredito implements SyncFila {
  @override
  final String id;
  final String negocioId;
  final String clienteId;
  final String rutaId;
  final int cuota;
  final int nCuotas;
  final int monto;
  final int total;
  final String periodicidad;
  final String fechaInicio;
  final String estado;

  const SyncCredito({
    required this.id,
    required this.negocioId,
    required this.clienteId,
    required this.rutaId,
    required this.cuota,
    required this.nCuotas,
    required this.monto,
    required this.total,
    this.periodicidad = 'DIARIO',
    required this.fechaInicio,
    this.estado = 'ACTIVO',
  });

  factory SyncCredito.fromJson(Map<String, dynamic> json) {
    return SyncCredito(
      id: json['id'] as String,
      negocioId: json['negocio_id'] as String,
      clienteId: json['cliente_id'] as String,
      rutaId: json['ruta_id'] as String,
      cuota: json['cuota'] as int,
      nCuotas: json['n_cuotas'] as int,
      monto: json['monto'] as int,
      total: json['total'] as int,
      periodicidad: json['periodicidad'] as String? ?? 'DIARIO',
      fechaInicio: json['fecha_inicio'] as String,
      estado: json['estado'] as String? ?? 'ACTIVO',
    );
  }

  @override
  Map<String, dynamic> toMap() => {
        'id': id,
        'negocio_id': negocioId,
        'cliente_id': clienteId,
        'ruta_id': rutaId,
        'cuota': cuota,
        'n_cuotas': nCuotas,
        'monto': monto,
        'total': total,
        'periodicidad': periodicidad,
        'fecha_inicio': fechaInicio,
        'estado': estado,
      };
}

class SyncCuota implements SyncFila {
  @override
  final String id;
  final String creditoId;
  final int numero;
  final String fechaVencimiento;
  final int monto;
  final String estado;

  const SyncCuota({
    required this.id,
    required this.creditoId,
    required this.numero,
    required this.fechaVencimiento,
    required this.monto,
    this.estado = 'PENDIENTE',
  });

  factory SyncCuota.fromJson(Map<String, dynamic> json) {
    return SyncCuota(
      id: json['id'] as String,
      creditoId: json['credito_id'] as String,
      numero: json['numero'] as int,
      fechaVencimiento: json['fecha_vencimiento'] as String,
      monto: json['monto'] as int,
      estado: json['estado'] as String? ?? 'PENDIENTE',
    );
  }

  @override
  Map<String, dynamic> toMap() => {
        'id': id,
        'credito_id': creditoId,
        'numero': numero,
        'fecha_vencimiento': fechaVencimiento,
        'monto': monto,
        'estado': estado,
      };
}

class SyncPago implements SyncFila {
  @override
  final String id;
  final String negocioId;
  final String? creditoId;
  final String? jornadaId;
  final String? cobradorId;
  final String tipo;
  final int monto;
  final String? registradoElDispositivo;
  final String? recibidoElServidor;
  final String claveIdempotencia;
  final String? nota;
  final String? reversalOfPaymentId;

  const SyncPago({
    required this.id,
    required this.negocioId,
    this.creditoId,
    this.jornadaId,
    this.cobradorId,
    required this.tipo,
    required this.monto,
    this.registradoElDispositivo,
    this.recibidoElServidor,
    required this.claveIdempotencia,
    this.nota,
    this.reversalOfPaymentId,
  });

  factory SyncPago.fromJson(Map<String, dynamic> json) {
    return SyncPago(
      id: json['id'] as String,
      negocioId: json['negocio_id'] as String,
      creditoId: json['credito_id'] as String?,
      jornadaId: json['jornada_id'] as String?,
      cobradorId: json['cobrador_id'] as String?,
      tipo: json['tipo'] as String,
      monto: json['monto'] as int,
      registradoElDispositivo: json['registrado_el_dispositivo'] as String?,
      recibidoElServidor: json['recibido_el_servidor'] as String?,
      claveIdempotencia: json['clave_idempotencia'] as String,
      nota: json['nota'] as String?,
      reversalOfPaymentId: json['reversal_of_payment_id'] as String?,
    );
  }

  @override
  Map<String, dynamic> toMap() => {
        'id': id,
        'negocio_id': negocioId,
        'credito_id': creditoId,
        'jornada_id': jornadaId,
        'cobrador_id': cobradorId,
        'tipo': tipo,
        'monto': monto,
        'clave_idempotencia': claveIdempotencia,
        'nota': nota,
        'registrado_el_dispositivo': registradoElDispositivo,
        'recibido_el_servidor': recibidoElServidor,
        'reversal_of_payment_id': reversalOfPaymentId,
      };
}

class SyncMovimiento implements SyncFila {
  @override
  final String id;
  final String negocioId;
  final String? jornadaId;
  final String tipo;
  final String? naturaleza;
  final int monto;
  final String? nota;
  final String? claveIdempotencia;
  final String? creadoPor;
  final String? creadoEl;

  const SyncMovimiento({
    required this.id,
    required this.negocioId,
    this.jornadaId,
    required this.tipo,
    this.naturaleza,
    required this.monto,
    this.nota,
    this.claveIdempotencia,
    this.creadoPor,
    this.creadoEl,
  });

  factory SyncMovimiento.fromJson(Map<String, dynamic> json) {
    return SyncMovimiento(
      id: json['id'] as String,
      negocioId: json['negocio_id'] as String,
      jornadaId: json['jornada_id'] as String?,
      tipo: json['tipo'] as String,
      naturaleza: json['naturaleza'] as String?,
      monto: json['monto'] as int,
      nota: json['nota'] as String?,
      claveIdempotencia: json['clave_idempotencia'] as String?,
      creadoPor: json['creado_por'] as String?,
      creadoEl: json['creado_el'] as String?,
    );
  }

  @override
  Map<String, dynamic> toMap() => {
        'id': id,
        'negocio_id': negocioId,
        'jornada_id': jornadaId,
        'tipo': tipo,
        'naturaleza': naturaleza,
        'monto': monto,
        'nota': nota,
        'clave_idempotencia': claveIdempotencia,
        'creado_por': creadoPor,
        'creado_el': creadoEl,
      };
}

class SyncJornada implements SyncFila {
  @override
  final String id;
  final String negocioId;
  final String rutaId;
  final String fecha;
  final String estado;
  final int openingBase;
  final int openingCarry;
  final int esperado;
  final int contado;
  final int diferencia;
  final String? diferenciaMotivo;
  final int sobranteManana;

  const SyncJornada({
    required this.id,
    required this.negocioId,
    required this.rutaId,
    required this.fecha,
    this.estado = 'OPEN',
    this.openingBase = 0,
    this.openingCarry = 0,
    this.esperado = 0,
    this.contado = 0,
    this.diferencia = 0,
    this.diferenciaMotivo,
    this.sobranteManana = 0,
  });

  factory SyncJornada.fromJson(Map<String, dynamic> json) {
    return SyncJornada(
      id: json['id'] as String,
      negocioId: json['negocio_id'] as String,
      rutaId: json['ruta_id'] as String,
      fecha: json['fecha'] as String,
      estado: json['estado'] as String? ?? 'OPEN',
      openingBase: json['opening_base'] as int? ?? 0,
      openingCarry: json['opening_carry'] as int? ?? 0,
      esperado: json['esperado'] as int? ?? 0,
      contado: json['contado'] as int? ?? 0,
      diferencia: json['diferencia'] as int? ?? 0,
      diferenciaMotivo: json['diferencia_motivo'] as String?,
      sobranteManana: json['sobrante_manana'] as int? ?? 0,
    );
  }

  @override
  Map<String, dynamic> toMap({String? cobradorId}) => {
        'id': id,
        'negocio_id': negocioId,
        'ruta_id': rutaId,
        'cobrador_id': cobradorId,
        'fecha': fecha,
        'estado': estado,
        'opening_base': openingBase,
        'opening_carry': openingCarry,
        'esperado': esperado,
        'contado': contado,
        'diferencia': diferencia,
        'diferencia_motivo': diferenciaMotivo,
        'sobrante_manana': sobranteManana,
      };
}

/// Respuesta completa de GET /api/mobile/sync. El scope (ruta activa unica)
/// lo deriva el servidor; aqui solo se refleja para validar coherencia local.
class SyncDataset {
  final String negocioId;
  final String cobradorId;
  final String rutaId;
  final int rutaVersion;
  final List<SyncCliente> clientes;
  final List<SyncCredito> creditos;
  final List<SyncCuota> cuotas;
  final List<SyncPago> pagos;
  final List<SyncMovimiento> movimientos;
  final List<SyncJornada> jornadas;

  const SyncDataset({
    required this.negocioId,
    required this.cobradorId,
    required this.rutaId,
    required this.rutaVersion,
    this.clientes = const [],
    this.creditos = const [],
    this.cuotas = const [],
    this.pagos = const [],
    this.movimientos = const [],
    this.jornadas = const [],
  });

  factory SyncDataset.fromJson(Map<String, dynamic> json) {
    return SyncDataset(
      negocioId: json['negocio_id'] as String,
      cobradorId: json['cobrador_id'] as String,
      rutaId: json['ruta_id'] as String,
      rutaVersion: json['ruta_version'] as int,
      clientes: (json['clientes'] as List<dynamic>? ?? [])
          .map((e) => SyncCliente.fromJson(e as Map<String, dynamic>))
          .toList(),
      creditos: (json['creditos'] as List<dynamic>? ?? [])
          .map((e) => SyncCredito.fromJson(e as Map<String, dynamic>))
          .toList(),
      cuotas: (json['cuotas'] as List<dynamic>? ?? [])
          .map((e) => SyncCuota.fromJson(e as Map<String, dynamic>))
          .toList(),
      pagos: (json['pagos'] as List<dynamic>? ?? [])
          .map((e) => SyncPago.fromJson(e as Map<String, dynamic>))
          .toList(),
      movimientos: (json['movimientos'] as List<dynamic>? ?? [])
          .map((e) => SyncMovimiento.fromJson(e as Map<String, dynamic>))
          .toList(),
      jornadas: (json['jornadas'] as List<dynamic>? ?? [])
          .map((e) => SyncJornada.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
