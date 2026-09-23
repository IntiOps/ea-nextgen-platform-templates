# Catalog contracts

The application template schema 1.0 remains unchanged. Blueprints/components use separate JSON manifests and indexes. `tools/catalog.py validate` validates types, endpoints, references, digests and paths without running downloaded code. `schemas/metamodel-reference.json` is an authored snapshot of the platform catalog; workspace import must still validate against its active metamodel, scope and RBAC. These manifests are not accepted by the old application importer.
