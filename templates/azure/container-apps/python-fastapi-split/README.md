# FastAPI on Azure Container Apps · separated CI/CD (draft)

Same layered FastAPI service and AI kit as `templates/azure/app-service/python-fastapi-split`. This one
ships as a container image to Azure Container Apps. Two Azure Pipelines definitions in one repository deliver it, and a third, queued by hand, removes it:

| Pipeline | File | Does | Never does |
| --- | --- | --- | --- |
| CI producer | `pipelines/azure-pipelines/ci.yml` | Tests, runs the guardrail, builds the image **once** (`operations/package_image.py`), saves it as `image.tar.gz` with `artifact.json` (SHA-256, image id, base image digest, commit, run id), publishes the delivery files | Deploy; log in to a registry; hold a cloud connection |
| CD consumer | `pipelines/azure-pipelines/cd.yml` | Consumes one CI run through `resources.pipelines`, verifies the artifact, previews infrastructure per environment, waits for approval, loads the image, pushes it to that environment's registry, deploys it **by digest**, checks `/health` reports the CI commit | Build; check out source; run on push; deploy a tag |
| Gated cleanup | `pipelines/azure-pipelines/cleanup.yml` | Queued by hand with `confirm: delete <service>`: lists the resources tagged `managed_by=ea-nextgen-template` and `instance=<service>-<env>`, waits for the environment approval, deletes exactly that list (dependents first) | Run on a trigger; delete the resource group; touch untagged, shared or `bind` resources |

Each environment has two stages. `plan_<env>` verifies the artifact, then runs `what-if`, or in `bind`
mode checks that the existing app exists and pulls from the registry. It uses no protected environment.
`promote_<env>` declares the Azure DevOps environment, so its approval is evaluated after the preview. It then:

1. re-verifies the tarball's SHA-256 against `artifact.json` and the CI run, before any cloud step;
2. runs `docker load` and checks the loaded image id is the one CI recorded;
3. runs `az acr login` through the environment's service connection (no password), pushes the image as
   `<registry>/<artifactName>:<commit>-<run id>`, and reads the registry digest
   (`operations/image_reference.py`);
4. deploys `<registry>/<artifactName>@sha256:…`: `az deployment group create` with `image=` in `new` and
   `shared`, `az containerapp update --image` in `bind`. Then it reads back what the app runs and fails
   if that is not the digest;
5. runs `tests/smoke.py`: `/health` must report the CI commit.

A manual CD run must pass `expectedDigest` (the tarball digest EA approved). Without it the verifier
refuses before any cloud step. `what-if` previews the unique tag, because the digest only exists once
promote has pushed the image. Promote deploys the digest.

## Modes per environment (`infraMode`)

| `infraMode` | Template owns | CD does | Extra keys |
| --- | --- | --- | --- |
| `new` (default) | Log Analytics workspace + Container Apps managed environment (Consumption) + container app | what-if, push, apply with the digest, smoke | — |
| `shared` | container app only | what-if, push, apply (app joins the existing environment), smoke | `existingEnvironmentId` (may be in another resource group) |
| `bind` | nothing | check app and registry, push, `az containerapp update --image <digest>`, smoke; no IaC | `appName` (in `resourceGroup`) |

Every environment also sets `resourceGroup`, `registry` (login server of its existing ACR) and
optionally `registryIdentityId`. The container app has external ingress on port 8000, HTTPS only. Its
minimum replicas are 0 in `development`/`poc` (scale to zero, so the first request has a cold start),
1 in `staging` and 2 in `production`. Probes check `/health` (liveness) and `/ready` (readiness). Tags:
`managed_by=ea-nextgen-template`, `instance`, `owner_id`, `purpose`, `revision`.

## Prerequisites (per environment, owned by the platform team)

- **Resource group** that exists already. The service connection (workload identity federation) has
  **Contributor on that group only**. `main.bicep` is resource-group scoped.
- **Azure DevOps environment** with approvals and checks, plus an Exclusive Lock check if promotions
  must be serialised (`lockBehavior: sequential`).
- **Azure Container Registry**, platform-owned, named by `registry`. The service connection needs
  **AcrPush** on it.
- **AcrPull for the app's identity.** Contributor cannot create role assignments, and the registry is
  not in the app's resource group, so `main.bicep` grants nothing. Choose one:
  - **Recommended:** a platform-owned user-assigned identity, already granted AcrPull, in the app's
    resource group (so Contributor may assign it). Pass its id as `registryIdentityId`. The first
    deployment can pull.
  - Leave `registryIdentityId` empty and the app uses its system-assigned identity. That identity does
    not exist until the app does, so the first `new`/`shared` deployment cannot pull. The apply step
    prints `principal_id`. The platform team grants it AcrPull, then you re-run the promote stage.
- **`shared`:** the service connection needs `Microsoft.App/managedEnvironments/join/action` on the
  shared environment. `location` must be that environment's region.
- **`bind`:** the existing app must have a single container and already pull from `registry` with a
  managed identity (plan fails otherwise). The service connection needs write access to the app.
  The agent installs the `containerapp` Azure CLI extension at run time.

## Image build: what is and is not deterministic

- **Deterministic:** the build context (`app/`, `Dockerfile`, `.dockerignore`, `build-info.json`) has
  fixed modes and timestamps. The base image is pinned to the digest pulled at build time and recorded
  as `base_image`. The gzip wrapper has no timestamp. So the tarball digest depends only on what
  `docker save` produced.
- **Not deterministic:** the image itself. `pip install` resolves transitive dependencies at build
  time, and files and layers carry build-time timestamps. `SOURCE_DATE_EPOCH` (commit time) only fixes
  what BuildKit controls. Rebuilding the same commit gives a different image id.
- **Guaranteed:** CI builds once and records the SHA-256 and image id. Every environment verifies both,
  receives exactly those bytes, and runs them by registry digest.

The image is built for `linux/amd64` (what Container Apps runs). It runs `python -m uvicorn main:app`
on port 8000 as uid 10001. Local build: `docker build -t service .` (revision then reports `development`).

## Artifact transport

The image travels only as the native Azure Pipelines artifact. `template.yaml` declares no `transport`:
Azure Blob and S3 copies are not implemented for images.

## Cleanup and TTL report (P4-05)

`pipelines/azure-pipelines/cleanup.yml` never runs on its own. Queue it by hand with the `cd.yml`
environments and `confirm` set to exactly `delete <service>`. In each environment's resource group it
deletes only the resources tagged BOTH `managed_by=ea-nextgen-template` and `instance=<service>-<env>`.
`list_<env>` publishes that list without approval. `delete_<env>` is a deployment job on the
environment, so the approval comes after the list. It refuses if the set changed, then deletes the
container app, then the managed environment, then Log Analytics. `bind` environments are skipped. The
resource group, shared environments and registry images are never touched.
`operations/ttl_report.py` reports groups and resources whose `ea-ttl` tag has passed. Details:
`operations/cleanup.md`. Contract tests: `tests/test_cleanup.py`, `tests/test_ttl_report.py`.

## AI agent guardrails

The AI kit files are byte-identical copies of `components/ai-kit` 0.3.0 (see the App Service split
README). `AGENTS.md` is runtime-neutral, and `Dockerfile` and `.dockerignore` are protected paths.

## Advisory AI review of pull requests (opt-in, P5-04)

**Off by default, because it sends source code to an external API.** With the pipeline variable
`AI_REVIEW_ENABLED` set to `true`, a pull request build runs `tools/ai_review.py` right after the
guardrail (step from `pipelines/azure-pipelines/ai-review-steps.yml`, an AI kit file). It sends the diff
against the target branch, `AGENTS.md`, the review prompt and the guardrail result to the Claude API
(Anthropic; default model `claude-sonnet-5-5`, override with `AI_REVIEW_MODEL`) and posts the answer as
one comment thread on the pull request, updated in place on every run.

To enable it: add `ANTHROPIC_API_KEY` as a **secret** pipeline variable, set `AI_REVIEW_ENABLED` to
`true`, and give the project's build service identity "Contribute to pull requests" on the repository.
Files that look like secrets (`.env*`, keys, certificates, credential patterns) are withheld and listed
by path only; a diff over `AI_REVIEW_MAX_DIFF_BYTES` (default 150000) is skipped, not truncated. It is
advisory: the step never fails the build (`continueOnError`, exit 0) and the thread is created closed so
comment-resolution policies ignore it. `evidence/ai-review.json` records what was sent (paths, sizes,
model, request id), never code. Contract tests: `tests/test_ai_review.py` (fakes only). No real API call
or Azure DevOps run has been made with it yet.

## Status

**Draft, `cloud_verified: false`.** Verified locally on 2026-11-17:
- the contract, unit and API tests in `tests/` pass;
- `az bicep build` (Bicep CLI 0.47.16) compiles `main.bicep` with no errors or warnings;
- `package_image.py` built a real image; `docker load` plus the verifier accepted it; the container
  served `/health` with the build's commit as uid 10001;
- a push to a local registry resolved the digest through `image_reference.py`.

**Unverified (no Azure run yet):**
- `az acr login`/push with a service connection, and system-assigned versus user-assigned registry pull;
- first-deployment behaviour without AcrPull;
- `shared` across resource groups with only the join permission;
- `bind` through `az containerapp update`;
- cold start against the smoke test's 5-minute window.
