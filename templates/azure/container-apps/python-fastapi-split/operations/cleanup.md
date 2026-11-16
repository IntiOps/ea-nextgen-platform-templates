# Remove an environment

What this template owns depends on `infraMode` (see the `resource_ids` output of `main.bicep`):

- `new`: the container app, its managed environment and the Log Analytics workspace, all tagged
  `managed_by: ea-nextgen-template` in the environment's resource group.
- `shared`: the container app only. Never delete the shared managed environment.
- `bind`: nothing. The app belongs to whoever created it.

Remove owned resources through an approved change in that environment's subscription, after
confirming no other workload uses them. Images pushed to the platform-owned registry
(`<artifactName>:<commit>-<run id>`) follow the registry's retention policy, which the platform team
owns. Nothing here deletes resources on a schedule, and CD never removes an environment. Keep the CD
run evidence.
