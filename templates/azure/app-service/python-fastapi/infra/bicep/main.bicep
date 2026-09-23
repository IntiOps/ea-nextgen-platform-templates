targetScope = 'subscription'
param instance string
param ownerId string
param location string
@allowed(['poc', 'development', 'staging', 'production'])
param purpose string
param revision string
param retentionDays int = 7
var suffix = uniqueString(subscription().subscriptionId, ownerId, instance)
resource group 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-ea-${instance}-${suffix}'
  location: location
  tags: { managed_by: 'ea-nextgen-template', instance: instance, owner_id: ownerId, purpose: purpose }
}
module web './web.bicep' = {
  name: 'web-${instance}'
  scope: group
  params: { name: 'ea-${instance}-${suffix}', location: location, purpose: purpose, ownerId: ownerId, instance: instance, revision: revision, retentionDays: retentionDays }
}
output application_name string = web.outputs.applicationName
output application_url string = web.outputs.applicationUrl
output resource_group_name string = group.name
output resource_ids array = web.outputs.resourceIds
