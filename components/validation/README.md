# Quality validation foundation — source CI, not deployment authorization

Delivered:

- Explicit `local-source` build profile, fixed test suites and bounded JUnit normalization.
- Clean checked-out commit verification, fresh output directory, runner attempt context,
  report/profile digests, evidence validity and fail-closed local CI evaluation.
- Native GitHub composite action and Azure step template publishing reports on failure too.
- Offline SonarQube and ZAP report assessors with identity/target checks and tests.

`core/run.py` accepts metadata and output location, not an arbitrary command or test
path from a package. It runs trusted repository tests with a timeout and no cloud
credentials. Do not execute unreviewed PR code on a privileged/self-hosted runner.

```sh
python tools/validate_quality_catalog.py
python components/validation/core/run.py --commit FULL_CHECKED_OUT_SHA \
  --repository IntiOps/ea-nextgen-platform-templates --run-id local-1 --attempt 1 \
  --output /tmp/ea-quality-unique-new-directory
```

Install the same test dependencies as source CI. Output must be outside the clean
checkout and not already exist. `evidence.json` contains normalized counts/status,
not test names, logs or exception bodies. Native JUnit still contains test details:
only publish reviewed synthetic test data, restrict artifact access and retention.

## Trust boundary

`ci_gate_passed` assesses this CI profile only. `deployment_authorized` is always
false and origin is not verified by EA. A developer can forge a JSON file or modify
a workflow: platform acceptance must authenticate the native run, protect workflow
and profile revisions, correlate approved source/artifact/architecture/environment,
and evaluate organization policy. These protections are not implemented here.
The local source profile has no SAST/DAST success by default and grants no exception.

## Offline adapter limits

Sonar: caller supplies captured compute task, gate fetched by analysisId, and analysis
metadata. `OK` is not accepted for mismatched project/analysis/commit; `NONE` means no
evidence. The gate response alone cannot prove its analysisId, so authenticated
retrieval/correlation is still required before use in a platform gate.

ZAP: report sites must match the explicit origin; unknown risk levels are rejected.
No network requests, scan, target authorization or coverage verification occurs.
An empty-alert report does not prove authenticated crawling or sufficient coverage.
Use expected scan policy, deployed image and native run evidence in the future adapter.

Live Sonar scanner/authentication, DAST execution, SCA, secret/IaC/image scans,
performance and AI evaluation runners are pending. Operational health/recovery
remain postdeploy controls; this source pipeline cannot certify them. CI files
currently target GitHub-hosted runners and Azure DevOps Services. Azure DevOps Server
needs a supported artifact task adapter; do not claim parity before testing.
