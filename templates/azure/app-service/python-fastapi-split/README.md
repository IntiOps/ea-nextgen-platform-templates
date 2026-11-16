# FastAPI on Azure Web App · separated CI/CD (draft)

Two Azure Pipelines definitions from one repository deliver the service; a third, queued by hand, removes it:

| Pipeline | File | Does | Never does |
| --- | --- | --- | --- |
| CI producer | `pipelines/azure-pipelines/ci.yml` | Tests, builds `app.zip` once with resolved dependencies, publishes it with `artifact.json` (SHA-256, commit, run id) and the delivery files | Deploy; hold a cloud connection |
| CD consumer | `pipelines/azure-pipelines/cd.yml` | Consumes one CI run through `resources.pipelines`, verifies the artifact, previews infrastructure per environment, waits for approval, applies and deploys the same zip, checks the revision is serving | Build; check out source; run on push |
| Gated cleanup | `pipelines/azure-pipelines/cleanup.yml` | Queued by hand with `confirm: delete <service>`: lists the resources tagged `managed_by=ea-nextgen-template` and `instance=<service>-<env>`, waits for the environment approval, deletes exactly that list (app before plan) | Run on a trigger; delete the resource group; touch untagged or `bind` resources |

Promotion order and each environment's Azure DevOps environment and service connection come from
the EA delivery topology (`parameters.environments`). Approvals and checks live on the Azure DevOps
environments. Infrastructure is previewed (`what-if`) and applied per environment; the application
package is the same bytes everywhere — App Service does not rebuild it (`SCM_DO_BUILD_DURING_DEPLOYMENT=false`).

Each environment has two stages: `plan_<env>` verifies the artifact and runs `what-if` without any
protected environment, then `promote_<env>` declares the Azure DevOps environment. Azure DevOps evaluates
approvals when a stage starts, so approvers see the preview first. `what-if` is a preview, not a saved
plan: Azure evaluates again at apply. `lockBehavior: sequential` needs an Exclusive Lock check on each
environment to serialise promotions.

A manual CD run must pass `expectedDigest`, the package digest EA recorded and a person approved.
Picking a CI run by hand is not an approval, and the default resource version is the latest run, so
without it the verifier refuses before any cloud step (`Build.Reason == Manual`).

## Resource groups and identity

Each environment deploys into an existing resource group named by `resourceGroup` in
`parameters.environments`. The platform team creates or selects that group; `main.bicep` is
resource-group scoped and creates only the plan and the web app inside it. Each environment's service
connection (workload identity federation, no secret) needs Contributor on its resource group alone.
New infrastructure and infrastructure already in place are the same operation: deploy into a given group.

| `infraMode` | Template owns | CD does | Extra per environment |
| --- | --- | --- | --- |
| `new` (default) | plan + web app | what-if, apply, deploy, smoke | — |
| `shared` | web app only | what-if, apply (app on the existing plan), deploy, smoke | `existingPlanId` |
| `bind` | nothing | verify the app exists, deploy, smoke; no infrastructure step | `appName` |

`shared` across resource groups is unverified: App Service may require the app and the plan in the same
resource group and region. Until a run proves otherwise, put the app's `resourceGroup` where the plan is.

## Cleanup and TTL report (P4-05)

`cleanup.yml` deletes only what the template owns: in each environment's resource group, the
resources tagged BOTH `managed_by=ea-nextgen-template` and `instance=<service>-<env>`. `list_<env>`
publishes that list without approval; `delete_<env>` is a deployment job on the environment, so the
approval comes after the list, and it refuses if the set changed. `bind` environments are skipped.
`operations/ttl_report.py` reports groups and resources whose `ea-ttl` tag has passed. Details and
commands: `operations/cleanup.md`. Contract tests: `tests/test_cleanup.py`, `tests/test_ttl_report.py`.

## AI agent guardrails (AI kit)

`AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `.github/copilot-instructions.md` and
`.eanextgen.d/rules/protected-paths.txt` come from `components/ai-kit` (byte-identical copies). They tell
coding agents how to work in the generated repository and keep them off the paths that judge them
(pipelines, infra, operations, `Dockerfile`, `.dockerignore`, the delivery contract test). `AGENTS.md` carries `{{ea.<key>}}` tokens the
platform renders. Enforcement is the Azure Repos policy: build validation with the CI pipeline and the
Platform Team as required reviewer on the protected paths.

## Artifact transport (ART-T1)

The package always travels as the native Azure Pipelines artifact, and CD always verifies that run's
`artifact.json`. An environment may additionally keep the package in **Azure Blob** or **Amazon S3**
(`delivery.artifact.transport` in `template.yaml`). Then EA publishes its transport tool to
`.ea/delivery/transport.py`, pinned by SHA-256 in both pipelines, and each environment carries
`artifactProvider`, `artifactDestinationJson`, `storageServiceConnection` (the runner identity, an
Azure DevOps service connection) and, for S3, `storageRegion`. CI uploads the verified zip under
organization/project/producer/run/SHA-256; CD downloads that exact key and checks the SHA-256 before
the verifier runs. There is no `latest`, no branch name and no storage key or SAS in these files.

The template's part: CD jobs use a managed Python (the image's system Python refuses `pip install`),
and `operations/transport-requirements.txt` is installed only where a transport is in use — in CI when
the tool is present, in CD per environment. Azure Artifacts feeds are not supported. No Blob or S3
transfer has been run against a real account.

Status: **draft**. Contract tests in `tests/test_split_delivery.py` pass locally and the Bicep compiles
without errors or warnings (`az bicep build`, Bicep CLI 0.47.16, 2026-09-25). No Azure run has been executed. `cloud_verified` stays false until a promoted artifact is observed.
