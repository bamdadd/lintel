"""SSO configuration types for SAML2 and OIDC providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SSOProtocol(StrEnum):
    """Supported SSO protocols."""

    SAML2 = "saml2"
    OIDC = "oidc"


@dataclass(frozen=True)
class SSOProviderConfig:
    """Configuration for an SSO identity provider."""

    config_id: str
    name: str
    protocol: SSOProtocol
    enabled: bool = True

    # OIDC fields
    issuer_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    scopes: tuple[str, ...] = ("openid", "profile", "email")

    # SAML2 fields
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    idp_certificate: str = ""
    sp_entity_id: str = ""

    # Common
    redirect_uri: str = ""
    group_attribute: str = "groups"
    email_attribute: str = "email"
    name_attribute: str = "name"
    group_role_map: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SSOLoginRequest:
    """Represents a pending SSO login (state token → config mapping)."""

    state: str
    config_id: str
    redirect_url: str = ""


@dataclass(frozen=True)
class SSOCallbackResult:
    """Result of processing an SSO callback."""

    email: str
    name: str
    external_id: str
    groups: tuple[str, ...] = ()
    raw_claims: dict[str, Any] = field(default_factory=dict)
