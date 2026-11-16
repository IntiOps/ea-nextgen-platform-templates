"""Rendering contract v1 (tools/render_local.py). The platform renderer must pass the same fixture."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/render-contract.json").read_text())
spec = importlib.util.spec_from_file_location("render_local", ROOT / "tools/render_local.py")
render_local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_local)


@pytest.fixture
def rendered(tmp_path):
    out = tmp_path / "orders-api"
    record = render_local.render(ROOT / FIXTURE["package"], out, FIXTURE["values"])
    return out, record


def test_no_token_survives_and_names_follow_the_preset(rendered):
    out, record = rendered
    assert record["names"] == FIXTURE["expect"]["names"]
    leftovers = [p for p in out.rglob("*") if p.is_file() and render_local.TOKEN.search(p.read_text(errors="ignore"))]
    assert leftovers == []
    agents = (out / "AGENTS.md").read_text()
    assert all(text in agents for text in FIXTURE["expect"]["agents_md_contains"])


def test_pipelines_carry_the_environment_chain(rendered):
    out, _ = rendered
    cd = yaml.safe_load((out / "pipelines/azure-pipelines/cd.yml").read_text())
    ci = yaml.safe_load((out / "pipelines/azure-pipelines/ci.yml").read_text())
    params = {p["name"]: p["default"] for p in cd["parameters"]}
    assert params["environments"] == FIXTURE["expect"]["cd_environments"]
    assert params["service"] == params["artifactName"] == "orders-api"
    assert cd["resources"]["pipelines"][0]["source"] == "orders-api-ci"
    assert {p["name"]: p["default"] for p in ci["parameters"]}["artifactName"] == "orders-api"
    assert "      name: orders-api\n" in (out / "template.yaml").read_text()
    provenance = json.loads((out / ".ea/package.json").read_text())
    assert provenance["package_id"] == "fastapi-azure-webapp-split" and provenance["rendering_contract"] == "1"


def test_the_rendered_repository_passes_its_own_tests(rendered):
    """The service repo starts green: delivery contract, unit and API tests, architecture check."""
    out, _ = rendered
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=out,
                           capture_output=True, text=True)
    assert tests.returncode == 0, tests.stdout[-2000:]
    arch = subprocess.run([sys.executable, "tools/check_architecture.py"], cwd=out, capture_output=True, text=True)
    assert arch.returncode == 0, arch.stdout


@pytest.mark.parametrize("change, message", [
    ({"service": "Orders_API"}, "kebab-case"),
    ({"environments": [{"name": "dev", "purpose": "development"}]}, "resourceGroup"),
    ({"environments": [{"name": "dev", "purpose": "development", "resourceGroup": "rg", "infraMode": "shared"}]}, "existingPlanId"),
    ({"environments": [{"name": "dev", "purpose": "development", "resourceGroup": "rg", "infraMode": "bind"}]}, "appName"),
])
def test_invalid_values_are_refused(tmp_path, change, message):
    with pytest.raises(render_local.RenderError, match=message):
        render_local.render(ROOT / FIXTURE["package"], tmp_path / "out", {**FIXTURE["values"], **change})


def test_an_unknown_token_is_refused(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "template.yaml").write_text("id: x\nversion: 0.1.0\nvariants: []\n")
    (package / "README.md").write_text("Hello {{ea.nope}}\n")
    with pytest.raises(render_local.RenderError, match="unknown token"):
        render_local.render(package, tmp_path / "out", {"service": "orders-api"})


def test_infra_mode_defaults_to_new(tmp_path):
    values = {**FIXTURE["values"], "environments": [{"name": "dev", "purpose": "development", "resourceGroup": "rg-a-dev"}]}
    render_local.render(ROOT / FIXTURE["package"], tmp_path / "out", values)
    cd = yaml.safe_load((tmp_path / "out/pipelines/azure-pipelines/cd.yml").read_text())
    [env] = {p["name"]: p["default"] for p in cd["parameters"]}["environments"]
    assert env["infraMode"] == "new" and env["existingPlanId"] == "" and env["appName"] == ""
