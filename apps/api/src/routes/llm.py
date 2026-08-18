"""W10 — API admin del Provider Gateway Multi-LLM + BYOK.

Endpoints (SOLO ADMINISTRADOR — llm:ver / llm:gestionar):
  GET    /api/llm/providers                     — catálogo 6 providers + estado
  GET    /api/llm/providers/{provider}          — estado de un provider
  PUT    /api/llm/providers/{provider}/config   — config no secreta
  PUT    /api/llm/providers/{provider}/credential — set BYOK (se cifra)
  DELETE /api/llm/providers/{provider}/credential — eliminar BYOK
  POST   /api/llm/providers/{provider}/test     — test de conexión

Separación credential/config: una lectura normal (GET) NUNCA devuelve la
clave; solo configured/credential_source/key_hint. La clave vive en el
SecretStore (secret_ref opaco).

RBAC: backend authority. COBRADOR/INVERSIONISTA -> 403 (direct URL incluida).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import AuditLog
from src.rbac import tiene_capability
from src.schemas import (
    LLMConfigUpdate,
    LLMCredentialSet,
    LLMCredentialStatus,
    LLMProviderListResponse,
    LLMProviderStatus,
    LLMProviderTestResponse,
)
from src.services import llm_config_service
from src.services.llm import registry
from src.services.llm.deps import dep_llm_gateway, dep_secret_store
from src.services.llm.errors import LLMProviderError
from src.services.llm.gateway import ProviderGateway
from src.services.llm.secret_store import SecretStore, SecretStoreNotConfigured

router = APIRouter(prefix="/api/llm", tags=["llm"])

WriteSession = Annotated[Session, Depends(get_db_transaction, scope="function")]
ReadSession = Annotated[Session, Depends(get_db)]


def _require(rol: str | None, capability: str, detail: str) -> None:
    if not tiene_capability(rol, capability):
        raise HTTPException(status_code=403, detail=detail)


def _endpoint_profiles_payload() -> list[dict]:
    return [
        {
            "profile_id": p.profile_id,
            "label": p.label,
            "protocol": p.protocol,
            "capabilities": {
                "text": p.capabilities.text,
                "tools": p.capabilities.tools,
                "structured_output": p.capabilities.structured_output,
                "vision": p.capabilities.vision,
                "streaming": p.capabilities.streaming,
            },
        }
        for p in registry.ENDPOINT_PROFILES.values()
    ]


def _audit(
    db: Session,
    negocio_id: UUID,
    actor_id: UUID | None,
    action: str,
    metadata: dict,
    request: Request,
) -> None:
    db.add(
        AuditLog(
            negocio_id=negocio_id,
            actor_id=actor_id,
            action=action,
            entity_type="LLM_PROVIDER",
            entity_id=negocio_id,
            metadata_col=metadata,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.flush()


@router.get("/providers", response_model=LLMProviderListResponse)
def list_providers(
    request: Request,
    db: ReadSession,
    ctx: RequestContext = Depends(get_request_context),
    store: SecretStore = Depends(dep_secret_store),
):
    _require(ctx.role, "llm:ver", "Solo ADMINISTRADOR puede ver la config LLM")
    providers = llm_config_service.list_providers(db, ctx.negocio_id, store)
    return LLMProviderListResponse(
        providers=[LLMProviderStatus(**p) for p in providers],
        endpoint_profiles=_endpoint_profiles_payload(),
    )


@router.get("/providers/{provider}", response_model=LLMProviderStatus)
def get_provider(
    provider: str,
    db: ReadSession,
    ctx: RequestContext = Depends(get_request_context),
    store: SecretStore = Depends(dep_secret_store),
):
    _require(ctx.role, "llm:ver", "Solo ADMINISTRADOR puede ver la config LLM")
    status = llm_config_service.get_provider(db, ctx.negocio_id, provider, store)
    if status is None:
        raise HTTPException(status_code=404, detail=f"provider desconocido: {provider}")
    return LLMProviderStatus(**status)


@router.put("/providers/{provider}/config", response_model=LLMProviderStatus)
def update_config(
    provider: str,
    data: LLMConfigUpdate,
    request: Request,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
    store: SecretStore = Depends(dep_secret_store),
):
    _require(ctx.role, "llm:gestionar", "Solo ADMINISTRADOR puede gestionar la config LLM")
    try:
        llm_config_service.update_config(
            db,
            ctx.negocio_id,
            provider,
            model=data.model,
            endpoint_profile=data.endpoint_profile,
            enabled=data.enabled,
            is_default=data.is_default,
            actor_id=ctx.user_id,
        )
    except LLMProviderError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail or e.error_class)
    _audit(
        db,
        ctx.negocio_id,
        ctx.user_id,
        "LLM_PROVIDER_CONFIG_UPDATED",
        {
            "provider": provider,
            "model": data.model,
            "endpoint_profile": data.endpoint_profile,
            "enabled": data.enabled,
            "is_default": data.is_default,
        },
        request,
    )
    db.commit()
    status = llm_config_service.get_provider(db, ctx.negocio_id, provider, store)
    return LLMProviderStatus(**status)


@router.put("/providers/{provider}/credential", response_model=LLMCredentialStatus)
def set_credential(
    provider: str,
    data: LLMCredentialSet,
    request: Request,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
    store: SecretStore = Depends(dep_secret_store),
):
    _require(ctx.role, "llm:gestionar", "Solo ADMINISTRADOR puede gestionar la config LLM")
    try:
        config = llm_config_service.set_credential(
            db, ctx.negocio_id, provider, data.api_key, store, actor_id=ctx.user_id
        )
    except LLMProviderError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail or e.error_class)
    except SecretStoreNotConfigured:
        # Fail-closed del SecretStore (master key ausente) -> 503.
        raise HTTPException(status_code=503, detail="SecretStore no configurado (fail-closed)")
    _audit(
        db,
        ctx.negocio_id,
        ctx.user_id,
        "LLM_BYOK_SET",
        {
            "provider": provider,
            "key_hint": config.key_hint,
            "model": config.model,
            "endpoint_profile": config.endpoint_profile,
        },
        request,
    )
    db.commit()
    return LLMCredentialStatus(
        provider=provider,
        configured=True,
        credential_source="TENANT_BYOK",
        key_hint=config.key_hint,
    )


@router.delete("/providers/{provider}/credential", response_model=LLMCredentialStatus)
def delete_credential(
    provider: str,
    request: Request,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
    store: SecretStore = Depends(dep_secret_store),
):
    _require(ctx.role, "llm:gestionar", "Solo ADMINISTRADOR puede gestionar la config LLM")
    removed = llm_config_service.delete_credential(db, ctx.negocio_id, provider, store)
    if removed:
        _audit(
            db,
            ctx.negocio_id,
            ctx.user_id,
            "LLM_BYOK_REMOVED",
            {"provider": provider},
            request,
        )
    db.commit()
    # Tras eliminar el BYOK, la fuente puede pasar a PLATFORM_MANAGED.
    from src.services.llm.credentials import resolve_credential

    resolved = resolve_credential(db, ctx.negocio_id, provider, store)
    return LLMCredentialStatus(
        provider=provider,
        configured=resolved.credential_source is not None,
        credential_source=resolved.credential_source,
        key_hint=None,
    )


@router.post("/providers/{provider}/test", response_model=LLMProviderTestResponse)
def test_provider(
    provider: str,
    db: ReadSession,
    ctx: RequestContext = Depends(get_request_context),
    gateway: ProviderGateway = Depends(dep_llm_gateway),
):
    _require(ctx.role, "llm:gestionar", "Solo ADMINISTRADOR puede testear el provider")
    try:
        result = llm_config_service.test_provider(db, ctx.negocio_id, provider, gateway)
    except LLMProviderError as e:
        return LLMProviderTestResponse(
            provider=provider,
            status=e.error_class,
            detail=e.detail,
            available=False,
        )
    caps = result.get("capabilities")
    from src.schemas import LLMCapabilitiesSchema

    return LLMProviderTestResponse(
        provider=provider,
        status=result.get("status", "OK"),
        model=result.get("model"),
        latency_ms=result.get("latency_ms"),
        credential_source=result.get("credential_source"),
        available=result.get("available", False),
        capabilities=LLMCapabilitiesSchema(**caps) if caps else None,
    )
