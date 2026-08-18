"""W10 — Resolución de credenciales (orden obligatorio).

Contrato W10 §5:
  TENANT_BYOK activo
      ↓ si no existe
  PLATFORM_MANAGED disponible
      ↓ si no existe
  PROVIDER_UNAVAILABLE

Exacto: tenant override → platform default → unavailable. NO hay fallback
secreto hacia un proveedor diferente sin política explícita.

La respuesta (LLMResolvedProvider) indica SOLO credential_source
(TENANT_BYOK | PLATFORM_MANAGED) — NUNCA la clave (esta es transitoria para
el gateway).
"""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.llm_provider import LLMProviderConfig
from src.services.llm import registry
from src.services.llm.secret_store import SecretStore
from src.services.llm.types import LLMResolvedProvider

# Variable de entorno de la clave plataforma por familia de proveedor.
_PLATFORM_KEY_ENV = "LLM_PLATFORM_{provider}_API_KEY"
# Profile por defecto para OPENAI_COMPATIBLE_GENERIC en modo plataforma.
_GENERIC_PROFILE_ENV = "LLM_PLATFORM_OPENAI_COMPATIBLE_GENERIC_PROFILE"
_GENERIC_DEFAULT_PROFILE = "openrouter"


def _platform_key(provider: str) -> str | None:
    """Clave administrada por plataforma (ENV). None si no está configurada."""
    return os.getenv(_PLATFORM_KEY_ENV.format(provider=provider)) or None


def _platform_generic_profile() -> str:
    return os.getenv(_GENERIC_PROFILE_ENV) or _GENERIC_DEFAULT_PROFILE


def _resolve_base_url(
    spec: registry.ProviderSpec,
    endpoint_profile: str | None,
) -> str | None:
    """Resuelve la base_url a llamar.

    - Provider nativo: base_url nativa.
    - OPENAI_COMPATIBLE_GENERIC: base_url del endpoint profile allowlistado
      (el tenant elige profile_id; nunca URL arbitraria).
    """
    if spec.uses_endpoint_profile:
        if not endpoint_profile:
            return None
        profile = registry.get_endpoint_profile(endpoint_profile)
        return profile.base_url if profile else None
    return spec.native_base_url


def resolve_credential(
    db: Session,
    negocio_id: UUID,
    provider: str,
    secret_store: SecretStore,
) -> LLMResolvedProvider:
    """Resuelve la credencial para (negocio, provider) en el orden obligatorio."""
    spec = registry.get_spec(provider)
    if spec is None:
        return LLMResolvedProvider(provider=provider, available=False)

    # 1) TENANT_BYOK activo.
    config = (
        db.query(LLMProviderConfig)
        .filter(
            LLMProviderConfig.negocio_id == negocio_id,
            LLMProviderConfig.provider == provider,
            LLMProviderConfig.enabled == 1,
        )
        .first()
    )
    if config is not None and config.secret_ref and secret_store.has(config.secret_ref):
        api_key = secret_store.get(config.secret_ref)
        base_url = _resolve_base_url(spec, config.endpoint_profile)
        if base_url is None:
            # Config BYOK con profile inválido -> indisponible (no fallback
            # secreto a plataforma con otra config).
            return LLMResolvedProvider(provider=provider, available=False)
        return LLMResolvedProvider(
            provider=provider,
            available=True,
            credential_source="TENANT_BYOK",
            api_key=api_key,
            base_url=base_url,
            model=config.model or spec.default_model,
            endpoint_profile=config.endpoint_profile,
        )

    # 2) PLATFORM_MANAGED disponible.
    platform_key = _platform_key(provider)
    if platform_key:
        if spec.uses_endpoint_profile:
            profile_id = _platform_generic_profile()
            profile = registry.get_endpoint_profile(profile_id)
            if profile is None:
                return LLMResolvedProvider(provider=provider, available=False)
            return LLMResolvedProvider(
                provider=provider,
                available=True,
                credential_source="PLATFORM_MANAGED",
                api_key=platform_key,
                base_url=profile.base_url,
                model=spec.default_model,
                endpoint_profile=profile_id,
            )
        return LLMResolvedProvider(
            provider=provider,
            available=True,
            credential_source="PLATFORM_MANAGED",
            api_key=platform_key,
            base_url=spec.native_base_url,
            model=spec.default_model,
        )

    # 3) PROVIDER_UNAVAILABLE.
    return LLMResolvedProvider(provider=provider, available=False)
