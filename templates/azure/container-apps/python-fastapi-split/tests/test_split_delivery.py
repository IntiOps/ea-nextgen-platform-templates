"""The separated CI/CD contract for a container image, checked against the pipeline files themselves.

Same rules as the App Service split template (SPLIT-T1), adapted to an image: CI builds the image once
and holds no cloud connection; CD never builds or checks out source, verifies the saved image before any
cloud step, pushes it to each environment's registry and deploys it by digest, never by tag. These run
in the CI producer before anything is built, so a change that breaks a rule stops the pipeline.
"""
import gzip
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "operations"))

import image_reference  # noqa: E402
import package_image  # noqa: E402
import verify_artifact  # noqa: E402

REVISION = "a" * 40
IMAGE_ID = "sha256:" + "c" * 64
BASE_DIGEST = "sha256:" + "b" * 64


def _load(relative):
    return yaml.safe_load((ROOT / relative).read_text())


MANIFEST = _load("template.yaml")
VARIANT = MANIFEST["variants"][0]
DELIVERY = VARIANT["delivery"]
CI = _load(DELIVERY["ci_pipeline"])
CD = _load(DELIVERY["cd_pipeline"])
CD_TEXT = (ROOT / DELIVERY["cd_pipeline"]).read_text()
CI_TEXT = (ROOT / DELIVERY["ci_pipeline"]).read_text()
BICEP = {name: (ROOT / "infra/bicep" / name).read_text() for name in ("main.bicep", "environment.bicep", "app.bicep")}
DOCKERFILE = (ROOT / "Dockerfile").read_text()
ENVIRONMENTS = {p["name"]: p for p in CD["parameters"]}["environments"]["default"]


def _flatten(steps):
    """Expand `${{ if ... }}:` entries into their steps, in order (infraMode new/shared vs bind)."""
    flat = []
    for step in steps:
        if len(step) == 1 and next(iter(step)).startswith("${{ if"):
            flat += _flatten(next(iter(step.values())))
        else:
            flat.append(step)
    return flat


def _raw(job):
    return job["strategy"]["runOnce"]["deploy"]["steps"] if "strategy" in job else job["steps"]


def _branch(job, condition):
    """The steps under one `${{ if <condition> }}:` entry of a job."""
    key = f"${{{{ if {condition} }}}}"
    return [s for step in _raw(job) if list(step) == [key] for s in step[key]]


def _steps(job):
    return _flatten(_raw(job))


def _cd_stages():
    [loop] = CD["stages"]
    [stages] = loop.values()
    return stages


def _cd_jobs():
    return {job.get("job") or job.get("deployment"): job for stage in _cd_stages() for job in stage["jobs"]}


def _script(step):
    return str(step.get("bash", "")) + str(step.get("inputs", {}).get("inlineScript", ""))


def _is_cloud(step):
    return step.get("task", "").startswith("AzureCLI")


# ── Manifest ──────────────────────────────────────────────────────────────────────────────────


def test_manifest_declares_the_split_and_its_files_exist():
    assert MANIFEST["schema_version"] == "1.3" and DELIVERY["topology"] == "split_ci_cd"
    assert DELIVERY["ci_pipeline"] == VARIANT["files"]["pipeline"], "the stored pipeline is the CI producer"
    assert DELIVERY["ci_pipeline"] != DELIVERY["cd_pipeline"]
    assert DELIVERY["cleanup_pipeline"] == "pipelines/azure-pipelines/cleanup.yml", "EA generates the declared cleanup"
    files = VARIANT["files"]
    for path in (DELIVERY["ci_pipeline"], DELIVERY["cd_pipeline"], DELIVERY["cleanup_pipeline"], *files["application"], *files["infrastructure"],
                 files["smoke_test"], files["cleanup"], files["readme"]):
        assert (ROOT / path).is_file(), path
    assert (VARIANT["runtime"], VARIANT["cicd_provider"], VARIANT["iac_engine"]) == ("azure_container_apps", "azure_pipelines", "bicep")


def test_artifact_is_a_container_image_named_the_same_everywhere():
    name = DELIVERY["artifact"]["name"]
    ci_params = {p["name"]: p.get("default") for p in CI["parameters"]}
    cd_params = {p["name"]: p.get("default") for p in CD["parameters"]}
    assert ci_params["artifactName"] == cd_params["artifactName"] == name
    assert DELIVERY["artifact"]["kind"] == "container_image"
    assert "transport" not in DELIVERY["artifact"], "only the native artifact is implemented for images"
    assert {env["artifactProvider"] for env in ENVIRONMENTS} == {"azure_pipeline"}


# ── CI: build once, never deploy ──────────────────────────────────────────────────────────────


def test_ci_builds_once_and_never_deploys():
    assert CI["trigger"]["branches"]["include"] and CI["pr"]["branches"]["include"]
    for forbidden in ("deployment:", "AzureCLI", "azureSubscription", "az ", "docker push", "docker login", "acr "):
        assert forbidden not in CI_TEXT, forbidden
    assert CI_TEXT.count("operations/package_image.py") == 1, "built exactly once"
    assert "docker build" not in CI_TEXT, "the only build is package_image.py"
    assert "persistCredentials: false" in CI_TEXT


def test_ci_publishes_the_image_tarball_and_the_delivery_files():
    [job] = [job for stage in CI["stages"] for job in stage["jobs"]]
    scripts = [step.get("bash", "") for step in job["steps"]]
    [build] = [s for s in scripts if "package_image.py" in s]
    assert '--output "$(Build.ArtifactStagingDirectory)/image/image.tar.gz"' in build
    assert '--manifest "$(Build.ArtifactStagingDirectory)/image/artifact.json"' in build
    assert '--revision "$(Build.SourceVersion)"' in build and '--build-id "$(Build.BuildId)"' in build
    [stage] = [s for s in scripts if "$out/infra" in s]
    for path in ("infra/bicep/*.bicep", "operations/verify_artifact.py", "operations/image_reference.py", "tests/smoke.py"):
        assert path in stage, path
    published = {step["artifact"]: step["publish"] for step in job["steps"] if "publish" in step}
    assert published["${{ parameters.artifactName }}"] == "$(Build.ArtifactStagingDirectory)/image"
    assert set(published) == {"${{ parameters.artifactName }}", "delivery", "evidence"}


def test_ci_runs_the_guardrail_on_the_whole_change_and_keeps_its_evidence():
    """Rule violations fail the build; protected paths and size become needs_review for the required reviewer."""
    [job] = [job for stage in CI["stages"] for job in stage["jobs"]]
    steps = job["steps"]
    assert steps[0].get("fetchDepth") == 0, "a shallow clone cannot measure the change"
    scripts = [step.get("bash", "") for step in steps]
    [guard] = [i for i, s in enumerate(scripts) if "tools/guardrail.py" in s]
    assert "check --ci --no-tests --base" in scripts[guard] and "--json" in scripts[guard]
    tests = next(i for i, s in enumerate(scripts) if "pytest" in s)
    build = next(i for i, s in enumerate(scripts) if "operations/package_image.py" in s)
    assert tests < guard < build, "after the tests, before anything is built"
    [evidence] = [s for s in steps if s.get("artifact") == "evidence"]
    assert "succeededOrFailed()" in evidence["condition"], "evidence survives a failed guardrail"


# ── CD: runs from one CI run, never builds ────────────────────────────────────────────────────


def _activation_ok(resource):
    """Two legitimate CD activations: on CI completion, which needs explicit branch filters, or `none` when
    EA NextGen promotes each verified run itself (its topology's consumer trigger is "manual" and it renders
    `trigger: none` here). Rule 2 holds either way: the CD never runs on push."""
    trigger = resource.get("trigger", "none")
    return trigger == "none" or bool((trigger.get("branches") or {}).get("include"))


@pytest.mark.parametrize("trigger, ok", [
    ("none", True),
    ({"branches": {"include": ["main"]}}, True),
    ({"branches": {"include": []}}, False),
    ({}, False),
])
def test_cd_activation_is_filtered_completion_or_ea_orchestrated(trigger, ok):
    assert _activation_ok({"pipeline": "ci", "source": "x-ci", "trigger": trigger}) is ok


def test_cd_runs_only_from_a_ci_run_never_on_push():
    assert CD["trigger"] == "none" and CD["pr"] == "none"
    [resource] = CD["resources"]["pipelines"]
    assert resource["pipeline"] == "ci" and resource["source"] and resource["source"] != "self"
    assert _activation_ok(resource), "completion activation needs explicit branch filters"


def test_cd_never_builds_or_checks_out_source():
    for forbidden in ("package_image.py", "docker build", "Dockerfile", "checkout: self", "app/requirements.txt",
                      "pip install", "latest"):
        assert forbidden not in CD_TEXT, forbidden
    assert _steps(_cd_jobs()["plan"])[0] == {"checkout": "none"}


def test_every_download_comes_from_the_ci_run():
    downloads = [step for job in _cd_jobs().values() for step in _steps(job) if "download" in step]
    assert downloads and all(step["download"] == "ci" for step in downloads)


def test_artifact_is_verified_before_any_cloud_step_or_docker_use_in_every_job():
    for name, job in _cd_jobs().items():
        steps = _steps(job)
        verify = next(i for i, s in enumerate(steps) if "verify_artifact.py" in _script(s))
        cloud = [i for i, s in enumerate(steps) if _is_cloud(s)]
        docker = [i for i, s in enumerate(steps) if "docker " in _script(s)]
        assert cloud and verify < min(cloud + docker), name


def test_the_loaded_image_is_checked_against_the_image_ci_built_before_it_is_pushed():
    steps = _steps(_cd_jobs()["apply"])
    load = next(i for i, s in enumerate(steps) if "docker load" in _script(s))
    push = next(i for i, s in enumerate(steps) if "docker push" in _script(s))
    assert load < push
    assert "verify_artifact.py" in _script(steps[load]) and '--loaded-image-id "$loaded"' in _script(steps[load])
    assert "docker image inspect --format '{{.Id}}'" in _script(steps[load])


def test_every_verification_passes_the_run_reason():
    verifications = [_script(step) for job in _cd_jobs().values() for step in _steps(job) if "verify_artifact.py" in _script(step)]
    assert len(verifications) == 3, "plan, promote, and after docker load"
    assert all('--reason "$(Build.Reason)"' in script for script in verifications)
    assert all('--expected-digest "${{ parameters.expectedDigest }}"' in script for script in verifications)


# ── Per-environment preview, approval, push, deploy ───────────────────────────────────────────


def test_the_preview_runs_in_its_own_stage_before_the_approval():
    """Azure DevOps evaluates an environment's approvals when the stage that uses it starts. The preview
    must therefore live in an earlier stage that uses no protected environment, or approvers never see it."""
    plan, promote = _cd_stages()
    assert plan["stage"].startswith("plan_") and promote["stage"].startswith("promote_")
    assert "environment" not in str(plan["jobs"]), "the preview stage must not wait for an approval"
    assert all("deployment" not in job for job in plan["jobs"])
    assert "what-if" in str(plan["jobs"]) and "docker push" not in str(plan["jobs"]), "nothing changes before approval"
    assert promote["dependsOn"] == plan["stage"]
    [apply] = promote["jobs"]
    assert apply["environment"] == "${{ env.azureEnvironment }}"
    text = str(_steps(apply))
    assert "deployment group create" in text and "docker push" in text and "containerapp update" in text


def test_promotions_to_one_environment_run_one_at_a_time():
    _plan, promote = _cd_stages()
    assert promote["lockBehavior"] == "sequential"


def test_stage_names_are_safe_for_any_environment_name():
    for stage in _cd_stages():
        assert "replace(env.name, '-', '_')" in stage["stage"], "Azure stage ids allow only letters, digits and _"


def test_every_cloud_step_uses_its_environment_identity():
    cloud = [step for job in _cd_jobs().values() for step in _steps(job) if _is_cloud(step)]
    assert len(cloud) == 5, "what-if, bind check, push, apply, bind update"
    assert all(step["inputs"]["azureSubscription"] == "${{ env.serviceConnection }}" for step in cloud)


def test_the_image_goes_to_the_environment_registry_through_its_service_connection():
    [push] = [s for s in _steps(_cd_jobs()["apply"]) if "docker push" in _script(s)]
    script = _script(push)
    assert _is_cloud(push) and 'registry="${{ env.registry }}"' in script
    assert 'az acr login --name "${registry%%.*}"' in script, "token from the environment identity, no password"
    assert 'target="$repository:$(CI_COMMIT)-$(CI_RUN_ID)"' in script, "a unique tag per CI run, never reused"
    for forbidden in ("--password", "-p ", "admin", "docker login"):
        assert forbidden not in script, forbidden


def test_the_image_is_deployed_by_digest_never_by_tag():
    apply = _cd_jobs()["apply"]
    [push] = [s for s in _steps(apply) if "docker push" in _script(s)]
    assert "image_reference.py\" --repository \"$repository\"" in _script(push)
    assert "task.setvariable variable=IMAGE_REF]$image_ref" in _script(push)
    [create] = [s for s in _branch(apply, "ne(env.infraMode, 'bind')") if "deployment group create" in _script(s)]
    assert 'image="$(IMAGE_REF)"' in _script(create)
    [update] = [s for s in _branch(apply, "eq(env.infraMode, 'bind')") if "containerapp update" in _script(s)]
    assert '--image "$(IMAGE_REF)"' in _script(update)
    for step in (create, update):
        assert 'if [ "$deployed" != "$(IMAGE_REF)" ]' in _script(step), "what runs is checked to be the digest"
    assert ":latest" not in CD_TEXT + CI_TEXT + DOCKERFILE + "".join(BICEP.values())


def test_image_reference_accepts_only_one_digest_of_the_pushed_repository():
    repo = "acrplatformdev.azurecr.io/fastapi-containerapp"
    digest = "sha256:" + "d" * 64
    assert image_reference.pinned([f"{repo}@{digest}", f"other.azurecr.io/x@sha256:{'e' * 64}"], repo) == f"{repo}@{digest}"
    for digests in ([], [f"{repo}@sha256:{'d' * 63}"], [f"{repo}@{digest}", f"{repo}@sha256:{'e' * 64}"], [f"{repo}:tag"]):
        with pytest.raises(ValueError):
            image_reference.pinned(digests, repo)
    with pytest.raises(ValueError):
        image_reference.pinned([f"{repo}@{digest}"], "not a repository")
    run = subprocess.run([sys.executable, str(ROOT / "operations/image_reference.py"), "--repository", repo],
                         input=json.dumps([f"{repo}@{digest}"]), capture_output=True, text=True)
    assert run.returncode == 0 and run.stdout.strip() == f"{repo}@{digest}"


def test_the_promoted_revision_is_smoke_tested_last():
    steps = _steps(_cd_jobs()["apply"])
    assert steps[-1]["bash"] == 'python3 "$(Pipeline.Workspace)/ci/delivery/tests/smoke.py" --url "$(APP_URL)" --revision "$(CI_COMMIT)"'


def test_default_chain_has_one_identity_registry_and_group_per_environment():
    assert [e["name"] for e in ENVIRONMENTS] == ["dev", "prod"]
    assert len({e["serviceConnection"] for e in ENVIRONMENTS}) == len(ENVIRONMENTS), "no identity shared across environments"
    assert all(re.fullmatch(r"[a-z0-9]+\.azurecr\.io", e["registry"]) for e in ENVIRONMENTS)


def test_every_environment_names_its_registry_and_mode():
    for env in ENVIRONMENTS:
        assert env.get("registry"), env["name"]
        assert env["infraMode"] in {"new", "shared", "bind"}
        assert {"existingEnvironmentId", "appName", "registryIdentityId"} <= set(env)


def test_infrastructure_stays_inside_each_environment_resource_group():
    """The platform team owns the resource group; the template never needs subscription rights."""
    assert "targetScope = 'resourceGroup'" in BICEP["main.bicep"]
    assert not any("Microsoft.Resources/resourceGroups" in text for text in BICEP.values())
    assert all(e.get("resourceGroup") for e in ENVIRONMENTS), "every environment names its resource group"
    assert len({e["resourceGroup"] for e in ENVIRONMENTS}) == len(ENVIRONMENTS), "no resource group shared across environments"
    assert "deployment sub " not in CD_TEXT
    assert "what-if --resource-group \"${{ env.resourceGroup }}\"" in CD_TEXT
    assert "deployment group create --resource-group \"${{ env.resourceGroup }}\"" in CD_TEXT


def test_no_role_assignment_or_registry_credential_in_the_infrastructure():
    """Contributor cannot write role assignments and the registry is the platform's: AcrPull is a prerequisite."""
    text = "".join(BICEP.values())
    for forbidden in ("roleAssignments", "passwordSecretRef", "adminUserEnabled", "listCredentials", "Microsoft.ContainerRegistry"):
        assert forbidden not in text, forbidden
    assert "identity: useUserIdentity ? registryIdentityId : 'system'" in BICEP["app.bicep"]


# ── infraMode new / shared / bind ─────────────────────────────────────────────────────────────


def test_new_mode_creates_the_environment_and_its_logs():
    assert "module environment './environment.bicep' = if (createEnvironment)" in BICEP["main.bicep"]
    assert "var createEnvironment = empty(existingEnvironmentId)" in BICEP["main.bicep"]
    assert "resource logs 'Microsoft.OperationalInsights/workspaces@" in BICEP["environment.bicep"]
    assert "resource environment 'Microsoft.App/managedEnvironments@" in BICEP["environment.bicep"]


def test_shared_mode_reuses_an_existing_environment_without_owning_it():
    main = BICEP["main.bicep"]
    assert "environmentId: createEnvironment ? environment!.outputs.environmentId : existingEnvironmentId" in main
    assert ("output resource_ids array = createEnvironment ? concat(environment!.outputs.resourceIds, "
            "[app.outputs.applicationId]) : [app.outputs.applicationId]") in main
    assert "Microsoft.App/managedEnvironments" not in BICEP["app.bicep"], "the app never declares the environment"
    assert CD_TEXT.count('existingEnvironmentId="${{ env.existingEnvironmentId }}"') == 2, "what-if and apply pass the same environment"


def test_bind_mode_never_changes_infrastructure():
    """infraMode bind: the app already exists, so no deployment of any template may run."""
    jobs = _cd_jobs()
    for name in ("plan", "apply"):
        bind = _branch(jobs[name], "eq(env.infraMode, 'bind')")
        assert bind, f"{name} has a bind branch"
        assert "az deployment" not in str(bind) and "az containerapp show" in str(bind)
        assert "--name \"${{ env.appName }}\"" in str(bind)
        infra = _branch(jobs[name], "ne(env.infraMode, 'bind')")
        assert "az deployment group" in str(infra)
    plan_bind = str(_branch(jobs["plan"], "eq(env.infraMode, 'bind')"))
    assert "properties.configuration.registries[].server" in plan_bind, "bind checks the app already pulls from the registry"
    push = [s for s in _steps(jobs["apply"]) if "docker push" in _script(s)]
    assert len(push) == 1 and push[0] in _raw(jobs["apply"]), "every mode pushes the same image with one step"


# ── The container app ─────────────────────────────────────────────────────────────────────────


def test_container_app_ingress_scale_and_tags():
    app = BICEP["app.bicep"]
    assert "external: true" in app and "targetPort: 8000" in app and "allowInsecure: false" in app
    assert "var minReplicas = production ? 2 : purpose == 'staging' ? 1 : 0" in app
    assert "scale: { minReplicas: minReplicas" in app
    assert "{ type: 'Liveness', httpGet: { path: '/health', port: 8000 }" in app
    tags = "var tags = { managed_by: 'ea-nextgen-template', owner_id: ownerId, instance: instance, purpose: purpose, revision: revision }"
    assert tags in BICEP["main.bicep"]
    assert BICEP["environment.bicep"].count("tags: tags") == 2
    assert "tags: empty(azdServiceName) ? tags : union(tags, { 'azd-service-name': azdServiceName })" in app


def test_dockerfile_runs_uvicorn_on_8000_as_a_non_root_user():
    assert "ARG PYTHON_IMAGE=python:3.12-slim\nFROM ${PYTHON_IMAGE}" in DOCKERFILE
    users = re.findall(r"^USER (\S+)$", DOCKERFILE, re.MULTILINE)
    assert users and users[-1].split(":")[0] not in {"root", "0"}
    assert 'CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]' in DOCKERFILE
    assert "EXPOSE 8000" in DOCKERFILE
    ignore = (ROOT / ".dockerignore").read_text().splitlines()
    assert ignore[ignore.index("*")] == "*" and "!app/" in ignore, "allow-list: only app/ reaches the image"


# ── The build and the verifier ────────────────────────────────────────────────────────────────


class FakeDocker:
    """Stands in for the docker CLI: records the commands and saves a fixed tarball."""

    def __init__(self, image_id=IMAGE_ID):
        self.calls, self.image_id = [], image_id

    def __call__(self, argv, check=True, capture_output=False, text=False, stdout=None, env=None):
        self.calls.append(argv)
        out = ""
        if argv[:2] == ["docker", "image"] and "{{json .RepoDigests}}" in argv:
            out = json.dumps([f"python@{BASE_DIGEST}"])
        elif argv[:2] == ["docker", "image"]:
            out = self.image_id + "\n"
        elif argv[:2] == ["docker", "save"]:
            stdout.write(b"saved image bytes " + argv[2].encode())
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")


def _build(tmp_path, name="image.tar.gz", build_id="42", docker=None):
    docker = docker or FakeDocker()
    record = package_image.build(ROOT, tmp_path / name, name="fastapi-containerapp", revision=REVISION,
                                 build_id=build_id, run=docker)
    return record, docker


def test_the_build_context_is_deterministic_and_records_its_run(tmp_path):
    first = package_image.stage_context(ROOT, tmp_path / "a", revision=REVISION, build_id="42")
    second = package_image.stage_context(ROOT, tmp_path / "b", revision=REVISION, build_id="42")
    assert first == second
    assert all((tmp_path / "a" / p).read_bytes() == (tmp_path / "b" / p).read_bytes() for p in first)
    assert {"Dockerfile", ".dockerignore", "app/main.py", "app/requirements.txt", "app/build-info.json",
            "app/service/domain/greeting.py"} <= set(first)
    assert not any(part in p for p in first for part in ("__pycache__", "tests/", "infra/", "pipelines/", ".pyc"))
    assert json.loads((tmp_path / "a/app/build-info.json").read_text()) == {"revision": REVISION, "build_id": "42"}
    assert (tmp_path / "a/app/main.py").stat().st_mtime == package_image.FIXED_EPOCH


def test_the_image_is_built_once_from_the_pinned_base_and_saved(tmp_path):
    record, docker = _build(tmp_path)
    verbs = [call[1] if call[1] != "image" else "inspect" for call in docker.calls]
    assert verbs == ["pull", "inspect", "build", "inspect", "save"]
    [build] = [call for call in docker.calls if call[1] == "build"]
    assert f"PYTHON_IMAGE=python@{BASE_DIGEST}" in build and "fastapi-containerapp:" + REVISION in build
    assert f"org.opencontainers.image.revision={REVISION}" in build
    assert record == package_image.manifest(name="fastapi-containerapp", revision=REVISION, build_id="42",
                                            digest=hashlib.sha256((tmp_path / "image.tar.gz").read_bytes()).hexdigest(),
                                            image="fastapi-containerapp:" + REVISION, image_id=IMAGE_ID,
                                            base=f"python@{BASE_DIGEST}")
    assert record["kind"] == "container_image" and record["file"] == "image.tar.gz"
    with gzip.open(tmp_path / "image.tar.gz") as saved:
        assert saved.read() == b"saved image bytes fastapi-containerapp:" + REVISION.encode()


def test_the_same_saved_image_gives_the_same_tarball_digest(tmp_path):
    """gzip without a timestamp or file name: the tarball digest depends only on what docker saved."""
    first, _ = _build(tmp_path, "a.tar.gz")
    second, _ = _build(tmp_path, "b.tar.gz")
    assert first["sha256"] == second["sha256"]


def test_the_build_refuses_bad_inputs(tmp_path):
    for kwargs in ({"revision": "main", "build_id": "42", "name": "x"}, {"revision": REVISION, "build_id": "abc", "name": "x"},
                   {"revision": REVISION, "build_id": "42", "name": "Not_Kebab"}):
        with pytest.raises(ValueError):
            package_image.build(ROOT, tmp_path / "x.tar.gz", run=FakeDocker(), **kwargs)
    with pytest.raises(RuntimeError):
        _build(tmp_path, docker=FakeDocker(image_id="not-an-id"))
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("ARG PYTHON_IMAGE=python:latest\nFROM ${PYTHON_IMAGE}\n")
    with pytest.raises(ValueError):
        package_image.base_image(dockerfile)
    assert package_image.base_image(ROOT / "Dockerfile") == "python:3.12-slim"


def _artifact(tmp_path, build_id="42"):
    record, _ = _build(tmp_path, build_id=build_id)
    manifest = tmp_path / "artifact.json"
    manifest.write_text(json.dumps(record))
    return tmp_path / "image.tar.gz", manifest, record


def test_verifier_accepts_only_the_exact_artifact(tmp_path):
    tarball, manifest, record = _artifact(tmp_path)
    run = {"revision": REVISION, "build_id": "42"}
    result = verify_artifact.verify(tarball, manifest, expected_digest=record["sha256"], **run)
    assert result["status"] == "verified" and result["image_id"] == IMAGE_ID
    for kwargs in ({"revision": "b" * 40, "build_id": "42"},  # manifest from another commit
                   {"revision": REVISION, "build_id": "43"},  # manifest from another run
                   {**run, "expected_digest": "0" * 64},  # not what EA approved
                   {**run, "loaded_image_id": "sha256:" + "e" * 64}):  # docker loaded something else
        with pytest.raises(verify_artifact.ArtifactRejected):
            verify_artifact.verify(tarball, manifest, **kwargs)
    assert verify_artifact.verify(tarball, manifest, loaded_image_id=IMAGE_ID, **run)["loaded"] is True
    tarball.write_bytes(tarball.read_bytes() + b"tampered")
    with pytest.raises(verify_artifact.ArtifactRejected, match="digest CI recorded"):
        verify_artifact.verify(tarball, manifest, **run)


def test_verifier_refuses_a_manifest_that_is_not_this_image(tmp_path):
    tarball, manifest, record = _artifact(tmp_path)
    for change in ({"kind": "application_package"}, {"file": "app.zip"}, {"image_id": "abc"}, {"image": "x:latest"}):
        manifest.write_text(json.dumps({**record, **change}))
        with pytest.raises(verify_artifact.ArtifactRejected):
            verify_artifact.verify(tarball, manifest, revision=REVISION, build_id="42")


def test_a_manual_run_must_name_the_approved_digest(tmp_path):
    """Queuing CD by hand is not an approval, and the default resource version there is the latest run."""
    tarball, manifest, record = _artifact(tmp_path)
    run = {"revision": REVISION, "build_id": "42"}
    with pytest.raises(verify_artifact.ArtifactRejected, match="manual run"):
        verify_artifact.verify(tarball, manifest, reason="Manual", **run)
    assert verify_artifact.verify(tarball, manifest, reason="Manual", expected_digest=record["sha256"], **run)["status"] == "verified"
    assert verify_artifact.verify(tarball, manifest, reason="ResourceTrigger", **run)["status"] == "verified"


def test_saved_tarballs_are_read_in_blocks_not_into_memory():
    """A Python image tarball is hundreds of megabytes; both sides hash it streaming."""
    assert "read_bytes()" not in (ROOT / "operations/verify_artifact.py").read_text()
    assert "handle.read(1024 * 1024)" in (ROOT / "operations/package_image.py").read_text()


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
    for env in ENVIRONMENTS:
        assert env["azureEnvironment"] == _render(naming["environment"], service=service, environment=env["name"])


def test_repository_preset_matches_the_package_layout():
    assert DELIVERY["ci_pipeline"].endswith("ci.yml") and DELIVERY["cd_pipeline"].endswith("cd.yml")
    assert (ROOT / "infra").is_dir() and (ROOT / "app").is_dir(), "app_with_iac: application and IaC in one repository"


@pytest.mark.parametrize("job_name", ["plan", "apply"])
def test_cd_jobs_use_a_managed_python_before_any_script(job_name):
    steps = _steps(_cd_jobs()[job_name])
    python = next(i for i, step in enumerate(steps) if step.get("task") == "UsePythonVersion@0")
    first_script = next(i for i, step in enumerate(steps) if "bash" in step or _is_cloud(step))
    assert python < first_script and steps[python]["inputs"]["versionSpec"] == "3.12"


def test_no_secret_or_latest_reference():
    for text in (CI_TEXT, CD_TEXT, DOCKERFILE, *BICEP.values()):
        lowered = text.lower()
        for forbidden in ("accountkey", "sig=", "aws_secret_access_key", "sas_token", "latest", "password"):
            assert forbidden not in lowered, forbidden

