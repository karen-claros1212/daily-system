/// Tipo de pago: PAYMENT o REVERSAL.
enum PagoType {
  payment,
  reversal,
}

extension PagoTypeExtension on PagoType {
  String toSql() {
    switch (this) {
      case PagoType.payment:
        return 'PAYMENT';
      case PagoType.reversal:
        return 'REVERSAL';
    }
  }

  static PagoType fromSql(String sql) {
    switch (sql) {
      case 'PAYMENT':
        return PagoType.payment;
      case 'REVERSAL':
        return PagoType.reversal;
      default:
        throw ArgumentError('Tipo de pago no reconocido: $sql');
    }
  }
}

/// Tipo de movimiento financiero.
enum MovimientoType {
  gasolina,
  oficina,
  ahorro,
  vale,
  entrega,
  recibido,
  desembolso,
  ajuste,
  otro,
}

extension MovimientoTypeExtension on MovimientoType {
  String toSql() {
    switch (this) {
      case MovimientoType.gasolina:
        return 'GASOLINA';
      case MovimientoType.oficina:
        return 'OFICINA';
      case MovimientoType.ahorro:
        return 'AHORRO';
      case MovimientoType.vale:
        return 'VALE';
      case MovimientoType.entrega:
        return 'ENTREGA';
      case MovimientoType.recibido:
        return 'RECIBIDO';
      case MovimientoType.desembolso:
        return 'DESEMBOLSO';
      case MovimientoType.ajuste:
        return 'AJUSTE';
      case MovimientoType.otro:
        return 'OTRO';
    }
  }

  static MovimientoType fromSql(String sql) {
    switch (sql) {
      case 'GASOLINA':
        return MovimientoType.gasolina;
      case 'OFICINA':
        return MovimientoType.oficina;
      case 'AHORRO':
        return MovimientoType.ahorro;
      case 'VALE':
        return MovimientoType.vale;
      case 'ENTREGA':
        return MovimientoType.entrega;
      case 'RECIBIDO':
        return MovimientoType.recibido;
      case 'DESEMBOLSO':
        return MovimientoType.desembolso;
      case 'AJUSTE':
        return MovimientoType.ajuste;
      case 'OTRO':
        return MovimientoType.otro;
      default:
        throw ArgumentError('Tipo de movimiento no reconocido: $sql');
    }
  }

  /// Lista de tipos disponibles en la UI.
  static List<MovimientoType> get allValues => [
        MovimientoType.gasolina,
        MovimientoType.oficina,
        MovimientoType.ahorro,
        MovimientoType.vale,
        MovimientoType.entrega,
        MovimientoType.recibido,
        MovimientoType.desembolso,
        MovimientoType.ajuste,
        MovimientoType.otro,
      ];

  /// Etiqueta para mostrar en la UI.
  String get label {
    switch (this) {
      case MovimientoType.gasolina:
        return 'GASOLINA';
      case MovimientoType.oficina:
        return 'OFICINA';
      case MovimientoType.ahorro:
        return 'AHORRO';
      case MovimientoType.vale:
        return 'VALE';
      case MovimientoType.entrega:
        return 'ENTREGA';
      case MovimientoType.recibido:
        return 'RECIBIDO';
      case MovimientoType.desembolso:
        return 'DESEMBOLSO';
      case MovimientoType.ajuste:
        return 'AJUSTE';
      case MovimientoType.otro:
        return 'OTRO';
    }
  }
}
