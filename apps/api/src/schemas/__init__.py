from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# --- Negocio ---

class NegocioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=255)
    nit: str | None = None


class NegocioResponse(BaseModel):
    id: UUID
    nombre: str
    nit: str | None
    pais: str
    moneda: str
    plan: str
    estado_suscripcion: str
    creado_el: datetime

    model_config = {"from_attributes": True}


# --- Usuario ---

class UsuarioCreate(BaseModel):
    nombre: str = Field(..., min_length=1)
    rol: str = Field(..., pattern="^(INVERSIONISTA|ADMINISTRADOR|COBRADOR)$")
    documento: str | None = None


class UsuarioResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    rol: str
    nombre: str
    documento: str | None
    activo: int
    creado_el: datetime

    model_config = {"from_attributes": True}


# --- Ruta ---

class RutaCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    cobrador_id: UUID | None = None


class RutaReasignarRequest(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)


class RutaResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    nombre: str
    cobrador_id: UUID | None
    activa: int
    version: int
    creado_el: datetime

    model_config = {"from_attributes": True}


class RutaReasignarResponse(BaseModel):
    ruta_anterior_id: UUID
    ruta_anterior_nombre: str
    ruta_nueva_id: UUID
    ruta_nueva_nombre: str
    cobrador_id: UUID
    cobrador_nombre: str
    version_asignacion: int

    model_config = {"from_attributes": True}


# --- Cliente ---

class ClienteCreate(BaseModel):
    primer_apellido: str
    nombres: str
    tipo_documento: str | None = None
    documento_normalizado: str | None = None
    telefono_1: str | None = None
    direccion: str | None = None
    ciudad: str | None = None


class ClienteResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    primer_apellido: str
    nombres: str
    documento_normalizado: str | None
    identity_status: str
    direccion: str | None
    ciudad: str | None
    creado_el: datetime

    model_config = {"from_attributes": True}


class ClienteSyncResponse(BaseModel):
    """Cliente para el sync del movil: expone las columnas que la tabla local
    `cliente` del dispositivo puede conservar (ver lib/database/tables.dart).
    """

    id: UUID
    negocio_id: UUID
    primer_apellido: str
    nombres: str
    tipo_documento: str | None
    documento_normalizado: str | None
    telefono_1: str | None
    direccion: str | None
    barrio: str | None
    ciudad: str | None
    ocupacion: str | None
    identity_status: str
    creado_el: datetime

    model_config = {"from_attributes": True}


# --- Credito ---

class CreditoCreate(BaseModel):
    cliente_id: UUID
    ruta_id: UUID
    cuota: int = Field(..., gt=0)
    n_cuotas: int = Field(..., gt=0)
    monto: int = Field(..., gt=0)
    fecha_inicio: date
    periodicidad: str = Field(default="DIARIO", pattern="^(DIARIO|SEMANAL|QUINCENAL|UNICA)$")


class CreditoResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    cliente_id: UUID
    ruta_id: UUID
    cuota: int
    n_cuotas: int
    monto: int
    total: int
    periodicidad: str
    fecha_inicio: date
    estado: str
    tasa_efectiva_anual: float | None
    residuo_redondeo: int
    version: int
    creado_el: datetime

    model_config = {"from_attributes": True}


class CuotaProgramadaResponse(BaseModel):
    """Cuota del plan contractual de un credito, para el sync del movil."""

    id: UUID
    credito_id: UUID
    numero: int
    fecha_vencimiento: date
    monto: int
    estado: str

    model_config = {"from_attributes": True}


# --- Pago ---

class PagoCreate(BaseModel):
    credito_id: UUID
    jornada_id: UUID | None = None
    monto: int = Field(..., gt=0)
    clave_idempotencia: str = Field(..., min_length=1)
    nota: str | None = None


class PagoReversalCreate(BaseModel):
    motivo: str = Field(..., min_length=1)
    clave_idempotencia: str | None = Field(None, max_length=200)


class PagoResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    credito_id: UUID | None
    jornada_id: UUID | None
    tipo: str
    monto: int
    registrado_el_dispositivo: datetime | None
    recibido_el_servidor: datetime
    clave_idempotencia: str

    model_config = {"from_attributes": True}


class PagoSyncResponse(BaseModel):
    """Vista de pago para el sync móvil.

    Expone, además de los campos base de PagoResponse, los que el modelo local
    pago necesita para preservar la fidelidad financiera: cobrador_id, nota y
    reversal_of_payment_id. Critical para que un REVERSAL del servidor no pierda
    su enlace al pago original y el movil no permita revertir dos veces.
    """

    id: UUID
    negocio_id: UUID
    credito_id: UUID | None
    jornada_id: UUID | None
    cobrador_id: UUID | None
    tipo: str
    monto: int
    clave_idempotencia: str
    nota: str | None
    registrado_el_dispositivo: datetime | None
    recibido_el_servidor: datetime
    reversal_of_payment_id: UUID | None

    model_config = {"from_attributes": True}


# --- Jornada ---

class JornadaResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    ruta_id: UUID
    fecha: date
    estado: str
    opening_base: int
    opening_carry: int
    esperado: int
    contado: int
    diferencia: int
    diferencia_motivo: str | None
    sobrante_manana: int
    creado_el: datetime

    model_config = {"from_attributes": True}


# --- Hoja Viva ---

class HojaVivaCliente(BaseModel):
    """Fila completa de la hoja viva del cobrador."""
    credito_id: UUID
    cliente_nombre: str
    cuota: int
    saldo: int
    mora_legacy: int
    pico: int
    cuotas_pagadas: int
    estado_credito: str
    semaforo: str  # GRIS, VERDE, AMARILLO, ROJO


class HojaVivaResponse(BaseModel):
    """Respuesta de la hoja viva de una ruta."""
    ruta_id: UUID
    ruta_nombre: str
    fecha: date
    clientes: list[HojaVivaCliente]
    vence_hoy: int
    vence_hoy_monto: int = 0
    cuotas_que_vencen_hoy: int = 0
    dc_legacy: int  # PROMEDIO/DC legado
    efectivo_esperado: int


# === Jornada ===

class JornadaCreate(BaseModel):
    ruta_id: UUID
    opening_base: int = Field(default=0, ge=0)
    clave_idempotencia: str = Field(..., min_length=1, max_length=100)

    @field_validator("clave_idempotencia", mode="before")
    @classmethod
    def strip_clave_idempotencia(cls, v):
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("clave_idempotencia no puede estar vacío ni ser solo espacios")
        return v


class JornadaCierreCreate(BaseModel):
    efectivo_contado: int = Field(default=0, ge=0)
    idempotencia_cierre: str = Field(..., min_length=1, max_length=100)
    motivo: str = Field(default="", max_length=500)

    @field_validator("idempotencia_cierre", mode="before")
    @classmethod
    def strip_idempotencia_cierre(cls, v):
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("idempotencia_cierre no puede estar vacío ni ser solo espacios")
        return v


class JornadaCierreResponse(BaseModel):
    jornada_id: UUID
    estado: str
    fecha: date
    opening_base: int
    opening_carry: int
    recaudo_real: int
    desembolsos: int
    vales: int
    gastos: int
    ahorro: int
    efectivo_esperado: int
    efectivo_contado: int
    diferencia: int
    diferencia_motivo: str | None
    sobrante_manana: int
    cierre_idempotency_key: str | None
    cierre_version: int
    cerrada_local_el: datetime | None
    snapshot_hash: str | None

    model_config = {"from_attributes": True}


class JornadaSyncResponse(BaseModel):
    jornada_id: UUID
    estado: str
    sincronizada_el: datetime | None
    snapshot_valido: bool


class JornadaResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    ruta_id: UUID
    fecha: date
    estado: str
    opening_base: int
    opening_carry: int
    esperado: int
    contado: int
    diferencia: int
    diferencia_motivo: str | None
    sobrante_manana: int
    cierre_idempotency_key: str | None
    cierre_version: int
    cerrada_por: UUID | None
    cerrada_local_el: datetime | None
    recibida_servidor_el: datetime | None
    sincronizada_el: datetime | None
    creado_el: datetime

    model_config = {"from_attributes": True}


# === Movimiento Caja ===

class MovimientoCreate(BaseModel):
    jornada_id: UUID
    tipo: str = Field(..., pattern="^(GASOLINA|OFICINA|AHORRO|VALE|ENTREGA|RECIBIDO|DESEMBOLSO|AJUSTE|OTRO)$")
    naturaleza: str | None = Field(default=None, pattern="^(GASTO|CUSTODIA|CUENTA_POR_COBRAR|TRASLADO_ENTRADA|TRASLADO_SALIDA|DESEMBOLSO|AJUSTE)$")
    monto: int = Field(..., gt=0)
    nota: str | None = None
    clave_idempotencia: str = Field(..., min_length=1, max_length=100)
    credito_id: UUID | None = None
    renovacion_id: UUID | None = None
    ajuste_de_movimiento_id: UUID | None = None
    motivo: str | None = None

    @field_validator("clave_idempotencia", mode="before")
    @classmethod
    def strip_movimiento_clave(cls, v):
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("clave_idempotencia no puede estar vacío ni ser solo espacios")
        return v


class MovimientoResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    jornada_id: UUID
    tipo: str
    naturaleza: str
    monto: int
    nota: str | None
    clave_idempotencia: str | None
    registrado_el_dispositivo: datetime | None
    recibido_el_servidor: datetime | None
    dispositivo_id: UUID | None
    credito_id: UUID | None
    renovacion_id: UUID | None
    creado_por: UUID | None
    creado_el: datetime

    model_config = {"from_attributes": True}


# === Caja ===

class CadenaCajaResponse(BaseModel):
    opening_base: int
    opening_carry: int
    recaudo_real: int
    desembolsos: int
    vales: int
    gastos: int
    ahorro: int
    entregas: int
    otros_entrada: int
    efectivo_esperado: int
    movimientos_count: int
    pagos_count: int
    renovaciones_count: int


# === Dispositivo ===

class DispositivoCreate(BaseModel):
    huella: str = Field(..., min_length=1, max_length=64)
    modelo: str | None = None
    plataforma: str | None = None


class DispositivoResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    usuario_id: UUID | None
    huella: str | None
    public_key_hash: str | None
    algoritmo_clave: str | None
    estado: str
    modelo: str | None
    plataforma: str | None
    autorizado_por: UUID | None
    autorizado_el: datetime | None
    revocado_el: datetime | None
    ultima_validacion_servidor: datetime | None
    activo: int
    creado_el: datetime

    model_config = {"from_attributes": True}


# === Activacion (contrato de activacion, revision 4) ===


class CodigoActivacionCreate(BaseModel):
    cobrador_id: UUID | None = None
    usuario_id: UUID | None = None
    expira_minutos: int = Field(default=10, ge=1, le=1440)

    @model_validator(mode="after")
    def _resolver_objetivo(self) -> "CodigoActivacionCreate":
        """Etapa 2: el código puede ligarse a cualquier rol con sesión.

        `usuario_id` es el campo canónico; `cobrador_id` se mantiene como alias
        legado para compatibilidad con consumidores que aún no migraron. Se
        rechaza pasar ambos (ambigüedad de objetivo).
        """
        if self.usuario_id and self.cobrador_id and self.usuario_id != self.cobrador_id:
            raise ValueError("No se pueden combinar usuario_id y cobrador_id distintos")
        if not (self.usuario_id or self.cobrador_id):
            raise ValueError("usuario_id (o su alias cobrador_id) es requerido")
        if self.cobrador_id and not self.usuario_id:
            self.usuario_id = self.cobrador_id
        return self


class CodigoActivacionResponse(BaseModel):
    codigo_id: UUID
    token: str
    prefijo: str
    expira_el: datetime


class DesafioRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    clave_publica: str = Field(..., min_length=1, max_length=4096)
    modelo: str | None = None
    plataforma: str | None = None

    model_config = {"extra": "forbid"}


class DesafioResponse(BaseModel):
    intento_id: UUID
    nonce: str
    expira_el: str
    environment: str


class CanjearRequest(BaseModel):
    intento_id: UUID
    firma: str = Field(..., min_length=1, max_length=1024)

    model_config = {"extra": "forbid"}


class CanjearResponse(BaseModel):
    dispositivo_id: UUID
    negocio_id: UUID
    # Campos canónicos (Etapa 2): el usuario objetivo puede ser cualquier rol.
    usuario_id: UUID
    rol: str | None = None
    # Legado: alias de usuario_id (se conserva para compatibilidad de consumidores
    # que aún no migraron). Se rellena desde usuario_id en validación.
    cobrador_id: UUID | None = None
    credencial_bootstrap: str
    expira_el: str
    idempotente: bool = False

    @model_validator(mode="after")
    def _compat_cobrador_id(self) -> "CanjearResponse":
        """compat: si el servicio no envió usuario_id, use cobrador_id (legacy)."""
        if self.usuario_id is None and self.cobrador_id is not None:
            object.__setattr__(self, "usuario_id", self.cobrador_id)
        # cobrador_id sigue como alias legado apuntando al mismo usuario objetivo.
        if self.cobrador_id is None and self.usuario_id is not None:
            object.__setattr__(self, "cobrador_id", self.usuario_id)
        return self


class DesafioAuthResponse(BaseModel):
    challenge_id: UUID
    nonce: str
    expira_el: str
    environment: str


class CanjearDesafioRequest(BaseModel):
    challenge_id: UUID
    firma: str = Field(..., min_length=1, max_length=1024)

    model_config = {"extra": "forbid"}


class CanjearDesafioResponse(BaseModel):
    token: str
    negocio_id: UUID
    usuario_id: UUID
    dispositivo_id: UUID
    version_asignacion: int
    expira_el: str


class BootstrapResponse(BaseModel):
    negocio_id: UUID
    negocio_nombre: str
    cobrador_id: UUID
    cobrador_nombre: str
    dispositivo_id: UUID
    version_asignacion: int
    ruta_id: UUID
    ruta_nombre: str
    ruta_version: int
    rol: str


# === Identity canonica — GET /api/auth/me ===

class NegocioInfo(BaseModel):
    negocio_id: UUID
    nombre: str
    plan: str
    moneda: str
    zona_horaria: str
    estado_suscripcion: str
    suscripcion_activa: bool


class MeResponse(BaseModel):
    user_id: UUID
    usuario_nombre: str
    rol: str
    activo: bool
    negocio: NegocioInfo
    route_id: UUID | None = None
    route_nombre: str | None = None
    device_id: UUID | None = None
    version_asignacion: int | None = None
    capabilities: list[str] = Field(default_factory=list)


# === Suscripcion ===

class SuscripcionStatusResponse(BaseModel):
    negocio_id: UUID
    estado_suscripcion: str
    plan: str
    paid_through_at: datetime | None
    activa: bool


# === Inversionista — Aggregates ===

class InversionistaPortfolioResponse(BaseModel):
    total_creditos_activos: int
    cartera_neta: int
    recaudo_hoy: int
    jornada_cerrada_hoy: bool
    cobradores_activos: int
    rutas_activas: int


class InversionistaSummaryResponse(BaseModel):
    portfolio: InversionistaPortfolioResponse
    negocio_nombre: str
    plan: str
    moneda: str
    zona_horaria: str


# === Sync del movil (Bloque offline sync, S2) ===
#
# GET /api/mobile/sync devuelve TODO el dataset de la ruta activa unica del
# cobrador en una sola respuesta (JWT-only, scope derivado por el servidor).
# El movil escribe cada lista en su propia transaccion local (nada de
# transaccion gigante) y nunca elige ruta ni envia route_id como autoridad.


class SyncResponse(BaseModel):
    """Dataset completo de la ruta activa del cobrador, para el primer sync.

    El scope sale del RequestContext (JWT -> base), nunca de query/body:
    clientes, creditos/cuotas, pagos, movimientos y jornadas quedan limitados
    a la ruta activa unica del cobrador autenticado. ruta_version permite al
    movil detectar una reasignacion (R1->R2) como resultado de un bootstrap
    posterior; aqui es solo eco del servidor.
    """

    negocio_id: UUID
    cobrador_id: UUID
    ruta_id: UUID
    ruta_version: int
    clientes: list[ClienteSyncResponse]
    creditos: list[CreditoResponse]
    cuotas: list[CuotaProgramadaResponse]
    pagos: list[PagoSyncResponse]
    movimientos: list[MovimientoResponse]
    jornadas: list[JornadaResponse]
