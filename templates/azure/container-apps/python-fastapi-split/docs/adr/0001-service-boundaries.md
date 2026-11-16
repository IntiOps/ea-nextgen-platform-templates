# ADR-0001 · Layered service boundaries

- Status: Accepted (comes with the template; change it with a new ADR, not an edit)

## Context

AI agents and people both change this service. Without explicit boundaries, framework and cloud code
spreads into business rules and every change gets harder to review.

## Decision

`app/service` has three layers, checked by `tools/check_architecture.py` on every edit and in CI:

| Layer | May import | Must not import |
|---|---|---|
| `domain` | the standard library, other domain modules | application, infrastructure, frameworks, cloud SDKs (ARCH-001) |
| `application` | domain, its own ports (`ports.py`) | infrastructure, frameworks, cloud SDKs (ARCH-002) |
| `infrastructure` | anything | — |

Use cases depend on ports (Protocols). Adapters in `infrastructure` implement them. `app/main.py` is the
only entrypoint (ARCH-003).

## Consequences

- Business rules are testable without FastAPI, Azure or a network (see `tests/unit`).
- A new external dependency means a new port and an adapter, which makes it visible in review.
