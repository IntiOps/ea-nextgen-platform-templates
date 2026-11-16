# AI kit · guardrails for repositories generated from a template

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
| `tools/check_architecture.py` | people, agents, CI | layer rules from `architecture-rules.toml`, read with `ast` |
| `tools/guardrail.py` | Claude hooks, `make check`, CI (`--ci`) | rules + tests + weakened tests + protected paths + change budget; JSON evidence |
| `.eanextgen.d/rules/architecture-rules.toml` | the two tools | ARCH-001..003 and `[change_budget]` |
| `.eanextgen.d/standards/*.prompt.md` | the team | shared prompts: feature, analyse, review, infra request, bootstrap review, bind architecture |
| `docs/adr/0001-service-boundaries.md` | people, agents | why the layers exist |
| `Makefile` | everyone | `install`, `run`, `test`, `check` (definition of done) |

`AGENTS.md` contains `{{ea.<key>}}` tokens (`service`, `package_id`, `package_version`,
`package_commit`) that the platform renders when it creates the repository.

`AGENTS.md` is context, not enforcement. Claude Code runs `guardrail.py post-edit` after every edit and
`guardrail.py stop` before it may finish. The server enforces: CI runs `guardrail.py check --ci` (protected
paths and budget become `needs_review` there, for the required reviewer), and the build-validation
policy plus required reviewers on the protected paths decide the merge.

Used by: `templates/azure/app-service/python-fastapi-split`.
