"""Seed reproducible para la integración Web ↔ FastAPI real (gate E2E).

Crea en API_DATABASE_URL un negocio apto para el flujo web real:
  - negocio al_dia (el resumen de inversionista exige suscripción vigente)
  - cobrador COBRADOR con EXACTAMENTE UNA ruta activa (exigencia del canje)
  - inversionista INVERSIONISTA y administrador ADMINISTRADOR del mismo negocio
  - un código de activación PENDING válido (el admin lo emitiría)
  - dispositivos ACTIVE por rol y JWTs reales (issue_token) firmados con la
    clave del servidor (AUTH_JWT_PRIVATE_KEY), para que el spec real-rbac
    pruebe la autoridad por rol contra FastAPI real sin mock.

Uso (idempotente): seed_web_integration.py [output_json]
  Requiere AUTH_JWT_PRIVATE_KEY (y AUTH_JWT_PUBLIC_KEY) para emitir los JWTs
  reales; fail-closed si faltan. Si ya existe negocio/usuarios en la DB los
  reutiliza; el output (por defecto a stdout) da {negocio_id, cobrador_id,
  codigo_activacion, ruta_id, inversionista_id, administrador_id, tokens}
  para que los tests lean qué código usar y con qué JWT de rol autenticar.

Útil para CI: source /tmp/be.env antes de correr (contiene las claves ES256).
"""

import base64
import hashlib
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.database import Base, engine, SessionLocal
from src.models import CodigoActivacion, Dispositivo, Negocio, Ruta, Usuario

_IDS = None
_CODIGO_TTL = 60  # minutos


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _find_values(db):
    negocio = (
        db.query(Negocio)
        .filter(Negocio.nombre == "Web E2E Real")
        .first()
    )
    if not negocio:
        return None
    cobrador = (
        db.query(Usuario)
        .filter(Usuario.negocio_id == negocio.id, Usuario.rol == "COBRADOR")
        .first()
    )
    if not cobrador:
        return None
    ruta = (
        db.query(Ruta)
        .filter(Ruta.cobrador_id == cobrador.id, Ruta.activa == 1)
        .first()
    )
    if not ruta:
        return None
    codigo = (
        db.query(CodigoActivacion)
        .filter(CodigoActivacion.negocio_id == negocio.id, CodigoActivacion.estado == "PENDING")
        .first()
    )
    return negocio, cobrador, ruta, codigo


def _ec_par() -> tuple[str, str]:
    """Genera una clave EC P-256 y devuelve (SPKI b64, sha256 del DER).

    El dispositivo ACTIVE del seed debe tener `public_key` (SPKI base64) y
    `public_key_hash` (hex sha256 del DER) consistentes con los claims del
    JWT que emita `issue_token` (misma regla que auth_service).
    """
    priv = ec.generate_private_key(ec.SECP256R1())
    der = priv.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    spki = base64.b64encode(der).decode("ascii")
    return spki, hashlib.sha256(der).hexdigest()


def _crear_dispositivo_activo(db, negocio_id: uuid4.__class__, usuario_id: uuid4.__class__) -> Dispositivo:
    """Crea un dispositivo ACTIVE para el usuario (índice único por usuario)."""
    spki, pk_hash = _ec_par()
    disp = Dispositivo(
        id=uuid4(),
        negocio_id=negocio_id,
        usuario_id=usuario_id,
        public_key=spki,
        public_key_hash=pk_hash,
        algoritmo_clave="EC_P256",
        modelo="web-e2e",
        plataforma="web",
        estado="ACTIVE",
        version_asignacion=1,
        activo=1,
    )
    db.add(disp)
    db.flush()
    return disp


def main() -> None:
    db = SessionLocal()
    try:
        existing = _find_values(db)
        if existing:
            negocio, cobrador, ruta, codigo = existing
            if codigo is not None:
                db.delete(codigo)
            for disp in db.query(Dispositivo).filter(
                Dispositivo.negocio_id == negocio.id, Dispositivo.estado == "ACTIVE"
            ):
                disp.estado = "REVOKED"
            db.commit()
        else:
            negocio = Negocio(
                id=uuid4(),
                nombre="Web E2E Real",
                nit="901234567",
                pais="CO",
                moneda="COP",
                zona_horaria="America/Bogota",
                plan="basic",
                estado_suscripcion="al_dia",
                paid_through_at=_now() + timedelta(days=365),
            )
            db.add(negocio)
            db.flush()

            cobrador = Usuario(
                id=uuid4(),
                negocio_id=negocio.id,
                rol="COBRADOR",
                nombre="Cobrador Web E2E",
                documento="1000000001",
                activo=1,
            )
            db.add(cobrador)
            db.flush()

            ruta = Ruta(
                id=uuid4(),
                negocio_id=negocio.id,
                nombre="Ruta Unica Web E2E",
                cobrador_id=cobrador.id,
                activa=1,
                version=1,
            )
            db.add(ruta)
            db.flush()

        # Usuarios de otros roles (idempotente por rol+negocio).
        inversionista = (
            db.query(Usuario)
            .filter(Usuario.negocio_id == negocio.id, Usuario.rol == "INVERSIONISTA")
            .first()
        )
        if not inversionista:
            inversionista = Usuario(
                id=uuid4(),
                negocio_id=negocio.id,
                rol="INVERSIONISTA",
                nombre="Inversionista Web E2E",
                documento="1000000002",
                activo=1,
            )
            db.add(inversionista)
            db.flush()

        administrador = (
            db.query(Usuario)
            .filter(Usuario.negocio_id == negocio.id, Usuario.rol == "ADMINISTRADOR")
            .first()
        )
        if not administrador:
            administrador = Usuario(
                id=uuid4(),
                negocio_id=negocio.id,
                rol="ADMINISTRADOR",
                nombre="Administrador Web E2E",
                documento="1000000003",
                activo=1,
            )
            db.add(administrador)
            db.flush()

        # Dispositivos ACTIVE para INVERSIONISTA y ADMINISTRADOR. El COBRADOR
        # NO se crea aquí: el flujo de canje real (real-integration /
        # real-contract) crea el dispositivo del cobrador vía el par de la
        # activación, y el índice único ACTIVE por usuario lo bloquea. Los
        # JWTs de los roles sin flujo de dispositivo (inv/admin) los emite el
        # servidor con issue_token (misma clave y reglas de validación).
        disp_inv = _crear_dispositivo_activo(db, negocio.id, inversionista.id)
        disp_adm = _crear_dispositivo_activo(db, negocio.id, administrador.id)
        db.commit()

        token = secrets.token_urlsafe(32)
        codigo = CodigoActivacion(
            negocio_id=negocio.id,
            cobrador_id=cobrador.id,
            hash_codigo=_sha256(token),
            prefijo=token[:8],
            expira_el=_now() + timedelta(minutes=_CODIGO_TTL),
            estado="PENDING",
            creado_por=None,
            entregado_el=_now(),
        )
        db.add(codigo)
        db.commit()
        result_codigo = token

        from src.auth.token import issue_token

        tokens = {}
        for etiqueta, disp, usuario in (
            ("inversionista", disp_inv, inversionista),
            ("administrador", disp_adm, administrador),
        ):
            tokens[etiqueta] = issue_token(
                negocio_id=negocio.id,
                usuario_id=usuario.id,
                dispositivo_id=disp.id,
                public_key_hash=disp.public_key_hash,
                version_asignacion=disp.version_asignacion or 1,
            )

        out = {
            "negocio_id": str(negocio.id),
            "cobrador_id": str(cobrador.id),
            "ruta_id": str(ruta.id),
            "inversionista_id": str(inversionista.id),
            "administrador_id": str(administrador.id),
            "codigo_activacion": result_codigo,
            "tokens": tokens,
        }
    finally:
        db.close()

    print(json.dumps(out, indent=2))
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()