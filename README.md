# EA NextGen Platform Templates

Public application, infrastructure and CI/CD packages, organized by cloud, ecosystem and application stack.

```text
templates/
  azure/
    app-service/
      python-fastapi/
catalog/index.yaml
```

The initial candidate is a FastAPI web service on Azure App Service with Terraform,
GitHub Actions, health checks and an explicit cleanup workflow. Azure DevOps pipelines
are a separate delivery variant and are not implemented by this initial package.

See [the package guide](templates/azure/app-service/python-fastapi/README.md).
The catalog lists candidates separately from cloud certification: local tests do not
prove a successful Azure deployment. Import using a full commit SHA, never a moving branch.

## Import into EA NextGen

From the platform repository, preview the public package (replace FULL_COMMIT_SHA):

```sh
PYTHONPATH=backend .venv/bin/python -m app.domains.application_templates.import_cli \
  --public --repository https://github.com/IntiOps/ea-nextgen-platform-templates.git \
  --commit FULL_COMMIT_SHA --package-path templates/azure/app-service/python-fastapi
```

To store it in the local organization, add `--write --organization-id ORGANIZATION_ID --actor OPERATOR`.
Import reads and validates files; it never executes downloaded code or deploys resources.

## Costs and authorization

The example creates a Linux B1 App Service plan, which is billable. It requires a
sandbox subscription, a Terraform state backend, OIDC setup and protected GitHub
environments as documented in the package. Publishing or importing this repository
creates no Azure resources. Deployment and cleanup are manual, approved workflows.

Do not commit credentials, `.env`, Terraform state or local caches. This repository
contains no account-specific connection configuration. AWS/Lambda, Kubernetes and
additional application stacks can be added under their own cloud/ecosystem paths.
