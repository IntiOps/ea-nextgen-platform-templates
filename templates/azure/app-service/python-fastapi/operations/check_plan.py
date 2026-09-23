"""Restrict the demo's plan to its three owned resources before asking for approval."""
import hashlib
import json
import os
import sys
from pathlib import Path


def validate(plan, subscription, owner, instance, operation):
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    group = f"rg-ea-demo-{instance}-{digest(owner)[:6]}"
    app = f"ea-{instance}-{digest(f'{subscription}:{owner}:{instance}')[:8]}"
    base = f"/subscriptions/{subscription}/resourceGroups/{group}"
    expected = {
        "azurerm_resource_group.demo": base,
        "azurerm_service_plan.demo": f"{base}/providers/Microsoft.Web/serverFarms/{app}-plan",
        "azurerm_linux_web_app.demo": f"{base}/providers/Microsoft.Web/sites/{app}",
    }
    for change in plan.get("resource_changes", []):
        address = change.get("address")
        if address not in expected:
            raise ValueError("plan includes resources outside this demo")
        values = change.get("change", {})
        if "delete" in values.get("actions", []) and operation != "destroy":
            raise ValueError("destructive changes require an explicit cleanup run")
        identifier = (values.get("before") or {}).get("id")
        if identifier and identifier.lower() != expected[address].lower():
            raise ValueError("existing resource does not belong to this demo instance")


if __name__ == "__main__":
    validate(json.loads(Path(sys.argv[1]).read_text()), os.environ["ARM_SUBSCRIPTION_ID"], os.environ["TF_VAR_owner_id"], os.environ["TF_VAR_instance"], os.environ["DEMO_OPERATION"])
