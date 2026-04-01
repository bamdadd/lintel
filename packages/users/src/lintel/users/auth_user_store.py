"""Postgres-backed store for authenticated users (auth_users table)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lintel.contracts.auth import AuthUser, UserRole

if TYPE_CHECKING:
    from uuid import UUID

    import asyncpg


class AuthUserStore:
    """CRUD operations for the ``auth_users`` Postgres table."""

    def __init__(self, pool: asyncpg.Pool) -> None:  # type: ignore[type-arg]
        self._pool = pool

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_user(row: asyncpg.Record) -> AuthUser:  # type: ignore[type-arg]
        return AuthUser(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            role=UserRole(row["role"]),
            hashed_password=row["hashed_password"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        email: str,
        display_name: str,
        role: str,
        hashed_password: str,
    ) -> AuthUser:
        """Insert a new user and return the created ``AuthUser``."""
        sql = """
            INSERT INTO auth_users (email, display_name, role, hashed_password)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(sql, email, display_name, role, hashed_password)
        return self._row_to_user(row)

    async def get(self, user_id: UUID) -> AuthUser | None:
        """Fetch a user by primary key."""
        sql = "SELECT * FROM auth_users WHERE id = $1"
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(sql, user_id)
        return self._row_to_user(row) if row else None

    async def get_by_email(self, email: str) -> AuthUser | None:
        """Fetch a user by email address."""
        sql = "SELECT * FROM auth_users WHERE email = $1"
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(sql, email)
        return self._row_to_user(row) if row else None

    async def list_all(self) -> list[AuthUser]:
        """Return all users ordered by creation date."""
        sql = "SELECT * FROM auth_users ORDER BY created_at"
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            rows = await conn.fetch(sql)
        return [self._row_to_user(r) for r in rows]

    async def update(self, user_id: UUID, **fields: str) -> AuthUser | None:
        """Update specific fields on a user. Returns the updated user or None."""
        allowed = {"email", "display_name", "role", "hashed_password"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return await self.get(user_id)

        set_clauses = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
        set_clauses += ", updated_at = now()"
        sql = f"UPDATE auth_users SET {set_clauses} WHERE id = $1 RETURNING *"
        values: list[Any] = [user_id, *updates.values()]
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(sql, *values)
        return self._row_to_user(row) if row else None

    async def delete(self, user_id: UUID) -> bool:
        """Delete a user. Returns True if a row was removed."""
        sql = "DELETE FROM auth_users WHERE id = $1"
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(sql, user_id)
        return result == "DELETE 1"
