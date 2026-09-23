# SonarQube report adapter

Offline `report.assess` accepts a captured compute task, quality gate and analysis
metadata with expected project, analysis ID and commit. No token storage, network
fetch or scanner is implemented. Result provenance remains unverified.

Native reference: https://github.com/SonarSource/sonarqube-quality-gate-action
The live adapter must retrieve the exact analysis, enforce server origin and TLS,
use CI credentials, and avoid project-latest races. Do not expose tokens in artifacts.
