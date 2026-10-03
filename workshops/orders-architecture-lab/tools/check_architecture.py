#!/usr/bin/env python3
"""Map the system and check it against docs/architecture/architecture-rules.toml.

    python tools/check_architecture.py            # map + violations, exit 1 if any
    python tools/check_architecture.py --json     # the same, machine-readable (for EA NextGen or CI)

Reads imports with ``ast``; nothing is executed. Every finding cites the rule, its ADR and file:line.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RULES = ROOT / "docs" / "architecture" / "architecture-rules.toml"


def module_name(path: Path) -> str:
    parts = list(path.relative_to(SRC).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = module_name(path).rsplit(".", 1)[0] if path.name != "__init__.py" else module_name(path)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(alias.name, node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: resolve against the package
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                found.append((".".join([*base, node.module] if node.module else base), node.lineno))
            elif node.module:
                found.append((node.module, node.lineno))
    return found


def unit(module: str, contexts: list[str], layers: list[str]) -> tuple[str | None, str | None]:
    parts = module.split(".")
    context = parts[0] if parts[0] in contexts else None
    layer = parts[1] if context and len(parts) > 1 and parts[1] in layers else None
    return context, layer


def check() -> dict:
    config = tomllib.loads(RULES.read_text(encoding="utf-8"))
    contexts, layers = config["contexts"], config["layers"]
    edges: Counter = Counter()
    violations = []
    files = sorted(p for p in SRC.rglob("*.py"))
    for path in files:
        source = module_name(path)
        src_context, src_layer = unit(source, contexts, layers)
        try:
            found = imports(path)
        except (SyntaxError, ValueError) as error:  # code that does not parse cannot be shown to respect anything
            violations.append({"rule": "SYNTAX", "adr": None, "statement": "The file does not parse; none of its dependencies can be checked.",
                               "evidence": f"{path.relative_to(ROOT)}:{getattr(error, 'lineno', None) or 1}", "from": source, "imports": "—"})
            continue
        for target, line in found:
            dst_context, dst_layer = unit(target, contexts, layers)
            if src_context and dst_context and (src_context, src_layer) != (dst_context, dst_layer):
                edges[(f"{src_context}.{src_layer}", f"{dst_context}.{dst_layer}")] += 1
            for rule in config["rules"]:
                if not any(fnmatchcase(source, pattern) for pattern in rule["source"]):
                    continue
                broken = any(fnmatchcase(target, pattern) for pattern in rule.get("forbid", []))
                if rule.get("forbid_foreign") and dst_context and dst_context != src_context and dst_layer in rule["forbid_foreign"]:
                    broken = True
                if broken:
                    violations.append({"rule": rule["id"], "adr": rule.get("adr"), "statement": rule["statement"],
                                       "evidence": f"{path.relative_to(ROOT)}:{line}", "from": source, "imports": target})
    forbidden_edges = {(v["from"], v["imports"]) for v in violations}
    return {
        "contexts": {c: sorted({layer for p in files if module_name(p).split(".")[0] == c
                                for layer in [unit(module_name(p), contexts, layers)[1]] if layer}) for c in contexts},
        "dependencies": [{"from": a, "to": b, "imports": n} for (a, b), n in sorted(edges.items())],
        "violations": violations,
        "summary": {"files": len(files), "violations": len(violations), "rules_broken": sorted({v["rule"] for v in violations}),
                    "imports_breaking_rules": len(forbidden_edges)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    report = check()
    if parser.parse_args().json:
        print(json.dumps(report, indent=2))
        return 1 if report["violations"] else 0
    print("SYSTEM MAP")
    for context, context_layers in report["contexts"].items():
        print(f"  {context}: {', '.join(context_layers)}")
    print("\nDEPENDENCIES BETWEEN UNITS")
    broken_units = {(v["from"].split(".")[0] + "." + v["from"].split(".")[1], v["imports"].split(".")[0] + "." + (v["imports"].split(".") + [""])[1])
                    for v in report["violations"] if "." in v["from"]}
    for edge in report["dependencies"]:
        mark = "✕" if (edge["from"], edge["to"]) in broken_units else "✓"
        print(f"  {mark} {edge['from']} → {edge['to']} ({edge['imports']} import(s))")
    print(f"\nVIOLATIONS ({report['summary']['violations']})")
    for violation in report["violations"]:
        print(f"  {violation['rule']} [{violation['adr']}] {violation['evidence']}: {violation['from']} imports {violation['imports']}")
        print(f"      {violation['statement']}")
    if not report["violations"]:
        print("  none — the code respects docs/architecture")
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
