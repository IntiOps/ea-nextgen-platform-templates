# AI kit v0 · guardrails for repositories generated from a template

The files an AI coding agent reads in a service repository created from a template, and the deny list
that keeps it away from what judges it. Canonical source; templates carry byte-identical copies
(`tests/test_components.py` checks both, and that the protected paths agree everywhere).

| File | Read by | Role |
|---|---|---|
| `AGENTS.md` | Codex, Copilot, Cursor; Claude through `CLAUDE.md` | rules and commands, single source |
| `CLAUDE.md` | Claude Code | imports `AGENTS.md` |
| `.claude/settings.json` | Claude Code | denies edits to protected paths, `az`, `git push` and reading `.env*` |
| `.github/copilot-instructions.md` | GitHub Copilot (any git host) | points to `AGENTS.md` |
| `.eanextgen.d/rules/protected-paths.txt` | people, the Azure Repos required-reviewer policy | one list of protected paths |
| `.gitignore` | git | keeps caches and `.env` files out |

`AGENTS.md` contains `{{ea.<key>}}` tokens (`service`, `package_id`, `package_version`,
`package_commit`) that the platform renders when it creates the repository.

This file is context, not enforcement. Enforcement lives on the server: a build-validation policy and
required reviewers on the protected paths. v0 has no guardrail hooks; `tools/guardrail.py` and
`make check` arrive with P2.

Used by: `templates/azure/app-service/python-fastapi-split`.
