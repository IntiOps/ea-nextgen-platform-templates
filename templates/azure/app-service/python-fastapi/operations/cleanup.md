# Remove a demo instance

Dispatch the same workflow from main with operation `destroy`, the same instance and region,
and confirmation `destroy INSTANCE` (replace INSTANCE with the exact instance name).

The plan reads only this repository/instance's dedicated state key. Inspect the destroy plan,
then approve `demo-cleanup`. The job applies the saved destroy plan and checks that state has
no managed resources left. The plan guard refuses unknown addresses or IDs outside this
instance's expected subscription/resource group. The provider refuses removal of a resource
group containing resources it does not manage. The shared state backend is not in the plan.

If a resource lock or unexpected shared resource prevents deletion, inspect it and create
a new plan after resolving the issue. Do not bypass ownership guards or erase the state to
hide a failed cleanup. Keep the result artifact as evidence. No TTL-triggered deletion occurs.
