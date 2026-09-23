import importlib.util
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_application_health_identifies_revision():
    module = load("demo_app", "app/main.py")
    response = TestClient(module.app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "revision": module.REVISION}


def test_archive_is_deterministic_and_contains_commit(tmp_path):
    package = load("demo_package", "operations/package.py")
    first, second = tmp_path / "one.zip", tmp_path / "two.zip"
    package.build(ROOT / "app", first, "a" * 40)
    package.build(ROOT / "app", second, "a" * 40)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == {"main.py", "requirements.txt", "build-info.json"}
        assert json.loads(archive.read("build-info.json"))["revision"] == "a" * 40


def test_wrong_deployed_commit_is_not_success():
    smoke = load("demo_smoke", "tests/smoke.py")
    assert not smoke.verify({"status": "ok", "revision": "old"}, "new")
    assert not smoke.verify({"status": "error", "revision": "new"}, "new")
    assert smoke.verify({"status": "ok", "revision": "new"}, "new")


@pytest.fixture
def context(monkeypatch):
    module = load("demo_context", "operations/context.py")
    for field in module.FIELDS:
        monkeypatch.setenv(field, "fixture")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("TF_VAR_instance", "demo")
    monkeypatch.setenv("DEMO_OPERATION", "deploy")
    return module


def test_destroy_requires_exact_instance_confirmation(context, monkeypatch):
    monkeypatch.setenv("DEMO_OPERATION", "destroy")
    monkeypatch.setenv("DEMO_CONFIRMATION", "destroy other")
    with pytest.raises(ValueError):
        context.current()
    monkeypatch.setenv("DEMO_CONFIRMATION", "destroy demo")
    assert context.current()["DEMO_OPERATION"] == "destroy"


def test_changed_plan_and_cloud_context_are_detected(context, monkeypatch, tmp_path):
    (tmp_path / "tfplan").write_bytes(b"plan")
    (tmp_path / "application.zip").write_bytes(b"application")
    before = context.record(tmp_path)
    (tmp_path / "tfplan").write_bytes(b"other plan")
    assert before != context.record(tmp_path)
    (tmp_path / "tfplan").write_bytes(b"plan")
    monkeypatch.setenv("ARM_SUBSCRIPTION_ID", "another-subscription")
    assert before != context.record(tmp_path)


def test_only_main_can_execute(context, monkeypatch):
    monkeypatch.setenv("GITHUB_REF", "refs/heads/unreviewed")
    with pytest.raises(ValueError):
        context.current()


def test_unprotected_environment_cannot_authorize_deploy():
    approval = load("demo_approval", "operations/approval.py")
    assert not approval.protected({})
    assert not approval.protected({"protection_rules": [{"type": "required_reviewers", "reviewers": [{"id": 1}], "prevent_self_review": False}]})
    assert approval.protected({"protection_rules": [{"type": "required_reviewers", "reviewers": [{"id": 1}], "prevent_self_review": True}]})


@pytest.mark.parametrize("change,operation", [
    ({"address": "azurerm_storage_account.shared", "change": {"actions": ["delete"]}}, "destroy"),
    ({"address": "azurerm_linux_web_app.demo", "change": {"actions": ["delete", "create"]}}, "deploy"),
    ({"address": "azurerm_linux_web_app.demo", "change": {"actions": ["delete"], "before": {"id": "/subscriptions/other/resourceGroups/shared"}}}, "destroy"),
])
def test_plan_cannot_destroy_unrelated_or_unapproved_resources(change, operation):
    guard = load("demo_plan", "operations/check_plan.py")
    with pytest.raises(ValueError):
        guard.validate({"resource_changes": [change]}, "subscription", "123", "demo", operation)
