// Resource-group scope: the platform team creates (or selects) the resource group of each environment;
// this template owns only what it creates inside it. The service connection therefore needs Contributor
// on that resource group, nothing at subscription level.
//
// infraMode new     Log Analytics workspace + Container Apps managed environment + container app
// infraMode shared  container app only, in an existing managed environment (existingEnvironmentId,
//                   which may live in another resource group); the environment is never modified
// infraMode bind    this file is not deployed at all (CD updates the existing app's image)
//
// The image comes from the environment's existing, platform-owned Azure Container Registry and is
// always referenced by digest. No role assignment is made here: Contributor cannot write role
// assignments, and the registry is not in this resource group. The platform team grants AcrPull
// (see README, "Registry access").
targetScope = 'resourceGroup'
param instance string
param ownerId string
param location string = resourceGroup().location
@allowed(['poc', 'development', 'staging', 'production'])
param purpose string
param revision string
@description('Image to run, by digest: <registry login server>/<repository>@sha256:<digest>.')
param image string
@description('Login server of the environment\'s existing Azure Container Registry, e.g. myregistry.azurecr.io.')
param registryServer string
@description('Optional resource id of a platform-owned user-assigned identity that already has AcrPull on the registry. Empty: the app\'s system-assigned identity pulls (AcrPull granted by the platform team).')
param registryIdentityId string = ''
@description('infraMode shared: resource id of an existing Container Apps managed environment. Empty in infraMode new.')
param existingEnvironmentId string = ''
@minValue(30)
@maxValue(730)
param retentionDays int = 30
var createEnvironment = empty(existingEnvironmentId)
var suffix = uniqueString(resourceGroup().id, ownerId, instance)
var tags = { managed_by: 'ea-nextgen-template', owner_id: ownerId, instance: instance, purpose: purpose, revision: revision }
module environment './environment.bicep' = if (createEnvironment) {
  name: 'environment-${instance}'
  params: { name: 'ea-${instance}-${suffix}', location: location, tags: tags, retentionDays: retentionDays }
}
module app './app.bicep' = {
  name: 'app-${instance}'
  params: {
    // Container app names: 2-32 characters, lower-case letters, digits and single hyphens.
    name: replace('${take('ea-${instance}', 25)}-${take(suffix, 6)}', '--', '-')
    location: location
    purpose: purpose
    instance: instance
    tags: tags
    image: image
    registryServer: registryServer
    registryIdentityId: registryIdentityId
    environmentId: createEnvironment ? environment!.outputs.environmentId : existingEnvironmentId
  }
}
output application_name string = app.outputs.applicationName
output application_url string = app.outputs.applicationUrl
output image string = app.outputs.image
output principal_id string = app.outputs.principalId
output resource_group_name string = resourceGroup().name
// Only what this template owns: an existing (shared) environment is never listed, so cleanup never touches it.
output resource_ids array = createEnvironment ? concat(environment!.outputs.resourceIds, [app.outputs.applicationId]) : [app.outputs.applicationId]
