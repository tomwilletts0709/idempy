# Changelog

All notable changes to idempy are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
idempy uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-04-05

Initial release.

### Added

**Core**
- `Core` class orchestrating the full idempotency lifecycle: `begin`, `complete`, `fail`, `replay`, `get_status`
- `begin()` accepts both `Request` dataclass and plain `dict` input
- Fingerprint computed as SHA-256 of the caller-supplied canonical value
- Configurable key prefix, datetime class, and store backend via `settings` dict

**Storage**
- `BaseStore` abstract base class — implement to provide any custom backend
- `MemoryStore` — thread-safe, in-process store with 30-day lazy TTL expiry
- `RedisStore` — distributed store backed by Redis hashes; uses `SET NX` for atomic creation, native Redis TTL, and optional key namespacing via `key_prefix`
- `Stores` registry — named backends with automatic default selection

**Models**
- `Request`, `IdempotencyKey`, `IdempotencyRecord` dataclasses
- Result types: `BeginResult`, `CompleteResult`, `FailResult`, `ReplayResult`, `GetStatusResult`, `DeleteResult`
- Enums: `BeginAction`, `ReplayAction`, `Status`, `State`, `CompleteAction`, `FailAction`, `GetStatusAction`, `DeleteAction`

**Errors**
- `IdempotencyError` base exception
- `IdempotencyKeyNotFoundError`, `IdempotencyKeyAlreadyExistsError`, `IdempotencyKeyInvalidError`

**Validation**
- `ValidatedField` descriptor — cast-and-validate field assignments
- Built-in validators: `non_empty`, `min_value`

**Framework middleware**
- `idempy.flask_middleware.IdemMiddleware` — Flask extension (`init_app` pattern)
- `idempy.fastapi_middleware.IdemMiddleware` — Starlette/FastAPI `BaseHTTPMiddleware`
- `idempy.django_middleware.IdemMiddleware` — Django `MIDDLEWARE`-compatible class
- All three: automatic fingerprint computation, replay/conflict/pass-through logic, configurable header name and safe methods

**Logging**
- `NullHandler` registered on the `idempy` logger — no output unless the application configures handlers
- `configure_logging()` helper for development and CLI use
- Structured log calls at key lifecycle events in `Core` (`begin`, `complete`, `fail`)

**Packaging**
- Optional dependency extras: `redis`, `flask`, `fastapi`, `django`, `all`
- `pyproject.toml` metadata: description, author, license (MIT), classifiers, project URLs

**Tests**
- 70 tests across unit, integration, and framework adapter layers
- `fakeredis` used for Redis store tests — no live instance required
