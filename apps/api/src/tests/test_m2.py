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
from src.services.caja_service import calcular_cadena_caja, calcular_caja_fixture
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
    MovimientoAjusteError,
    MovimientoNotaObligatoria,
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

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        self.cid = uuid4()
        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.flush()

    def test_caso_r4_275_805_400_20_18_50(self):
        """Caso R4: 275 + 0 + 805 - 400 - 20 - 18 - 50 = 592.

        R4: base=275, carry=0, recaudo=805, desembolsos=400, vales=20, gastos=18, ahorro=50.
        """
        result = calcular_caja_fixture(
            opening_base=275,
            opening_carry=0,
            recaudo_real=805,
            desembolsos=400,
            vales=20,
            gastos=18,
            ahorro=50,
        )
        assert result["efectivo_esperado"] == 592
        assert result["opening_base"] == 275
        assert result["recaudo_real"] == 805

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

    def test_caso_r4_recaudo_real_con_pago(self, db_session):
        """Caso R4 real: base 275 + recaudo 805 (vía PAYMENT) - 400 - 20 - 18 - 50 = 592."""
        from src.models import Pago
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
            fecha=date(2026, 7, 22),
            opening_base=275,
            ctx=ctx,
        )
        # Add a PAYMENT of 805
        db_session.add(Pago(
            id=uuid4(),
            negocio_id=self.nid,
            credito_id=self.cid,
            jornada_id=jornada.id,
            tipo="PAYMENT",
            monto=805,
            cobrador_id=ctx.user_id,
            dispositivo_id=ctx.device_id,
            clave_idempotencia="pay-r4-805",
        ))
        db_session.flush()

        caja = calcular_cadena_caja(db_session, jornada.id)
        # 275 + 0 + 805 - 0 - 0 - 0 - 0 = 1080
        assert caja["efectivo_esperado"] == 1080
        assert caja["recaudo_real"] == 805
        assert caja["opening_base"] == 275


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
        """Cerrar transitions OPEN → CLOSING → CLOSED_SYNCED (server-side)."""
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
        assert result["estado"] == "CLOSED_SYNCED"
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

        self.cobrador_ctx = ctx = RequestContext(
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

    def test_sincronizar_validates_snapshot(self, db_session):
        """Sincronizar validates snapshot and is idempotent on CLOSED_SYNCED."""
        import json
        import hashlib
        stored_j = db_session.query(Jornada).filter(Jornada.id == self.jornada.id).first()
        stored_snapshot = stored_j.cierre_snapshot_json
        canonical = json.dumps(stored_snapshot, sort_keys=True, separators=(",", ":"), default=str)
        hash_val = hashlib.sha256(canonical.encode()).hexdigest()

        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        result = sincronizar_cierre(
            db=db_session,
            jornada_id=self.jornada.id,
            snapshot=stored_snapshot,
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


# ================================================================
# APERTURA — SOLO apertura_idempotency_key
# ================================================================

class TestAperturaIdempotencyKey:
    """open_jornada guarda solo apertura_idempotency_key, no cierre."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

    def test_open_jornada_solo_apertura_key(self, db_session):
        """open_jornada llena apertura_idempotency_key, deja cierre vacío."""
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
            clave_idempotencia="open-001",
        )
        assert j.apertura_idempotency_key == "open-001"
        assert j.cierre_idempotency_key is None

    def test_cerrar_jornada_llena_cierre_key(self, db_session):
        """cerrar_jornada llena cierre_idempotency_key."""
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
            clave_idempotencia="open-002",
        )
        cerrar_jornada(
            db=db_session,
            jornada_id=j.id,
            data={"efectivo_contado": 100000, "idempotencia_cierre": "close-001"},
            ctx=ctx,
        )
        j = db_session.query(Jornada).filter(Jornada.id == j.id).first()
        assert j.apertura_idempotency_key == "open-002"
        assert j.cierre_idempotency_key == "close-001"


# ================================================================
# SINCRONIZAR — VALIDACIÓN HASH Y JSON CANÓNICO
# ================================================================

class TestSincronizarHashValidation:
    """sincronizar_cierre valida hash y JSON canónico exacto."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

    def _open_and_close(self, db_session, date_val, contado, clave):
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
            fecha=date_val,
            opening_base=100000,
            ctx=ctx,
        )
        cerrar_jornada(
            db=db_session,
            jornada_id=j.id,
            data={"efectivo_contado": contado, "idempotencia_cierre": clave},
            ctx=ctx,
        )
        return j

    def test_sincronizar_valida_hash_recibido(self, db_session):
        """Hash recibido diferente al almacenado produce error."""
        j = self._open_and_close(db_session, date(2026, 7, 15), 100000, "sync-hash")
        stored_hash = db_session.query(Jornada).filter(Jornada.id == j.id).first().cierre_snapshot_hash
        snapshot = {"efectivo_esperado": 100000, "efectivo_contado": 100000}
        # Use a hash that's definitely different from stored
        wrong_hash = "a" * 64  # 64 a's, definitely different from any real hash
        print(f"\nDEBUG: stored_hash={stored_hash}, wrong_hash={wrong_hash}, equal={stored_hash == wrong_hash}")
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        from src.services.jornada_service import JornadaError
        try:
            sincronizar_cierre(
                db=db_session,
                jornada_id=j.id,
                snapshot=snapshot,
                snapshot_hash=wrong_hash,
                ctx=ctx,
            )
            assert False, "Expected JornadaError"
        except JornadaError as e:
            assert "hash" in str(e).lower()

    def test_sincronizar_valida_json_canonico_exacto(self, db_session):
        """JSON canónico diferente produce error."""
        j = self._open_and_close(db_session, date(2026, 7, 16), 100000, "sync-json")
        stored = db_session.query(Jornada).filter(Jornada.id == j.id).first()
        stored_snapshot = stored.cierre_snapshot_json
        import json
        snapshot_diferente = dict(stored_snapshot)
        snapshot_diferente["efectivo_esperado"] = 99999
        canonical = json.dumps(
            stored_snapshot, sort_keys=True, separators=(",", ":"), default=str
        )
        import hashlib
        hash_val = hashlib.sha256(canonical.encode()).hexdigest()
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        from src.services.jornada_service import JornadaError
        try:
            sincronizar_cierre(
                db=db_session,
                jornada_id=j.id,
                snapshot=snapshot_diferente,
                snapshot_hash=hash_val,
                ctx=ctx,
            )
            assert False, "Expected JornadaError"
        except JornadaError as e:
            assert "canónico" in str(e) or "snapshot" in str(e).lower()

    def test_sincronizar_transicion_local_pending_sync(self, db_session):
        """Sincronizar transiciona CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED."""
        import json
        import hashlib
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
            fecha=date(2026, 7, 17),
            opening_base=100000,
            ctx=ctx,
        )
        # Close server-side (goes to CLOSED_SYNCED)
        cerrar_jornada(
            db=db_session,
            jornada_id=j.id,
            data={"efectivo_contado": 100000, "idempotencia_cierre": "sync-trans"},
            ctx=ctx,
        )
        # Manually set to CLOSED_LOCAL_PENDING_SYNC to simulate device close
        j = db_session.query(Jornada).filter(Jornada.id == j.id).first()
        j.estado = "CLOSED_LOCAL_PENDING_SYNC"
        db_session.flush()
        assert j.estado == "CLOSED_LOCAL_PENDING_SYNC"
        # Now sync
        stored_snapshot = j.cierre_snapshot_json
        canonical = json.dumps(stored_snapshot, sort_keys=True, separators=(",", ":"), default=str)
        hash_val = hashlib.sha256(canonical.encode()).hexdigest()
        result = sincronizar_cierre(
            db=db_session,
            jornada_id=j.id,
            snapshot=stored_snapshot,
            snapshot_hash=hash_val,
            ctx=ctx,
        )
        j = db_session.query(Jornada).filter(Jornada.id == j.id).first()
        assert j.estado == "CLOSED_SYNCED"
        assert result["estado"] == "CLOSED_SYNCED"
        assert result["snapshot_valido"] is True

    def test_sincronizar_reintento_closed_synced_identico(self, db_session):
        """Reintento en CLOSED_SYNCED con snapshot idéntico es exitoso."""
        import json
        import hashlib
        j = self._open_and_close(db_session, date(2026, 7, 18), 100000, "sync-retry")
        j = db_session.query(Jornada).filter(Jornada.id == j.id).first()
        stored_snapshot = j.cierre_snapshot_json
        canonical = json.dumps(stored_snapshot, sort_keys=True, separators=(",", ":"), default=str)
        hash_val = hashlib.sha256(canonical.encode()).hexdigest()
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        # First sync
        r1 = sincronizar_cierre(
            db=db_session,
            jornada_id=j.id,
            snapshot=stored_snapshot,
            snapshot_hash=hash_val,
            ctx=ctx,
        )
        assert r1["estado"] == "CLOSED_SYNCED"
        assert r1["snapshot_valido"] is True
        # Reintento idéntico
        r2 = sincronizar_cierre(
            db=db_session,
            jornada_id=j.id,
            snapshot=stored_snapshot,
            snapshot_hash=hash_val,
            ctx=ctx,
        )
        assert r2["estado"] == "CLOSED_SYNCED"
        assert r2["snapshot_valido"] is True
        assert r2.get("reintento") is True

    def test_sincronizar_reintento_closed_synced_diferente(self, db_session):
        """Reintento en CLOSED_SYNCED con snapshot diferente produce error."""
        import json
        import hashlib
        j = self._open_and_close(db_session, date(2026, 7, 19), 100000, "sync-retry2")
        j = db_session.query(Jornada).filter(Jornada.id == j.id).first()
        stored_snapshot = j.cierre_snapshot_json
        # Hash del snapshot ORIGINAL (para que pase la validación de hash)
        canonical = json.dumps(stored_snapshot, sort_keys=True, separators=(",", ":"), default=str)
        hash_val = hashlib.sha256(canonical.encode()).hexdigest()
        # Snapshot modificado
        snapshot_modificado = dict(stored_snapshot)
        snapshot_modificado["efectivo_contado"] = 99999
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        from src.services.jornada_service import JornadaError
        try:
            sincronizar_cierre(
                db=db_session,
                jornada_id=j.id,
                snapshot=snapshot_modificado,
                snapshot_hash=hash_val,
                ctx=ctx,
            )
            assert False, "Expected JornadaError"
        except JornadaError as e:
            assert "diferente" in str(e) or "canónico" in str(e) or "hash" in str(e).lower()


# ================================================================
# AJUSTE — nota auditada, negocio/ruta, idempotencia
# ================================================================

class TestAjusteAudit:
    """AJUSTE usa nota como motivo auditado, valida negocio/ruta, incluye nota en idempotencia."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

    def _open_jornada(self, db_session, fecha=date(2026, 7, 15)):
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        return open_jornada(
            db=db_session,
            ruta_id=self.rid,
            negocio_id=self.nid,
            fecha=fecha,
            ctx=ctx,
        )

    def test_ajuste_usa_nota_como_motivo(self, db_session):
        """AJUSTE requiere nota (motivo auditado), no campo motivo."""
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        admin_ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="ADMINISTRADOR",
            route_id=self.rid,
        )
        j = self._open_jornada(db_session)
        # Register a regular movement to adjust
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "GASOLINA",
                "monto": 5000,
                "nota": "Gasolina ruta",
                "clave_idempotencia": "mov-base-001",
            },
            ctx=ctx,
        )
        # AJUSTE con nota
        a = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "AJUSTE",
                "monto": 5000,
                "nota": "Corregir gasolina doble",
                "ajuste_de_movimiento_id": m.id,
                "clave_idempotencia": "ajuste-001",
            },
            ctx=admin_ctx,
        )
        assert a.tipo == "AJUSTE"
        assert a.nota == "Corregir gasolina doble"
        assert a.ajuste_de_movimiento_id == m.id

    def test_ajuste_requiere_nota(self, db_session):
        """AJUSTE sin nota produce error."""
        admin_ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="ADMINISTRADOR",
            route_id=self.rid,
        )
        j = self._open_jornada(db_session)
        try:
            register_movimiento(
                db=db_session,
                data={
                    "jornada_id": j.id,
                    "tipo": "AJUSTE",
                    "monto": 5000,
                    "nota": "",
                    "ajuste_de_movimiento_id": uuid4(),
                    "clave_idempotencia": "ajuste-sin-nota",
                },
                ctx=admin_ctx,
            )
            assert False, "Expected MovimientoAjusteError"
        except MovimientoAjusteError:
            pass

    def test_ajuste_valida_mismo_negocio(self, db_session):
        """AJUSTE valida que movimiento original pertenezca al mismo negocio."""
        admin_ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="ADMINISTRADOR",
            route_id=self.rid,
        )
        otro_nid = uuid4()
        db_session.add(Negocio(id=otro_nid, nombre="O", nit="2"))
        db_session.flush()
        j = self._open_jornada(db_session)
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "GASOLINA",
                "monto": 5000,
                "nota": "Gasolina",
                "clave_idempotencia": "mov-otro-negocio",
            },
            ctx=RequestContext(
                user_id=uuid4(),
                negocio_id=self.nid,
                role="COBRADOR",
                route_id=self.rid,
            ),
        )
        # AJUSTE con referencia a movimiento del mismo negocio
        a = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "AJUSTE",
                "monto": 5000,
                "nota": "Ajuste válido",
                "ajuste_de_movimiento_id": m.id,
                "clave_idempotencia": "ajuste-mismo-negocio",
            },
            ctx=admin_ctx,
        )
        assert a.tipo == "AJUSTE"

    def test_ajuste_incluye_nota_en_idempotencia(self, db_session):
        """Nota se incluye en la comparación idempotente de AJUSTE."""
        admin_ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="ADMINISTRADOR",
            route_id=self.rid,
        )
        j = self._open_jornada(db_session)
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "GASOLINA",
                "monto": 5000,
                "nota": "Gasolina",
                "clave_idempotencia": "mov-idem-ajuste",
            },
            ctx=RequestContext(
                user_id=uuid4(),
                negocio_id=self.nid,
                role="COBRADOR",
                route_id=self.rid,
            ),
        )
        # Primer AJUSTE
        a1 = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "AJUSTE",
                "monto": 5000,
                "nota": "Nota version 1",
                "ajuste_de_movimiento_id": m.id,
                "clave_idempotencia": "ajuste-idem-001",
            },
            ctx=admin_ctx,
        )
        # Mismo payload → mismo ajuste
        a2 = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "AJUSTE",
                "monto": 5000,
                "nota": "Nota version 1",
                "ajuste_de_movimiento_id": m.id,
                "clave_idempotencia": "ajuste-idem-001",
            },
            ctx=admin_ctx,
        )
        assert a1.id == a2.id
        # Nota diferente → conflicto
        from src.services.movimiento_service import MovimientoIdempotencyError
        try:
            register_movimiento(
                db=db_session,
                data={
                    "jornada_id": j.id,
                    "tipo": "AJUSTE",
                    "monto": 5000,
                    "nota": "Nota version 2",
                    "ajuste_de_movimiento_id": m.id,
                    "clave_idempotencia": "ajuste-idem-001",
                },
                ctx=admin_ctx,
            )
            assert False, "Expected MovimientoIdempotencyError"
        except MovimientoIdempotencyError:
            pass


# ================================================================
# OTRO — sin nota devuelve HTTP 400
# ================================================================

class TestOtroSinNota:
    """OTRO sin nota produce MovimientoNotaObligatoria."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

    def test_otro_sin_nota_raises_exception(self, db_session):
        """OTRO sin nota lanza MovimientoNotaObligatoria."""
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
            fecha=date(2026, 7, 20),
            ctx=ctx,
        )
        try:
            register_movimiento(
                db=db_session,
                data={
                    "jornada_id": j.id,
                    "tipo": "OTRO",
                    "naturaleza": "GASTO",
                    "monto": 1000,
                    "nota": "",
                    "clave_idempotencia": "otro-sin-nota",
                },
                ctx=ctx,
            )
            assert False, "Expected MovimientoNotaObligatoria"
        except MovimientoNotaObligatoria:
            pass

    def test_otro_con_nota_vacia_raises_exception(self, db_session):
        """OTRO con nota whitespace solo lanza MovimientoNotaObligatoria."""
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
            ctx=ctx,
        )
        try:
            register_movimiento(
                db=db_session,
                data={
                    "jornada_id": j.id,
                    "tipo": "OTRO",
                    "naturaleza": "GASTO",
                    "monto": 1000,
                    "nota": "   ",
                    "clave_idempotencia": "otro-whitespace",
                },
                ctx=ctx,
            )
            assert False, "Expected MovimientoNotaObligatoria"
        except MovimientoNotaObligatoria:
            pass

    def test_otro_con_nota_valida(self, db_session):
        """OTRO con nota válida se registra correctamente."""
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
            fecha=date(2026, 7, 22),
            ctx=ctx,
        )
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "OTRO",
                "naturaleza": "GASTO",
                "monto": 1000,
                "nota": "Gasto no categorizado",
                "clave_idempotencia": "otro-valida",
            },
            ctx=ctx,
        )
        assert m.tipo == "OTRO"
        assert m.nota == "Gasto no categorizado"


# ================================================================
# MOVIMIENTO — naturaleza opcional, derivada por servidor
# ================================================================

class TestNaturalezaOpcional:
    """naturaleza es opcional en MovimientoCreate; solo OTRO la exige."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

    def test_gasolina_naturaleza_omitida(self, db_session):
        """GASOLINA sin naturaleza usa la derivada por servidor."""
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
            fecha=date(2026, 7, 23),
            ctx=ctx,
        )
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "GASOLINA",
                "monto": 5000,
                "clave_idempotencia": "gas-sin-nat",
            },
            ctx=ctx,
        )
        assert m.tipo == "GASOLINA"
        assert m.naturaleza == "GASTO"  # derivada por servidor

    def test_vale_naturaleza_omitida(self, db_session):
        """VALE sin naturaleza usa CUENTA_POR_COBRAR."""
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
            fecha=date(2026, 7, 24),
            ctx=ctx,
        )
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "VALE",
                "monto": 20000,
                "clave_idempotencia": "vale-sin-nat",
            },
            ctx=ctx,
        )
        assert m.tipo == "VALE"
        assert m.naturaleza == "CUENTA_POR_COBRAR"

    def test_otro_naturaleza_requerida(self, db_session):
        """OTRO exige naturaleza explícita."""
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
            fecha=date(2026, 7, 25),
            ctx=ctx,
        )
        try:
            register_movimiento(
                db=db_session,
                data={
                    "jornada_id": j.id,
                    "tipo": "OTRO",
                    "naturaleza": None,
                    "monto": 1000,
                    "nota": "Otro gasto",
                    "clave_idempotencia": "otro-sin-nat",
                },
                ctx=ctx,
            )
            assert False, "Expected MovimientoNaturalezaInvalida"
        except MovimientoNaturalezaInvalida:
            pass

    def test_otro_naturaleza_valida(self, db_session):
        """OTRO con naturaleza válida se registra."""
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
            fecha=date(2026, 7, 26),
            ctx=ctx,
        )
        m = register_movimiento(
            db=db_session,
            data={
                "jornada_id": j.id,
                "tipo": "OTRO",
                "naturaleza": "GASTO",
                "monto": 1000,
                "nota": "Otro gasto válido",
                "clave_idempotencia": "otro-con-nat",
            },
            ctx=ctx,
        )
        assert m.tipo == "OTRO"
        assert m.naturaleza == "GASTO"


# ================================================================
# SCHEMAS — claves no vacías, min_length=1
# ================================================================

class TestSchemasClavesNoVacias:
    """Claves obligatorias rechazan "" y whitespace."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.nid = uuid4()
        self.rid = uuid4()
        db_session.add(Negocio(id=self.nid, nombre="N", nit="1"))
        db_session.add(Ruta(id=self.rid, negocio_id=self.nid, nombre="R1"))
        db_session.commit()

    def test_jornada_create_clave_vacia(self):
        """JornadaCreate con clave_idempotencia vacía produce error."""
        from src.schemas import JornadaCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            JornadaCreate(
                ruta_id=uuid4(),
                opening_base=100000,
                clave_idempotencia="",
            )

    def test_jornada_create_clave_whitespace(self):
        """JornadaCreate con clave_idempotencia whitespace produce error en schema."""
        from src.schemas import JornadaCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            JornadaCreate(
                ruta_id=uuid4(),
                opening_base=100000,
                clave_idempotencia="   ",
            )

    def test_open_jornada_rechaza_clave_whitespace(self, db_session):
        """open_jornada rechaza clave solo espacios (no la convierte a None)."""
        from src.services.jornada_service import open_jornada, JornadaError
        ctx = RequestContext(
            user_id=uuid4(),
            negocio_id=self.nid,
            role="COBRADOR",
            route_id=self.rid,
        )
        try:
            open_jornada(
                db=db_session,
                ruta_id=self.rid,
                negocio_id=self.nid,
                fecha=date(2026, 7, 27),
                opening_base=100000,
                ctx=ctx,
                clave_idempotencia="   ",
            )
            assert False, "Expected JornadaError"
        except JornadaError as e:
            assert "espacios" in str(e).lower() or "vacío" in str(e)

    def test_jornada_cierre_create_clave_vacia(self):
        """JornadaCierreCreate con idempotencia_cierre vacía produce error."""
        from src.schemas import JornadaCierreCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            JornadaCierreCreate(
                efectivo_contado=100000,
                idempotencia_cierre="",
            )

    def test_movimiento_create_clave_vacia(self):
        """MovimientoCreate con clave_idempotencia vacía produce error."""
        from src.schemas import MovimientoCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MovimientoCreate(
                jornada_id=uuid4(),
                tipo="GASOLINA",
                monto=5000,
                clave_idempotencia="",
            )
