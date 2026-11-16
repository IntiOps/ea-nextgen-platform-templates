"""operations/ttl_report.py: which Azure groups and resources have outlived their ea-ttl tag (P4-05)."""
import io
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "operations"))

import ttl_report  # noqa: E402

TODAY = date(2026, 11, 17)
SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"
GROUPS = [
    {"id": f"{SUB}/resourceGroups/rg-old", "name": "rg-old", "type": "Microsoft.Resources/resourceGroups",
     "tags": {"ea-ttl": "2026-11-01"}},
    {"id": f"{SUB}/resourceGroups/rg-today", "name": "rg-today", "type": "Microsoft.Resources/resourceGroups",
     "tags": {"ea-ttl": "2026-11-17"}},
    {"id": f"{SUB}/resourceGroups/rg-forever", "name": "rg-forever", "type": "Microsoft.Resources/resourceGroups",
     "tags": None},
]
RESOURCES = [
    {"id": f"{SUB}/resourceGroups/rg-a/providers/Microsoft.Web/sites/app", "name": "app",
     "type": "Microsoft.Web/sites", "tags": {"EA-TTL": "2026-11-16", "managed_by": "ea-nextgen-template"}},
    {"id": f"{SUB}/resourceGroups/rg-a/providers/Microsoft.Web/serverfarms/plan", "name": "plan",
     "type": "Microsoft.Web/serverfarms", "tags": {"ea-ttl": "next week"}},
    {"id": f"{SUB}/resourceGroups/rg-a/providers/Microsoft.App/containerApps/ca", "name": "ca",
     "type": "Microsoft.App/containerApps", "tags": {"ea-ttl": "2027-01-01"}},
]


def _names(entries):
    return [e["name"] for e in entries]


def test_only_a_ttl_before_today_is_expired():
    result = ttl_report.report(GROUPS + RESOURCES, TODAY)
    assert _names(result["expired"]) == ["rg-old", "app"]
    assert [e["days_over"] for e in result["expired"]] == [16, 1]
    assert result["not_expired"] == 2, "the last day (today) and future dates are not expired"
    assert result["today"] == "2026-11-17"


@pytest.mark.parametrize("value", ["next week", "2026/11/01", "20261101", "2026-W45-1", "2026-13-01", "", "1"])
def test_an_unreadable_ttl_is_reported_as_invalid(value):
    item = {"id": "/x", "name": "x", "type": "t", "tags": {"ea-ttl": value}}
    result = ttl_report.report([item], TODAY)
    assert _names(result["invalid"]) == ["x"] and result["expired"] == []


def test_the_same_item_from_two_listings_is_reported_once():
    result = ttl_report.report(GROUPS + [dict(GROUPS[0], id=GROUPS[0]["id"].upper())], TODAY)
    assert _names(result["expired"]) == ["rg-old"]


def test_cli_reads_files_and_exits_1_when_anything_expired(tmp_path, capsys):
    groups, resources = tmp_path / "groups.json", tmp_path / "resources.json"
    groups.write_text(json.dumps(GROUPS))
    resources.write_text(json.dumps(RESOURCES))
    assert ttl_report.main([str(groups), str(resources), "--today", "2026-11-17", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert _names(out["expired"]) == ["rg-old", "app"] and _names(out["invalid"]) == ["plan"]


def test_cli_exits_0_when_nothing_expired(tmp_path, capsys):
    path = tmp_path / "groups.json"
    path.write_text(json.dumps(GROUPS))
    assert ttl_report.main([str(path), "--today", "2026-10-01"]) == 0
    assert "0 expired, 0 invalid, 2 not expired" in capsys.readouterr().out


def test_cli_reads_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(RESOURCES)))
    assert ttl_report.main(["--today", "2026-11-17"]) == 1
    out = capsys.readouterr().out
    assert "EXPIRED  2026-11-16" in out and "INVALID  ea-ttl='next week'" in out


@pytest.mark.parametrize("content", ["not json", json.dumps({"value": []})])
def test_unreadable_input_exits_2(tmp_path, content):
    path = tmp_path / "x.json"
    path.write_text(content)
    assert ttl_report.main([str(path)]) == 2


def test_runs_as_a_script_with_the_standard_library_only():
    run = subprocess.run([sys.executable, "-I", str(ROOT / "operations/ttl_report.py"), "-", "--today", "2026-11-17"],
                         input="[]", capture_output=True, text=True)
    assert run.returncode == 0 and "0 expired" in run.stdout
    source = (ROOT / "operations/ttl_report.py").read_text()
    imports = {line.split()[1].split(".")[0] for line in source.splitlines() if line.startswith(("import ", "from "))}
    assert imports <= {"__future__", "argparse", "json", "re", "sys", "datetime", "pathlib"}
