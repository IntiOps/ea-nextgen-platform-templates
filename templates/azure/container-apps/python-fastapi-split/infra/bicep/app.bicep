// The container app. Ingress is external on 8000 (the Dockerfile's port); the image is pulled from the
// environment's registry with a managed identity, never with registry admin credentials.
param name string
param location string
@allowed(['poc', 'development', 'staging', 'production'])
param purpose string
param instance string
param tags object
param image string
param registryServer string
param registryIdentityId string
param environmentId string
var production = purpose == 'production'
var useUserIdentity = !empty(registryIdentityId)
// Scale to zero outside staging and production; production keeps two replicas warm.
var minReplicas = production ? 2 : purpose == 'staging' ? 1 : 0
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: useUserIdentity ? { type: 'UserAssigned', userAssignedIdentities: { '${registryIdentityId}': {} } } : { type: 'SystemAssigned' }
  properties: {
    environmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        { server: registryServer, identity: useUserIdentity ? registryIdentityId : 'system' }
      ]
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          resources: { cpu: json(production ? '1.0' : '0.5'), memory: production ? '2Gi' : '1Gi' }
          env: [ { name: 'SERVICE_NAME', value: instance } ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/health', port: 8000 }, periodSeconds: 30 }
            { type: 'Readiness', httpGet: { path: '/ready', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      scale: { minReplicas: minReplicas, maxReplicas: production ? 10 : 3 }
    }
  }
}
output applicationId string = app.id
output applicationName string = app.name
output applicationUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output image string = app.properties.template.containers[0].image
output principalId string = useUserIdentity ? '' : app.identity.principalId
