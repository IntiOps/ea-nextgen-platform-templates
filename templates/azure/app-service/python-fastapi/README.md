# FastAPI + Azure Web App — candidate 0.4.0

Runnable implementation, not yet certified against a real Azure subscription. It remains
absent from the published catalog until plan, deployment, health and cleanup have cloud evidence.

The package creates a dedicated resource group, Linux B1 service plan and Python 3.12 Web App.
Names and Terraform state are separated by immutable GitHub repository ID and instance name.
The HTTPS `/health` response must report the exact source commit that produced the zip.
No database, customer data, custom DNS, private networking or production hardening is included.

## GitHub setup

Keep this package at `templates/azure/app-service/python-fastapi` and copy its pipeline to
`.github/workflows/fastapi-azure-webapp.yml` (already supplied in the sibling repository).
The workflow runs from `main` only. Protect that branch with review requirements.
Actions are pinned to commits; Terraform/provider versions and provider checksums are fixed.

Create these GitHub Environments before running:

| Environment | Purpose | Azure permissions |
| --- | --- | --- |
| demo-plan | Read resources and build a saved plan | Subscription read; Blob Data Contributor for state locking |
| demo-deploy | Apply plan and deploy zip | Rights to create/update the demo resource group and its Web resources; backend access |
| demo-cleanup | Destroy only demo-owned resources | Delete rights for that instance; backend access |

On `demo-deploy` and `demo-cleanup`, require reviewers and prevent self-review. The workflow
reads these rules and refuses mutation runs if they are missing. Some GitHub subscription
plans do not support required reviewers for private repositories; use a plan/repository
configuration supporting these controls. No approval bypass is implemented.

Configure an Entra federated credential for each used identity with audience
`api://AzureADTokenExchange` and subject `repo:OWNER/REPOSITORY:environment:ENVIRONMENT`.
Pre-register Microsoft.Web. Provision the state backend first (Azure Blob by default; S3 or HCP
Terraform when EA's environment says so); this demo never creates or destroys it.

Set the following non-secret repository/environment variables:

- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- `TF_STATE_RESOURCE_GROUP`, `TF_STATE_STORAGE_ACCOUNT`, `TF_STATE_CONTAINER`, **or**
  `EA_STATE_BACKEND_JSON` (below).

### Terraform state per environment

`main.tf` has no backend block. `operations/init.sh` runs `operations/state_backend.py`, which
writes `ea_backend.tf` (ignored by git) from `EA_STATE_BACKEND_JSON` — the state backend the
environment has in EA, non-secret JSON exactly as EA stores it — or, when unset, from the
`TF_STATE_*` trio above with key `ea-demo/<owner>/<instance>.tfstate`. It applies EA's checks,
refuses any field that is not a setting of the chosen backend (keys, SAS, tokens) and recomputes the
identity EA recorded. The approved plan context binds that identity, so apply cannot use other state.

| Backend | Settings | Runner authentication |
| --- | --- | --- |
| `azurerm` | resource group, storage account, container, key | Entra OIDC (`use_azuread_auth`), data-plane role on the container |
| `s3` | bucket, region, key; encrypted, native lock file (Terraform ≥ 1.10) | AWS credential chain of the runner (for example an OIDC role step before init) |
| `remote` (HCP Terraform) | organization, workspace | `TF_TOKEN_APP_TERRAFORM_IO` repository secret; the workspace must use **local** execution, because the workflow applies a saved plan |

The backend is never created or destroyed here. Verified locally: `terraform fmt -check` and
`terraform validate` with each generated backend (Terraform 1.14.9); no state operation has been run
against a real account.

Plan and apply may use different client IDs. Subscription, tenant and backend values must
match across environments; the saved context is checked before apply. Never use production
credentials for the first verification. No client secret or publish profile is required.

## Run

1. Dispatch **FastAPI Azure Web App demo**, selecting `plan`, an instance and a region.
2. Inspect the `demo-plan-RUN_ID` artifact. Plans and resource identifiers are visible to
   repository readers; artifacts expire after three days.
3. Dispatch `deploy`. This creates a fresh plan, then waits at `demo-deploy`. Review this
   run's plan before approving. The apply job uses that binary plan, the same commit and
   the previously built application zip; it does not silently regenerate the plan.
4. Inspect `demo-result-RUN_ID-ATTEMPT`: outputs, context hashes, health evidence and completion.
   A 200 from an older app version does not pass the check. Failed runs never write a
   successful completion record.
5. Run the separately approved cleanup described in `operations/cleanup.md`.

The live app is public over HTTPS and incurs B1 charges while provisioned. TTL is advisory,
not an automatic delete schedule. A changed plan, subscription, state backend or archive
fails validation. A stale Terraform plan fails normally; produce a new plan rather than
forcing it. Deploy mode rejects deletes/replacements; use an explicit cleanup run first.

## Local checks

From this package, in a Python 3.12 environment:

```sh
python -m pip install -r app/requirements.txt -r tests/requirements.txt
python -m pytest tests -q
terraform -chdir=infra/terraform init -backend=false -lockfile=readonly
terraform -chdir=infra/terraform validate
```

`operations/package.py --revision FULL_COMMIT_SHA --output application.zip` produces a
deterministic zip with its revision embedded. Terraform validation does not contact Azure.

## EA NextGen integration boundary

This candidate imports as an application package with a draft pipeline. Its GitHub workflow
is a standalone path with native Environment approvals. It does not yet implement the EA
execution input/webhook/evidence protocol or automatic PR materialization from package
selection. Do not mark the platform package deployable based on local tests or native GitHub
success alone; that end-to-end integration and sandbox evidence remain required.

References: https://learn.microsoft.com/en-us/azure/app-service/deploy-github-actions
and https://registry.terraform.io/providers/hashicorp/azurerm/4.62.0/docs/resources/linux_web_app

## Architecture materialization

Package 0.3.1 uses manifest schema 1.1 and offers the `azure-terraform-github` variant for metamodel `api` components. It scaffolds the FastAPI HTTP service; it does not claim to implement every application or system in an architecture. Candidate selection and binding do not authorize deployment or certify Azure execution. Previously imported 0.3.0 commits remain unchanged. Import 0.3.1 from a new full commit after review and publication.
