"""G3 — guard de TRUNCATE sobre PostgreSQL (conjuncion estricta).

La auditoria de 206b376 exige que ALLOW_PG_TRUNCATE NO sea un bypass
independiente: TRUNCATE solo se permite si las TRES condiciones son verdaderas
simultaneamente (DAILY_ENV=="test" AND nombre de DB test/scratch AND
ALLOW_PG_TRUNCATE=="1").
"""

from src.tests.conftest import pg_truncate_permitted


class TestGuardTruncateConjuncion:
    """Matriz de decision del guard (mismos casos que la auditoria)."""

    def test_production_cobro_test_optin(self):
        """DAILY_ENV=production + cobro_test + opt-in=1 -> DENEGAR."""
        assert not pg_truncate_permitted("production", "cobro_test", "1")

    def test_test_cobro_optin(self):
        """DAILY_ENV=test + cobro + opt-in=1 -> DENEGAR."""
        assert not pg_truncate_permitted("test", "cobro", "1")

    def test_test_cobro_test_sin_optin(self):
        """DAILY_ENV=test + cobro_test + sin opt-in -> DENEGAR."""
        assert not pg_truncate_permitted("test", "cobro_test", None)

    def test_test_cobro_test_optin(self):
        """DAILY_ENV=test + cobro_test + opt-in=1 -> PERMITIR."""
        assert pg_truncate_permitted("test", "cobro_test", "1")

    def test_nombres_scratch_validos(self):
        """cobro_scratch y cobro_scratch_m7 se reconocen como test/scratch."""
        assert pg_truncate_permitted("test", "cobro_scratch", "1")
        assert pg_truncate_permitted("test", "cobro_scratch_m7", "1")
        assert pg_truncate_permitted("test", "daily_system_test", "1")

    def test_optin_por_si_solo_denegado(self):
        """ALLOW_PG_TRUNCATE=1 por si solo (DB productiva) -> DENEGAR."""
        assert not pg_truncate_permitted("test", "cobro", "1")
        assert not pg_truncate_permitted("production", "cobro", "1")

    def test_env_test_por_si_solo_denegado(self):
        """DAILY_ENV=test por si solo (DB productiva) -> DENEGAR."""
        assert not pg_truncate_permitted("test", "cobro", None)
