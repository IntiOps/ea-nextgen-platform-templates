param name string
param location string
@allowed(['poc', 'development', 'staging', 'production'])
param purpose string
param ownerId string
param instance string
param revision string
@minValue(1)
@maxValue(365)
param retentionDays int
@description('Empty: this template creates the App Service plan. Otherwise the resource id of an existing plan (infraMode shared).')
param existingPlanId string = ''
var createPlan = empty(existingPlanId)
var production = purpose == 'production'
var tags = { managed_by: 'ea-nextgen-template', owner_id: ownerId, instance: instance, purpose: purpose, revision: revision }
resource plan 'Microsoft.Web/serverfarms@2024-04-01' = if (createPlan) {
  name: '${name}-plan'
  location: location
  kind: 'linux'
  tags: tags
  sku: { name: production ? 'P1v3' : purpose == 'staging' ? 'S1' : 'B1', capacity: production ? 2 : 1 }
  properties: { reserved: true, zoneRedundant: production }
}
resource web 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: location
  kind: 'app,linux'
  tags: tags
  properties: {
    serverFarmId: createPlan ? plan.id : existingPlanId
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      // Dependencies ship inside the package (operations/package.py): nothing is resolved at deploy time.
      appCommandLine: 'python -m uvicorn main:app --host 0.0.0.0 --port 8000'
      alwaysOn: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      healthCheckPath: '/health'
      // Build once, promote the same bytes: App Service must not rebuild the package per environment.
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'false' }
        { name: 'ENABLE_ORYX_BUILD', value: 'false' }
        { name: 'PYTHONPATH', value: '/home/site/wwwroot/packages' }
      ]
    }
  }
}
resource ftp 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  name: 'ftp'
  parent: web
  properties: { allow: false }
}
resource scm 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  name: 'scm'
  parent: web
  properties: { allow: false }
}
resource logs 'Microsoft.Web/sites/config@2024-04-01' = {
  name: 'logs'
  parent: web
  properties: { httpLogs: { fileSystem: { enabled: true, retentionInDays: retentionDays, retentionInMb: 100 } } }
}
output applicationName string = web.name
output applicationUrl string = 'https://${web.properties.defaultHostName}'
// Only what this template owns: an existing (shared) plan is never listed, so cleanup never touches it.
output resourceIds array = createPlan ? [plan.id, web.id] : [web.id]
