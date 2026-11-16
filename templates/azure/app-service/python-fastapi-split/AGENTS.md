# AGENTS.md — {{ea.service}}

This repository is the `{{ea.service}}` service, created from template `{{ea.package_id}}`
{{ea.package_version}} at commit `{{ea.package_commit}}` (see `.ea/package.json`).
It runs on Azure App Service. Azure Pipelines builds it once (`pipelines/azure-pipelines/ci.yml`) and
promotes the same package dev → prod (`cd.yml`), with an approval before prod.

## Commands
- Install:  `python -m pip install -r app/requirements.txt -r tests/requirements.txt`
- Run:      `python -m uvicorn main:app --app-dir app --reload` then open http://127.0.0.1:8000/health
- Test:     `python -m pytest tests -q`  (this is the definition of done until `make check` arrives)

## Rules
1. **Analyse first.** When asked to analyse, change nothing. Report file, line and the problem.
2. **Plan, then change.** For any feature, state the plan (files, tests) and wait for approval.
3. **Smallest change that solves the task.** No drive-by refactors. No new dependency without an ADR
   in `docs/adr/`.
4. **You may not change what judges you:** the paths in `.eanextgen.d/rules/protected-paths.txt`
   (`AGENTS.md`, `CLAUDE.md`, `template.yaml`, `.claude/`, `.github/`, `.ea/`, `.eanextgen*`,
   `pipelines/`, `infra/`, `operations/`, `tools/`, `Makefile`). Infra or pipeline needs go into an
   ADR or a change request for the Platform Team.
5. **Tests may change, never weaken.** Never delete an assertion or skip a test to make the build pass.
   `tests/test_split_delivery.py` guards the delivery contract: leave it alone.
6. **No secrets.** No keys, connection strings or tokens in code, tests, logs or prompts.
7. **No new cloud resources, public endpoints or outbound calls** without an ADR approved by the architect.
8. **Before you say you are done**, run the tests. They must pass. Paste the output.
9. Work on a feature branch and open a pull request. Never push to `main`. A person reviews and merges.

This file is context, not permission. It grants no access to Azure, Azure DevOps or secrets.
