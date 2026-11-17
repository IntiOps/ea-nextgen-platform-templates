# AGENTS.md — {{ea.service}}

This repository is the `{{ea.service}}` service, created from template `{{ea.package_id}}`
{{ea.package_version}} at commit `{{ea.package_commit}}` (see `.ea/package.json`).
Its runtime and Azure resources are described in `template.yaml` and `infra/`. Azure Pipelines builds it
once (`pipelines/azure-pipelines/ci.yml`) and promotes the same artifact dev → prod (`cd.yml`), with an
approval before prod.
The advisory AI review of pull requests is opt-in (`AI_REVIEW_ENABLED`): it sends the diff to an external API.

## Commands
- `make install`  install app and test dependencies
- `make run`      start locally, then open http://127.0.0.1:8000/health, /ready, /hello?name=Ada
- `make test`     unit, API and delivery-contract tests
- `make check`    architecture rules + tests + guardrail. **This is the definition of done.**

## Where things go
- `app/service/domain/`          business rules, pure Python (ARCH-001)
- `app/service/application/`     use cases and their ports (ARCH-002)
- `app/service/infrastructure/`  adapters: HTTP, clock, storage, external services
- `docs/adr/`                    decisions; read ADR-0001 before adding a layer, port or dependency
- `.eanextgen.d/standards/`      the team's prompts (feature, analyse, review, infra request)

## Rules
1. **Analyse first.** When asked to analyse, change nothing. Report file, line and the rule broken.
2. **Plan, then change.** For any feature, state the plan (files, tests) and wait for approval.
3. **Respect the layers and keep changes small.** Follow `architecture-rules.toml`. No drive-by
   refactors. No new dependency without an ADR in `docs/adr/`. Changes over the `[change_budget]`
   need a person to look first.
4. **You may not change what judges you:** the paths in `.eanextgen.d/rules/protected-paths.txt`
   (`AGENTS.md`, `CLAUDE.md`, `template.yaml`, `.claude/`, `.github/`, `.ea/`, `.eanextgen*`,
   `pipelines/`, `infra/`, `operations/`, `tools/`, `Makefile`, `Dockerfile`, `.dockerignore`,
   `tests/test_ai_review.py`).
   Infra, pipeline or image build needs go into an ADR or a change request for the Platform Team.
5. **Tests may change, never weaken.** Never delete an assertion or skip a test to make the build pass.
   `tests/test_split_delivery.py` guards the delivery contract: leave it alone.
6. **No secrets.** No keys, connection strings or tokens in code, tests, logs or prompts.
7. **No new cloud resources, public endpoints or outbound calls** without an ADR approved by the architect.
8. **Before you say you are done**, run `make check`. It must exit 0. Paste the output. If it fails,
   keep working or explain what you could not resolve. Never report success without that output.
9. Work on a feature branch and open a pull request. Never push to `main`. A person reviews and merges.

This file is context, not permission. It grants no access to Azure, Azure DevOps or secrets.
