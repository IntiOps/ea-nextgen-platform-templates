"""Decide exactly which resources the gated cleanup pipeline may delete (P4-05). Standard library only.

The pipeline (``pipelines/azure-pipelines/cleanup.yml``) lists the resources of one environment's
resource group with a query filtered on BOTH tags ``managed_by=ea-nextgen-template`` and
``instance=<service>-<environment>``, and passes the JSON here:

    review LISTING     list stage: check the listing and print it for the approvers
    plan PUBLISHED CURRENT
                       delete stage, after approval: check the fresh listing, refuse if it differs from
                       the published one, then print the ids to delete, dependents first

Both commands re-check every item, so a wrong query cannot widen what is deleted:
  * it carries both tags with the expected values;
  * its id is in ``--resource-group`` (resource groups are never listed, never deleted);
  * its type is one this template creates (anything else needs a person, not this pipeline);
  * it is not a ``--keep`` id (infraMode shared: the existing plan or managed environment).
Any violation exits 1 and prints why. Ids compare case-insensitively, as Azure resource ids do.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MANAGED_BY = "ea-nextgen-template"

#: Delete order by resource type, lowest first: apps before what they run on, workspaces last.
DELETE_ORDER = {
    "microsoft.web/sites": 0,
    "microsoft.app/containerapps": 0,
    "microsoft.web/serverfarms": 1,
    "microsoft.app/managedenvironments": 1,
    "microsoft.operationalinsights/workspaces": 2,
}


class CleanupRefused(Exception):
    pass


def _tag(tags: dict | None, key: str) -> str | None:
    """Azure tag names are case-insensitive."""
    for name, value in (tags or {}).items():
        if name.lower() == key:
            return value
    return None


def _resource_group(resource_id: str) -> str | None:
    parts = resource_id.split("/")
    lowered = [p.lower() for p in parts]
    if "resourcegroups" not in lowered or "providers" not in lowered:
        return None
    index = lowered.index("resourcegroups")
    return parts[index + 1] if index + 1 < len(parts) else None


def check(items: object, *, instance: str, resource_group: str, keep: list[str]) -> list[dict]:
    """Return the items if every one of them may be deleted; raise CleanupRefused otherwise."""
    if not isinstance(items, list):
        raise CleanupRefused("the listing is not a JSON array")
    keep_ids = {k.lower() for k in keep if k}
    problems, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("type"), str):
            problems.append(f"not a resource with id and type: {item!r}")
            continue
        rid = item["id"]
        if rid.lower() in seen:
            problems.append(f"listed twice: {rid}")
        seen.add(rid.lower())
        if _tag(item.get("tags"), "managed_by") != MANAGED_BY:
            problems.append(f"not tagged managed_by={MANAGED_BY}: {rid}")
        if _tag(item.get("tags"), "instance") != instance:
            problems.append(f"not tagged instance={instance}: {rid}")
        group = _resource_group(rid)
        if group is None or group.lower() != resource_group.lower() or rid.lower().rstrip("/").endswith(f"resourcegroups/{group.lower()}"):
            problems.append(f"not a resource inside resource group {resource_group}: {rid}")
        if item["type"].lower() not in DELETE_ORDER:
            problems.append(f"type {item['type']} is not created by this template, a person must decide: {rid}")
        if rid.lower() in keep_ids:
            problems.append(f"belongs to the platform (infraMode shared), never deleted here: {rid}")
    if problems:
        raise CleanupRefused("; ".join(problems))
    return items


def ordered(items: list[dict]) -> list[str]:
    """Ids, dependents first (stable within one rank)."""
    return [i["id"] for i in sorted(items, key=lambda i: (DELETE_ORDER[i["type"].lower()], i["id"].lower()))]


def compare(published: list[dict], current: list[dict]) -> None:
    before = {i["id"].lower(): i["id"] for i in published}
    now = {i["id"].lower(): i["id"] for i in current}
    if before.keys() != now.keys():
        added = sorted(now[k] for k in now.keys() - before.keys())
        gone = sorted(before[k] for k in before.keys() - now.keys())
        raise CleanupRefused("the resources changed since the approved list was published "
                             f"(new: {added or 'none'}; gone: {gone or 'none'}); run the cleanup again")


def _load(path: Path) -> object:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise CleanupRefused(f"cannot read {path}: {error}") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("review", "plan"):
        command = sub.add_parser(name)
        if name == "review":
            command.add_argument("listing", type=Path)
        else:
            command.add_argument("published", type=Path, help="the list published by the list stage")
            command.add_argument("current", type=Path, help="the same query, run again after approval")
        command.add_argument("--instance", required=True, help="<service>-<environment>")
        command.add_argument("--resource-group", required=True)
        command.add_argument("--keep", action="append", default=[], help="resource id never to delete (repeatable)")
    args = parser.parse_args(argv)
    rules = {"instance": args.instance, "resource_group": args.resource_group, "keep": args.keep}
    try:
        if args.command == "review":
            items = check(_load(args.listing), **rules)
            print(f"{len(items)} resource(s) tagged managed_by={MANAGED_BY} and instance={args.instance} "
                  f"in {args.resource_group}, in delete order:", file=sys.stderr)
            for item in sorted(items, key=lambda i: (DELETE_ORDER[i["type"].lower()], i["id"].lower())):
                print(f"  {item['type']}  {item.get('name', '')}  {item['id']}", file=sys.stderr)
            if not items:
                print("  nothing to delete", file=sys.stderr)
        else:
            published = check(_load(args.published), **rules)
            current = check(_load(args.current), **rules)
            compare(published, current)
            for rid in ordered(current):
                print(rid)
    except CleanupRefused as error:
        print(f"cleanup refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
