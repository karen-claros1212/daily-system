"""W10 — Dependencies de la API LLM (SecretStore + Gateway singleton).

El SecretStore es un singleton de proceso (los secretos BYOK viven en memoria
en W10; en producción se sustituye por tabla/KMS sin cambiar la interfaz).
`reset_shared()` permite a los tests reiniciar el singleton tras cambiar env.
"""

from __future__ import annotations

from src.services.llm.gateway import ProviderGateway
from src.services.llm.secret_store import SecretStore

_shared_secret_store: SecretStore | None = None
_shared_gateway: ProviderGateway | None = None


def get_shared_secret_store() -> SecretStore:
    global _shared_secret_store
    if _shared_secret_store is None:
        _shared_secret_store = SecretStore.from_env()
    return _shared_secret_store


def get_shared_gateway() -> ProviderGateway:
    global _shared_gateway
    if _shared_gateway is None:
        _shared_gateway = ProviderGateway(get_shared_secret_store())
    return _shared_gateway


def reset_shared() -> None:
    """Reinicia los singletons (tests: tras cambiar LLM_SECRET_MASTER_KEY)."""
    global _shared_secret_store, _shared_gateway
    _shared_secret_store = None
    _shared_gateway = None


# --- FastAPI dependencies (sobrescribibles en tests) ---


def dep_secret_store() -> SecretStore:
    return get_shared_secret_store()


def dep_llm_gateway() -> ProviderGateway:
    return get_shared_gateway()
