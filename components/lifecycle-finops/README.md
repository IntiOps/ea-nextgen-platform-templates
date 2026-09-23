# Lifecycle and FinOps contract

`runtime_policy.py` validates cloud/IaC/CI/purpose, timezone-aware working hours,
expiry, production 24/7/HA, resource pricing and budget. `profiles.json` lists sizing
recommendations; region/zone support must still be verified before apply.

`estimate.py --intent intent.json --ends-at 2026-10-01T00:00:00Z --output cost.json`
fetches public Azure/AWS compute retail prices without cloud credentials. Lambda
also requires requests and GB-seconds for the estimate period. Install the pinned
requirements first. Exit 2 means the report exists but is incomplete/over budget.
It intentionally cannot authorize apply until storage, logs and network coverage
and the signed plan/approval binding are implemented. No unknown price becomes zero.

App Service plan hours remain billable when the app is stopped. An advisory expiry
also does not end billing. Destroy-based estimates assume cleanup succeeds; they are
not a spending cap. AWS rates use the first on-demand x86 tier without free-tier or
volume discounts. This is a conservative estimate, not an invoice.

This component validates policy; it does not run a scheduler or destroy resources.
A governed scheduler and immutable resource ownership manifest remain required.
Importing a package never executes these files.
