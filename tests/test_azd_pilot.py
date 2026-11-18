"""The developer azd path shares the Bicep entrypoint with governed split delivery."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "templates/azure/container-apps/python-fastapi-split"


def test_azd_pilot_declares_the_same_bicep_as_split_delivery():
    manifest = yaml.safe_load((PACKAGE / "template.yaml").read_text())
    schema = json.loads((ROOT / "schemas/template.schema.json").read_text())
    assert "1.3" in schema["properties"]["schema_version"]["enum"]
    assert "developer_loop" in schema["$defs"]["Variant"]["properties"]
    variant = manifest["variants"][0]
    azd = yaml.safe_load((PACKAGE / variant["developer_loop"]["file"]).read_text())
    entrypoint = f"{azd['infra']['path']}/{azd['infra']['module']}.bicep"
    assert variant["developer_loop"] == {"tool": "azd", "file": "azure.yaml"}
    assert entrypoint in variant["files"]["infrastructure"]
    assert entrypoint == "infra/bicep/main.bicep"
    assert 'cp "${{ parameters.packageRoot }}"/infra/bicep/*.bicep "$out/infra/"' in (
        PACKAGE / variant["delivery"]["ci_pipeline"]
    ).read_text()
    assert 'delivery/infra/main.bicep' in (PACKAGE / variant["delivery"]["cd_pipeline"]).read_text()
    assert "targetScope = 'resourceGroup'" in (PACKAGE / entrypoint).read_text()


def test_azd_pilot_is_sandbox_only_and_has_no_hooks_or_pipeline_setup():
    azd_text = (PACKAGE / "azure.yaml").read_text()
    azd = yaml.safe_load(azd_text)
    params = json.loads((PACKAGE / "infra/bicep/main.parameters.json").read_text())["parameters"]
    bicep = (PACKAGE / "infra/bicep/main.bicep").read_text()
    required = set(re.findall(r"(?m)^param\s+(\w+)\s+[^\n=]+$", bicep))
    assert required <= set(params)
    assert params["purpose"]["value"] == "development"
    assert params["azdServiceName"]["value"] == "api"
    assert params["image"]["value"] == "${AZD_BOOTSTRAP_IMAGE}"
    assert azd["services"]["api"]["docker"]["registry"] == "${AZD_REGISTRY_SERVER}"
    assert "hooks" not in azd_text and "pipeline config" not in azd_text
    assert "'azd-service-name': azdServiceName" in (PACKAGE / "infra/bicep/app.bicep").read_text()
    assert "param azdServiceName string = ''" in bicep
