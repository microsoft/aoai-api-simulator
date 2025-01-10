targetScope = 'resourceGroup'

@description('The base name for the deployment')
param baseName string

@description('The supported Azure location (region) where the resources will be deployed')
param location string

@secure()
param simulatorApiKey string

@secure()
param azureOpenAIKey string

param currentUserPrincipalId string

var containerRegistryName = replace('aoaisim-${baseName}', '-', '')
var managedIdentityName = 'aoaisim-${baseName}'
var keyVaultName = replace('aoaisim-${baseName}', '-', '')
var storageAccountName = replace('aoaisim${baseName}', '-', '')


resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-12-01-preview' existing = {
  name: containerRegistryName
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
}

module roleAssignments './modules/role-assignments.bicep' = {
  name: 'roleAssignments'
  params: {
    currentUserPrincipalId: currentUserPrincipalId

    managedIdentityName: managedIdentityName
    containerRegistryName: containerRegistryName
    keyVaultName: keyVaultName
  }
}

module monitor './modules/monitor.bicep' = {
  name: 'monitor'
  params: {
    baseName: baseName
    location: location
  }
}

module applicationSecrets './modules/application-secrets.bicep' = {
  name: 'keyVault'
  params: {
    simulatorApiKey: simulatorApiKey
    azureOpenAIKey: azureOpenAIKey

    keyVaultName: keyVaultName
    appInsightsName: monitor.outputs.logAnalyticsName
  }
}

module kubernetesService './modules/kubernetes-service.bicep' = {
  name: 'kubernetesService'
  params: {
    baseName: baseName
    location: location

    managedIdentityName: managedIdentityName
    containerRegistryName: containerRegistryName
  }
}

output rgName string = resourceGroup().name
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerRegistryName string = containerRegistryName
output storageAccountName string = storageAccountName
output fileShareName string = 'TODO'

output aksClusterName string = kubernetesService.outputs.aksClusterName
output acaIdentityId string = managedIdentity.id

output logAnalyticsName string = monitor.outputs.logAnalyticsName

output keyVaultName string = keyVaultName
