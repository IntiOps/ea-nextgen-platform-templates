# Catalog contracts

The application template schema accepts 1.0, 1.1 and 1.2. Version 1.1 adds explicit `materializes` declarations; version 1.2 adds a variant's `delivery` (separated CI/CD: pipelines, artifact, transport, presets, and the optional `cleanup_pipeline`, the gated cleanup EA generates with the CD's environments chain). Existing 1.0 and 1.1 manifests retain their original digest. Blueprints/components use separate JSON manifests and indexes. `tools/catalog.py validate` validates types, endpoints, references, digests and paths without running downloaded code. `schemas/metamodel-reference.json` is an authored snapshot of the platform catalog; workspace import must still validate against its active metamodel, scope and RBAC. These manifests are not accepted by the old application importer. Variant `runtime` `azure_container_apps` (Azure Container Apps, ecosystem `container-apps`) was added for `fastapi-azure-containerapps-split`; the platform contract must accept it before that package imports.

## Rendering contract v1

How a package becomes a service repository. `tools/render_local.py` is the reference implementation;
`tests/fixtures/render-contract.json` is the shared fixture the platform renderer must also pass.

1. Copy every file of the package at a full commit SHA, except caches.
2. Replace `{{ea.<key>}}` in UTF-8 text files. Keys: `service`, `location`, `package_id`, `package_version`,
   `package_commit`, `architecture_name`, `architecture_version`, `architecture_digest`, `node_id`.
   An unknown key or a token left after rendering is an error. Tokens never appear in `template.yaml`
   (the manifest stays valid for import) and never collide with Azure Pipelines `${{ }}` expressions.
3. For a 1.2 split delivery, set pipeline defaults from the naming preset: CI `artifactName`; CD `service`,
   `artifactName`, the CI resource `source`, and the environment chain (`name`, `azureEnvironment`,
   `serviceConnection`, `purpose`, `location`, `resourceGroup`, `infraMode`, `existingPlanId`, `appName`,
   `artifactProvider`). `template.yaml` keeps its text; only the delivery artifact name changes.
4. Write `.ea/package.json` with the package id, version, commit and the names used.

Rendering never executes package code.
