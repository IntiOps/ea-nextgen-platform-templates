# Remove an environment

The platform team owns each environment's resource group (`resourceGroup` in `cd.yml`). This template
never deletes it. What the template owns inside it depends on `infraMode` (see the `resource_ids`
output of `main.bicep`), and every owned resource is tagged `managed_by=ea-nextgen-template` and
`instance=<service>-<environment>`:

- `new`: the container app, its managed environment and the Log Analytics workspace.
- `shared`: the container app only. The shared managed environment (`existingEnvironmentId`) belongs
  to the platform team.
- `bind`: nothing. The app belongs to whoever created it.

Images pushed to the platform-owned registry (`<artifactName>:<commit>-<run id>`) follow the
registry's retention policy, which the platform team owns. The cleanup below does not touch them.

## Gated cleanup pipeline

`pipelines/azure-pipelines/cleanup.yml` is the only way this template deletes anything. It never runs
on its own (no trigger, no PR trigger, no schedule). Create an Azure Pipelines definition from it and
queue it by hand with the same `environments` chain as `cd.yml` and `confirm` set to exactly
`delete <service>`. Every job checks `confirm` before any cloud step.

Per environment:

1. `list_<env>` runs without approval. It lists the resources in `resourceGroup` tagged with BOTH
   tags, prints them in delete order and publishes the list as the artifact `cleanup-<env>`.
2. `delete_<env>` is a deployment job on the environment's Azure DevOps environment, so its approvals
   apply after the list is visible. It runs the same query again and refuses if anything was added or
   removed since the list was published. Then it deletes exactly those ids: the container app first,
   then the managed environment, then the Log Analytics workspace. Finally it checks nothing tagged
   is left.

`operations/cleanup_resources.py` re-checks every listed item: both tags, inside `resourceGroup`, a
type this template creates, and not `existingEnvironmentId`. Anything else stops the run for a person
to decide. `bind` environments are skipped with a message. If a delete stage fails half way, queue the
pipeline again: the old list no longer matches and the stage refuses to reuse it.

## TTL report

`operations/ttl_report.py` reports groups and resources whose `ea-ttl` tag (`YYYY-MM-DD`, the last day
they are meant to exist) has passed. It only reads JSON and never deletes anything:

    az group list -o json > groups.json
    az resource list --tag ea-ttl -o json > resources.json
    python3 operations/ttl_report.py groups.json resources.json [--json]

It exits 1 when anything is expired or carries an unreadable `ea-ttl`. Expired items owned by this
template are removed with the cleanup pipeline. Anything else is the owner's call. Keep the CD and
cleanup run evidence.
