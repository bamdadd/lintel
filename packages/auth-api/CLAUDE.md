# lintel-auth-api

Builtin JWT authentication API package (REQ-033a).

## Structure

- `src/lintel/auth_api/routes.py` — Login endpoint, token refresh routes
- `src/lintel/auth_api/middleware.py` — FastAPI middleware for JWT request authentication
- `src/lintel/auth_api/access_log.py` — API access logging middleware (structured JSON logs with user identity, timing, IP)
- `src/lintel/auth_api/store.py` — Auth store interface

Domain logic (JWT creation/validation, password hashing) lives in `packages/domain/src/lintel/domain/auth/`.

## Testing

```bash
make test-auth-api
```
