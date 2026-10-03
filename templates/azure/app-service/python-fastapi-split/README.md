# FastAPI on Azure Web App · separated CI/CD (draft)

Two Azure Pipelines definitions from one repository:

| Pipeline | File | Does | Never does |
| --- | --- | --- | --- |
| CI producer | `pipelines/azure-pipelines/ci.yml` | Tests, builds `app.zip` once with resolved dependencies, publishes it with `artifact.json` (SHA-256, commit, run id) and the delivery files | Deploy; hold a cloud connection |
| CD consumer | `pipelines/azure-pipelines/cd.yml` | Consumes one CI run through `resources.pipelines`, verifies the artifact, previews infrastructure per environment, waits for approval, applies and deploys the same zip, checks the revision is serving | Build; check out source; run on push |

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
