from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from uuid import UUID


# --- Negocio ---

class NegocioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=255)
    nit: Optional[str] = None


class NegocioResponse(BaseModel):
    id: UUID
    nombre: str
    nit: Optional[str]
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
    documento: Optional[str] = None


class UsuarioResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    rol: str
    nombre: str
    documento: Optional[str]
    activo: int
    creado_el: datetime

    model_config = {"from_attributes": True}


# --- Ruta ---

class RutaCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    cobrador_id: Optional[UUID] = None


class RutaResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    nombre: str
    cobrador_id: Optional[UUID]
    activa: int
    version: int
    creado_el: datetime

    model_config = {"from_attributes": True}


# --- Cliente ---

class ClienteCreate(BaseModel):
    primer_apellido: str
    nombres: str
    tipo_documento: Optional[str] = None
    documento_normalizado: Optional[str] = None
    telefono_1: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None


class ClienteResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    primer_apellido: str
    nombres: str
    documento_normalizado: Optional[str]
    identity_status: str
    direccion: Optional[str]
    ciudad: Optional[str]
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
    tasa_efectiva_anual: Optional[float]
    residuo_redondeo: int
    version: int
    creado_el: datetime

    model_config = {"from_attributes": True}


# --- Pago ---

class PagoCreate(BaseModel):
    credito_id: UUID
    jornada_id: Optional[UUID] = None
    monto: int = Field(..., gt=0)
    clave_idempotencia: str = Field(..., min_length=1)
    nota: Optional[str] = None


class PagoReversalCreate(BaseModel):
    motivo: str = Field(..., min_length=1)


class PagoResponse(BaseModel):
    id: UUID
    negocio_id: UUID
    credito_id: Optional[UUID]
    jornada_id: Optional[UUID]
    tipo: str
    monto: int
    registrado_el_dispositivo: Optional[datetime]
    recibido_el_servidor: datetime
    clave_idempotencia: str

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
    diferencia_motivo: Optional[str]
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
