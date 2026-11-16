#!/usr/bin/env python3
"""The architecture as a guardrail inside the agent's loop and in CI.

    python tools/guardrail.py check                 # a person or an agent: exit 1 if not acceptable
    python tools/guardrail.py check --ci --base REF --no-tests --json out.json   # CI evidence
    python tools/guardrail.py post-edit             # Claude Code PostToolUse hook (architecture only)
    python tools/guardrail.py stop                  # Claude Code Stop hook (full check)

Checks, and what each mode does with a problem:

    check                     agent / local          --ci
    architecture rules        fail                   fail
    tests pass                fail                   skipped with --no-tests (CI ran them)
    a test lost an assertion  fail                   fail
    protected path changed    fail (agents may not)  report: the required reviewer decides
    change budget exceeded    fail: ask a person     needs_review in the evidence
    change not measurable     fail                   fail (use fetchDepth: 0)

Nothing here decides that a change is good: a person reviews it. The guardrail only refuses what the
architecture already decided. Generalized from workshops/orders-architecture-lab/tools/guardrail.py.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_architecture import ROOT, check, load_rules  # noqa: E402

PROTECTED = ROOT / ".eanextgen.d" / "rules" / "protected-paths.txt"


def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def protected_patterns() -> list[str]:
    return [line.strip() for line in PROTECTED.read_text().splitlines() if line.strip() and not line.startswith("#")]


def is_protected(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, p) or (p.endswith("/*") and path.startswith(p[:-1])) for p in patterns)


def changes(base: str | None) -> dict[str, int] | None:
    """Changed files and their added+removed lines. Agent mode: working tree (and untracked) against HEAD.
    CI mode: HEAD against the merge base with ``base``."""
    if base:
        merge_base = (_git("merge-base", base, "HEAD") or "").strip()
        numstat = _git("diff", "--numstat", "--relative", merge_base or base, "HEAD") if (merge_base or base) else None
    else:
        numstat = _git("diff", "--numstat", "--relative", "HEAD")
    if numstat is None:
        return None
    changed: dict[str, int] = {}
    for row in numstat.splitlines():
        added, removed, path = row.split("\t", 2)
        changed[path] = (int(added) if added.isdigit() else 0) + (int(removed) if removed.isdigit() else 0)
    if not base:
        for path in (_git("ls-files", "--others", "--exclude-standard") or "").splitlines():
            try:
                changed[path] = len((ROOT / path).read_text(encoding="utf-8").splitlines())
            except (OSError, UnicodeDecodeError):
                changed[path] = 0
    return changed


def assertions(source: str) -> int:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            count += 1
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", "") in {"raises", "assertEqual", "assertTrue",
                                                                                "assertFalse", "assertRaises", "assertIn"}:
            count += 1
    return count


def weakened_tests(changed: dict[str, int], base: str | None) -> list[str]:
    ref = "HEAD"
    if base:
        ref = (_git("merge-base", base, "HEAD") or "").strip() or base
    weakened = []
    for path in changed:
        if not (path.startswith("tests/") and path.endswith(".py")):
            continue
        before = _git("show", f"{ref}:./{path}")
        if before is None:
            continue  # a new test file
        now = (ROOT / path).read_text(encoding="utf-8") if (ROOT / path).exists() else ""
        if assertions(now) < assertions(before):
            weakened.append(path)
    return weakened


def tests_pass() -> tuple[bool, str]:
    try:
        done = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "tests"],
                              cwd=ROOT, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    return done.returncode == 0, (done.stdout.strip().splitlines() or [""])[-1]


def evaluate(*, ci: bool, base: str | None, run_tests: bool) -> dict:
    rules = load_rules()
    budget = rules.get("change_budget", {})
    arch = check()
    changed = changes(base if ci else None)
    result: dict = {"schema_version": "1", "mode": "ci" if ci else "agent", "base": base,
                    "architecture": {"violations": arch["violations"], "modules": arch["modules"]}}
    failures, review = [], []
    if arch["violations"]:
        failures.append(f"{len(arch['violations'])} architecture violation(s)")
    if run_tests:
        ok, summary = tests_pass()
        result["tests"] = {"passed": ok, "summary": summary}
        if not ok:
            failures.append(f"tests fail: {summary}")
    if changed is None:
        result["change"] = {"measured": False}
        failures.append("the change could not be measured with git (in CI, check out with fetchDepth: 0)")
    else:
        lines = sum(changed.values())
        protected = sorted(p for p in changed if is_protected(p, protected_patterns()))
        weakened = weakened_tests(changed, base if ci else None)
        over = len(changed) > budget.get("max_files", 10**6) or lines > budget.get("max_changed_lines", 10**9)
        result["change"] = {"measured": True, "files": len(changed), "lines": lines, "protected_paths": protected,
                            "weakened_tests": weakened, "budget": budget, "over_budget": over}
        if weakened:
            failures.append(f"tests lost assertions: {', '.join(weakened)}")
        if protected:
            (review if ci else failures).append(f"protected paths changed: {', '.join(protected)}")
        if over:
            (review if ci else failures).append(
                f"change of {len(changed)} files / {lines} lines is over the budget "
                f"({budget.get('max_files')} files / {budget.get('max_changed_lines')} lines): a person must look first")
    result["failures"], result["needs_review"] = failures, review
    result["result"] = "fail" if failures else ("needs_review" if review else "pass")
    return result


def _message(result: dict) -> str:
    lines = [f"guardrail: {result['result']}"]
    for v in result["architecture"]["violations"]:
        lines.append(f"  {v['file']}:{v['line']} {v['rule']}: {v['module']} imports {v['imports']}. {v['statement']}")
    lines += [f"  FAIL {f}" for f in result["failures"]] + [f"  REVIEW {r}" for r in result["needs_review"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Architecture guardrail")
    parser.add_argument("command", choices=["check", "post-edit", "stop"])
    parser.add_argument("--ci", action="store_true", help="CI mode: protected paths and budget become needs_review")
    parser.add_argument("--base", help="git ref to compare against (CI: the PR target branch or the previous commit)")
    parser.add_argument("--no-tests", action="store_true")
    parser.add_argument("--json", type=Path, help="write the evidence JSON to this path")
    args = parser.parse_args()

    if args.command == "post-edit":
        # Fast feedback after every edit: architecture only. Exit 2 shows the message to the agent.
        arch = check()
        if arch["violations"]:
            print(_message({"result": "fail", "architecture": arch, "failures": [], "needs_review": []}), file=sys.stderr)
            return 2
        return 0

    if args.command == "stop":
        hook = {}
        if not sys.stdin.isatty():
            try:
                hook = json.loads(sys.stdin.read() or "{}")
            except json.JSONDecodeError:
                hook = {}
        result = evaluate(ci=False, base=None, run_tests=True)
        if result["result"] == "pass":
            return 0
        print(_message(result), file=sys.stderr)
        # A second stop attempt means the agent could not resolve it: let it stop and explain, never loop.
        return 0 if hook.get("stop_hook_active") else 2

    result = evaluate(ci=args.ci, base=args.base, run_tests=not args.no_tests)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + "\n")
    print(_message(result))
    return 1 if result["result"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
