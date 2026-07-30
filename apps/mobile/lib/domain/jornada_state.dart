/// Estado de una jornada de cobro.
/// Reemplaza los strings 'OPEN', 'CLOSED_LOCAL_PENDING_SYNC', 'CLOSED_SYNCED'
/// dispersos en el código.
enum JornadaState {
  /// Jornada abierta, acepta mutaciones financieras.
  open,

  /// Jornada cerrada localmente, pendiente de sincronizar.
  closedLocalPendingSync,

  /// Jornada cerrada y sincronizada con el servidor.
  closedSynced,
}

extension JornadaStateExtension on JornadaState {
  /// Convierte el enum a string para persistencia en SQLite.
  String toSql() {
    switch (this) {
      case JornadaState.open:
        return 'OPEN';
      case JornadaState.closedLocalPendingSync:
        return 'CLOSED_LOCAL_PENDING_SYNC';
      case JornadaState.closedSynced:
        return 'CLOSED_SYNCED';
    }
  }

  /// Convierte un string de SQLite al enum correspondiente.
  static JornadaState fromSql(String sql) {
    switch (sql) {
      case 'OPEN':
        return JornadaState.open;
      case 'CLOSED_LOCAL_PENDING_SYNC':
        return JornadaState.closedLocalPendingSync;
      case 'CLOSED_SYNCED':
        return JornadaState.closedSynced;
      default:
        throw ArgumentError('Estado de jornada no reconocido: $sql');
    }
  }

  /// Verifica si la jornada acepta mutaciones financieras.
  bool get isMutatable => this == JornadaState.open;
}
