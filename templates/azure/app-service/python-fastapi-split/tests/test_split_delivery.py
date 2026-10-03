"""The separated CI/CD contract, checked against the pipeline files themselves (SPLIT-T1).

Each test names the rule of docs/v2/TABLERO.md «Contrato mínimo de CI/CD separados» it pins. These run
in the CI producer before anything is built, so a change that breaks a rule stops the pipeline.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "operations"))

import package  # noqa: E402
import verify_artifact  # noqa: E402

REVISION = "a" * 40


def _load(relative):
    return yaml.safe_load((ROOT / relative).read_text())


MANIFEST = _load("template.yaml")
VARIANT = MANIFEST["variants"][0]
DELIVERY = VARIANT["delivery"]
CI = _load(DELIVERY["ci_pipeline"])
CD = _load(DELIVERY["cd_pipeline"])
CD_TEXT = (ROOT / DELIVERY["cd_pipeline"]).read_text()
CI_TEXT = (ROOT / DELIVERY["ci_pipeline"]).read_text()


def _steps(job):
    if "strategy" in job:
        return job["strategy"]["runOnce"]["deploy"]["steps"]
    return job["steps"]


def _cd_stages():
    [loop] = CD["stages"]
    [stages] = loop.values()
    return stages


def _cd_jobs():
    return {job.get("job") or job.get("deployment"): job for stage in _cd_stages() for job in stage["jobs"]}


# ── Manifest ──────────────────────────────────────────────────────────────────────────────────


def test_manifest_declares_the_split_and_its_files_exist():
    assert MANIFEST["schema_version"] == "1.2" and DELIVERY["topology"] == "split_ci_cd"
    assert DELIVERY["ci_pipeline"] == VARIANT["files"]["pipeline"], "the stored pipeline is the CI producer"
    assert DELIVERY["ci_pipeline"] != DELIVERY["cd_pipeline"]
    for path in (DELIVERY["ci_pipeline"], DELIVERY["cd_pipeline"], *VARIANT["files"]["application"], *VARIANT["files"]["infrastructure"]):
        assert (ROOT / path).is_file(), path
    assert VARIANT["cicd_provider"] == "azure_pipelines"


def test_artifact_name_is_the_same_everywhere():
    name = DELIVERY["artifact"]["name"]
    ci_params = {p["name"]: p.get("default") for p in CI["parameters"]}
    cd_params = {p["name"]: p.get("default") for p in CD["parameters"]}
    assert ci_params["artifactName"] == cd_params["artifactName"] == name
    assert DELIVERY["artifact"]["kind"] == "application_package"


# ── Rule 1: two definitions; Rule 4: declared activation, no double trigger ───────────────────


def test_ci_builds_and_never_deploys():
    assert CI["trigger"]["branches"]["include"] and CI["pr"]["branches"]["include"]
    assert "deployment:" not in CI_TEXT and "AzureCLI" not in CI_TEXT and "azureSubscription" not in CI_TEXT
    assert CI_TEXT.count("operations/package.py") == 1, "built exactly once"
    assert "persistCredentials: false" in CI_TEXT


def test_cd_runs_only_from_a_ci_run_never_on_push():
    assert CD["trigger"] == "none" and CD["pr"] == "none"
    [resource] = CD["resources"]["pipelines"]
    assert resource["pipeline"] == "ci" and resource["source"]
    assert resource["trigger"]["branches"]["include"], "completion activation needs explicit branch filters"
    assert CD["resources"]["pipelines"][0]["source"] != "self"


# ── Rule 3 and 6: the same bytes, never rebuilt, never "latest" ───────────────────────────────


def test_cd_never_builds_or_checks_out_source():
    for forbidden in ("package.py", "checkout: self", "latest", "app/requirements.txt"):
        assert forbidden not in CD_TEXT, forbidden
    # The only install CD may run is the pinned runner transport dependencies (ART-T1), never the app's.
    assert CD_TEXT.count("pip install") == CD_TEXT.count("-r \"$(Pipeline.Workspace)/ci/delivery/operations/transport-requirements.txt\"")
    jobs = _cd_jobs()
    assert _steps(jobs["plan"])[0] == {"checkout": "none"}


def test_every_download_comes_from_the_ci_run():
    downloads = [step for job in _cd_jobs().values() for step in _steps(job) if "download" in step]
    assert downloads and all(step["download"] == "ci" for step in downloads)


def test_artifact_is_verified_before_any_cloud_step_in_every_job():
    for name, job in _cd_jobs().items():
        steps = _steps(job)
        verify = next(i for i, s in enumerate(steps) if "verify_artifact.py" in str(s.get("bash", "")))
        cloud = [i for i, s in enumerate(steps) if s.get("task", "").startswith("AzureCLI")]
        assert cloud and verify < min(cloud), name


# ── Rule 5 and 6: per-environment preview, approval, apply ────────────────────────────────────


def test_the_preview_runs_in_its_own_stage_before_the_approval():
    """Azure DevOps evaluates an environment's approvals when the stage that uses it starts. The preview
    must therefore live in an earlier stage that uses no protected environment, or approvers never see it."""
    plan, promote = _cd_stages()
    assert plan["stage"].startswith("plan_") and promote["stage"].startswith("promote_")
    assert "environment" not in str(plan["jobs"]), "the preview stage must not wait for an approval"
    assert all("deployment" not in job for job in plan["jobs"])
    assert "what-if" in str(plan["jobs"])
    assert promote["dependsOn"] == plan["stage"]
    [apply] = promote["jobs"]
    assert apply["environment"] == "${{ env.azureEnvironment }}"
    assert "sub create" in str(_steps(apply)) and "webapp deploy" in str(_steps(apply))


def test_promotions_to_one_environment_run_one_at_a_time():
    _plan, promote = _cd_stages()
    assert promote["lockBehavior"] == "sequential"


def test_stage_names_are_safe_for_any_environment_name():
    for stage in _cd_stages():
        assert "replace(env.name, '-', '_')" in stage["stage"], "Azure stage ids allow only letters, digits and _"


def test_every_cloud_step_uses_its_environment_identity():
    cloud = [step for job in _cd_jobs().values() for step in _steps(job) if step.get("task", "").startswith("AzureCLI")]
    assert len(cloud) == 3
    assert all(step["inputs"]["azureSubscription"] == "${{ env.serviceConnection }}" for step in cloud), "per-environment identity"


def test_default_chain_approves_production():
    envs = {p["name"]: p for p in CD["parameters"]}["environments"]["default"]
    assert [e["name"] for e in envs] == ["dev", "prod"]
    assert len({e["serviceConnection"] for e in envs}) == len(envs), "no identity shared across environments"


def test_app_service_does_not_rebuild_the_package():
    web = (ROOT / "infra/bicep/web.bicep").read_text()
    assert "'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'false'" in web and "'ENABLE_ORYX_BUILD', value: 'false'" in web


# ── The build and the verifier ────────────────────────────────────────────────────────────────


def _build(tmp_path, name="a.zip", build_id="42"):
    return package.build(ROOT / "app", tmp_path / name, revision=REVISION, build_id=build_id)


def test_package_is_deterministic_and_records_its_run(tmp_path):
    assert _build(tmp_path, "a.zip") == _build(tmp_path, "b.zip")
    with zipfile.ZipFile(tmp_path / "a.zip") as archive:
        info = json.loads(archive.read("build-info.json"))
    assert info == {"revision": REVISION, "build_id": "42"}
    with pytest.raises(ValueError):
        package.build(ROOT / "app", tmp_path / "c.zip", revision="main", build_id="42")


def _manifest(tmp_path, digest, **overrides):
    data = {**package.manifest(name="fastapi-webapp", revision=REVISION, build_id="42", digest=digest), **overrides}
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(data))
    return path


def test_verifier_accepts_only_the_exact_artifact(tmp_path):
    zip_path = tmp_path / "app.zip"
    digest = package.build(ROOT / "app", zip_path, revision=REVISION, build_id="42")
    manifest = _manifest(tmp_path, digest)
    assert verify_artifact.verify(zip_path, manifest, revision=REVISION, build_id="42", expected_digest=digest)["status"] == "verified"

    for kwargs in ({"revision": "b" * 40, "build_id": "42"},  # manifest from another commit
                   {"revision": REVISION, "build_id": "43"},  # manifest from another run
                   {"revision": REVISION, "build_id": "42", "expected_digest": "0" * 64}):  # not what EA approved
        with pytest.raises(verify_artifact.ArtifactRejected):
            verify_artifact.verify(zip_path, manifest, **kwargs)

    zip_path.write_bytes(zip_path.read_bytes() + b"tampered")
    with pytest.raises(verify_artifact.ArtifactRejected):
        verify_artifact.verify(zip_path, manifest, revision=REVISION, build_id="42")


def test_manifest_digest_is_the_zip_sha256(tmp_path):
    zip_path = tmp_path / "app.zip"
    digest = package.build(ROOT / "app", zip_path, revision=REVISION, build_id="7")
    assert digest == hashlib.sha256(zip_path.read_bytes()).hexdigest()


def test_a_manual_run_must_name_the_approved_digest(tmp_path):
    """Queuing CD by hand is not an approval, and the default resource version there is the latest run."""
    zip_path = tmp_path / "app.zip"
    digest = package.build(ROOT / "app", zip_path, revision=REVISION, build_id="42")
    manifest = _manifest(tmp_path, digest)
    run = {"revision": REVISION, "build_id": "42"}
    with pytest.raises(verify_artifact.ArtifactRejected, match="manual run"):
        verify_artifact.verify(zip_path, manifest, reason="Manual", **run)
    assert verify_artifact.verify(zip_path, manifest, reason="Manual", expected_digest=digest, **run)["status"] == "verified"
    assert verify_artifact.verify(zip_path, manifest, reason="ResourceTrigger", **run)["status"] == "verified"


def test_every_verification_passes_the_run_reason():
    verifications = [step["bash"] for job in _cd_jobs().values() for step in _steps(job)
                     if "verify_artifact.py" in str(step.get("bash", ""))]
    assert len(verifications) == 2
    assert all('--reason "$(Build.Reason)"' in bash for bash in verifications)



# ── SPLIT-T2: declared presets agree with the pipelines themselves ────────────────────────────


def _render(pattern, **values):
    for key, value in values.items():
        pattern = pattern.replace(f"<{key}>", value)
    return pattern


def test_presets_are_declared_and_the_default_names_follow_them():
    presets = DELIVERY["presets"]
    assert (presets["repository_preset"], presets["merge_method"]) == ("app_with_iac", "squash")
    naming = presets["naming"]
    service = {p["name"]: p.get("default") for p in CD["parameters"]}["service"]
    assert DELIVERY["artifact"]["name"] == _render(naming["artifact"], service=service)
    [resource] = CD["resources"]["pipelines"]
    assert resource["source"] == _render(naming["ci_pipeline"], service=service), "CD finds CI by the convention's name"
    environments = {p["name"]: p.get("default") for p in CD["parameters"]}["environments"]
    for env in environments:
        assert env["azureEnvironment"] == _render(naming["environment"], service=service, environment=env["name"])


def test_repository_preset_matches_the_package_layout():
    assert DELIVERY["ci_pipeline"].endswith("ci.yml") and DELIVERY["cd_pipeline"].endswith("cd.yml")
    assert (ROOT / "infra").is_dir() and (ROOT / "app").is_dir(), "app_with_iac: application and IaC in one repository"



def test_wheels_are_built_for_the_runtime_app_service_runs():
    """Audit 2026-09-24: the build agent's platform is not the target's."""
    web = (ROOT / "infra/bicep/web.bicep").read_text()
    version = web.split("linuxFxVersion: 'PYTHON|")[1].split("'")[0]
    install = next(step["bash"] for step in CI["stages"][0]["jobs"][0]["steps"] if "--target" in str(step.get("bash", "")))
    assert "--platform manylinux2014_x86_64" in install and f"--python-version {version}" in install
    assert f"--abi cp{version.replace('.', '')}" in install


# ── Artifact transport (ART-T1) ───────────────────────────────────────────────────────────────


TRANSPORT = DELIVERY["artifact"]["transport"]
EXTERNAL = {"azure_blob", "s3"}


def test_transport_declares_only_what_the_pipelines_implement():
    assert TRANSPORT["destinations"][0] == "azure_pipeline", "the native artifact stays the record CD verifies"
    assert set(TRANSPORT["destinations"]) == {"azure_pipeline"} | EXTERNAL
    assert not {"azure_artifacts", "github_packages"} & set(TRANSPORT["destinations"]), "feeds have no adapter"
    assert TRANSPORT["tool_path"] == ".ea/delivery/transport.py"
    assert (ROOT / TRANSPORT["requirements"]).is_file()


def test_transport_requirements_are_pinned_and_minimal():
    lines = [line.strip() for line in (ROOT / TRANSPORT["requirements"]).read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    assert lines == ["requests==2.31.0", "boto3>=1.42,<1.43"], "same versions the transport tool is tested with"


def test_ci_ships_transport_requirements_and_installs_them_only_with_the_tool():
    [job] = [job for stage in CI["stages"] for job in stage["jobs"]]
    scripts = [step.get("bash", "") for step in job["steps"]]
    assert any("operations/transport-requirements.txt\" \"$out/operations/\"" in script for script in scripts)
    [install] = [script for script in scripts if "transport-requirements.txt" in script and "pip install" in script]
    assert "if [ -f .ea/delivery/transport.py ]" in install, "native-only deliveries install nothing extra"
    publish = next(i for i, step in enumerate(job["steps"]) if "publish" in step)
    assert scripts.index(install) < publish, "prepared before anything is published or uploaded"


@pytest.mark.parametrize("job_name", ["plan", "apply"])
def test_cd_jobs_use_a_managed_python_before_any_script(job_name):
    steps = _steps(_cd_jobs()[job_name])
    python = next(i for i, step in enumerate(steps) if step.get("task") == "UsePythonVersion@0")
    first_script = next(i for i, step in enumerate(steps) if "bash" in step)
    assert python < first_script and steps[python]["inputs"]["versionSpec"] == "3.12"


@pytest.mark.parametrize("job_name", ["plan", "apply"])
def test_cd_installs_transport_only_for_environments_that_use_it(job_name):
    steps = _steps(_cd_jobs()[job_name])
    [conditional] = [step for step in steps if any(str(key).startswith("${{ if") for key in step)]
    [(condition, inner)] = conditional.items()
    assert condition == "${{ if in(env.artifactProvider, 'azure_blob', 's3') }}"
    assert "ci/delivery/operations/transport-requirements.txt" in inner[0]["bash"], "from the CI run, not a checkout"
    verify = next(i for i, step in enumerate(steps) if "verify_artifact.py" in step.get("bash", ""))
    assert steps.index(conditional) < verify, "the download EA adds before verification finds its dependencies ready"


def test_default_environments_are_native():
    [environments] = [p for p in CD["parameters"] if p["name"] == "environments"]
    assert {env["artifactProvider"] for env in environments["default"]} == {"azure_pipeline"}


def test_no_storage_secret_or_latest_reference():
    for text in (CI_TEXT, CD_TEXT, (ROOT / TRANSPORT["requirements"]).read_text()):
        lowered = text.lower()
        for forbidden in ("accountkey", "sig=", "aws_secret_access_key", "sas_token", "latest"):
            assert forbidden not in lowered
