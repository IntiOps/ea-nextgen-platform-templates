# Implementation status

## Source and validation matrix

| Cloud / ecosystem | IaC | Local evidence | Deploy workflow |
|---|---|---|---|
| Azure / App Service | Terraform | fmt + validate + application tests | Existing GitHub Actions candidate; cloud execution not certified |
| Azure / App Service | Bicep | Bicep 0.40.2 compile | Pending reviewed what-if/apply binding |
| AWS / Lambda | Terraform | fmt + init without backend + validate | Pending |
| AWS / Lambda | CDK Python | CloudFormation synthesis with fictitious account | Pending |
| AWS / Lambda | CDK TypeScript | TypeScript compile + CloudFormation synthesis | Pending |

The native GitHub Actions and Azure Pipelines files validate sources. This does not
mean all deployment variants or Azure DevOps service connections are configured.
Only the Azure/Terraform/GitHub candidate is currently listed by the import manifest.
Additional sources intentionally stay outside deployable variants until plan/cost,
approval, apply, health and cleanup contracts are implemented and verified.

## Implemented foundation

- Cloud/ecosystem/application directory hierarchy.
- Immutable import from a public repository through the platform importer.
- Production App Service Premium/zone redundancy/two instances, Lambda managed
  multi-zone runtime, parameterized log retention; explicit environment purpose.
- Validated timezone/DST schedules, TTL policy, production outage prohibition.
- Public retail pricing adapters for Linux App Service and standard x86 Lambda.
- Compute estimate with evidence and missing-cost blockers; App Service bills while stopped.
- Pinned provider/npm/Python CDK dependencies; no credentials or state in source.

## Required before an end-to-end deployment release

1. Version the template contract to represent explicit CDK languages and immutable
   shared component pins without changing historical manifest digests.
2. Expose profile/lifecycle choices in workspace/environment APIs and UI; persist
   with additive migrations and bind their digest to approvals.
3. Complete native plan/apply/health/cleanup adapters for both CI systems. Azure
   DevOps organization/project/repository/service connection/environment remain
   distinct from GitHub repository/workflow/environment.
4. Price logs, transfer and backend storage from the plan and usage assumptions;
   enforce completeness, budget and evidence freshness before approval/apply.
5. Add an audited, idempotent scheduler bound to an approved resource manifest.
   No subscription-wide deletion and no expiry/scheduled outages for production.
6. Configure real CI identities, protected environments, state/evidence stores,
   then approve a sandbox budget and lifetime before cloud execution.

No cloud resources were created during this source-validation delivery.

## Architecture catalog expansion (2026-09-24)

Twelve blueprint manifests, three content-pinned components, and three demo
compositions now have a read-only list/export/validation CLI. Request persistence
and local transactional queue behavior have functional tests. Both native CI
validation files run the catalog check. New cloud queue bindings are design-only.
Platform UI/import integration, managed data/queue adapters and cloud execution
remain pending; the existing application catalog is unchanged.

## Quality foundation (2026-09-24)

Delivered: profile/evidence contract, fixed local suites, bounded JUnit parser,
context/freshness checks, offline Sonar/ZAP assessment, and native source-CI report
publication. `catalog/validation.json` binds App Service, Lambda and request-service
sources without changing their historical application manifests.

Pending: authenticated provider retrieval, live scanners, SCA/secrets/IaC/image
security checks, postdeploy operational tests, performance/AI evaluators, platform
policy inheritance and evidence admission. All generated evidence explicitly denies
cloud deployment authorization. The source pipeline does not modify cloud credentials.
