"""The gated cleanup contract (P4-05), checked against pipelines/azure-pipelines/cleanup.yml itself.

The cleanup may delete only what this template created in one environment: resources in that
environment's resource group tagged BOTH managed_by=ea-nextgen-template AND instance=<service>-<env>,
listed before the approval, unchanged after it, dependents first. Never the resource group, never
anything in infraMode bind, never an id typed by hand.
"""
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "operations"))

import cleanup_resources  # noqa: E402

CLEANUP_PATH = ROOT / "pipelines/azure-pipelines/cleanup.yml"
CLEANUP = yaml.safe_load(CLEANUP_PATH.read_text())
TEXT = CLEANUP_PATH.read_text()
CD = yaml.safe_load((ROOT / "pipelines/azure-pipelines/cd.yml").read_text())
VARIANT = yaml.safe_load((ROOT / "template.yaml").read_text())["variants"][0]
#: The key that names the platform-owned resource an app joins in infraMode shared.
SHARED_KEY = {"azure_web_app": "existingPlanId", "azure_container_apps": "existingEnvironmentId"}[VARIANT["runtime"]]
APP_TYPE = {"azure_web_app": "Microsoft.Web/sites", "azure_container_apps": "Microsoft.App/containerApps"}[VARIANT["runtime"]]
TAG_FILTER = "[?tags.managed_by=='ea-nextgen-template' && tags.instance=='$INSTANCE']"

[LOOP] = CLEANUP["stages"]
[(LOOP_KEY, BRANCHES)] = LOOP.items()
BIND = next(v for b in BRANCHES for k, v in b.items() if k == "${{ if eq(env.infraMode, 'bind') }}")
OWNED = next(v for b in BRANCHES for k, v in b.items() if k == "${{ if ne(env.infraMode, 'bind') }}")
STAGES = {stage["stage"].split("_${{")[0]: stage for stage in OWNED}


def _steps(job):
    return job["strategy"]["runOnce"]["deploy"]["steps"] if "strategy" in job else job["steps"]


def _jobs():
    return [job for stage in OWNED for job in stage["jobs"]]


def _cli_tasks():
    return [step for job in _jobs() for step in _steps(job) if step.get("task", "").startswith("AzureCLI@")]


def _commands(script):
    """Shell commands with their backslash continuations joined."""
    return [line.strip() for line in script.replace("\\\n", " ").splitlines() if line.strip()]


def _delete_task():
    [task] = [step for step in _steps(STAGES["delete"]["jobs"][0]) if step.get("task", "").startswith("AzureCLI@")]
    return task


# ── Pipeline shape ────────────────────────────────────────────────────────────────────────────


def test_cleanup_never_runs_by_itself():
    assert CLEANUP["trigger"] == "none" and CLEANUP["pr"] == "none"
    assert "schedules" not in CLEANUP and "resources" not in CLEANUP


def test_parameters_mirror_cd_and_require_a_confirmation():
    params = {p["name"]: p for p in CLEANUP["parameters"]}
    assert set(params) == {"service", "environments", "confirm"}
    assert params["confirm"]["type"] == "string" and params["confirm"]["default"] == ""
    cd = {p["name"]: p["default"] for p in CD["parameters"]}
    assert params["service"]["default"] == cd["service"]
    assert LOOP_KEY == "${{ each env in parameters.environments }}"
    for mine, theirs in zip(params["environments"]["default"], cd["environments"], strict=True):
        for key in ("name", "azureEnvironment", "serviceConnection", "resourceGroup"):
            assert mine[key] == theirs[key], key
        assert {"infraMode", SHARED_KEY, "appName"} <= set(mine)


def test_there_is_no_group_delete_and_one_delete_command():
    assert "group delete" not in TEXT and "az group" not in TEXT
    deletes = [c for t in _cli_tasks() for c in _commands(t["inputs"]["inlineScript"]) if re.search(r"\bdelete\b", c)
               and c.startswith("az ")]
    assert deletes == ['az resource delete --ids "$id"']


def test_every_tag_filter_names_both_tags_and_the_environment_resource_group():
    for task in _cli_tasks():
        assert task["env"]["RESOURCE_GROUP"] == "${{ env.resourceGroup }}"
        assert task["env"]["INSTANCE"] == "${{ parameters.service }}-${{ env.name }}"
        assert task["inputs"]["azureSubscription"] == "${{ env.serviceConnection }}"
        lists = [c for c in _commands(task["inputs"]["inlineScript"]) if c.startswith("az ")and " list " in c + " "]
        assert lists
        for command in lists:
            assert command.startswith('az resource list --resource-group "$RESOURCE_GROUP"'), command
            assert f'--query "{TAG_FILTER}' in command, command
    assert TEXT.count("az resource list") == TEXT.count(TAG_FILTER) == 3


def test_every_deleted_id_comes_from_the_tag_filtered_query():
    commands = _commands(_delete_task()["inputs"]["inlineScript"])
    query = next(i for i, c in enumerate(commands) if c.startswith("az resource list") and c.endswith('> "$work/current.json"'))
    plan = next(i for i, c in enumerate(commands) if "cleanup_resources.py plan" in c)
    loop = commands.index('while read -r id; do')
    delete = commands.index('az resource delete --ids "$id"')
    assert query < plan < loop < delete
    assert commands[plan].startswith('python3 operations/cleanup_resources.py plan "$APPROVED" "$work/current.json"')
    assert commands[plan].endswith('> "$work/ids.txt"')
    assert commands[delete + 1] == 'done < "$work/ids.txt"'
    assert TEXT.count("--ids") == 1, "no other command takes resource ids"


def test_confirm_is_checked_first_in_every_job_before_any_cloud_step():
    for job in _jobs():
        steps = _steps(job)
        first_cli = next(i for i, s in enumerate(steps) if s.get("task", "").startswith("AzureCLI@"))
        assert steps[0]["env"] == {"CONFIRM": "${{ parameters.confirm }}", "EXPECTED": "delete ${{ parameters.service }}"}
        assert '[ "$CONFIRM" != "$EXPECTED" ]' in steps[0]["bash"] and "exit 1" in steps[0]["bash"]
        assert 0 < first_cli


@pytest.mark.parametrize("confirm, ok", [("delete orders-api", True), ("delete orders-api ", False),
                                         ("Delete orders-api", False), ("delete", False), ("", False),
                                         ("delete other-api", False)])
def test_the_confirm_check_accepts_only_the_exact_phrase(confirm, ok):
    script = _steps(STAGES["list"]["jobs"][0])[0]["bash"]
    run = subprocess.run(["bash", "-c", script], env={"PATH": os.environ["PATH"], "CONFIRM": confirm,
                                                      "EXPECTED": "delete orders-api"}, capture_output=True, text=True)
    assert (run.returncode == 0) is ok


def test_the_list_runs_unprotected_and_the_delete_waits_for_the_environment_approval():
    [listing] = STAGES["list"]["jobs"]
    assert "job" in listing and "environment" not in listing and "deployment" not in listing
    assert STAGES["list"]["dependsOn"] == []
    delete_stage = STAGES["delete"]
    assert delete_stage["dependsOn"] == STAGES["list"]["stage"]
    [job] = delete_stage["jobs"]
    assert job["deployment"] == "delete" and job["environment"] == "${{ env.azureEnvironment }}"
    assert delete_stage["lockBehavior"] == "sequential"


def test_the_delete_compares_with_exactly_the_published_list():
    publish = next(s for s in _steps(STAGES["list"]["jobs"][0]) if "publish" in s)
    download = next(s for s in _steps(STAGES["delete"]["jobs"][0]) if "download" in s)
    assert download == {"download": "current", "artifact": publish["artifact"]}
    assert publish["artifact"] == "cleanup-${{ env.name }}" and publish["publish"] == "$(Pipeline.Workspace)/cleanup-${{ env.name }}"
    assert _delete_task()["env"]["APPROVED"] == "$(Pipeline.Workspace)/cleanup-${{ env.name }}/resources.json"


def test_shared_mode_refuses_the_platform_resource():
    for task in _cli_tasks():
        assert task["env"]["KEEP"] == f"${{{{ env.{SHARED_KEY} }}}}"
        assert '--keep "$KEEP"' in task["inputs"]["inlineScript"]


def test_bind_environments_are_skipped_with_a_message():
    [stage] = BIND
    assert stage["stage"].startswith("skip_") and stage["dependsOn"] == []
    steps = [s for job in stage["jobs"] for s in job["steps"]]
    assert all("task" not in s for s in steps) and "az " not in json.dumps(steps)
    assert any("owns nothing" in s.get("bash", "") for s in steps)


def test_stage_names_are_safe_for_any_environment_name():
    for stage in [*OWNED, *BIND]:
        assert "${{ replace(env.name, '-', '_') }}" in stage["stage"]


# ── What may be deleted, and in which order ───────────────────────────────────────────────────

RG = "rg-orders-dev"
SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"


def _res(rtype, name, instance="orders-api-dev", managed_by="ea-nextgen-template", group=RG):
    return {"id": f"{SUB}/resourceGroups/{group}/providers/{rtype}/{name}", "name": name, "type": rtype,
            "tags": {"managed_by": managed_by, "instance": instance, "purpose": "development"}}


WEB = [_res("Microsoft.Web/serverfarms", "ea-plan"), _res("Microsoft.Web/sites", "ea-app")]
CAPPS = [_res("Microsoft.OperationalInsights/workspaces", "ea-logs"),
         _res("Microsoft.App/managedEnvironments", "ea-env"), _res("Microsoft.App/containerApps", "ea-app")]
RULES = {"instance": "orders-api-dev", "resource_group": RG, "keep": []}


def test_dependents_are_deleted_first():
    order = cleanup_resources.DELETE_ORDER
    assert order[APP_TYPE.lower()] == 0
    assert [i.rsplit("/", 1)[1] for i in cleanup_resources.ordered(WEB)] == ["ea-app", "ea-plan"]
    assert [i.rsplit("/", 1)[1] for i in cleanup_resources.ordered(CAPPS)] == ["ea-app", "ea-env", "ea-logs"]


@pytest.mark.parametrize("item, reason", [
    (_res("Microsoft.Web/sites", "x", managed_by="someone"), "managed_by"),
    (_res("Microsoft.Web/sites", "x", instance="orders-api-prod"), "instance"),
    (_res("Microsoft.Web/sites", "x", group="rg-other"), "resource group"),
    (_res("Microsoft.Storage/storageAccounts", "x"), "not created by this template"),
    ({"id": f"{SUB}/resourceGroups/{RG}", "type": "Microsoft.Resources/resourceGroups",
      "tags": {"managed_by": "ea-nextgen-template", "instance": "orders-api-dev"}}, "resource group"),
    ({"id": 3, "type": "x"}, "not a resource"),
])
def test_anything_the_query_should_not_have_returned_is_refused(item, reason):
    with pytest.raises(cleanup_resources.CleanupRefused, match=reason):
        cleanup_resources.check([*WEB, item], **RULES)


def test_the_shared_platform_resource_is_refused_even_if_tagged():
    with pytest.raises(cleanup_resources.CleanupRefused, match="never deleted"):
        cleanup_resources.check(WEB, **{**RULES, "keep": [WEB[0]["id"].upper()]})


def test_tags_and_ids_compare_the_way_azure_does():
    item = _res("Microsoft.Web/sites", "ea-app")
    item["tags"] = {"Managed_By": "ea-nextgen-template", "INSTANCE": "orders-api-dev"}
    cleanup_resources.check([item], **{**RULES, "resource_group": RG.upper()})
    cleanup_resources.compare(WEB, [{**w, "id": w["id"].lower()} for w in WEB])


@pytest.mark.parametrize("current", [WEB[:1], [*WEB, _res("Microsoft.Web/sites", "ea-new")]])
def test_a_set_that_changed_after_approval_is_refused(current):
    with pytest.raises(cleanup_resources.CleanupRefused, match="changed since the approved list"):
        cleanup_resources.compare(WEB, current)


# ── The delete script, run against a fake az ──────────────────────────────────────────────────

FAKE_AZ = r'''
import json, os, re, sys
state_path = os.environ["FAKE_AZ_STATE"]
state = json.load(open(state_path))
args = sys.argv[1:]
with open(os.environ["FAKE_AZ_LOG"], "a") as log:
    log.write(" ".join(args) + "\n")
if args[:2] == ["resource", "list"]:
    query = args[args.index("--query") + 1]
    managed = re.search(r"tags.managed_by=='([^']*)'", query).group(1)
    instance = re.search(r"tags.instance=='([^']*)'", query).group(1)
    group = args[args.index("--resource-group") + 1]
    hits = [r for r in state if (r.get("tags") or {}).get("managed_by") == managed
            and (r.get("tags") or {}).get("instance") == instance and f"/resourceGroups/{group}/" in r["id"]]
    if query.endswith("].id"):
        sys.stdout.write("".join(r["id"] + "\n" for r in hits))
    else:
        print(json.dumps(hits))
elif args[:2] == ["resource", "delete"]:
    rid = args[args.index("--ids") + 1]
    json.dump([r for r in state if r["id"] != rid], open(state_path, "w"))
else:
    sys.exit(f"unexpected az call: {args}")
'''


def _run_delete(tmp_path, approved, cloud):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    az = bin_dir / "az"
    az.write_text(f"#!{sys.executable}\n{FAKE_AZ}")
    az.chmod(az.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "state.json").write_text(json.dumps(cloud))
    (tmp_path / "approved.json").write_text(json.dumps(approved))
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_AZ_STATE": str(tmp_path / "state.json"),
           "FAKE_AZ_LOG": str(tmp_path / "az.log"), "RESOURCE_GROUP": RG, "INSTANCE": "orders-api-dev",
           "KEEP": "", "APPROVED": str(tmp_path / "approved.json"), "TMPDIR": str(tmp_path)}
    run = subprocess.run(["bash", "-c", _delete_task()["inputs"]["inlineScript"]], cwd=ROOT, env=env,
                         capture_output=True, text=True)
    deleted = [line.split("--ids ", 1)[1] for line in (tmp_path / "az.log").read_text().splitlines()
               if line.startswith("resource delete")]
    return run, deleted, json.loads((tmp_path / "state.json").read_text())


def test_the_delete_script_removes_exactly_the_approved_set_dependents_first(tmp_path):
    other = [_res("Microsoft.Web/sites", "neighbour", instance="billing-dev"),
             {**_res("Microsoft.Web/sites", "untagged"), "tags": None},
             _res("Microsoft.Web/sites", "prod-app", instance="orders-api-prod")]
    run, deleted, left = _run_delete(tmp_path, approved=CAPPS, cloud=[*CAPPS, *other])
    assert run.returncode == 0, run.stderr
    assert [d.rsplit("/", 1)[1] for d in deleted] == ["ea-app", "ea-env", "ea-logs"]
    assert left == other


def test_the_delete_script_deletes_nothing_when_the_set_changed(tmp_path):
    extra = _res("Microsoft.App/containerApps", "ea-sneaky")
    run, deleted, left = _run_delete(tmp_path, approved=CAPPS, cloud=[*CAPPS, extra])
    assert run.returncode != 0 and "changed since the approved list" in run.stderr
    assert deleted == [] and len(left) == 4


def test_the_delete_script_with_an_empty_approved_list_deletes_nothing(tmp_path):
    run, deleted, _ = _run_delete(tmp_path, approved=[], cloud=[])
    assert run.returncode == 0 and deleted == []
