# Orders architecture lab

Workshop level 3 of **"AI writes code. Who designs the architecture?"** — a small, realistic
repository with correct decisions **and three deliberate architectural problems**.

```text
src/
  orders/          domain · application · infrastructure
  payments/        domain · application · infrastructure
  notifications/   application · infrastructure
docs/architecture/ C4 (context, containers, components), ADRs, architecture-rules.toml
tests/             behaviour tests (they pass)
tools/             check_architecture.py (the architecture does not)
```

## Two questions, two answers

```bash
python -m pytest -q                    # Does the code work?              → yes
python tools/check_architecture.py     # Is the architecture still right? → no (exit 1)
python tools/check_architecture.py --json   # evidence for EA NextGen / CI
```

Requirements: Python 3.11+ and pytest. Nothing else.

## How the workshop uses it

1. **Analyse before changing.** Ask the AI (Codex, Claude Code, or a local model with Ollama) for a
   map of the system and evidence of every problem, comparing the code with `docs/architecture`. No
   edits yet.
2. **Minimal fix.** Ask for the smallest change that removes the violations without touching other
   components.
3. **Verify.** Run the tests and the checker. Then review the evidence and decide — a person, not the
   AI, accepts the change.

The facilitator guide (expected findings and the minimal fix) is in the EA NextGen repository:
`docs/v5/workshop/ai-writes-code-who-designs-the-architecture.md`.

## The agent as a guardrail, not only a better prompt

A good prompt asks the AI to respect the architecture. A guardrail **refuses** a change that does not.
`tools/guardrail.py` accepts a change only when

1. it respects `docs/architecture/architecture-rules.toml` (the checker),
2. the tests pass,
3. it stays within the change budget (`[change_budget]`: files and changed lines in `src/`, measured with git),
4. it does not touch what judges it (rules, ADRs, checker, agent configuration), and
5. no test loses an assertion — a fix may change how a test builds a use case, never what it checks.

```bash
python3 tools/guardrail.py check     # a person, Codex or CI — exit 1 if not acceptable
```

**Claude Code** (open *this folder* as the project): `.claude/settings.json` runs the guardrail after every
edit (the violations go back to the agent) and before the agent finishes (it cannot stop while the change is
not acceptable; analysis-only turns are never blocked). It also denies edits to the files that judge it.
**Codex** reads `AGENTS.md`: same rules; it must show the `check` output before saying it is done.

| What the agent does | Guardrail |
|---|---|
| Analyses without changing anything | lets it finish |
| Reference fix (port `PaymentGateway`, `tax_rate` as a value, no `save`) — 2 files, ~21 lines | **acceptable** |
| Rewrites (70+ lines) | `CHANGE-BUDGET` |
| Hides the import inside a function | `ARCH-001/003/004` still found |
| Deletes an assertion to make tests pass | `TESTS-WEAKENED` |
| Loosens the rules file | `PROTECTED` |

Limits, said plainly: the guardrail runs on the participant's machine, so an agent with shell access could
still tamper with it. The decision that counts is the one re-run from a clean copy (CI, EA NextGen) and the
person who reviews the change.
