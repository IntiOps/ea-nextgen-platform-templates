# AGENTS.md — Orders lab

You are changing a system whose architecture is already decided. Read it before you write code:
`docs/architecture/README.md` (C4), `docs/architecture/adr/`, `docs/architecture/architecture-rules.toml`.

1. **Analyse first.** When asked to analyse, change nothing: return a map of the system and every problem
   with file, line and the rule it breaks.
2. **Smallest change.** Fix the cause, use the ports that already exist, keep behaviour. The change budget
   is in `architecture-rules.toml` (`[change_budget]`).
3. **You may not change what judges you:** `docs/architecture/`, `tools/`, `.claude/`, this file,
   `CLAUDE.md`, `pyproject.toml`. Tests may change how they build a use case, never lose an assertion.
4. **Before you say you are done**, run `python3 tools/guardrail.py check`. It must exit 0. If it does not,
   keep working or explain what you could not resolve. Never report success without that output.
5. A person reviews and accepts the change. You propose; the architecture decides.
