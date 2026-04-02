"""Tests for external authentication provider integration."""

from __future__ import annotations

import pytest

from lintel.domain.auth.external_providers import (
    ExternalAuthBridge,
    ExternalAuthProvider,
    ExternalAuthUser,
    OIDCConfig,
)
from lintel.domain.auth.types import AuthRole


class TestExternalAuthProvider:
    def test_enum_values(self) -> None:
        assert ExternalAuthProvider.KEYCLOAK == "keycloak"
        assert ExternalAuthProvider.CLERK == "clerk"
        assert ExternalAuthProvider.AUTH0 == "auth0"
        assert ExternalAuthProvider.OKTA == "okta"


class TestOIDCConfig:
    def test_frozen(self) -> None:
        cfg = OIDCConfig(
            provider=ExternalAuthProvider.KEYCLOAK,
            issuer_url="https://kc.example.com/realms/main",
            client_id="lintel",
            client_secret="secret",
        )
        with pytest.raises(AttributeError):
            cfg.client_id = "other"  # type: ignore[misc]

    def test_default_scopes(self) -> None:
        cfg = OIDCConfig(
            provider=ExternalAuthProvider.AUTH0,
            issuer_url="https://example.auth0.com/",
            client_id="cid",
            client_secret="csec",
        )
        assert cfg.scopes == ("openid", "profile", "email")

    def test_custom_scopes(self) -> None:
        cfg = OIDCConfig(
            provider=ExternalAuthProvider.CLERK,
            issuer_url="https://clerk.example.com",
            client_id="c",
            client_secret="s",
            scopes=("openid", "groups"),
        )
        assert cfg.scopes == ("openid", "groups")


class TestExternalAuthUser:
    def test_frozen(self) -> None:
        user = ExternalAuthUser(
            provider=ExternalAuthProvider.OKTA,
            external_id="ext-1",
            email="a@b.com",
            name="A",
        )
        with pytest.raises(AttributeError):
            user.email = "x@y.com"  # type: ignore[misc]

    def test_defaults(self) -> None:
        user = ExternalAuthUser(
            provider=ExternalAuthProvider.CLERK,
            external_id="u1",
            email="u@x.com",
            name="U",
        )
        assert user.groups == ()
        assert user.raw_claims == {}


class TestExternalAuthBridge:
    @pytest.fixture()
    def bridge(self) -> ExternalAuthBridge:
        b = ExternalAuthBridge()
        b.register_provider(
            OIDCConfig(
                provider=ExternalAuthProvider.KEYCLOAK,
                issuer_url="https://kc.example.com/realms/main",
                client_id="lintel",
                client_secret="secret",
            )
        )
        return b

    def test_register_and_list(self, bridge: ExternalAuthBridge) -> None:
        providers = bridge.list_providers()
        assert len(providers) == 1
        assert providers[0].provider == ExternalAuthProvider.KEYCLOAK

    def test_register_replaces(self, bridge: ExternalAuthBridge) -> None:
        bridge.register_provider(
            OIDCConfig(
                provider=ExternalAuthProvider.KEYCLOAK,
                issuer_url="https://new.example.com",
                client_id="new",
                client_secret="new-sec",
            )
        )
        assert len(bridge.list_providers()) == 1
        assert bridge.list_providers()[0].client_id == "new"

    def test_validate_token_stub(self, bridge: ExternalAuthBridge) -> None:
        user = bridge.validate_token(ExternalAuthProvider.KEYCLOAK, "fake-token")
        assert isinstance(user, ExternalAuthUser)
        assert user.provider == ExternalAuthProvider.KEYCLOAK

    def test_validate_token_unregistered_provider(self, bridge: ExternalAuthBridge) -> None:
        with pytest.raises(ValueError, match="not registered"):
            bridge.validate_token(ExternalAuthProvider.AUTH0, "tok")

    def test_map_to_local_role_member_default(self, bridge: ExternalAuthBridge) -> None:
        assert bridge.map_to_local_role(("users", "developers")) == AuthRole.MEMBER

    def test_map_to_local_role_admin(self, bridge: ExternalAuthBridge) -> None:
        assert bridge.map_to_local_role(("users", "admins")) == AuthRole.ADMIN

    def test_map_to_local_role_superuser(self, bridge: ExternalAuthBridge) -> None:
        assert bridge.map_to_local_role(("admins", "superusers")) == AuthRole.SUPERUSER

    def test_map_to_local_role_case_insensitive(self, bridge: ExternalAuthBridge) -> None:
        assert bridge.map_to_local_role(("Admins",)) == AuthRole.ADMIN

    def test_map_to_local_role_highest_wins(self, bridge: ExternalAuthBridge) -> None:
        assert bridge.map_to_local_role(("admin", "superuser")) == AuthRole.SUPERUSER

    def test_custom_group_role_map(self) -> None:
        bridge = ExternalAuthBridge(group_role_map={"ops": AuthRole.ADMIN})
        assert bridge.map_to_local_role(("ops",)) == AuthRole.ADMIN
        # Default mapping not present
        assert bridge.map_to_local_role(("admins",)) == AuthRole.MEMBER
