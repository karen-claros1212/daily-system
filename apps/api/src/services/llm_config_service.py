"""W10 — Servicio de configuración LLM + credenciales BYOK.

Lógica de dominio para la API admin: listar/obtener providers (con
credential_source resuelta, NUNCA la clave), actualizar config, set/eliminar
credencial BYOK (vía SecretStore), y test de conexión (vía gateway).

Separación credential/config (W10 §11): una lectura normal de config no
devuelve el secreto; el secreto vive en el SecretStore (secret_ref opaco).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.llm_provider import LLMProviderConfig
from src.services.llm import registry
from src.services.llm.errors import LLMProviderError
from src.services.llm.gateway import ProviderGateway
from src.services.llm.secret_store import SecretStore


def make_key_hint(key: str | None) -> str | None:
    """Hint segura de la clave: prefijo + … + sufijo. Nunca permite reconstruirla."""
    if not key:
        return None
    if len(key) <= 7:
        return "…" + key[-4:] if len(key) >= 4 else "…"
    return key[:3] + "…" + key[-4:]


def _provider_status(
    db: Session,
    negocio_id: UUID,
    provider: str,
    secret_store: SecretStore,
) -> dict:
    """Estado de un provider para el negocio (sin la clave)."""
    spec = registry.get_spec(provider)
    config = (
        db.query(LLMProviderConfig)
        .filter(
            LLMProviderConfig.negocio_id == negocio_id,
            LLMProviderConfig.provider == provider,
        )
        .first()
    )
    # Resuelve la credencial para informar credential_source (sin exponer la key).
    resolved = _resolve(db, negocio_id, provider, secret_store)
    byok_configured = bool(
        config is not None
        and config.secret_ref
        and secret_store.has(config.secret_ref)
    )
    return {
        "provider": provider,
        "protocol": spec.protocol if spec else None,
        "type": "openai-compatible" if (spec and spec.protocol == "openai") else (spec.protocol if spec else None),
        "model": (config.model if config else None) or (spec.default_model if spec else None),
        "endpoint_profile": config.endpoint_profile if config else None,
        "enabled": bool(config.enabled) if config else False,
        "is_default": bool(config.is_default) if config else False,
        "configured": byok_configured or resolved.credential_source is not None,
        "credential_source": resolved.credential_source,
        "available": resolved.available,
        "key_hint": config.key_hint if config else None,
        "capabilities": _capabilities_for(provider, config),
    }


def _resolve(db, negocio_id, provider, secret_store):
    from src.services.llm.credentials import resolve_credential

    return resolve_credential(db, negocio_id, provider, secret_store)


def _capabilities_for(provider: str, config: LLMProviderConfig | None) -> dict:
    """Capacidades del provider (del profile si aplica, del adapter si no)."""
    spec = registry.get_spec(provider)
    if spec is None:
        return {}
    if spec.uses_endpoint_profile:
        profile_id = config.endpoint_profile if config else None
        profile = registry.get_endpoint_profile(profile_id or "")
        caps = profile.capabilities if profile else registry.LLMCapabilities(text=True, streaming=True)
    else:
        # Instanciar el adapter solo para leer capacidades (sin llamar).
        adapter = spec.adapter_cls(base_url=spec.native_base_url or "", api_key="", model=spec.default_model)
        caps = adapter.capabilities()
    return {
        "text": caps.text,
        "tools": caps.tools,
        "structured_output": caps.structured_output,
        "vision": caps.vision,
        "streaming": caps.streaming,
    }


# --- API del servicio ---


def list_providers(db: Session, negocio_id: UUID, secret_store: SecretStore) -> list[dict]:
    """Catálogo de los 6 providers con su estado para el negocio."""
    return [
        _provider_status(db, negocio_id, p, secret_store)
        for p in registry.ALL_PROVIDERS
    ]


def get_provider(db: Session, negocio_id: UUID, provider: str, secret_store: SecretStore) -> dict | None:
    if not registry.is_known_provider(provider):
        return None
    return _provider_status(db, negocio_id, provider, secret_store)


def update_config(
    db: Session,
    negocio_id: UUID,
    provider: str,
    *,
    model: str | None = None,
    endpoint_profile: str | None = None,
    enabled: int | None = None,
    is_default: int | None = None,
    actor_id: UUID | None = None,
) -> LLMProviderConfig:
    """Upsert de la config NO secreta (model/endpoint_profile/enabled/is_default)."""
    if not registry.is_known_provider(provider):
        raise LLMProviderError("INVALID_CONFIGURATION", f"provider desconocido: {provider}")
    spec = registry.get_spec(provider)
    # Validar endpoint_profile (solo para OPENAI_COMPATIBLE_GENERIC).
    if spec and spec.uses_endpoint_profile and endpoint_profile is not None:
        if registry.get_endpoint_profile(endpoint_profile) is None:
            raise LLMProviderError(
                "INVALID_CONFIGURATION",
                f"endpoint_profile fuera de allowlist: {endpoint_profile}",
            )
    elif endpoint_profile is not None:
        # Provider nativo no usa endpoint_profile.
        raise LLMProviderError(
            "INVALID_CONFIGURATION",
            f"{provider} no usa endpoint_profile",
        )

    config = (
        db.query(LLMProviderConfig)
        .filter(
            LLMProviderConfig.negocio_id == negocio_id,
            LLMProviderConfig.provider == provider,
        )
        .first()
    )
    if config is None:
        config = LLMProviderConfig(negocio_id=negocio_id, provider=provider)
        db.add(config)
    if model is not None:
        config.model = model
    if endpoint_profile is not None:
        config.endpoint_profile = endpoint_profile
    if enabled is not None:
        config.enabled = 1 if enabled else 0
    if is_default is not None:
        config.is_default = 1 if is_default else 0
    config.actualizado_por = actor_id
    db.flush()
    return config


def set_credential(
    db: Session,
    negocio_id: UUID,
    provider: str,
    api_key: str,
    secret_store: SecretStore,
    *,
    actor_id: UUID | None = None,
) -> LLMProviderConfig:
    """Cifra la clave BYOK en el SecretStore y guarda secret_ref + key_hint."""
    if not registry.is_known_provider(provider):
        raise LLMProviderError("INVALID_CONFIGURATION", f"provider desconocido: {provider}")
    if not api_key or not api_key.strip():
        raise LLMProviderError("INVALID_CONFIGURATION", "api_key vacía")
    api_key = api_key.strip()

    config = (
        db.query(LLMProviderConfig)
        .filter(
            LLMProviderConfig.negocio_id == negocio_id,
            LLMProviderConfig.provider == provider,
        )
        .first()
    )
    # Reutiliza el secret_ref existente si hay uno (actualiza el secreto).
    secret_ref = config.secret_ref if config and config.secret_ref else None
    secret_ref = secret_store.put(api_key, secret_ref=secret_ref)

    if config is None:
        config = LLMProviderConfig(negocio_id=negocio_id, provider=provider)
        db.add(config)
    config.secret_ref = secret_ref
    config.key_hint = make_key_hint(api_key)
    config.enabled = 1
    config.actualizado_por = actor_id
    db.flush()
    return config


def delete_credential(
    db: Session,
    negocio_id: UUID,
    provider: str,
    secret_store: SecretStore,
) -> bool:
    """Invalida el secret_ref y limpia key_hint. Devuelve True si había BYOK."""
    config = (
        db.query(LLMProviderConfig)
        .filter(
            LLMProviderConfig.negocio_id == negocio_id,
            LLMProviderConfig.provider == provider,
        )
        .first()
    )
    if config is None or not config.secret_ref:
        return False
    secret_store.delete(config.secret_ref)
    config.secret_ref = None
    config.key_hint = None
    db.flush()
    return True


def test_provider(
    db: Session,
    negocio_id: UUID,
    provider: str,
    gateway: ProviderGateway,
) -> dict:
    """Test de conexión (delega en el gateway)."""
    if not registry.is_known_provider(provider):
        raise LLMProviderError("INVALID_CONFIGURATION", f"provider desconocido: {provider}")
    return gateway.test_connection(db, negocio_id, provider)
