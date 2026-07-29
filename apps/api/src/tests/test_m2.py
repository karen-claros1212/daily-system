"""M2 tests: jornada open/close, caja cadena, movimientos append-only, idempotency."""

from datetime import date, timedelta, timezone
from uuid import uuid4

import pytest

from src.auth.context import RequestContext
from src.models import (
    Cliente,
    Jornada,
    Negocio,
    Ruta,
)
from src.services.caja_service import calcular_caja_fixture
from src.services.jornada_service import (
    JornadaAlreadyClosed,
    cerrar_jornada,
    open_jornada,
    preparar_siguiente_jornada,
    sincronizar_cierre,
)
from src.services.movimiento_service import (
    MovimientoNaturalezaInvalida,
    MovimientoTipoInvalido,
    register_movimiento,
    validate_naturaleza,
    validate_tipo,
)

BOGOTA_TZ = timezone(timedelta(hours=-5))


# ================================================================
# CAJA — CADENA DE CAJA (R4)
# ================================================================

class TestCadenaCaja:
    """Caja calculation via physical flows. Caso R4 obligatorio."""

    def test_caso_r4_275_805_400_20_18_50(self):
        """Caso R4: 275 + 805 - 400 - 20 - 18 - 50 = 592."""
        result = calcular_caja_fixture(
            opening_base=275,
            opening_carry=805,
            recaudo_real=0,
            desembolsos=400,
            vales=20,
            gastos=18,
            ahorro=50,
        )
        assert result["efectivo_esperado"] == 592
        assert result["opening_base"] == 275
        assert result["opening_carry"] == 805

    def test_caja_sin_movimientos(self):
        """Caja con solo base y carry."""
        result = calcular_caja_fixture(
            opening_base=1000,
            opening_carry=500,
            recaudo_real=0,
            desembolsos=0,
            vales=0,
            gastos=0,
            ahorro=0,
        )
        assert result["efectivo_esperado"] == 1500

    def test_caja_con_recaudo(self):
        """Caja con recaudo real en efectivo."""
        result = calcular_caja_fixture(
            opening_base=500,
            opening_carry=0,
            recaudo_real=120000,
            desembolsos=30000,
            vales=0,
            gastos=5000,
            ahorro=10000,
        )
        expected = 500 + 0 + 120000 - 30000 - 0 - 5000 - 10000
        assert result["efectivo_esperado"] == expected


# ================================================================
# JORNADA — ABRIR
# ================================================================

class TestJornadaOpen:
    """Open jornada with carry chain."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        self.cid = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.add(Cliente(
            id=self.cid, negocio_id=self.nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.commit()

    def test_open_jornada_creates_open(self, db_session):
        """open_jornada creates a jornada in OPEN state."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        jornada = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            opening_base=50000,
            ctx=ctx,
        )
        assert jornada.estado == "OPEN"
        assert jornada.opening_base == 50000
        assert jornada.opening_carry == 0  # first day

    def test_open_jornada_calculates_carry(self, db_session):
        """opening_carry(D) = sobrante_manana(D-1)."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )

        # Day 1: close with sobrante_manana = 25000
        j1 = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 14),
            opening_base=10000,
            ctx=ctx,
        )
        j1.estado = "CLOSED_SYNCED"
        j1.sobrante_manana = 25000
        db_session.flush()

        # Day 2: opening_carry should be 25000
        j2 = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            opening_base=10000,
            ctx=ctx,
        )
        assert j2.opening_carry == 25000

    def test_open_jornada_duplicate_returns_existing(self, db_session):
        """Opening same date twice returns existing OPEN jornada."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        j1 = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            ctx=ctx,
        )
        j2 = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            ctx=ctx,
        )
        assert j1.id == j2.id


# ================================================================
# JORNADA — CERRAR
# ================================================================

class TestJornadaClose:
    """Close jornada with idempotency, snapshot, carry."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        self.cid = uuid4()
        self.jid = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.add(Cliente(
            id=self.cid, negocio_id=self.nid,
            primer_apellido="X", nombres="Y", identity_status="PROVISIONAL",
        ))
        db_session.commit()

        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        self.jornada = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            opening_base=100000,
            ctx=ctx,
        )

    def test_cerrar_jornada_transitions_state(self, db_session):
        """Cerrar transitions OPEN → CLOSING → CLOSED_LOCAL_PENDING_SYNC."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        # Create yesterday's jornada (2026-07-15) with sobrante_manana
        prev = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            opening_base=100000,
            ctx=ctx,
        )
        prev.estado = "CLOSED_SYNCED"
        prev.sobrante_manana = 50000
        db_session.flush()

        # Now open today's jornada (2026-07-16) — it gets carry=50000 from prev
        today_j = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 16),
            opening_base=100000,
            ctx=ctx,
        )

        result = cerrar_jornada(
            db=db_session,
            jornada_id=today_j.id,
            data={"efectivo_contado": 150000, "idempotencia_cierre": "close-001"},
            ctx=ctx,
        )
        assert result["estado"] == "CLOSED_LOCAL_PENDING_SYNC"
        assert result["efectivo_esperado"] == 150000  # 100k + 50k + 0 - 0
        assert result["efectivo_contado"] == 150000
        assert result["diferencia"] == 0

    def test_cerrar_jornada_requires_motivo_on_diferencia(self, db_session):
        """Cerrar with diferencia != 0 requires motivo."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        # self.jornada has opening_base=100000, opening_carry=0
        # efectivo_esperado = 100000
        result = cerrar_jornada(
            db=db_session,
            jornada_id=self.jornada.id,
            data={"efectivo_contado": 160000, "idempotencia_cierre": "close-002", "motivo": "Sobró dinero"},
            ctx=ctx,
        )
        assert result["diferencia"] == 60000  # 160000 - 100000
        assert result["diferencia_motivo"] == "Sobró dinero"

        # Try close again without motivo
        from src.services.jornada_service import JornadaError
        try:
            cerrar_jornada(
                db=db_session,
                jornada_id=self.jornada.id,
                data={"efectivo_contado": 160000, "idempotencia_cierre": "close-002b"},
                ctx=ctx,
            )
            assert False, "Expected JornadaError"
        except JornadaError:
            pass  # Expected

    def test_cerrar_jornada_idempotent(self, db_session):
        """Same idempotency key returns same result."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        j = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 21),
            opening_base=100000,
            ctx=ctx,
        )
        r1 = cerrar_jornada(
            db=db_session,
            jornada_id=j.id,
            data={"efectivo_contado": 100000, "idempotencia_cierre": "idem-001"},
            ctx=ctx,
        )
        r2 = cerrar_jornada(
            db=db_session,
            jornada_id=j.id,
            data={"efectivo_contado": 100000, "idempotencia_cierre": "idem-001"},
            ctx=ctx,
        )
        assert r1["jornada_id"] == r2["jornada_id"]
        assert r1["cierre_idempotency_key"] == r2["cierre_idempotency_key"]

    def test_cerrar_jornada_saves_snapshot(self, db_session):
        """Cerrar saves immutable snapshot with hash."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        cerrar_jornada(
            db=db_session,
            jornada_id=self.jornada.id,
            data={"efectivo_contado": 100000, "idempotencia_cierre": "snap-001"},
            ctx=ctx,
        )

        j = db_session.query(Jornada).filter(Jornada.id == self.jornada.id).first()
        assert j.cierre_snapshot_json is not None
        assert j.cierre_snapshot_hash is not None
        assert j.cierre_version == 1
        assert j.sobrante_manana == 100000  # carry to tomorrow

    def test_cerrar_jornada_cannot_close_twice(self, db_session):
        """Closing already closed jornada raises error."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        cerrar_jornada(
            db=db_session,
            jornada_id=self.jornada.id,
            data={"efectivo_contado": 100000, "idempotencia_cierre": "close-003"},
            ctx=ctx,
        )

        try:
            cerrar_jornada(
                db=db_session,
                jornada_id=self.jornada.id,
                data={"efectivo_contado": 100000, "idempotencia_cierre": "close-004"},
                ctx=ctx,
            )
            assert False, "Expected JornadaAlreadyClosed"
        except JornadaAlreadyClosed:
            pass  # Expected


# ================================================================
# JORNADA — SINCRONIZAR
# ================================================================

class TestJornadaSync:
    """Synchronize locally-closed jornada from device."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        self.jid = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        self.jornada = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            opening_base=100000,
            ctx=ctx,
        )
        cerrar_jornada(
            db=db_session,
            jornada_id=self.jornada.id,
            data={"efectivo_contado": 100000, "idempotencia_cierre": "sync-001"},
            ctx=ctx,
        )

    def test_sincronizar_transitions_to_closed_synced(self, db_session):
        """Sincronizar transitions CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED."""
        import hashlib
        snapshot = {"efectivo_esperado": 150000, "efectivo_contado": 150000}
        hash_val = hashlib.sha256(str(snapshot).encode()).hexdigest()

        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        result = sincronizar_cierre(
            db=db_session,
            jornada_id=self.jornada.id,
            snapshot=snapshot,
            snapshot_hash=hash_val,
            ctx=ctx,
        )
        assert result["estado"] == "CLOSED_SYNCED"
        assert result["snapshot_valido"] is True


# ================================================================
# JORNADA — PREPARAR SIGUIENTE
# ================================================================

class TestSiguienteJornada:
    """Prepare next day's opening_carry."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

    def test_preparar_siguiente_sets_carry(self, db_session):
        """Preparar next day returns sobrante_manana as opening_carry."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        j = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            opening_base=100000,
            ctx=ctx,
        )
        j.estado = "CLOSED_SYNCED"
        j.sobrante_manana = 35000
        db_session.flush()

        result = preparar_siguiente_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 16),
        )
        assert result["ready"] is True
        assert result["opening_carry"] == 35000

    def test_preparar_siguiente_no_prev(self, db_session):
        """No prev closed jornada returns not ready."""
        result = preparar_siguiente_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 16),
        )
        assert result["ready"] is False


# ================================================================
# MOVIMIENTO — APPEND-ONLY
# ================================================================

class TestMovimientoRegister:
    """Append-only movements with catalog validation."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()

        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        self.jornada = open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=date(2026, 7, 15),
            ctx=ctx,
        )
        self.jid = self.jornada.id

    def test_register_movimiento_gasolina(self, db_session):
        """Register a GASOLINA movement."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": self.jid,
                "tipo": "GASOLINA",
                "naturaleza": "GASTO",
                "monto": 5000,
                "clave_idempotencia": "mov-gas-001",
            },
            ctx=ctx,
        )
        assert m.tipo == "GASOLINA"
        assert m.naturaleza == "GASTO"
        assert m.monto == 5000

    def test_register_movimiento_vale(self, db_session):
        """Register a VALE movement (CUENTA_POR_COBRAR)."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": self.jid,
                "tipo": "VALE",
                "naturaleza": "CUENTA_POR_COBRAR",
                "monto": 20000,
                "clave_idempotencia": "mov-vale-001",
            },
            ctx=ctx,
        )
        assert m.tipo == "VALE"
        assert m.naturaleza == "CUENTA_POR_COBRAR"

    def test_register_movimiento_idempotente(self, db_session):
        """Same idempotency key returns existing movement."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        m1 = register_movimiento(
            db=db_session,
            data={
                "jornada_id": self.jid,
                "tipo": "GASOLINA",
                "naturaleza": "GASTO",
                "monto": 5000,
                "clave_idempotencia": "idem-mov-001",
            },
            ctx=ctx,
        )
        m2 = register_movimiento(
            db=db_session,
            data={
                "jornada_id": self.jid,
                "tipo": "GASOLINA",
                "naturaleza": "GASTO",
                "monto": 5000,
                "clave_idempotencia": "idem-mov-001",
            },
            ctx=ctx,
        )
        assert m1.id == m2.id

    def test_register_movimiento_mismo_key_monto_diferente_409(self, db_session):
        """Same key + different monto = conflict."""
        from src.services.movimiento_service import MovimientoIdempotencyError
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        register_movimiento(
            db=db_session,
            data={
                "jornada_id": self.jid,
                "tipo": "GASOLINA",
                "naturaleza": "GASTO",
                "monto": 5000,
                "clave_idempotencia": "conflict-001",
            },
            ctx=ctx,
        )
        try:
            register_movimiento(
                db=db_session,
                data={
                    "jornada_id": self.jid,
                    "tipo": "GASOLINA",
                    "naturaleza": "GASTO",
                    "monto": 6000,
                    "clave_idempotencia": "conflict-001",
                },
                ctx=ctx,
            )
            assert False, "Expected MovimientoIdempotencyError"
        except MovimientoIdempotencyError:
            pass


# ================================================================
# MOVIMIENTO — CATÁLOGO CERRADO
# ================================================================

class TestMovimientoCatalog:
    """Closed catalog of tipos and naturalezas."""

    def test_tipo_valido_gasolina(self):
        """GASOLINA is valid."""
        validate_tipo("GASOLINA")  # no exception

    def test_tipo_valido_desemolso(self):
        """DESEMBOLSO is valid."""
        validate_tipo("DESEMBOLSO")

    def test_tipo_invalido(self):
        """Invalid tipo raises error."""
        try:
            validate_tipo("INVENTARIO")
            assert False, "Expected MovimientoTipoInvalido"
        except MovimientoTipoInvalido:
            pass

    def test_naturaleza_valida_gasto(self):
        """GASTO is valid."""
        validate_naturaleza("GASTO")

    def test_naturaleza_valida_custodia(self):
        """CUSTODIA is valid."""
        validate_naturaleza("CUSTODIA")

    def test_naturaleza_invalida(self):
        """Invalid naturaleza raises error."""
        try:
            validate_naturaleza("VENTA")
            assert False, "Expected MovimientoNaturalezaInvalida"
        except MovimientoNaturalezaInvalida:
            pass


# ================================================================
# JORNADA — NO OPERAR SOBRE CERRADA
# ================================================================

class TestJornadaLocked:
    """Cannot add movements to closed jornada."""

    def test_cannot_add_movimiento_to_closed_jornada(self, db_session):
        """Adding movement to closed jornada raises error."""
        nid = uuid4()
        rid = uuid4()

        db_session.add(Negocio(id=nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=rid, negocio_id=nid, nombre="R1"))
        db_session.commit()

        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=nid,
            role="COBRADOR",
            route_id=rid,
        )
        jornada = open_jornada(
            db=db_session,
            ruta_id=rid,
            negocio_id=nid,
            fecha=date(2026, 7, 15),
            opening_base=100000,
            ctx=ctx,
        )
        jid = jornada.id

        # Verify jornada state before closing
        j = db_session.query(Jornada).filter(Jornada.id == jid).first()
        assert j is not None
        assert j.estado == "OPEN"
        assert j.opening_base == 100000

        cerrar_jornada(
            db=db_session,
            jornada_id=jid,
            data={"efectivo_contado": 100000, "idempotencia_cierre": "lock-001"},
            ctx=ctx,
        )

        from src.services.movimiento_service import MovimientoJornadaError
        try:
            register_movimiento(
                db=db_session,
                data={
                    "jornada_id": jid,
                    "tipo": "GASOLINA",
                    "naturaleza": "GASTO",
                    "monto": 5000,
                },
                ctx=ctx,
            )
            assert False, "Expected MovimientoJornadaError"
        except MovimientoJornadaError:
            pass  # Expected
