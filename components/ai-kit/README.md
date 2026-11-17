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
| `tools/ai_review.py` | CI, opt-in | advisory AI review of a pull request: one Azure Repos comment thread, always exits 0 |
| `pipelines/azure-pipelines/ai-review-steps.yml` | `ci.yml` of each template | the review step: pull requests only, `AI_REVIEW_ENABLED` only, `continueOnError` |
| `tests/test_ai_review.py` | each template's test run | review tool and step contract, with fakes (no API or Azure DevOps call) |
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

## Advisory AI review (opt-in)

**It sends source code to an external API**, so it is off unless a pipeline sets `AI_REVIEW_ENABLED` to
`true`. On a pull request build, after the guardrail, `tools/ai_review.py` sends the diff against the
target branch, `AGENTS.md`, `.eanextgen.d/standards/review.prompt.md` and the guardrail result to the
Claude API (default model `claude-sonnet-5-5`, `AI_REVIEW_MODEL` to change it) and posts the answer as
one comment thread on the Azure Repos pull request, updated in place on later runs (found by a marker).

- Files that look like secrets are withheld by name (`.env*`, keys, certificates, keystores, tfvars and
  state, credential files) or by content (private keys, cloud and VCS tokens, connection strings, quoted
  password/secret/token literals) and listed by path only.
- A diff over `AI_REVIEW_MAX_DIFF_BYTES` (default 150000) is not truncated: the review is skipped and the
  comment says so.
- Advisory: always exits 0, the step has `continueOnError: true`, and the thread is created closed so a
  comment-resolution policy never waits on it. Failures are pipeline warnings.
- `ANTHROPIC_API_KEY` is a secret variable mapped only into that step. The Anthropic SDK is pinned in the
  step and installed in its own virtual environment, never in `app/requirements.txt`.
- The build identity needs "Contribute to pull requests". `evidence/ai-review.json` records what was sent
  (paths, sizes, model, request id), never code.

Used by: `templates/azure/app-service/python-fastapi-split`, `templates/azure/container-apps/python-fastapi-split`.
