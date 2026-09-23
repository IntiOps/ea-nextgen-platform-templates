# Architecture and reusable source catalog

The original `catalog/index.yaml` and application schema 1.0 are unchanged.
New catalogs are intentionally separate:

- `catalog/blueprints.json`: twelve architecture models, never cloud deployments.
- `catalog/components.json`: three source components with SHA-256 file pins.
- `catalog/demos.json`: three compositions with pinned component manifests.

```sh
python tools/catalog.py validate
python tools/catalog.py list
python tools/catalog.py export --blueprint web-api-data > /tmp/web-api-data.json
```

Export is a proposed model, not a write to EA NextGen. Platform import must validate
active metamodel and workspace permissions and map local keys to node identities.
The platform application importer does not yet understand these new catalogs.
No command here downloads dependencies, executes package contents or creates resources.
Pin the whole repository to a full Git commit when publishing/importing; internal
file digests bind references within that commit. This validator is for authored
repository content, not a replacement for the platform's untrusted archive importer.

## Functional local demos

Follow `components/application/python-request-service/README.md` for request CRUD
and asynchronous work. SQLite persists locally. The explicit `--worker-once` command
processes one job. Cloud adapters remain pending and are identified in bindings;
the worker does not claim SQS/Service Bus, distributed delivery or automatic retries.

## Architecture coverage

Enterprise capability map; web API; web/data; queue/worker; serverless HTTP;
existing Kubernetes; scheduled batch; modular application; event integration;
RAG; read-only-tools agent; observable distributed application.

Read `gaps` before using a blueprint. RAG corpus/evaluation relationships and tool
permissions require further metamodel/runtime support. Open decisions are not
approvals. No new entry is certified for production or cloud execution.

## Promotion

Proposed model → metamodel validated → source tested → importable binding → sandbox
evidence. These are separate dimensions, not interchangeable status claims.
Azure Bicep/Terraform and AWS CDK Python/TypeScript/Terraform plus both CI providers
are target variants, not an implied Cartesian product of delivered support.

Schemas and this read-only CLI are an additive catalog contract. Historical
application manifests and their digests must not be rewritten to accommodate it.

## Quality validation catalog

`catalog/validation.json` is an additive index of pinned quality components and
three source-validation bindings (App Service, Lambda and the local request service).
It does not extend the old application manifest. Run `python tools/validate_quality_catalog.py`.
See `components/validation/README.md` for evidence, CI, trust boundaries and pending
live scanner/platform integration. A source CI pass is not cloud certification.
