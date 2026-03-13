# REQ-033: Authentication, Multi-User & Multi-Team Access Control

**Status:** Proposed
**Priority:** High
**Category:** Security / Multi-Tenancy

## Problem

Lintel currently has no authentication or authorization. All users see all assets (projects, pipelines, work items, conversations, etc.). There is no concept of teams owning resources or users having scoped visibility. For any real team deployment, Lintel needs user login, team-based resource ownership, and role-based access control.

## Goals

1. Users can sign up / log in and have their own identity.
2. Teams group users; assets (projects, pipelines, jobs, etc.) belong to teams.
3. Users only see assets belonging to their team(s).
4. A **superuser** role can see and manage everything across all teams.
5. The auth provider is **pluggable** — self-hosted open-source for local/on-prem, or managed SaaS for convenience.

## Auth Provider Strategy

Lintel must support swappable auth backends behind a `Protocol` interface. Three tiers:

### Tier 1: Built-in Simple Auth (default, local dev)

A minimal, self-managed auth system bundled with Lintel:

- Username/password with bcrypt hashing
- JWT token issuance and validation
- Stored in the existing PostgreSQL database
- No external dependencies — works out of the box for local dev and small self-hosted deployments
- **Not recommended for production** without TLS and proper secret management

### Tier 2: Keycloak (self-hosted, production)

For teams that need a full-featured, open-source identity provider they control:

- OIDC/OAuth2 compliant
- User federation (LDAP, Active Directory)
- Fine-grained roles and permissions
- Runs as a Docker container alongside Lintel
- Well-suited for on-prem / air-gapped environments

### Tier 3: Clerk (managed SaaS)

For teams that prefer a managed solution with minimal setup:

- Hosted authentication with generous free tier (https://clerk.com/pricing)
- Pre-built UI components, social login, MFA
- Webhook-based user sync
- Pairs well with Supabase for persistence if needed (https://supabase.com/pricing)
- Fastest path to production-grade auth

### Provider Interface

```python
class AuthProvider(Protocol):
    """Pluggable authentication provider."""

    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """Validate credentials, return user identity + tokens."""
        ...

    async def validate_token(self, token: str) -> TokenClaims:
        """Validate and decode a JWT/session token."""
        ...

    async def get_user_info(self, user_id: str) -> UserInfo:
        """Fetch user profile and team memberships."""
        ...

    async def refresh_token(self, refresh_token: str) -> AuthResult:
        """Refresh an expired access token."""
        ...
```

Configuration selects the provider:

```yaml
# config.yaml or env vars
auth:
  provider: "builtin"  # "builtin" | "keycloak" | "clerk"
  builtin:
    jwt_secret: "..."
    token_expiry_minutes: 60
  keycloak:
    server_url: "http://keycloak:8080"
    realm: "lintel"
    client_id: "lintel-app"
    client_secret: "..."
  clerk:
    api_key: "sk_..."
    frontend_api: "clerk.your-domain.com"
```

## Requirements

### Authentication

1. **Login/logout:** Users authenticate via the selected provider and receive a JWT access token.
2. **Token validation:** All API and MCP requests include a Bearer token. FastAPI middleware validates tokens via the configured provider.
3. **Session management:** Access tokens expire (configurable, default 1 hour). Refresh tokens allow re-authentication without re-entering credentials.
4. **Provider switching:** Changing the auth provider requires only configuration changes, not code changes. User records are synced/migrated via a CLI tool.

### Users & Teams

5. **User model:** Each user has an `id`, `email`, `display_name`, `role` (member | admin | superuser), and belongs to one or more teams.
6. **Team model:** Teams have an `id`, `name`, and a list of members with per-team roles (member | admin).
7. **Team ownership:** Every project, pipeline, job, work item, conversation, and other asset has a `team_id`. Assets without a `team_id` are visible only to superusers.

### Visibility & Authorization

8. **Team-scoped visibility:** Users see only assets belonging to their team(s). API queries are automatically filtered by team membership.
9. **Team admin:** Can manage team membership, create/delete projects within the team.
10. **Superuser:** Sees all assets across all teams. Can manage users, teams, and system settings. At least one superuser must exist.
11. **MCP tool scoping:** MCP tool calls include the authenticated user's context. Tools respect team-scoped visibility.

### Data Model

```python
@dataclass(frozen=True)
class User:
    user_id: str
    email: str
    display_name: str
    role: str  # "member" | "admin" | "superuser"
    team_ids: list[str]
    auth_provider: str  # which provider manages this user
    external_id: str  # ID in the external auth provider
    created_at: datetime
    updated_at: datetime

@dataclass(frozen=True)
class Team:
    team_id: str
    name: str
    description: str
    members: list[TeamMember]
    created_at: datetime
    updated_at: datetime

@dataclass(frozen=True)
class TeamMember:
    user_id: str
    role: str  # "member" | "admin"
    joined_at: datetime

@dataclass(frozen=True)
class AuthCredentials:
    email: str
    password: str | None = None  # for builtin
    oauth_code: str | None = None  # for OIDC flows

@dataclass(frozen=True)
class AuthResult:
    user_id: str
    access_token: str
    refresh_token: str
    expires_in: int  # seconds

@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    email: str
    role: str
    team_ids: list[str]
    exp: int  # expiry timestamp
```

### API & MCP Tools

**Auth endpoints:**
- `POST /api/v1/auth/login` — authenticate
- `POST /api/v1/auth/refresh` — refresh token
- `POST /api/v1/auth/logout` — invalidate session
- `GET /api/v1/auth/me` — current user info

**User management (admin/superuser):**
- `users_create_user`, `users_get_user`, `users_list_users`, `users_update_user`, `users_delete_user`

**Team management:**
- `teams_create_team`, `teams_get_team`, `teams_list_teams`, `teams_update_team`, `teams_delete_team`
- `teams_add_member`, `teams_remove_member`

### Implementation Sketch

```
src/lintel/
├── contracts/auth.py              # User, Team, AuthProvider Protocol, dataclasses
├── domain/auth.py                 # Authorization logic, permission checks
├── infrastructure/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── builtin.py             # Simple JWT auth with PostgreSQL user store
│   │   ├── keycloak.py            # Keycloak OIDC integration
│   │   └── clerk.py               # Clerk SDK integration
│   └── mcp/tools/users.py         # User/team MCP tool handlers
├── api/
│   ├── routes/auth.py             # Login/logout/refresh endpoints
│   ├── middleware/auth.py         # Token validation middleware
│   └── dependencies/auth.py      # FastAPI dependency for current user
└── projections/users.py           # Read-side user/team projections
```

### Migration Path

1. **Phase 1:** Ship with builtin auth as default. No breaking changes — unauthenticated access still works when `auth.provider = "none"`.
2. **Phase 2:** Add Keycloak integration for self-hosted production deployments.
3. **Phase 3:** Add Clerk integration for managed SaaS option.
4. **Phase 4:** Add `team_id` to all existing entities. Migration script backfills a "default" team.

### Dependencies

- Existing `users` and `teams` MCP tools/API routes (extend with auth)
- FastAPI middleware pipeline
- PostgreSQL for builtin user store

### Open Questions

1. Should we support social login (GitHub, Google) in the builtin provider, or leave that to Keycloak/Clerk?
2. Should API keys (for CI/automation) be a separate auth mechanism alongside user tokens?
3. How should MCP SSE connections authenticate — token in query param or initial handshake message?
4. Should Supabase be considered as a persistence backend alongside PostgreSQL, or keep it as a Clerk companion only?
