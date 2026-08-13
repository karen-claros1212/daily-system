"""RBAC canonico de Daily System — rol -> capabilities.

Fuente UNICA de verosimilitud UI (no de autoridad): el frontend construye su
navegacion desde estas capabilities, pero el backend conserva la autoridad en
cada endpoint (nunca se esconden botones como sustituto del control backend).

Regla del hito: no existe capability que un endpoint no implemente. Cada
entrada se justifica desde el dominio y tiene prueba negativa de que, sin
ella, el endpoint falla 401/403.

Verificacion en codigo (jun 2026):
  - inversionista.py: resumen/suscripcion  -> INVERSIONISTA | ADMINISTRADOR
  - jornada.py     : GET  filtrado por ruta (COBRADOR) o negocio (resto)
  - ruta.py        : POST creat + PATCH reasignar -> SOLO ADMINISTRADOR;
                     GET scoped a la ruta del COBRADOR
  - activacion.py  : POST /codigos -> SOLO ADMINISTRADOR
  - dispositivo.py : registrar -> SOLO ADMINISTRADOR
"""

from typing import Final

ROLES: Final = ("ADMINISTRADOR", "COBRADOR", "INVERSIONISTA")

# capabilities por rol. Administrador = superposicion de inversionista +
# operacion; se escribe explicito (no hereda) para que el contrato JSON sea
# estable y auditable.
CAPABILITIES_POR_ROL: Final[dict[str, tuple[str, ...]]] = {
    "INVERSIONISTA": (
        "inversionista:resumen",
        "inversionista:suscripcion",
        "jornadas:ver",
        "rutas:ver",
        "creditos:ver",
    ),
    "ADMINISTRADOR": (
        "inversionista:resumen",
        "inversionista:suscripcion",
        "jornadas:ver",
        "rutas:ver",
        "rutas:crear",
        "rutas:reasignar",
        "creditos:ver",
        "codigos:crear",
        "dispositivos:registrar",
    ),
    "COBRADOR": (
        "jornada:ver",
        "jornada:abrir",
        "jornada:cerrar",
        "ruta:ver",
        "movimientos:registrar",
        "pagos:registrar",
        "sync:ver",
    ),
}


def capabilities_de_rol(rol: str | None) -> list[str]:
    """Devuelve las capabilities del rol (tupla -> lista JSON-friendly).

    Rol desconocido -> lista vacia (default-deny): el frontend no recibe
    ninguna superficie para roles que el backend no reconoce.
    """
    if rol not in CAPABILITIES_POR_ROL:
        return []
    return list(CAPABILITIES_POR_ROL[rol])