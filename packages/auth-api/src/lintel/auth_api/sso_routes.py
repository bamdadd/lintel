"""SSO endpoints: configure providers, initiate login, handle callback."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.provider import StoreProvider
from lintel.auth_api.routes import auth_user_store_provider, session_store_provider
from lintel.domain.auth.passwords import hash_password
from lintel.domain.auth.sso import (
    SSOCallbackResult,
    SSOLoginRequest,
    SSOProtocol,
    SSOProviderConfig,
)
from lintel.domain.auth.types import AuthRole, AuthUser

if TYPE_CHECKING:
    from lintel.auth_api.sso_store import InMemorySSOConfigStore, InMemorySSOStateStore
    from lintel.auth_api.store import InMemoryAuthUserStore, InMemorySessionStore

sso_router = APIRouter()

sso_config_store_provider: StoreProvider[InMemorySSOConfigStore] = StoreProvider()
sso_state_store_provider: StoreProvider[InMemorySSOStateStore] = StoreProvider()


# -- Request / Response models -----------------------------------------------


class SSOConfigureRequest(BaseModel):
    """Request body for POST /auth/sso/configure."""

    name: str
    protocol: SSOProtocol
    enabled: bool = True
    # OIDC
    issuer_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    scopes: list[str] | None = None
    # SAML2
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    idp_certificate: str = ""
    sp_entity_id: str = ""
    # Common
    redirect_uri: str = ""
    group_attribute: str = "groups"
    email_attribute: str = "email"
    name_attribute: str = "name"
    group_role_map: dict[str, str] | None = None


class SSOConfigResponse(BaseModel):
    """Response for SSO provider configuration."""

    config_id: str
    name: str
    protocol: str
    enabled: bool
    issuer_url: str = ""
    client_id: str = ""
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    sp_entity_id: str = ""
    redirect_uri: str = ""


class SSOLoginResponse(BaseModel):
    """Response for GET /auth/sso/login — redirect URL for the IdP."""

    redirect_url: str
    state: str


class SSOCallbackResponse(BaseModel):
    """Response for GET /auth/sso/callback — tokens for the logged-in user."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    provisioned: bool = False


# -- Helpers ------------------------------------------------------------------

_DEFAULT_GROUP_ROLE_MAP: dict[str, AuthRole] = {
    "admin": AuthRole.ADMIN,
    "admins": AuthRole.ADMIN,
    "superuser": AuthRole.SUPERUSER,
    "superusers": AuthRole.SUPERUSER,
}


def _map_groups_to_role(
    groups: tuple[str, ...],
    custom_map: dict[str, str],
) -> AuthRole:
    """Map SSO group claims to the highest-privilege local role."""
    merged: dict[str, AuthRole] = dict(_DEFAULT_GROUP_ROLE_MAP)
    for k, v in custom_map.items():
        try:
            merged[k.lower()] = AuthRole(v)
        except ValueError:
            continue

    best = AuthRole.MEMBER
    priority = list(AuthRole)
    best_idx = priority.index(best)
    for group in groups:
        role = merged.get(group.lower())
        if role is not None:
            idx = priority.index(role)
            if idx > best_idx:
                best = role
                best_idx = idx
    return best


def _build_oidc_redirect(config: SSOProviderConfig, state: str) -> str:
    """Build the OIDC authorization URL."""
    scopes = "+".join(config.scopes)
    return (
        f"{config.issuer_url.rstrip('/')}/authorize"
        f"?client_id={config.client_id}"
        f"&response_type=code"
        f"&scope={scopes}"
        f"&redirect_uri={config.redirect_uri}"
        f"&state={state}"
    )


def _build_saml_redirect(config: SSOProviderConfig, state: str) -> str:
    """Build the SAML2 SSO redirect URL."""
    return f"{config.idp_sso_url}?RelayState={state}"


def _simulate_callback(
    config: SSOProviderConfig,
    params: dict[str, Any],
) -> SSOCallbackResult:
    """Simulate IdP callback processing.

    In production this would validate the SAML assertion or exchange the OIDC
    authorization code for tokens, then extract claims. Here we accept stub
    claims from query parameters for testability.
    """
    return SSOCallbackResult(
        email=str(params.get("email", "sso-user@example.com")),
        name=str(params.get("name", "SSO User")),
        external_id=str(params.get("external_id", f"ext-{uuid4().hex[:8]}")),
        groups=tuple(str(params.get("groups", "")).split(",")) if params.get("groups") else (),
        raw_claims=dict(params),
    )


# -- Endpoints ----------------------------------------------------------------


@sso_router.post("/auth/sso/configure", status_code=201)
async def configure_sso(
    body: SSOConfigureRequest,
    store: InMemorySSOConfigStore = Depends(sso_config_store_provider),  # noqa: B008
) -> SSOConfigResponse:
    """Register or update an SSO identity provider configuration."""
    if body.protocol == SSOProtocol.OIDC and not body.issuer_url:
        raise HTTPException(status_code=422, detail="issuer_url required for OIDC")
    if body.protocol == SSOProtocol.SAML2 and not body.idp_sso_url:
        raise HTTPException(status_code=422, detail="idp_sso_url required for SAML2")

    config = SSOProviderConfig(
        config_id=str(uuid4()),
        name=body.name,
        protocol=body.protocol,
        enabled=body.enabled,
        issuer_url=body.issuer_url,
        client_id=body.client_id,
        client_secret=body.client_secret,
        scopes=tuple(body.scopes) if body.scopes else ("openid", "profile", "email"),
        idp_entity_id=body.idp_entity_id,
        idp_sso_url=body.idp_sso_url,
        idp_certificate=body.idp_certificate,
        sp_entity_id=body.sp_entity_id,
        redirect_uri=body.redirect_uri,
        group_attribute=body.group_attribute,
        email_attribute=body.email_attribute,
        name_attribute=body.name_attribute,
        group_role_map=body.group_role_map or {},
    )
    await store.save(config)
    return SSOConfigResponse(
        config_id=config.config_id,
        name=config.name,
        protocol=config.protocol,
        enabled=config.enabled,
        issuer_url=config.issuer_url,
        client_id=config.client_id,
        idp_entity_id=config.idp_entity_id,
        idp_sso_url=config.idp_sso_url,
        sp_entity_id=config.sp_entity_id,
        redirect_uri=config.redirect_uri,
    )


@sso_router.get("/auth/sso/configs")
async def list_sso_configs(
    store: InMemorySSOConfigStore = Depends(sso_config_store_provider),  # noqa: B008
) -> list[SSOConfigResponse]:
    """List all configured SSO providers."""
    configs = await store.list_all()
    return [
        SSOConfigResponse(
            config_id=c.config_id,
            name=c.name,
            protocol=c.protocol,
            enabled=c.enabled,
            issuer_url=c.issuer_url,
            client_id=c.client_id,
            idp_entity_id=c.idp_entity_id,
            idp_sso_url=c.idp_sso_url,
            sp_entity_id=c.sp_entity_id,
            redirect_uri=c.redirect_uri,
        )
        for c in configs
    ]


@sso_router.get("/auth/sso/login")
async def sso_login(
    config_id: str,
    config_store: InMemorySSOConfigStore = Depends(sso_config_store_provider),  # noqa: B008
    state_store: InMemorySSOStateStore = Depends(sso_state_store_provider),  # noqa: B008
) -> SSOLoginResponse:
    """Initiate SSO login — returns the IdP redirect URL."""
    config = await config_store.get(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="SSO configuration not found")
    if not config.enabled:
        raise HTTPException(status_code=400, detail="SSO provider is disabled")

    state = uuid4().hex

    if config.protocol == SSOProtocol.OIDC:
        redirect_url = _build_oidc_redirect(config, state)
    else:
        redirect_url = _build_saml_redirect(config, state)

    await state_store.save(
        SSOLoginRequest(state=state, config_id=config.config_id, redirect_url=redirect_url)
    )
    return SSOLoginResponse(redirect_url=redirect_url, state=state)


@sso_router.get("/auth/sso/callback")
async def sso_callback(
    state: str,
    request: Request,
    config_store: InMemorySSOConfigStore = Depends(sso_config_store_provider),  # noqa: B008
    state_store: InMemorySSOStateStore = Depends(sso_state_store_provider),  # noqa: B008
    user_store: InMemoryAuthUserStore = Depends(auth_user_store_provider),  # noqa: B008
    sessions: InMemorySessionStore = Depends(session_store_provider),  # noqa: B008
) -> SSOCallbackResponse:
    """Handle SSO IdP callback — validate, provision user, return tokens."""
    from datetime import UTC, datetime

    from lintel.domain.auth.jwt import (
        REFRESH_TOKEN_EXPIRES,
        create_access_token,
        create_refresh_token,
    )
    from lintel.domain.auth.types import AuthSession

    login_req = await state_store.pop(state)
    if login_req is None:
        raise HTTPException(status_code=400, detail="Invalid or expired SSO state")

    config = await config_store.get(login_req.config_id)
    if config is None:
        raise HTTPException(status_code=400, detail="SSO configuration not found")

    # Process the callback (stub: uses query params as claims)
    params = dict(request.query_params)
    result = _simulate_callback(config, params)

    # Provision or look up the user
    provisioned = False
    existing = await user_store.get_by_email(result.email)
    if existing is not None:
        user = existing
    else:
        role = _map_groups_to_role(result.groups, config.group_role_map)
        user = AuthUser(
            user_id=str(uuid4()),
            email=result.email,
            name=result.name,
            hashed_password=hash_password(uuid4().hex),
            role=role,
        )
        await user_store.add(user)
        provisioned = True

    # Create session and tokens
    session_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    expires = datetime.fromtimestamp(
        datetime.now(UTC).timestamp() + REFRESH_TOKEN_EXPIRES,
        tz=UTC,
    ).isoformat()

    refresh_token, jti = create_refresh_token(
        user.user_id,
        user.role,
        session_id=session_id,
    )
    access_token = create_access_token(
        user.user_id,
        user.role,
        session_id=session_id,
    )

    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    session = AuthSession(
        session_id=session_id,
        user_id=user.user_id,
        refresh_token_jti=jti,
        created_at=now,
        expires_at=expires,
        user_agent=ua,
        ip_address=ip,
    )
    await sessions.create(session)

    return SSOCallbackResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        email=user.email,
        provisioned=provisioned,
    )
