"""W8 — Dashboard Ejecutivo: read-model de decisión para ADMINISTRADOR."""

from datetime import date, datetime, timedelta
from uuid import uuid4

from src.models import (
    Cliente,
    Credito,
    CuotaProgramada,
    Jornada,
    Negocio,
    Pago,
    Ruta,
    Usuario,
)
from src.services.hoja_viva_service import BOGOTA_TZ, today_bogota


def _auth(nid, role="ADMINISTRADOR", route_id=None, user_id=None):
    params = {"negocio_id": str(nid), "role": role}
    if route_id:
        params["route_id"] = str(route_id)
    if user_id:
        params["user_id"] = str(user_id)
    return params


def _setup(db_session, n_creditos=2, dias_mora_base=10):
    nid = uuid4()
    db_session.add(Negocio(id=nid, nombre="W8 Test", nit="900000008"))
    admin = uuid4()
    db_session.add(Usuario(id=admin, negocio_id=nid, rol="ADMINISTRADOR", nombre="Admin W8"))
    cob = uuid4()
    db_session.add(Usuario(id=cob, negocio_id=nid, rol="COBRADOR", nombre="Cob W8"))
    inv = uuid4()
    db_session.add(Usuario(id=inv, negocio_id=nid, rol="INVERSIONISTA", nombre="Inv W8"))

    r1 = uuid4()
    db_session.add(Ruta(id=r1, negocio_id=nid, nombre="Ruta W8", cobrador_id=cob, activa=1))

    creditos = []
    for i in range(n_creditos):
        cid = uuid4()
        clid = uuid4()
        db_session.add(Cliente(id=clid, negocio_id=nid, nombres=f"Cliente W8 {i}", primer_apellido=f"Apel {i}"))
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


def _pago_hoy(db_session, nid, cid, monto=50000):
    """Pago con timestamp dentro del día financiero actual (Bogotá)."""
    p = Pago(
        id=uuid4(),
        negocio_id=nid,
        credito_id=cid,
        tipo="PAYMENT",
        monto=monto,
        recibido_el_servidor=datetime.now(BOGOTA_TZ),
        clave_idempotencia=f"w8-hoy-{uuid4().hex[:10]}",
    )
    db_session.add(p)
    db_session.commit()
    return p


class TestW8DashboardEjecutivo:
    """GET /api/dashboard/ejecutivo — centro ejecutivo de decisión."""

    def test_admin_shape_completo(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        for key in ("fecha", "negocio", "hoy", "operativo", "riesgo", "tendencia_7d", "rutas", "alertas"):
            assert key in body, f"falta {key}"
        for key in ("cartera_vigente", "cartera_vencida", "pct_vencido", "recaudo_hoy", "gastos_hoy", "neto_hoy"):
            assert key in body["hoy"], f"hoy falta {key}"
        for key in ("rutas_activas", "cobradores_activos", "creditos_activos", "jornada_cerrada_hoy"):
            assert key in body["operativo"], f"operativo falta {key}"
        for key in ("clientes_en_mora", "promesas_activas", "promesas_incumplidas", "aging_distribution"):
            assert key in body["riesgo"], f"riesgo falta {key}"
        for key in ("serie", "total_recaudo", "total_reversal", "total_neto"):
            assert key in body["tendencia_7d"], f"tendencia_7d falta {key}"
        assert isinstance(body["alertas"], list)
        assert body["negocio"]["nombre"] == "W8 Test"
        assert body["negocio"]["moneda"] == "COP"

    def test_admin_consistencia_con_cobranza(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        rc = client.get("/api/cobranza/resumen", params=_auth(s["nid"]))
        assert rc.status_code == 200
        resumen = rc.json()
        assert body["hoy"]["cartera_vigente"] == resumen["total_cartera"]
        assert body["hoy"]["cartera_vencida"] == resumen["total_vencido"]
        assert body["hoy"]["pct_vencido"] == resumen["pct_vencido"]
        assert body["riesgo"]["clientes_en_mora"] == resumen["clientes_en_mora"]
        assert body["riesgo"]["aging_distribution"] == resumen["aging_distribution"]

    def test_admin_neto_hoy(self, client, db_session):
        s = _setup(db_session)
        _pago_hoy(db_session, s["nid"], s["creditos"][0], monto=50000)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        hoy = r.json()["hoy"]
        assert hoy["recaudo_hoy"] == 50000
        assert hoy["neto_hoy"] == hoy["recaudo_hoy"] - hoy["gastos_hoy"]

    def test_admin_tendencia_7d_serie(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        t = r.json()["tendencia_7d"]
        assert len(t["serie"]) == 7
        assert t["total_neto"] == sum(d["neto"] for d in t["serie"])
        assert t["total_recaudo"] == sum(d["recaudo"] for d in t["serie"])
        assert t["total_reversal"] == sum(d["reversal"] for d in t["serie"])

    def test_admin_alertas_estructura(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        for a in r.json()["alertas"]:
            assert "tipo" in a
            assert "mensaje" in a
            assert a["severidad"] in ("info", "warning", "critical")

    def test_admin_alerta_jornada_abierta(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        tipos = [a["tipo"] for a in r.json()["alertas"]]
        assert "JORNADA_ABIERTA" in tipos

    def test_admin_alerta_jornada_cerrada_no_aparece(self, client, db_session):
        s = _setup(db_session)
        db_session.add(Jornada(
            id=uuid4(), negocio_id=s["nid"], ruta_id=s["r1"],
            fecha=today_bogota(), estado="CLOSED_SYNCED",
        ))
        db_session.commit()
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        body = r.json()
        assert body["operativo"]["jornada_cerrada_hoy"] is True
        tipos = [a["tipo"] for a in body["alertas"]]
        assert "JORNADA_ABIERTA" not in tipos

    def test_admin_alerta_mora_90(self, client, db_session):
        s = _setup(db_session, n_creditos=1)
        cid = uuid4()
        clid = uuid4()
        db_session.add(Cliente(id=clid, negocio_id=s["nid"], nombres="Mora 90", primer_apellido="Larga"))
        db_session.add(Credito(
            id=cid, negocio_id=s["nid"], cliente_id=clid, ruta_id=s["r1"],
            cuota=10000, n_cuotas=30, total=300000, monto=10000,
            periodicidad="DIARIO", fecha_inicio=date.today() - timedelta(days=120),
            estado="ACTIVO",
        ))
        for j in range(1, 11):
            db_session.add(CuotaProgramada(
                id=uuid4(), negocio_id=s["nid"], credito_id=cid,
                numero=j, fecha_vencimiento=date.today() - timedelta(days=120 - j),
                monto=10000, estado="PENDIENTE",
            ))
        db_session.commit()
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        tipos = [a["tipo"] for a in r.json()["alertas"]]
        assert "MORA_90+" in tipos

    def test_admin_creditos_activos_count(self, client, db_session):
        s = _setup(db_session, n_creditos=3)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        assert r.json()["operativo"]["creditos_activos"] == 3
        assert r.json()["operativo"]["rutas_activas"] == 1
        assert r.json()["operativo"]["cobradores_activos"] == 1

    def test_admin_rutas_por_ruta(self, client, db_session):
        s = _setup(db_session, n_creditos=2)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        rutas = r.json()["rutas"]
        assert len(rutas) == 1
        assert rutas[0]["ruta_nombre"] == "Ruta W8"
        assert rutas[0]["creditos"] == 2
        assert "cartera" in rutas[0]
        assert "vencido" in rutas[0]

    def test_admin_fecha_business_date(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"]))
        assert r.status_code == 200
        assert r.json()["fecha"] == today_bogota().isoformat()

    def test_inversionista_403(self, client, db_session):
        s = _setup(db_session)
        r = client.get("/api/dashboard/ejecutivo", params=_auth(s["nid"], role="INVERSIONISTA", user_id=s["inv"]))
        assert r.status_code == 403

    def test_cobrador_403(self, client, db_session):
        s = _setup(db_session)
        r = client.get(
            "/api/dashboard/ejecutivo",
            params=_auth(s["nid"], role="COBRADOR", route_id=s["r1"], user_id=s["cob"]),
        )
        assert r.status_code == 403

    def test_negocio_vacio(self, client, db_session):
        nid = uuid4()
        db_session.add(Negocio(id=nid, nombre="Vacío W8", nit="900000009"))
        db_session.commit()
        r = client.get("/api/dashboard/ejecutivo", params=_auth(nid))
        assert r.status_code == 200
        body = r.json()
        assert body["hoy"]["cartera_vigente"] == 0
        assert body["hoy"]["recaudo_hoy"] == 0
        assert body["operativo"]["creditos_activos"] == 0
        assert body["tendencia_7d"]["total_neto"] == 0
