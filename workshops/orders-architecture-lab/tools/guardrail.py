#!/usr/bin/env python3
"""The architecture as a guardrail *inside* the agent's loop, not a report at the end.

    python tools/guardrail.py check       # a person, Codex or CI: exit 1 if the change is not acceptable
    python tools/guardrail.py post-edit   # Claude Code PostToolUse hook: violations go back to the agent
    python tools/guardrail.py stop        # Claude Code Stop hook: the agent cannot finish until it passes

A change is acceptable when
  1. it respects docs/architecture/architecture-rules.toml (tools/check_architecture.py),
  2. the tests still pass,
  3. it stays within the change budget (files and changed lines, measured with git), and
  4. it does not touch what judges it (rules, ADRs, checker, agent configuration), and
  5. no test loses an assertion: a fix may change how a test builds a use case, never what it checks.

Nothing here decides that the change is *good*: a person reviews it. The guardrail only refuses what the
architecture already decided. Without git the size of the change cannot be measured; that is said, not
assumed to be fine.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_architecture import RULES, ROOT, check  # noqa: E402


def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def changes() -> dict[str, int] | None:
    """Changed lines per file under the lab, relative to the last commit (untracked files count whole)."""
    prefix = _git("rev-parse", "--show-prefix")
    prefix = prefix.strip() if prefix is not None else None  # "" at a repository root, "<dir>/" inside one
    numstat = _git("diff", "--numstat", "HEAD", "--", ".")
    untracked = _git("ls-files", "--others", "--exclude-standard", "--", ".")
    if prefix is None or numstat is None or untracked is None:
        return None
    changed: dict[str, int] = {}
    for line in numstat.splitlines():
        added, deleted, path = line.split("\t", 2)
        path = path[len(prefix):] if path.startswith(prefix) else path
        changed[path] = (int(added) if added.isdigit() else 0) + (int(deleted) if deleted.isdigit() else 0)
    for path in untracked.splitlines():
        try:
            changed[path] = len((ROOT / path).read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError):
            changed[path] = 0
    return {p: n for p, n in changed.items() if "__pycache__" not in p and not p.startswith(".pytest_cache")}


def assertions(source: str) -> int:
    """``assert`` statements plus ``pytest.raises`` checks; -1 when the file does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return -1
    return sum(isinstance(node, ast.Assert) or (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                                                 and node.func.attr == "raises") for node in ast.walk(tree))


def weakened_tests(changed: dict[str, int]) -> list[str]:
    prefix = (_git("rev-parse", "--show-prefix") or "").strip()
    found = []
    for path in sorted(p for p in changed if p.startswith("tests/") and p.endswith(".py")):
        before = _git("show", f"HEAD:{prefix}{path}")
        if before is None:
            continue  # a new test file only adds checks
        current = ROOT / path
        after = current.read_text(encoding="utf-8") if current.exists() else ""
        if assertions(after) < assertions(before):
            found.append(f"{path} ({assertions(before)} → {max(assertions(after), 0)} checks)")
    return found


def tests_pass() -> tuple[bool, str]:
    try:
        done = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"], cwd=ROOT,
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"tests could not run: {error}"
    tail = (done.stdout.strip().splitlines() or ["no output"])[-1]
    return done.returncode == 0, tail


def evaluate(run_tests: bool = True) -> dict:
    budget = tomllib.loads(RULES.read_text(encoding="utf-8")).get("change_budget", {})
    report = check()
    problems = [f"{v['rule']} [{v['adr']}] {v['evidence']}: {v['from']} imports {v['imports']} — {v['statement']}"
                for v in report["violations"]]
    changed = changes()
    size = None
    if changed is None:
        size = "not measured (no git): a person must judge the size of the change"
    else:
        source = {p: n for p, n in changed.items() if p.startswith("src/")}
        lines = sum(source.values())
        size = f"{len(source)} file(s), {lines} changed line(s) in src/ (budget {budget.get('max_files')} / {budget.get('max_changed_lines')})"
        if budget.get("max_files") is not None and len(source) > budget["max_files"]:
            problems.append(f"CHANGE-BUDGET: {len(source)} files changed in src/, budget {budget['max_files']}. {budget.get('statement', '')}")
        if budget.get("max_changed_lines") is not None and lines > budget["max_changed_lines"]:
            problems.append(f"CHANGE-BUDGET: {lines} changed lines in src/, budget {budget['max_changed_lines']}. {budget.get('statement', '')}")
        touched = sorted(p for p in changed if any(fnmatchcase(p, pattern) for pattern in budget.get("protected", [])))
        if touched:
            problems.append(f"PROTECTED: {', '.join(touched)} changed. The rules, the checker and the agent configuration "
                            "judge the change; the agent may not change them. Revert those files.")
        weakened = weakened_tests(changed)
        if weakened:
            problems.append(f"TESTS-WEAKENED: {', '.join(weakened)}. A fix may change how a test builds a use case, never "
                            "remove what it checks.")
    tests = None
    if run_tests:
        ok, tail = tests_pass()
        tests = tail
        if not ok:
            problems.append(f"TESTS: {tail}")
    return {"acceptable": not problems, "problems": problems, "violations": len(report["violations"]), "size": size, "tests": tests,
            "src_changed": bool(changed and any(p.startswith("src/") for p in changed))}


def _message(result: dict) -> str:
    head = "Architecture guardrail: the change is NOT acceptable yet." if result["problems"] else "Architecture guardrail: acceptable."
    lines = [head, f"Size: {result['size']}"]
    if result["tests"]:
        lines.append(f"Tests: {result['tests']}")
    lines += [f"  - {p}" for p in result["problems"]]
    if result["problems"]:
        lines.append("Fix the cause with the smallest change (use the ports that already exist; see docs/architecture/adr). "
                     "Do not edit the rules, the checker or the tests.")
    return "\n".join(lines)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "check":
        result = evaluate()
        print(_message(result))
        return 0 if result["acceptable"] else 1
    hook = json.loads(sys.stdin.read() or "{}")
    if mode == "post-edit":
        edited = str((hook.get("tool_input") or {}).get("file_path") or "")
        if edited and str(ROOT) not in edited:
            return 0
        result = evaluate(run_tests=False)  # fast feedback after every edit; tests run before finishing
        if result["problems"]:
            print(_message(result), file=sys.stderr)
            return 2  # Claude Code shows stderr to the agent
        return 0
    if mode == "stop":
        if hook.get("stop_hook_active"):
            return 0  # already blocked once in this turn: let the person see the state rather than loop
        result = evaluate()
        if not result["src_changed"] and not any(p.startswith("PROTECTED") for p in result["problems"]):
            return 0  # analysis only (phase 1): nothing changed, nothing to accept
        if result["problems"]:
            print(_message(result), file=sys.stderr)
            return 2  # blocks the stop: the agent keeps working
        return 0
    print(f"unknown mode {mode!r}; use check, post-edit or stop", file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
