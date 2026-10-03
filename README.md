# EA NextGen Platform Templates

Public application, infrastructure and CI/CD packages, organized by cloud, ecosystem and application stack.

```text
templates/
  azure/
    app-service/
      python-fastapi/
  aws/
    lambda/
      python-http/
catalog/index.yaml
```

The initial candidate is a FastAPI web service on Azure App Service with Terraform,
GitHub Actions, health checks and an explicit cleanup workflow. The repository also contains Bicep and AWS Lambda Terraform/CDK sources.
GitHub Actions and Azure Pipelines validate these sources; deployment integration
for the new variants is tracked in [implementation status](IMPLEMENTATION_STATUS.md).

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
contains no account-specific connection configuration. Kubernetes and additional application stacks belong under their own cloud/ecosystem paths.

Environment profiles and public-price estimation live in
[components/lifecycle-finops](components/lifecycle-finops). Estimates explicitly
block approval when non-compute costs are still missing; no automated scheduler
is enabled by merely supplying a lifecycle policy.

## Architecture and reusable code

See [CATALOG.md](CATALOG.md) for twelve typed blueprints, three source components,
and local functional demos. Cloud variants and their verification remain separate.

## Demo independiente: revisión de arquitectura con IA

[Booking Rescue](demos/booking-rescue/README.md) es una aplicación local con fallas
intencionales para analizar y mejorar con ChatGPT, Codex u otra IA. Incluye un prompt,
escenarios reproducibles y una guía de revisión separada. Está fuera de los workshops
y del catálogo de paquetes importables; no es una referencia para producción.

[Monolito o microservicios](demos/monolith-or-microservices/README.md) sube la dificultad:
un reporte sencillo, propuestas engañosas de distribución y un runbook que induce a
duplicar app.py en main.py. Incluye una segunda ronda con verificación del contrato real.

[Correo y tablero de arquitectura](demos/email-architecture-board/README.md) es una
tercera demo de planificación: compartir un solo README con pistas engañosas, generar
TABLERO.md y filtrar sus decisiones con una guía separada antes de implementar.

## Quality and security evidence

See [validation foundation](components/validation/README.md) for the source profile,
context-bound evidence and GitHub/Azure CI components. SonarQube/ZAP support is
currently offline report assessment; no live scan is implied by catalog presence.
