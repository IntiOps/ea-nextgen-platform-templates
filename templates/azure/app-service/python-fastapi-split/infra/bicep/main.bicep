// Resource-group scope: the platform team creates (or selects) the resource group of each environment;
// this template owns only the plan and the web app inside it. The service connection therefore needs
// Contributor on that resource group, nothing at subscription level.
targetScope = 'resourceGroup'
param instance string
param ownerId string
param location string = resourceGroup().location
@allowed(['poc', 'development', 'staging', 'production'])
param purpose string
param revision string
param retentionDays int = 7
@description('infraMode shared: resource id of an existing App Service plan. Empty in infraMode new.')
param existingPlanId string = ''
var suffix = uniqueString(resourceGroup().id, ownerId, instance)
module web './web.bicep' = {
  name: 'web-${instance}'
  params: { name: 'ea-${instance}-${suffix}', location: location, purpose: purpose, ownerId: ownerId, instance: instance, revision: revision, retentionDays: retentionDays, existingPlanId: existingPlanId }
}
output application_name string = web.outputs.applicationName
output application_url string = web.outputs.applicationUrl
output resource_group_name string = resourceGroup().name
output resource_ids array = web.outputs.resourceIds
