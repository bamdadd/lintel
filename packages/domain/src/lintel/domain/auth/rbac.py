"""Role-based access control domain model.

Provides Permission, Role, TeamScope, and RBACPolicy for enforcing
team-scoped authorization across the platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Permission(StrEnum):
    """Fine-grained permission levels."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SUPERUSER = "superuser"


@dataclass(frozen=True)
class Role:
    """Named role with a set of permissions."""

    name: str
    permissions: frozenset[Permission]

    def has_permission(self, permission: Permission) -> bool:
        """Return whether this role includes the given permission."""
        return permission in self.permissions


# ------------------------------------------------------------------
# Default roles
# ------------------------------------------------------------------

VIEWER = Role(name="viewer", permissions=frozenset({Permission.READ}))
MEMBER = Role(name="member", permissions=frozenset({Permission.READ, Permission.WRITE}))
ADMIN = Role(
    name="admin",
    permissions=frozenset({Permission.READ, Permission.WRITE, Permission.ADMIN}),
)
SUPERUSER = Role(
    name="superuser",
    permissions=frozenset(
        {Permission.READ, Permission.WRITE, Permission.ADMIN, Permission.SUPERUSER}
    ),
)

DEFAULT_ROLES: dict[str, Role] = {r.name: r for r in (VIEWER, MEMBER, ADMIN, SUPERUSER)}


@dataclass(frozen=True)
class TeamScope:
    """Constrains a user's access to a specific team and its projects."""

    team_id: str
    allowed_project_ids: frozenset[str] = field(default_factory=frozenset)

    def includes_project(self, project_id: str) -> bool:
        """Return whether this scope grants access to the given project.

        An empty ``allowed_project_ids`` means *all* projects in the team.
        """
        if not self.allowed_project_ids:
            return True
        return project_id in self.allowed_project_ids


@dataclass(frozen=True)
class UserRoleBinding:
    """Binds a user to a role, optionally scoped to a team."""

    user_id: str
    role: Role
    scope: TeamScope | None = None


class RBACPolicy:
    """Evaluates access-control checks against a set of user-role bindings."""

    def __init__(self, bindings: list[UserRoleBinding] | None = None) -> None:
        self._bindings: list[UserRoleBinding] = list(bindings or [])

    # -- mutators --------------------------------------------------

    def add_binding(self, binding: UserRoleBinding) -> None:
        """Register a user-role binding."""
        self._bindings.append(binding)

    # -- queries ---------------------------------------------------

    def check_permission(
        self,
        user_id: str,
        action: Permission,
        resource_project_id: str | None = None,
    ) -> bool:
        """Return whether *user_id* may perform *action*.

        When *resource_project_id* is provided the check also verifies that at
        least one of the user's scopes covers that project.
        """
        for b in self._bindings:
            if b.user_id != user_id:
                continue
            if not b.role.has_permission(action):
                continue
            # Superuser bypasses scope checks
            if b.role.has_permission(Permission.SUPERUSER):
                return True
            if (
                resource_project_id is not None
                and b.scope is not None
                and not b.scope.includes_project(resource_project_id)
            ):
                continue
            return True
        return False

    def get_accessible_projects(self, user_id: str) -> list[str]:
        """Return deduplicated project IDs accessible to *user_id*.

        A binding with an empty ``allowed_project_ids`` means "all projects in
        that team", represented by an empty list return value when *any* such
        binding exists.
        """
        project_ids: set[str] = set()
        for b in self._bindings:
            if b.user_id != user_id:
                continue
            if b.scope is None or not b.scope.allowed_project_ids:
                # Unrestricted — caller should treat empty list as "all"
                return []
            project_ids.update(b.scope.allowed_project_ids)
        return sorted(project_ids)

    def get_bindings_for_user(self, user_id: str) -> list[UserRoleBinding]:
        """Return all bindings for a given user."""
        return [b for b in self._bindings if b.user_id == user_id]
