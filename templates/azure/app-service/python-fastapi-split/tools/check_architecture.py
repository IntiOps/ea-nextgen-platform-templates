#!/usr/bin/env python3
"""Check the code against .eanextgen.d/rules/architecture-rules.toml.

    python tools/check_architecture.py           # violations as text, exit 1 if any
    python tools/check_architecture.py --json    # the same, machine-readable (CI evidence, EA NextGen)

Reads imports with ``ast``; nothing is executed. Each finding cites the rule, its ADR and file:line.
Generalized from workshops/orders-architecture-lab/tools/check_architecture.py.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".eanextgen.d" / "rules" / "architecture-rules.toml"


def load_rules(path: Path = RULES) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def module_name(path: Path, source_root: Path) -> str:
    parts = list(path.relative_to(source_root).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports(path: Path, source_root: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = module_name(path, source_root)
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(alias.name, node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: resolve against the package
                base = package.split(".")[: max(len(package.split(".")) - node.level + 1, 0)]
                found.append((".".join([*base, node.module] if node.module else base), node.lineno))
            elif node.module:
                found.append((node.module, node.lineno))
    return found


def _matches(name: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(name, pattern) for pattern in patterns)


def check(root: Path = ROOT) -> dict:
    config = load_rules(root / ".eanextgen.d" / "rules" / "architecture-rules.toml")
    source_root = root / config.get("source_root", "app")
    violations, modules = [], 0
    for path in sorted(source_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        modules += 1
        source = module_name(path, source_root)
        for rule in config.get("rules", []):
            if not _matches(source, rule["source"]):
                continue
            for target, line in imports(path, source_root):
                if _matches(target, rule["forbid"]):
                    violations.append({"rule": rule["id"], "adr": rule.get("adr"), "statement": rule["statement"],
                                       "file": path.relative_to(root).as_posix(), "line": line,
                                       "module": source, "imports": target})
    return {"modules": modules, "rules": len(config.get("rules", [])), "violations": violations}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    result = check()
    if parser.parse_args().json:
        print(json.dumps(result, indent=2))
    else:
        for v in result["violations"]:
            print(f"{v['file']}:{v['line']}  {v['rule']} ({v['adr']}): {v['module']} imports {v['imports']}. {v['statement']}")
        print(f"{result['modules']} modules, {result['rules']} rules, {len(result['violations'])} violations")
    return 1 if result["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
