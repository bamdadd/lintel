"""Tests for RBAC domain model."""

from __future__ import annotations

from lintel.domain.auth.rbac import (
    ADMIN,
    DEFAULT_ROLES,
    MEMBER,
    SUPERUSER,
    VIEWER,
    Permission,
    RBACPolicy,
    Role,
    TeamScope,
    UserRoleBinding,
)

# ── Permission enum ──────────────────────────────────────────────


class TestPermission:
    def test_values(self) -> None:
        assert set(Permission) == {
            Permission.READ,
            Permission.WRITE,
            Permission.ADMIN,
            Permission.SUPERUSER,
        }

    def test_str_representation(self) -> None:
        assert str(Permission.READ) == "read"


# ── Role ─────────────────────────────────────────────────────────


class TestRole:
    def test_has_permission(self) -> None:
        role = Role(name="custom", permissions=frozenset({Permission.READ}))
        assert role.has_permission(Permission.READ)
        assert not role.has_permission(Permission.WRITE)

    def test_frozen(self) -> None:
        role = Role(name="x", permissions=frozenset())
        try:
            role.name = "y"  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass


# ── Default roles ────────────────────────────────────────────────


class TestDefaultRoles:
    def test_viewer_read_only(self) -> None:
        assert VIEWER.has_permission(Permission.READ)
        assert not VIEWER.has_permission(Permission.WRITE)

    def test_member_read_write(self) -> None:
        assert MEMBER.has_permission(Permission.READ)
        assert MEMBER.has_permission(Permission.WRITE)
        assert not MEMBER.has_permission(Permission.ADMIN)

    def test_admin_includes_admin(self) -> None:
        assert ADMIN.has_permission(Permission.ADMIN)
        assert not ADMIN.has_permission(Permission.SUPERUSER)

    def test_superuser_has_all(self) -> None:
        for p in Permission:
            assert SUPERUSER.has_permission(p)

    def test_default_roles_dict(self) -> None:
        assert set(DEFAULT_ROLES) == {"viewer", "member", "admin", "superuser"}


# ── TeamScope ────────────────────────────────────────────────────


class TestTeamScope:
    def test_empty_allows_all(self) -> None:
        scope = TeamScope(team_id="t1")
        assert scope.includes_project("any-project")

    def test_restricted_allows_listed(self) -> None:
        scope = TeamScope(team_id="t1", allowed_project_ids=frozenset({"p1", "p2"}))
        assert scope.includes_project("p1")
        assert not scope.includes_project("p3")

    def test_frozen(self) -> None:
        scope = TeamScope(team_id="t1")
        try:
            scope.team_id = "t2"  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass


# ── RBACPolicy ───────────────────────────────────────────────────


class TestRBACPolicy:
    def _policy(self) -> RBACPolicy:
        return RBACPolicy(
            bindings=[
                UserRoleBinding(
                    user_id="u1",
                    role=MEMBER,
                    scope=TeamScope(team_id="t1", allowed_project_ids=frozenset({"p1", "p2"})),
                ),
                UserRoleBinding(user_id="u2", role=SUPERUSER),
            ]
        )

    def test_check_permission_allowed(self) -> None:
        policy = self._policy()
        assert policy.check_permission("u1", Permission.READ, "p1")

    def test_check_permission_denied_wrong_project(self) -> None:
        policy = self._policy()
        assert not policy.check_permission("u1", Permission.READ, "p999")

    def test_check_permission_denied_wrong_action(self) -> None:
        policy = self._policy()
        assert not policy.check_permission("u1", Permission.ADMIN, "p1")

    def test_superuser_bypasses_scope(self) -> None:
        policy = self._policy()
        assert policy.check_permission("u2", Permission.ADMIN, "any-project")

    def test_check_no_resource_project(self) -> None:
        policy = self._policy()
        assert policy.check_permission("u1", Permission.WRITE)

    def test_unknown_user_denied(self) -> None:
        policy = self._policy()
        assert not policy.check_permission("unknown", Permission.READ)

    def test_get_accessible_projects_scoped(self) -> None:
        policy = self._policy()
        assert policy.get_accessible_projects("u1") == ["p1", "p2"]

    def test_get_accessible_projects_unrestricted(self) -> None:
        policy = self._policy()
        # u2 has no scope → unrestricted
        assert policy.get_accessible_projects("u2") == []

    def test_get_accessible_projects_unknown_user(self) -> None:
        policy = RBACPolicy()
        assert policy.get_accessible_projects("nobody") == []

    def test_add_binding(self) -> None:
        policy = RBACPolicy()
        policy.add_binding(UserRoleBinding(user_id="u3", role=VIEWER))
        assert policy.check_permission("u3", Permission.READ)
        assert not policy.check_permission("u3", Permission.WRITE)

    def test_get_bindings_for_user(self) -> None:
        policy = self._policy()
        bindings = policy.get_bindings_for_user("u1")
        assert len(bindings) == 1
        assert bindings[0].role == MEMBER

    def test_multiple_bindings_merge_projects(self) -> None:
        policy = RBACPolicy(
            bindings=[
                UserRoleBinding(
                    user_id="u1",
                    role=VIEWER,
                    scope=TeamScope("t1", frozenset({"p1"})),
                ),
                UserRoleBinding(
                    user_id="u1",
                    role=VIEWER,
                    scope=TeamScope("t2", frozenset({"p2"})),
                ),
            ]
        )
        assert policy.get_accessible_projects("u1") == ["p1", "p2"]

    def test_viewer_cannot_write(self) -> None:
        policy = RBACPolicy(bindings=[UserRoleBinding(user_id="u1", role=VIEWER)])
        assert not policy.check_permission("u1", Permission.WRITE)
