"""W9 — Inversionista Final: read-model financiero read-only + PII minimizada.

Certifica que el resumen del inversionista compone las autoridades canónicas
W6/W7 (una sola fórmula de cartera/recaudo) y que la PII del cobrador/cliente
no llega al inversionista en ninguna superficie.
"""

from datetime import date, datetime, timedelta
from uuid import uuid4

from src.models import (
    Cliente,
    Credito,
    CuotaProgramada,
    Negocio,
    Pago,
    Ruta,
    Usuario,
)
from src.services.hoja_viva_service import BOGOTA_TZ, today_bogota


def _auth(nid, role="INVERSIONISTA", route_id=None, user_id=None):
    params = {"negocio_id": str(nid), "role": role}
    if route_id:
        params["route_id"] = str(route_id)
    if user_id:
        params["user_id"] = str(user_id)
    return params


def _setup(db_session, n_creditos=2, nombre="W9 Test"):
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre=nombre, nit=f"90{uuid4().int % 10000000:07d}"))
    admin = uuid4()
    db_session.add(Usuario(id=admin, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin W9"))
    cob = uuid4()
    db_session.add(Usuario(id=cob, negocio_id=nid, rol="COBRADOR", nombre="Cobrador W9"))
    inv = uuid4()
    db_session.add(Usuario(id=inv, negocio_id=nid, rol="INVERSIONISTA", nombre="Inv W9"))

    r1 = uuid4()
    db_session.add(Ruta(id=r1, negocio_id=nid, nombre="Ruta W9", cobrador_id=cob, activa=1))

    creditos = []
    for i in range(n_creditos):
        cid = uuid4()
        clid = uuid4()
        db_session.add(Cliente(id=clid, negocio_id=nid, nombres=f"Cliente W9 {i}", primer_apellido=f"Apel {i}"))
        creditos.append(cid)
        db_session.add(Credito(
            id=cid, negocio_id=nid, cliente_id=clid, ruta_id=r1,
            cuota=10000, n_cuotas=30, total=300000, monto=10000,
            periodicidad="DIARIO", fecha_inicio=date.today() - timedelta(days=30 + i * 5),
            estado="ACTIVO",
        ))
        for j in range(1, 11):
            db_session.add(CuotaProgramada(
                id=uuid4(), negocio_id=nid, credito_id=cid,
                numero=j, fecha_vencimiento=date.today() - timedelta(days=30 + i * 5 - j),
                monto=10000, estado="PENDIENTE",
            ))

    db_session.commit()
    return {"nid": nid, "admin": admin, "cob": cob, "inv": inv, "r1": r1, "creditos": creditos}


def _pago(db_session, nid, cid, monto=50000, tipo="PAYMENT"):
    p = Pago(
        id=uuid4(),
        negocio_id=nid,
        credito_id=cid,
        tipo=tipo,
        monto=monto,
        recibido_el_servidor=datetime.now(BOGOTA_TZ),
        clave_idempotencia=f"w9-{tipo.lower()}-{uuid4().hex[:10]}",
    )
    db_session.add(p)
    db_session.commit()
    return p


class TestW9ResumenInversionista:
    """GET /api/inversionista/resumen — read-model financiero W9."""

    def test_inversionista_200_shape(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        body = r.json()
        # Secciones W9.
        for key in ("portfolio", "negocio", "riesgo", "tendencia_7d", "rutas"):
            assert key in body, f"falta sección {key}"
        # Portfolio: legacy + W9.
        for key in ("total_creditos_activos", "cartera_neta", "recaudo_hoy",
                    "cartera_viva", "cartera_vencida", "pct_vencido", "gastos_hoy", "neto_hoy"):
            assert key in body["portfolio"], f"portfolio falta {key}"
        # Riesgo.
        for key in ("clientes_en_mora", "promesas_activas", "promesas_incumplidas", "aging_distribution"):
            assert key in body["riesgo"], f"riesgo falta {key}"
        # Tendencia.
        for key in ("serie", "total_recaudo", "total_reversal", "total_neto"):
            assert key in body["tendencia_7d"], f"tendencia_7d falta {key}"
        # Negocio.
        assert body["negocio"]["nombre"] == "W9 Test"
        assert body["negocio"]["moneda"] == "COP"
        assert body["negocio"]["fecha"] == today_bogota().isoformat()

    def test_admin_200(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="ADMINISTRADOR", user_id=s["admin"]))
        assert r.status_code == 200

    def test_cobrador_403(self, client, db_session):
        s = _setup(db_session)
        r = client.get(
            "/api/inversionista/resumen",
            params=_auth(s["nid"], role="COBRADOR", route_id=s["r1"], user_id=s["cob"]),
        )
        assert r.status_code == 403

    def test_cartera_coincide_autoridad_w6(self, client, db_session):
        """Una sola fórmula de cartera: resumen INV == resumen_cobranza (W6)."""
        s = _setup(db_session)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        inv = r.json()
        rc = client.get("/api/cobranza/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert rc.status_code == 200
        cobranza = rc.json()
        assert inv["portfolio"]["cartera_viva"] == cobranza["total_cartera"]
        assert inv["portfolio"]["cartera_vencida"] == cobranza["total_vencido"]
        assert inv["portfolio"]["pct_vencido"] == cobranza["pct_vencido"]
        # Campo legacy apunta a la misma autoridad.
        assert inv["portfolio"]["cartera_neta"] == inv["portfolio"]["cartera_viva"]

    def test_riesgo_coincide_autoridad_w6(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        inv = r.json()
        rc = client.get("/api/cobranza/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        cobranza = rc.json()
        assert inv["riesgo"]["clientes_en_mora"] == cobranza["clientes_en_mora"]
        assert inv["riesgo"]["aging_distribution"] == cobranza["aging_distribution"]
        assert inv["riesgo"]["promesas_activas"] == cobranza["promesas_activas"]
        assert inv["riesgo"]["promesas_incumplidas"] == cobranza["promesas_incumplidas"]

    def test_recaudo_hoy_coincide_autoridad_w7(self, client, db_session):
        """Recaudo del día sale de la autoridad W7 (no de una fórmula propia)."""
        s = _setup(db_session)
        _pago(db_session, s["nid"], s["creditos"][0], monto=75000)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        assert r.json()["portfolio"]["recaudo_hoy"] == 75000

    def test_neto_hoy_recaudo_menos_gastos(self, client, db_session):
        s = _setup(db_session)
        _pago(db_session, s["nid"], s["creditos"][0], monto=75000)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        p = r.json()["portfolio"]
        assert p["neto_hoy"] == p["recaudo_hoy"] - p["gastos_hoy"]

    def test_reversal_reflejado_en_recaudo(self, client, db_session):
        """REVERSAL reduce el recaudo neto del día (autoridad W7)."""
        s = _setup(db_session)
        _pago(db_session, s["nid"], s["creditos"][0], monto=100000, tipo="PAYMENT")
        _pago(db_session, s["nid"], s["creditos"][0], monto=20000, tipo="REVERSAL")
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        assert r.json()["portfolio"]["recaudo_hoy"] == 80000

    def test_tendencia_7d_serie(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        t = r.json()["tendencia_7d"]
        assert len(t["serie"]) == 7
        assert t["total_neto"] == sum(d["neto"] for d in t["serie"])
        assert t["total_recaudo"] == sum(d["recaudo"] for d in t["serie"])
        assert t["total_reversal"] == sum(d["reversal"] for d in t["serie"])

    def test_exposicion_rutas_agregada(self, client, db_session):
        s = _setup(db_session, n_creditos=3)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        rutas = r.json()["rutas"]
        assert len(rutas) == 1
        assert rutas[0]["ruta_nombre"] == "Ruta W9"
        assert rutas[0]["creditos"] == 3
        assert "cartera" in rutas[0] and "vencido" in rutas[0]
        # PII: sin ruta_id ni cobrador en la exposición.
        assert "cobrador_nombre" not in rutas[0]
        assert "cobrador_id" not in rutas[0]

    def test_fecha_business_date_bogota(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        assert r.json()["negocio"]["fecha"] == today_bogota().isoformat()

    def test_negocio_vacio(self, client, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="Vacío W9", nit="900000099"))
        db_session.commit()
        r = client.get("/api/inversionista/resumen", params=_auth(nid, role="INVERSIONISTA"))
        assert r.status_code == 200
        body = r.json()
        assert body["portfolio"]["cartera_viva"] == 0
        assert body["portfolio"]["recaudo_hoy"] == 0
        assert body["portfolio"]["total_creditos_activos"] == 0
        assert body["tendencia_7d"]["total_neto"] == 0
        assert body["rutas"] == []

    def test_tenant_isolation(self, client, db_session):
        """El negocio A no ve cartera del negocio B."""
        a = _setup(db_session, n_creditos=2, nombre="Negocio A")
        b = _setup(db_session, n_creditos=5, nombre="Negocio B")
        ra = client.get("/api/inversionista/resumen", params=_auth(a["nid"], role="INVERSIONISTA", user_id=a["inv"]))
        rb = client.get("/api/inversionista/resumen", params=_auth(b["nid"], role="INVERSIONISTA", user_id=b["inv"]))
        assert ra.status_code == 200 and rb.status_code == 200
        assert ra.json()["portfolio"]["total_creditos_activos"] == 2
        assert rb.json()["portfolio"]["total_creditos_activos"] == 5
        assert ra.json()["portfolio"]["cartera_viva"] != rb.json()["portfolio"]["cartera_viva"]

    def test_pii_ausente_en_resumen(self, client, db_session):
        """El resumen no filtra nombres de cliente ni de cobrador."""
        s = _setup(db_session)
        r = client.get("/api/inversionista/resumen", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        raw = r.text
        assert "Cliente W9" not in raw
        assert "Cobrador W9" not in raw
        assert "Apel" not in raw


class TestW9Suscripcion:
    """GET /api/inversionista/suscripcion — read-only."""

    def test_inversionista_200_readonly(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/inversionista/suscripcion", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        body = r.json()
        assert body["estado_suscripcion"] == "al_dia"
        assert body["activa"] is True
        assert body["plan"] == "basic"

    def test_cobrador_403(self, client, db_session):
        s = _setup(db_session)
        r = client.get(
            "/api/inversionista/suscripcion",
            params=_auth(s["nid"], role="COBRADOR", route_id=s["r1"], user_id=s["cob"]),
        )
        assert r.status_code == 403


class TestW9PII:
    """PII minimizada del inversionista en las superficies ya hechas."""

    def test_rutas_inversionista_sin_cobrador(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/rutas", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["nombre"] == "Ruta W9"
        assert items[0]["cobrador_id"] is None
        assert items[0]["cobrador_nombre"] is None

    def test_rutas_detalle_inversionista_sin_cobrador(self, client, db_session):
        s = _setup(db_session)
        r = client.get(f"/api/rutas/{s['r1']}", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        body = r.json()
        assert body["nombre"] == "Ruta W9"
        assert body["cobrador_id"] is None
        assert body["cobrador_nombre"] is None

    def test_rutas_admin_con_cobrador(self, client, db_session):
        """ADMIN/COBRADOR conservan la identidad del cobrador."""
        s = _setup(db_session)
        r = client.get("/api/rutas", params=_auth(s["nid"], role="ADMINISTRADOR", user_id=s["admin"]))
        assert r.status_code == 200
        item = r.json()["items"][0]
        assert item["cobrador_id"] is not None
        assert item["cobrador_nombre"] == "Cobrador W9"

    def test_creditos_inversionista_sin_cobrador(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/creditos", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["cobrador_nombre"] is None
            assert item["cliente_nombre"] is None
            assert item["cliente_id"] is None

    def test_cobranza_worklist_inversionista_sin_cobrador(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/web", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["cobrador_nombre"] is None
            assert item["cliente_nombre"] is None

    def test_cobranza_admin_con_cobrador(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/cobranza/web", params=_auth(s["nid"], role="ADMINISTRADOR", user_id=s["admin"]))
        assert r.status_code == 200
        assert r.json()["items"], "debe haber filas"
        assert r.json()["items"][0]["cobrador_nombre"] == "Cobrador W9"
