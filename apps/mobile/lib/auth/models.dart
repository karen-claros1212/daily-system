// ─── DTOs del flujo productivo (bloque mobile auth + bootstrap) ────────────
//
// Mapean los contratos de respuesta del backend (src/schemas/__init__.py) y
// reflejan SOLO la identidad operativa que el dispositivo puede conservar:
// negocio, cobrador, dispositivo, version_asignacion, ruta unica y su
// version. No hay lista de rutas ni autoridad local de route_id.

class DesafioActivacion {
  final String intentoId;
  final String nonce;
  final String expiraEl;
  final String environment;

  const DesafioActivacion({
    required this.intentoId,
    required this.nonce,
    required this.expiraEl,
    required this.environment,
  });

  factory DesafioActivacion.fromJson(Map<String, dynamic> json) {
    return DesafioActivacion(
      intentoId: json['intento_id'] as String,
      nonce: json['nonce'] as String,
      expiraEl: json['expira_el'] as String,
      environment: json['environment'] as String,
    );
  }
}

class CanjearActivacion {
  final String dispositivoId;
  final String negocioId;
  final String cobradorId;
  final String credencialBootstrap;
  final String expiraEl;
  final bool idempotente;

  const CanjearActivacion({
    required this.dispositivoId,
    required this.negocioId,
    required this.cobradorId,
    required this.credencialBootstrap,
    required this.expiraEl,
    required this.idempotente,
  });

  factory CanjearActivacion.fromJson(Map<String, dynamic> json) {
    return CanjearActivacion(
      dispositivoId: json['dispositivo_id'] as String,
      negocioId: json['negocio_id'] as String,
      cobradorId: json['cobrador_id'] as String,
      credencialBootstrap: json['credencial_bootstrap'] as String,
      expiraEl: json['expira_el'] as String,
      idempotente: json['idempotente'] as bool? ?? false,
    );
  }
}

class DesafioAuth {
  final String challengeId;
  final String nonce;
  final String expiraEl;
  final String environment;

  const DesafioAuth({
    required this.challengeId,
    required this.nonce,
    required this.expiraEl,
    required this.environment,
  });

  factory DesafioAuth.fromJson(Map<String, dynamic> json) {
    return DesafioAuth(
      challengeId: json['challenge_id'] as String,
      nonce: json['nonce'] as String,
      expiraEl: json['expira_el'] as String,
      environment: json['environment'] as String,
    );
  }
}

class CanjearAuth {
  final String token;
  final String negocioId;
  final String usuarioId;
  final String dispositivoId;
  final int versionAsignacion;
  final String expiraEl;

  const CanjearAuth({
    required this.token,
    required this.negocioId,
    required this.usuarioId,
    required this.dispositivoId,
    required this.versionAsignacion,
    required this.expiraEl,
  });

  factory CanjearAuth.fromJson(Map<String, dynamic> json) {
    return CanjearAuth(
      token: json['token'] as String,
      negocioId: json['negocio_id'] as String,
      usuarioId: json['usuario_id'] as String,
      dispositivoId: json['dispositivo_id'] as String,
      versionAsignacion: json['version_asignacion'] as int,
      expiraEl: json['expira_el'] as String,
    );
  }
}

/// Identidad operativa que el dispositivo conserva tras el bootstrap.
/// La ruta unica y su version provienen del servidor; la reasignacion
/// (R1 -> R2) solo se refleja con un nuevo bootstrap, nunca se decide aqui.
class BootstrapIdentity {
  final String negocioId;
  final String negocioNombre;
  final String cobradorId;
  final String cobradorNombre;
  final String dispositivoId;
  final int versionAsignacion;
  final String rutaId;
  final String rutaNombre;
  final int rutaVersion;
  final String rol;

  const BootstrapIdentity({
    required this.negocioId,
    required this.negocioNombre,
    required this.cobradorId,
    required this.cobradorNombre,
    required this.dispositivoId,
    required this.versionAsignacion,
    required this.rutaId,
    required this.rutaNombre,
    required this.rutaVersion,
    required this.rol,
  });

  factory BootstrapIdentity.fromJson(Map<String, dynamic> json) {
    return BootstrapIdentity(
      negocioId: json['negocio_id'] as String,
      negocioNombre: json['negocio_nombre'] as String,
      cobradorId: json['cobrador_id'] as String,
      cobradorNombre: json['cobrador_nombre'] as String,
      dispositivoId: json['dispositivo_id'] as String,
      versionAsignacion: json['version_asignacion'] as int,
      rutaId: json['ruta_id'] as String,
      rutaNombre: json['ruta_nombre'] as String,
      rutaVersion: json['ruta_version'] as int,
      rol: json['rol'] as String,
    );
  }
}
