# ZAP report adapter

Offline `report.assess` validates explicit target origin and risk codes and returns
counts only. It never launches a scan. Active scans require an authorized isolated
target/window, timeout, authentication policy and deployment correlation.

Native reference: https://www.zaproxy.org/docs/docker/
Risk policy and successful scan coverage are distinct; zero alerts is not proof
that the scan ran against all intended endpoints. Coverage remains unverified.
