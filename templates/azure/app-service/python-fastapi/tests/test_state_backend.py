"""The Terraform state backend comes from the environment's EA configuration, checked like EA does.

Only non-secret settings travel; anything else is refused. The generated block is `terraform fmt`
clean, the identity matches the one EA records, and the approved plan context binds it so apply
cannot run against different state.
"""
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "operations"))
spec = importlib.util.spec_from_file_location("state_backend", ROOT / "operations/state_backend.py")
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)

AZURERM = {"mode": "azurerm", "resource_group_name": "rg-state", "storage_account_name": "state123",
           "container_name": "tfstate", "key": "orders/dev.tfstate"}
S3 = {"mode": "s3", "bucket": "orders-state", "region": "eu-west-1", "key": "orders/dev.tfstate"}
REMOTE = {"mode": "remote", "organization": "acme", "workspace": "orders-dev"}


def _identity(config):
    fields = {k: v for k, v in config.items() if k != "mode"}
    return config["mode"] + ":" + hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("config", [AZURERM, S3, REMOTE])
def test_each_backend_is_accepted_with_eas_identity(config):
    parsed = sb.parse(dict(config))
    assert parsed["identity"] == _identity(config)
    assert sb.parse({**config, "identity": parsed["identity"]}) == parsed, "EA's stored identity is accepted"


@pytest.mark.parametrize("change", [
    {"access_key": "x"}, {"sas_token": "x"}, {"bucket": "other"},                       # secrets or another backend's field
    {"storage_account_name": "Bad_Name"}, {"container_name": "a--b"}, {"key": "../other.tfstate"},
    {"key": "a//b"}, {"key": ""}, {"mode": "local"}, {"identity": "azurerm:" + "0" * 64},
])
def test_what_ea_would_refuse_is_refused(change):
    with pytest.raises(sb.StateBackendError):
        sb.parse({**AZURERM, **change})


@pytest.mark.parametrize("change", [{"region": "Europe"}, {"bucket": "ab"}, {"bucket": "Orders_State"}])
def test_s3_names_are_checked(change):
    with pytest.raises(sb.StateBackendError):
        sb.parse({**S3, **change})


def test_errors_never_echo_values():
    with pytest.raises(sb.StateBackendError) as exc:
        sb.parse({**AZURERM, "client_secret": "s3cr3t-value"})
    assert "s3cr3t-value" not in str(exc.value)


def test_without_ea_configuration_the_original_backend_is_kept():
    env = {"TF_STATE_RESOURCE_GROUP": "rg-state", "TF_STATE_STORAGE_ACCOUNT": "state123", "TF_STATE_CONTAINER": "tfstate",
           "TF_VAR_owner_id": "42", "TF_VAR_instance": "demo"}
    config = sb.resolve(env)
    assert (config["mode"], config["key"]) == ("azurerm", "ea-demo/42/demo.tfstate")
    assert sb.resolve({**env, "EA_STATE_BACKEND_JSON": json.dumps(S3)})["mode"] == "s3", "EA's choice wins"
    with pytest.raises(sb.StateBackendError):
        sb.resolve({"EA_STATE_BACKEND_JSON": "{not json"})


@pytest.mark.parametrize("config", [AZURERM, S3, REMOTE])
def test_rendered_backend(config):
    text = sb.render(sb.parse(dict(config)))
    assert f'backend "{config["mode"]}"' in text
    for forbidden in ("access_key", "sas_token", "client_secret", "token =", "password"):
        assert forbidden not in text
    if config["mode"] == "azurerm":
        assert re.search(r"use_azuread_auth\s+= true", text), "Entra auth to the state account, never an access key"
    if config["mode"] == "s3":
        assert "encrypt" in text and "use_lockfile" in text, "S3 state is encrypted and locked natively (Terraform >= 1.10)"


@pytest.mark.skipif(shutil.which("terraform") is None, reason="terraform not installed")
@pytest.mark.parametrize("config", [AZURERM, S3, REMOTE])
def test_rendered_backend_is_fmt_clean(tmp_path, config):
    sb.write(tmp_path, sb.parse(dict(config)))
    result = subprocess.run(["terraform", "fmt", "-check", "-diff", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_write_is_atomic_and_leaves_nothing_behind(tmp_path):
    (tmp_path / sb.OUTPUT).write_text("old")
    sb.write(tmp_path, sb.parse(dict(S3)))
    assert sorted(p.name for p in tmp_path.iterdir()) == [sb.OUTPUT]
    assert 'backend "s3"' in (tmp_path / sb.OUTPUT).read_text()


def test_terraform_has_no_hard_coded_backend_and_init_uses_the_generated_one():
    main = (ROOT / "infra/terraform/main.tf").read_text()
    assert 'backend "' not in main
    init = (ROOT / "operations/init.sh").read_text()
    assert "state_backend.py\" write" in init and "-backend-config" not in init
    assert "TF_TOKEN_app_terraform_io:?" in init, "HCP state needs the runner token, checked before init"


def test_the_approved_context_binds_the_state_backend(monkeypatch):
    context_spec = importlib.util.spec_from_file_location("ctx_state", ROOT / "operations/context.py")
    context = importlib.util.module_from_spec(context_spec)
    context_spec.loader.exec_module(context)
    for field in context.FIELDS:
        monkeypatch.setenv(field, "fixture")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("TF_VAR_instance", "demo")
    monkeypatch.setenv("DEMO_OPERATION", "deploy")
    monkeypatch.setenv("EA_STATE_BACKEND_JSON", json.dumps(AZURERM))
    planned = context.current()
    assert planned["STATE_BACKEND_IDENTITY"] == _identity(AZURERM)
    monkeypatch.setenv("EA_STATE_BACKEND_JSON", json.dumps(S3))
    assert context.current() != planned, "apply against another backend no longer matches the approved plan"
