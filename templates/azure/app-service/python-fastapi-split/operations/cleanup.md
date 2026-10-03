# Remove an environment

Each environment owns one resource group, `rg-ea-<service>-<environment>-<suffix>`, tagged
`managed_by: ea-nextgen-template`. Remove it through an approved change in that environment's
subscription, after confirming no other workload uses it. Nothing here deletes resources on a
schedule, and CD never removes an environment. Keep the CD run evidence.
