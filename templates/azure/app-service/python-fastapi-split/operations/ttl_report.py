"""Report Azure resource groups and resources whose ``ea-ttl`` tag has passed (P4-05). Standard library only.

    az group list -o json > groups.json
    az resource list --tag ea-ttl -o json > resources.json
    python3 operations/ttl_report.py groups.json resources.json [--json] [--today YYYY-MM-DD]
    az group list -o json | python3 operations/ttl_report.py          # or read stdin ("-")

``ea-ttl`` is a date, ``YYYY-MM-DD``: the last day the item is meant to exist. An item expires the day
after (its TTL is before today). Items without the tag are not reported. A tag that is not a valid
date is reported as ``invalid``: an unreadable TTL must not pass silently.

Exit codes: 0 nothing expired or invalid; 1 at least one expired or invalid item; 2 unreadable input.
It only reads JSON; it never calls Azure and never deletes anything (see cleanup.yml for that).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

TAG = "ea-ttl"
ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


class InputError(Exception):
    pass


def _ttl(tags: object) -> str | None:
    """Azure tag names are case-insensitive."""
    if not isinstance(tags, dict):
        return None
    for name, value in tags.items():
        if isinstance(name, str) and name.lower() == TAG:
            return value if isinstance(value, str) else str(value)
    return None


def report(items: list[dict], today: date) -> dict:
    expired, invalid, live = [], [], 0
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise InputError(f"not an Azure object: {item!r}")
        key = str(item.get("id") or item.get("name")).lower()
        if key in seen:
            continue
        seen.add(key)
        value = _ttl(item.get("tags"))
        if value is None:
            continue
        entry = {"id": item.get("id"), "name": item.get("name"), "type": item.get("type"), "ttl": value}
        try:
            ttl = date.fromisoformat(value.strip()) if ISO_DAY.fullmatch(value.strip()) else None
        except ValueError:
            ttl = None
        if ttl is None:
            invalid.append(entry)
        elif ttl < today:
            expired.append({**entry, "days_over": (today - ttl).days})
        else:
            live += 1
    expired.sort(key=lambda e: (e["ttl"], str(e["id"])))
    invalid.sort(key=lambda e: str(e["id"]))
    return {"today": today.isoformat(), "expired": expired, "invalid": invalid, "not_expired": live}


def _read(source: str) -> list[dict]:
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text()
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read {source}: {error}") from error
    if not isinstance(data, list):
        raise InputError(f"{source}: expected the JSON array printed by az group list / az resource list")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", default=["-"], help="JSON from az group list / az resource list; - is stdin")
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="YYYY-MM-DD (default: today, UTC)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    today = args.today or datetime.now(timezone.utc).date()
    try:
        items = [item for source in args.files for item in _read(source)]
        result = report(items, today)
    except InputError as error:
        print(f"ttl_report: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for e in result["expired"]:
            print(f"EXPIRED  {e['ttl']}  {e['days_over']:>4} day(s) over  {e['type']}  {e['name']}  {e['id']}")
        for e in result["invalid"]:
            print(f"INVALID  {TAG}={e['ttl']!r}  {e['type']}  {e['name']}  {e['id']}")
        print(f"{len(result['expired'])} expired, {len(result['invalid'])} invalid, "
              f"{result['not_expired']} not expired ({TAG} before {result['today']} is expired)")
    return 1 if result["expired"] or result["invalid"] else 0


if __name__ == "__main__":
    sys.exit(main())
