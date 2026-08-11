"""M6 sync tests — Offline Sync Real (Bloque offline sync, S1/S2).

Cubren GET /api/mobile/sync:
  - El scope se deriva COMPLETO del RequestContext (JWT -> base): la ruta
    activa unica del cobrador. El movil nunca envia route_id como autoridad.
  - Respuesta 200 con los CINCO datasets del primer sync (clientes, creditos,
    cuotas, pagos, movimientos, jornadas) limitados a la ruta activa.
  - Fail-closed: sin JWT -> 401; 0 o >1 rutas activas -> 401; la credencial
    bootstrap del canje ya NO autentica (JWT-only, sin stub query ni en test).
  - Aislamiento por ruta: datos de otra ruta / otro negocio NO se filtran.
  - route_id/negocio_id/rol en la URL se ignoran (autoridad del servidor).
  - El sync exige COBRADOR activo con ruta vigente (admin sin ruta -> 401).
"""

import base64
import hashlib
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.auth.token import issue_token
from src.models import (
    Cliente,
    Credito,
    CuotaProgramada,
    Dispositivo,
    Jornada,
    MovimientoCaja,
    Negocio,
    Pago,
    Ruta,
    Usuario,
)


def _ec_keypair():
    """Genera un par EC P-256; devuelve (privada, spki_b64, sha256_spki_hex)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    spki = base64.b64encode(der).decode("ascii")
    return private_key, spki, hashlib.sha256(der).hexdigest()


@pytest.fixture
def escenario(db_session):
    """Negocio + admin + cobrador + ruta activa (cobrador_id)."""
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="Neg", nit="1"))

    admin_id = uuid4()
    db_session.add(Usuario(id=admin_id, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin"))

    cob_id = uuid4()
    db_session.add(Usuario(id=cob_id, negocio_id=nid, rol="COBRADOR", nombre="Cob"))

    r1_id = uuid4()
    db_session.add(Ruta(id=r1_id, negocio_id=nid, nombre="R1", cobrador_id=cob_id, activa=1))
    db_session.flush()
    return {
        "negocio_id": nid,
        "admin_id": admin_id,
        "cobrador_id": cob_id,
        "ruta_id": r1_id,
    }


@pytest.fixture
def dispositivo_activo(db_session, escenario):
    """Dispositivo ACTIVE vinculado al cobrador, con clave publica registrada."""
    _private_key, spki, pk_hash = _ec_keypair()
    dev_id = uuid4()
    disp = Dispositivo(
        id=dev_id,
        negocio_id=escenario["negocio_id"],
        usuario_id=escenario["cobrador_id"],
        public_key=spki,
        public_key_hash=pk_hash,
        algoritmo_clave="EC_P256",
        estado="ACTIVE",
        version_asignacion=1,
        activo=1,
    )
    db_session.add(disp)
    db_session.flush()
    return {
        "dispositivo_id": dev_id,
        "public_key": spki,
        "public_key_hash": pk_hash,
    }


def _token(escenario, dispositivo_activo, version=1, ttl=3600):
    return issue_token(
        negocio_id=escenario["negocio_id"],
        usuario_id=escenario["cobrador_id"],
        dispositivo_id=dispositivo_activo["dispositivo_id"],
        public_key_hash=dispositivo_activo["public_key_hash"],
        version_asignacion=version,
        ttl_seconds=ttl,
    )


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _add_credito_con_cuotas(db_session, negocio_id, ruta_id, cliente_id, n_cuotas=3, cuota=10000):
    """Crea un credito ACTIVO con su plan contractual y devuelve (credito, cuotas)."""
    credito = Credito(
        id=uuid4(),
        negocio_id=negocio_id,
        cliente_id=cliente_id,
        ruta_id=ruta_id,
        origination_type="NEW",
        cuota=cuota,
        n_cuotas=n_cuotas,
        monto=cuota * n_cuotas,
        total=cuota * n_cuotas,
        periodicidad="DIARIO",
        fecha_inicio=date(2026, 8, 1),
        estado="ACTIVO",
        version=1,
    )
    db_session.add(credito)
    db_session.flush()

    cuotas = []
    for numero in range(1, n_cuotas + 1):
        c = CuotaProgramada(
            id=uuid4(),
            negocio_id=negocio_id,
            credito_id=credito.id,
            numero=numero,
            fecha_vencimiento=date(2026, 8, numero),
            monto=cuota,
            estado="PENDIENTE" if numero < n_cuotas else "PAGADO",
        )
        db_session.add(c)
        cuotas.append(c)
    db_session.flush()
    return credito, cuotas


def _add_jornada_y_pago_movimiento(
    db_session, negocio_id, ruta_id, cobrador_id, credito_id, fecha="2026-08-08"
):
    """Crea jornada OPEN + pago + movimiento de la ruta. Devuelve (jornada, pago, mov)."""
    jornada = Jornada(
        id=uuid4(),
        negocio_id=negocio_id,
        ruta_id=ruta_id,
        cobrador_id=cobrador_id,
        fecha=date.fromisoformat(fecha),
        estado="CLOSED_SYNCED",
        opening_base=100000,
        opening_carry=0,
        esperado=10000,
        contado=10000,
        diferencia=0,
        sobrante_manana=0,
        cierre_version=2,
    )
    db_session.add(jornada)
    db_session.flush()

    pago = Pago(
        id=uuid4(),
        negocio_id=negocio_id,
        credito_id=credito_id,
        jornada_id=jornada.id,
        cobrador_id=cobrador_id,
        tipo="PAYMENT",
        monto=10000,
        registrado_el_dispositivo=datetime.now(timezone.utc),
        clave_idempotencia=str(uuid4()),
    )
    db_session.add(pago)
    db_session.flush()

    mov = MovimientoCaja(
        id=uuid4(),
        negocio_id=negocio_id,
        jornada_id=jornada.id,
        tipo="GASOLINA",
        naturaleza="GASTO",
        monto=5000,
        nota="Combustible",
        clave_idempotencia=str(uuid4()),
        creado_por=cobrador_id,
    )
    db_session.add(mov)
    db_session.flush()
    return jornada, pago, mov


@pytest.fixture
def dataset_ruta(db_session, escenario, dispositivo_activo):
    """Dataset completo en la ruta del cobrador: cliente, credito, cuotas,
    jornada, pago y movimiento."""
    cliente = Cliente(
        id=uuid4(),
        negocio_id=escenario["negocio_id"],
        tipo_documento="CC",
        documento_normalizado="1000000001",
        primer_apellido="Gomez",
        nombres="Ana",
        telefono_1="3000000001",
        direccion="Calle 1",
        barrio="Centro",
        ciudad="Bogota",
        ocupacion="Comerciante",
        identity_status="VERIFIED",
    )
    db_session.add(cliente)
    db_session.flush()

    credito, cuotas = _add_credito_con_cuotas(
        db_session, escenario["negocio_id"], escenario["ruta_id"], cliente.id
    )
    jornada, pago, mov = _add_jornada_y_pago_movimiento(
        db_session,
        escenario["negocio_id"],
        escenario["ruta_id"],
        escenario["cobrador_id"],
        credito.id,
    )
    db_session.flush()
    return {
        "cliente_id": cliente.id,
        "credito_id": credito.id,
        "cuotas_ids": [c.id for c in cuotas],
        "jornada_id": jornada.id,
        "pago_id": pago.id,
        "movimiento_id": mov.id,
    }


@pytest.fixture
def dataset_otra_ruta(db_session, escenario):
    """Cliente + credito + jornada + pago en OTRA ruta del mismo negocio:
    debe quedar fuera del sync del cobrador (aislamiento por ruta)."""
    otra_ruta = Ruta(
        id=uuid4(),
        negocio_id=escenario["negocio_id"],
        nombre="R_Otra",
        activa=0,
    )
    db_session.add(otra_ruta)
    db_session.flush()

    cliente = Cliente(
        id=uuid4(),
        negocio_id=escenario["negocio_id"],
        tipo_documento="CC",
        documento_normalizado="1000000002",
        primer_apellido="Perez",
        nombres="Luis",
        identity_status="PROVISIONAL",
    )
    db_session.add(cliente)
    db_session.flush()

    credito, _cuotas = _add_credito_con_cuotas(
        db_session, escenario["negocio_id"], otra_ruta.id, cliente.id
    )
    jornada, pago, _mov = _add_jornada_y_pago_movimiento(
        db_session,
        escenario["negocio_id"],
        otra_ruta.id,
        escenario["cobrador_id"],
        credito.id,
        fecha="2026-07-01",
    )
    db_session.flush()
    return {
        "ruta_id": otra_ruta.id,
        "cliente_id": cliente.id,
        "credito_id": credito.id,
        "jornada_id": jornada.id,
        "pago_id": pago.id,
    }


# === GET /api/mobile/sync ===


class TestMobileSync:
    def _sync(self, client, token):
        return client.get("/api/mobile/sync", headers=_auth_header(token))

    def test_sync_200_dataset_completo_de_la_ruta(
        self, client, escenario, dispositivo_activo, dataset_ruta
    ):
        """200 con los cinco datasets del primer sync, solo de la ruta activa."""
        token = _token(escenario, dispositivo_activo)
        r = self._sync(client, token)
        assert r.status_code == 200, r.text
        data = r.json()

        assert data["negocio_id"] == str(escenario["negocio_id"])
        assert data["cobrador_id"] == str(escenario["cobrador_id"])
        assert data["ruta_id"] == str(escenario["ruta_id"])
        assert data["ruta_version"] == 1

        assert len(data["clientes"]) == 1
        assert data["clientes"][0]["id"] == str(dataset_ruta["cliente_id"])
        assert data["clientes"][0]["tipo_documento"] == "CC"
        assert data["clientes"][0]["telefono_1"] == "3000000001"
        assert data["clientes"][0]["barrio"] == "Centro"
        assert data["clientes"][0]["ocupacion"] == "Comerciante"
        assert data["clientes"][0]["identity_status"] == "VERIFIED"

        assert len(data["creditos"]) == 1
        assert data["creditos"][0]["id"] == str(dataset_ruta["credito_id"])
        assert data["creditos"][0]["ruta_id"] == str(escenario["ruta_id"])

        assert len(data["cuotas"]) == 3
        cuota_ids = {c["id"] for c in data["cuotas"]}
        assert cuota_ids == {str(c) for c in dataset_ruta["cuotas_ids"]}
        assert {c["numero"] for c in data["cuotas"]} == {1, 2, 3}
        assert {c["estado"] for c in data["cuotas"]} == {"PENDIENTE", "PAGADO"}

        assert len(data["pagos"]) == 1
        assert data["pagos"][0]["id"] == str(dataset_ruta["pago_id"])
        assert data["pagos"][0]["monto"] == 10000
        assert data["pagos"][0]["cobrador_id"] == str(escenario["cobrador_id"])
        assert data["pagos"][0]["clave_idempotencia"]
        assert data["pagos"][0]["nota"] is None
        assert data["pagos"][0]["reversal_of_payment_id"] is None

        assert len(data["movimientos"]) == 1
        assert data["movimientos"][0]["id"] == str(dataset_ruta["movimiento_id"])
        assert data["movimientos"][0]["tipo"] == "GASOLINA"

        assert len(data["jornadas"]) == 1
        assert data["jornadas"][0]["id"] == str(dataset_ruta["jornada_id"])
        assert data["jornadas"][0]["estado"] == "CLOSED_SYNCED"

    def test_sync_sin_jwt_401(self, client, escenario):
        """Sin Bearer JWT -> 401, incluso con query-params de dev/test."""
        r = client.get(
            "/api/mobile/sync",
            params={
                "negocio_id": str(escenario["negocio_id"]),
                "route_id": str(escenario["ruta_id"]),
                "role": "COBRADOR",
            },
        )
        assert r.status_code == 401, r.text

    def test_sync_0_rutas_activas_401(self, client, db_session, escenario, dispositivo_activo):
        """Ruta desactivada -> 401 fail-closed (0 rutas activas)."""
        ruta = db_session.get(Ruta, escenario["ruta_id"])
        ruta.activa = 0
        db_session.flush()

        token = _token(escenario, dispositivo_activo)
        r = self._sync(client, token)
        assert r.status_code == 401, r.text

    def test_sync_mas_de_una_ruta_activa_401(self, client, db_session, escenario, dispositivo_activo):
        """Dos rutas activas -> 401 fail-closed (o constraint parcial en PG)."""
        from sqlalchemy.exc import IntegrityError

        db_session.add(Ruta(
            id=uuid4(),
            negocio_id=escenario["negocio_id"],
            nombre="R2",
            cobrador_id=escenario["cobrador_id"],
            activa=1,
        ))
        try:
            db_session.flush()
        except IntegrityError:
            db_session.rollback()
            return  # PG: constraint parcial uq_ruta_activa_cobrador es la evidencia

        token = _token(escenario, dispositivo_activo)
        r = self._sync(client, token)
        assert r.status_code == 401, r.text

    def test_sync_ignora_route_id_negocio_id_rol_en_url(
        self, client, escenario, dispositivo_activo, dataset_ruta
    ):
        """route_id/negocio_id/rol en la URL no cambian la autoridad derivada."""
        token = _token(escenario, dispositivo_activo)
        r = client.get(
            "/api/mobile/sync",
            headers=_auth_header(token),
            params={
                "route_id": str(uuid4()),
                "negocio_id": str(uuid4()),
                "rol": "ADMINISTRADOR",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["ruta_id"] == str(escenario["ruta_id"])
        assert r.json()["negocio_id"] == str(escenario["negocio_id"])
        assert len(r.json()["clientes"]) == 1

    def test_sync_aislamiento_otra_ruta(
        self, client, escenario, dispositivo_activo, dataset_ruta, dataset_otra_ruta
    ):
        """Datos de otra ruta (mismo negocio) NO se filtran en el sync."""
        token = _token(escenario, dispositivo_activo)
        r = self._sync(client, token)
        assert r.status_code == 200, r.text
        data = r.json()

        cliente_ids = {c["id"] for c in data["clientes"]}
        assert str(dataset_otra_ruta["cliente_id"]) not in cliente_ids
        assert str(dataset_ruta["cliente_id"]) in cliente_ids

        credito_ids = {c["id"] for c in data["creditos"]}
        assert str(dataset_otra_ruta["credito_id"]) not in credito_ids

        pago_ids = {p["id"] for p in data["pagos"]}
        assert str(dataset_otra_ruta["pago_id"]) not in pago_ids

        jornada_ids = {j["id"] for j in data["jornadas"]}
        assert str(dataset_otra_ruta["jornada_id"]) not in jornada_ids

    def test_sync_admin_token_sin_ruta_401(self, client, db_session, escenario):
        """Un token de ADMINISTRADOR (sin ruta activa) -> 401: solo cobradores."""
        _k, spki, pk_hash = _ec_keypair()
        dev_id = uuid4()
        db_session.add(Dispositivo(
            id=dev_id,
            negocio_id=escenario["negocio_id"],
            usuario_id=escenario["admin_id"],
            public_key=spki,
            public_key_hash=pk_hash,
            algoritmo_clave="EC_P256",
            estado="ACTIVE",
            version_asignacion=1,
            activo=1,
        ))
        db_session.flush()

        token = issue_token(
            negocio_id=escenario["negocio_id"],
            usuario_id=escenario["admin_id"],
            dispositivo_id=dev_id,
            public_key_hash=pk_hash,
            version_asignacion=1,
        )
        r = self._sync(client, token)
        assert r.status_code == 401, r.text

    def test_sync_pagos_expone_reversal_of_payment_id(
        self, client, db_session, escenario, dispositivo_activo
    ):
        """Un REVERSAL del servidor debe circular con su enlace al pago original
        (reversal_of_payment_id) para que el movil preserve la relacion y no
       permita revertir dos veces el mismo pago."""
        from datetime import datetime, timezone
        from uuid import uuid4 as _uuid4

        cliente = Cliente(
            id=_uuid4(),
            negocio_id=escenario["negocio_id"],
            tipo_documento="CC",
            documento_normalizado="1000000010",
            primer_apellido="Rojas",
            nombres="Pedro",
            telefono_1="3000000010",
            direccion="Calle 10",
            barrio="Centro",
            ciudad="Bogota",
            ocupacion="Comerciante",
            identity_status="VERIFIED",
        )
        db_session.add(cliente)
        db_session.flush()

        credito = Credito(
            id=_uuid4(),
            negocio_id=escenario["negocio_id"],
            cliente_id=cliente.id,
            ruta_id=escenario["ruta_id"],
            origination_type="NEW",
            cuota=10000,
            n_cuotas=1,
            monto=10000,
            total=10000,
            periodicidad="DIARIO",
            fecha_inicio=date(2026, 8, 1),
            estado="ACTIVO",
            version=1,
        )
        db_session.add(credito)
        db_session.flush()

        jornada = Jornada(
            id=_uuid4(),
            negocio_id=escenario["negocio_id"],
            ruta_id=escenario["ruta_id"],
            cobrador_id=escenario["cobrador_id"],
            fecha=date(2026, 8, 8),
            estado="CLOSED_SYNCED",
            opening_base=100000,
            opening_carry=0,
            esperado=10000,
            contado=10000,
            diferencia=0,
            sobrante_manana=0,
            cierre_version=2,
        )
        db_session.add(jornada)
        db_session.flush()

        now = datetime.now(timezone.utc)
        pago = Pago(
            id=_uuid4(),
            negocio_id=escenario["negocio_id"],
            credito_id=credito.id,
            jornada_id=jornada.id,
            cobrador_id=escenario["cobrador_id"],
            tipo="PAYMENT",
            monto=10000,
            registrado_el_dispositivo=now,
            clave_idempotencia=str(_uuid4()),
        )
        reversal = Pago(
            id=_uuid4(),
            negocio_id=escenario["negocio_id"],
            credito_id=credito.id,
            jornada_id=jornada.id,
            cobrador_id=escenario["cobrador_id"],
            tipo="REVERSAL",
            monto=10000,
            registrado_el_dispositivo=now,
            clave_idempotencia=str(_uuid4()),
            reversal_of_payment_id=pago.id,
            nota="Reversal de prueba",
        )
        db_session.add_all([pago, reversal])
        db_session.flush()

        token = _token(escenario, dispositivo_activo)
        r = self._sync(client, token)
        assert r.status_code == 200, r.text
        pagos = {p["id"]: p for p in r.json()["pagos"]}

        assert str(pago.id) in pagos
        assert str(reversal.id) in pagos
        assert pagos[str(reversal.id)]["reversal_of_payment_id"] == str(pago.id)
        assert pagos[str(reversal.id)]["tipo"] == "REVERSAL"
        assert pagos[str(reversal.id)]["nota"] == "Reversal de prueba"
        assert pagos[str(pago.id)]["reversal_of_payment_id"] is None
