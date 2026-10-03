# ADR-0001 · Layered Orders domain

Status: accepted

## Context
Order rules (totals, status transitions, invariants) must be testable without a database or a web
framework, and survive a change of persistence.

## Decision
Each context is split into domain, application and infrastructure. Dependencies point inward. The
domain declares the ports it needs (`OrderRepository`); infrastructure implements them.

## Consequences
The domain is tested in memory. A persistence shortcut inside the aggregate (an active-record `save`)
breaks this decision, even when it works.
