export '../domain/domain_exceptions.dart' show JornadaCerradaException;

import 'package:uuid/uuid.dart';

final _uuid = Uuid();
String uid() => _uuid.v4();

// ─── Models ───────────────────────────────────────────────────────

class Negocio {
  final String id;
  final String nombre;
  final String? nit;
  Negocio({required this.id, required this.nombre, this.nit});
  Map<String, dynamic> toMap() => {'id': id, 'nombre': nombre, 'nit': nit};
  static Negocio fromMap(Map<String, dynamic> m) =>
      Negocio(id: m['id'] as String, nombre: m['nombre'] as String, nit: m['nit'] as String?);
}

class Usuario {
  final String id;
  final String negocioId;
  final String rol;
  final String nombre;
  final String? documento;
  final int activo;
  Usuario({required this.id, required this.negocioId, required this.rol, required this.nombre, this.documento, this.activo = 1});
  Map<String, dynamic> toMap() => {'id': id, 'negocio_id': negocioId, 'rol': rol, 'nombre': nombre, 'documento': documento, 'activo': activo};
  static Usuario fromMap(Map<String, dynamic> m) =>
      Usuario(id: m['id'] as String, negocioId: m['negocio_id'] as String, rol: m['rol'] as String, nombre: m['nombre'] as String, documento: m['documento'] as String?, activo: m['activo'] as int? ?? 1);
}

class Ruta {
  final String id;
  final String negocioId;
  final String nombre;
  final String? cobradorId;
  final int activa;
  Ruta({required this.id, required this.negocioId, required this.nombre, this.cobradorId, this.activa = 1});
  Map<String, dynamic> toMap() => {'id': id, 'negocio_id': negocioId, 'nombre': nombre, 'cobrador_id': cobradorId, 'activa': activa};
  static Ruta fromMap(Map<String, dynamic> m) =>
      Ruta(id: m['id'] as String, negocioId: m['negocio_id'] as String, nombre: m['nombre'] as String, cobradorId: m['cobrador_id'] as String?, activa: m['activa'] as int? ?? 1);
}

class Cliente {
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
  Cliente({required this.id, required this.negocioId, required this.primerApellido, required this.nombres, this.tipoDocumento, this.documentoNormalizado, this.telefono1, this.direccion, this.barrio, this.ciudad, this.ocupacion});
  Map<String, dynamic> toMap() => {'id': id, 'negocio_id': negocioId, 'primer_apellido': primerApellido, 'nombres': nombres, 'tipo_documento': tipoDocumento, 'documento_normalizado': documentoNormalizado, 'telefono_1': telefono1, 'direccion': direccion, 'barrio': barrio, 'ciudad': ciudad, 'ocupacion': ocupacion};
  static Cliente fromMap(Map<String, dynamic> m) =>
      Cliente(id: m['id'] as String, negocioId: m['negocio_id'] as String, primerApellido: m['primer_apellido'] as String, nombres: m['nombres'] as String, tipoDocumento: m['tipo_documento'] as String?, documentoNormalizado: m['documento_normalizado'] as String?, telefono1: m['telefono_1'] as String?, direccion: m['direccion'] as String?, barrio: m['barrio'] as String?, ciudad: m['ciudad'] as String?, ocupacion: m['ocupacion'] as String?);
  String get fullName => '$primerApellido $nombres';
}

class Credito {
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
  Credito({required this.id, required this.negocioId, required this.clienteId, required this.rutaId, required this.cuota, required this.nCuotas, required this.monto, required this.total, this.periodicidad = 'DIARIO', required this.fechaInicio, this.estado = 'ACTIVO'});
  Map<String, dynamic> toMap() => {'id': id, 'negocio_id': negocioId, 'cliente_id': clienteId, 'ruta_id': rutaId, 'cuota': cuota, 'n_cuotas': nCuotas, 'monto': monto, 'total': total, 'periodicidad': periodicidad, 'fecha_inicio': fechaInicio, 'estado': estado};
  static Credito fromMap(Map<String, dynamic> m) =>
      Credito(id: m['id'] as String, negocioId: m['negocio_id'] as String, clienteId: m['cliente_id'] as String, rutaId: m['ruta_id'] as String, cuota: m['cuota'] as int, nCuotas: m['n_cuotas'] as int, monto: m['monto'] as int, total: m['total'] as int, periodicidad: m['periodicidad'] as String? ?? 'DIARIO', fechaInicio: m['fecha_inicio'] as String, estado: m['estado'] as String? ?? 'ACTIVO');
  int saldoPendiente(int pagosTotal) => total - pagosTotal;
}

class CuotaProgramada {
  final String id;
  final String creditoId;
  final int numero;
  final String fechaVencimiento;
  final int monto;
  final String estado;
  CuotaProgramada({required this.id, required this.creditoId, required this.numero, required this.fechaVencimiento, required this.monto, this.estado = 'PENDIENTE'});
  Map<String, dynamic> toMap() => {'id': id, 'credito_id': creditoId, 'numero': numero, 'fecha_vencimiento': fechaVencimiento, 'monto': monto, 'estado': estado};
  static CuotaProgramada fromMap(Map<String, dynamic> m) =>
      CuotaProgramada(id: m['id'] as String, creditoId: m['credito_id'] as String, numero: m['numero'] as int, fechaVencimiento: m['fecha_vencimiento'] as String, monto: m['monto'] as int, estado: m['estado'] as String? ?? 'PENDIENTE');
}

class Jornada {
  final String id;
  final String negocioId;
  final String rutaId;
  final String? cobradorId;
  final String fecha;
  String estado;
  final int openingBase;
  final int openingCarry;
  int esperado;
  int contado;
  int diferencia;
  String? diferenciaMotivo;
  final int sobranteManana;
  String? cerradaLocalEl;
  final String? recibidaServidorEl;
  final String? sincronizadaEl;
  final int efectivoEsperado;
  final int efectivoContado;

  Jornada({required this.id, required this.negocioId, required this.rutaId, this.cobradorId, required this.fecha, this.estado = 'OPEN', this.openingBase = 0, this.openingCarry = 0, this.esperado = 0, this.contado = 0, this.diferencia = 0, this.diferenciaMotivo, this.sobranteManana = 0, this.cerradaLocalEl, this.recibidaServidorEl, this.sincronizadaEl, this.efectivoEsperado = 0, this.efectivoContado = 0});
  Map<String, dynamic> toMap() => {'id': id, 'negocio_id': negocioId, 'ruta_id': rutaId, 'cobrador_id': cobradorId, 'fecha': fecha, 'estado': estado, 'opening_base': openingBase, 'opening_carry': openingCarry, 'esperado': esperado, 'contado': contado, 'diferencia': diferencia, 'diferencia_motivo': diferenciaMotivo, 'sobrante_manana': sobranteManana, 'cerrada_local_el': cerradaLocalEl, 'recibida_servidor_el': recibidaServidorEl, 'sincronizada_el': sincronizadaEl};
  static Jornada fromMap(Map<String, dynamic> m) =>
      Jornada(id: m['id'] as String, negocioId: m['negocio_id'] as String, rutaId: m['ruta_id'] as String, cobradorId: m['cobrador_id'] as String?, fecha: m['fecha'] as String, estado: m['estado'] as String? ?? 'OPEN', openingBase: m['opening_base'] as int? ?? 0, openingCarry: m['opening_carry'] as int? ?? 0, esperado: m['esperado'] as int? ?? 0, contado: m['contado'] as int? ?? 0, diferencia: m['diferencia'] as int? ?? 0, diferenciaMotivo: m['diferencia_motivo'] as String?, sobranteManana: m['sobrante_manana'] as int? ?? 0, cerradaLocalEl: m['cerrada_local_el'] as String?, recibidaServidorEl: m['recibida_servidor_el'] as String?, sincronizadaEl: m['sincronizada_el'] as String?);
  bool get isOpen => estado == 'OPEN';
  bool get isClosed => estado == 'CLOSED_LOCAL_PENDING_SYNC' || estado == 'CLOSED_SYNCED';
}

class Pago {
  final String id;
  final String negocioId;
  final String? creditoId;
  final String? jornadaId;
  final String? cobradorId;
  final String tipo;
  final int monto;
  final String claveIdempotencia;
  final String? nota;
  final String? registradoElDispositivo;
  final String? recibidoElServidor;
  final String? reversalOfPaymentId;
  Pago({required this.id, required this.negocioId, this.creditoId, this.jornadaId, this.cobradorId, required this.tipo, required this.monto, required this.claveIdempotencia, this.nota, this.registradoElDispositivo, this.recibidoElServidor, this.reversalOfPaymentId});
  Map<String, dynamic> toMap() => {'id': id, 'negocio_id': negocioId, 'credito_id': creditoId, 'jornada_id': jornadaId, 'cobrador_id': cobradorId, 'tipo': tipo, 'monto': monto, 'clave_idempotencia': claveIdempotencia, 'nota': nota, 'registrado_el_dispositivo': registradoElDispositivo, 'recibido_el_servidor': recibidoElServidor, 'reversal_of_payment_id': reversalOfPaymentId};
  static Pago fromMap(Map<String, dynamic> m) =>
      Pago(id: m['id'] as String, negocioId: m['negocio_id'] as String, creditoId: m['credito_id'] as String?, jornadaId: m['jornada_id'] as String?, cobradorId: m['cobrador_id'] as String?, tipo: m['tipo'] as String, monto: m['monto'] as int, claveIdempotencia: m['clave_idempotencia'] as String, nota: m['nota'] as String?, registradoElDispositivo: m['registrado_el_dispositivo'] as String?, recibidoElServidor: m['recibido_el_servidor'] as String?, reversalOfPaymentId: m['reversal_of_payment_id'] as String?);
  bool get isPayment => tipo == 'PAYMENT';
  bool get isReversal => tipo == 'REVERSAL';
}

class Movimiento {
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
  Movimiento({required this.id, required this.negocioId, this.jornadaId, required this.tipo, this.naturaleza, required this.monto, this.nota, this.claveIdempotencia, this.creadoPor, this.creadoEl});
  Map<String, dynamic> toMap() => {'id': id, 'negocio_id': negocioId, 'jornada_id': jornadaId, 'tipo': tipo, 'naturaleza': naturaleza, 'monto': monto, 'nota': nota, 'clave_idempotencia': claveIdempotencia, 'creado_por': creadoPor, 'creado_el': creadoEl};
  static Movimiento fromMap(Map<String, dynamic> m) =>
      Movimiento(id: m['id'] as String, negocioId: m['negocio_id'] as String, jornadaId: m['jornada_id'] as String?, tipo: m['tipo'] as String, naturaleza: m['naturaleza'] as String?, monto: m['monto'] as int, nota: m['nota'] as String?, claveIdempotencia: m['clave_idempotencia'] as String?, creadoPor: m['creado_por'] as String?, creadoEl: m['creado_el'] as String?);
}

class SyncQueueItem {
  final String id;
  final String tipo;
  final String entidadId;
  final Map<String, dynamic> datos;
  final DateTime creadoEl;
  final String estado;
  SyncQueueItem({required this.id, required this.tipo, required this.entidadId, required this.datos, required this.creadoEl, this.estado = 'PENDIENTE_DE_SINCRONIZAR'});
  Map<String, dynamic> toMap() => {'id': id, 'tipo': tipo, 'entidad_id': entidadId, 'datos': datos.toString(), 'creado_el': creadoEl.toIso8601String(), 'estado': estado};
  static SyncQueueItem fromMap(Map<String, dynamic> m) =>
      SyncQueueItem(id: m['id'] as String, tipo: m['tipo'] as String, entidadId: m['entidad_id'] as String, datos: {}, creadoEl: DateTime.parse(m['creado_el'] as String), estado: m['estado'] as String? ?? 'PENDIENTE_DE_SINCRONIZAR');
}
