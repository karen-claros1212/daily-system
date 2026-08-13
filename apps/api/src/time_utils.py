"""Utilidades de tiempo compartidas (normalizacion UTC).

Postgres devuelve columnas `timestamp without time zone` como datetimes
NAIVE (no carry timezone). Comparar esas fechas contra `datetime.now(timezone.utc)`
levantaba `TypeError: can't compare offset-naive and offset-aware datetimes`.
Este helper normaliza cualquier fecha a UTC aware (asumiendo que un naive
representa UTC, como lo siembra el seed), de modo que los controles de
suscripcion sean deterministas y no dependan de como resuelve el driver.
"""

from datetime import datetime, timezone


def as_utc(dt: datetime | None) -> datetime | None:
    """Normaliza a UTC aware: naive se interpreta como UTC, aware se convierte."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
