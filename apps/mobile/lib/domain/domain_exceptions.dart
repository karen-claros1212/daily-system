// Excepciones tipadas del dominio financiero.
// Reemplazan las exceptions genéricas con mensajes String dispersos.

/// La jornada no existe en la base de datos.
class JornadaNoEncontradaException implements Exception {
  final String jornadaId;
  JornadaNoEncontradaException(this.jornadaId);
  @override
  String toString() => 'Jornada no encontrada: $jornadaId';
}

/// La jornada está cerrada y se intentó una mutación financiera.
class JornadaCerradaException implements Exception {
  final String jornadaId;
  final String estado;
  JornadaCerradaException(this.jornadaId, this.estado);
  @override
  String toString() =>
      'No se pueden registrar pagos en una jornada cerrada (jornada: $jornadaId, estado: $estado)';
}

/// El pago no existe en la base de datos.
class PagoNoEncontradoException implements Exception {
  final String pagoId;
  PagoNoEncontradoException(this.pagoId);
  @override
  String toString() => 'Pago no encontrado: $pagoId';
}

/// El pago no es reversible (ya fue reversado o no es un pago).
class PagoInvalidoParaReversionException implements Exception {
  final String pagoId;
  PagoInvalidoParaReversionException(this.pagoId);
  @override
  String toString() => 'Pago no reversible: $pagoId';
}

/// El pago ya fue reversado (doble reversión).
class PagoYaReversadoException implements Exception {
  final String pagoId;
  PagoYaReversadoException(this.pagoId);
  @override
  String toString() => 'Pago ya reversado: $pagoId';
}

/// El monto del pago no es válido.
class MontoInvalidoException implements Exception {
  final int monto;
  MontoInvalidoException(this.monto);
  @override
  String toString() => 'Monto inválido: $monto (debe ser > 0)';
}

/// La clave de idempotencia ya existe pero los campos no coinciden.
class IdempotenciaConflictoException implements Exception {
  final String clave;
  final String pagoExistenteId;
  final int nuevoMonto;
  final int montoExistente;
  IdempotenciaConflictoException(this.clave, this.pagoExistenteId, this.nuevoMonto, this.montoExistente);
  @override
  String toString() =>
      'Clave de idempotencia duplicada con monto distinto (clave: $clave, existente: $pagoExistenteId, nuevo: $nuevoMonto, existente: $montoExistente)';
}
