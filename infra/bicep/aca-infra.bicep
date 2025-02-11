targetScope = 'resourceGroup'

@description('The base name for the deployment')
param baseName string

@description('The supported Azure location (region) where the resources will be deployed')
param location string

param simulatorImageTag string
param simulatorMode string
param recordingDir string
param recordingAutoSave string
param extensionPath string
param azureOpenAIEndpoint string
param logLevel string

@secure()
param simulatorApiKey string

@secure()
param azureOpenAIKey string

param currentUserPrincipalId string

var containerRegistryName = replace('aoaisim-${baseName}', '-', '')
var keyVaultName = replace('aoaisim-${baseName}', '-', '')
var storageAccountName = replace('aoaisim${baseName}', '-', '')


resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-12-01-preview' existing = {
  name: containerRegistryName
}

module roleAssignments './modules/role-assignments.bicep' = {
  name: 'roleAssignments'
  params: {
    currentUserPrincipalId: currentUserPrincipalId
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

module containerApps './modules/container-apps.bicep' = {
  name: 'containerApps'
  params: {
    baseName: baseName
    location: location

    logAnalyticsName: monitor.outputs.logAnalyticsName
    storageAccountName: storageAccountName
    keyVaultName: keyVaultName
    containerRegistryName: containerRegistryName

    simulatorImageTag: simulatorImageTag
    simulatorMode: simulatorMode
    recordingDir: recordingDir
    recordingAutoSave: recordingAutoSave
    extensionPath: extensionPath
    azureOpenAIEndpoint: azureOpenAIEndpoint
    logLevel: logLevel
  }
}

output rgName string = resourceGroup().name
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerRegistryName string = containerRegistryName
output storageAccountName string = storageAccountName
output fileShareName string = containerApps.outputs.simulatorFileShareName

output acaName string = containerApps.outputs.containerAppName
output acaEnvName string = containerApps.outputs.containerAppEnvName
output acaIdentityId string = containerApps.outputs.managedIdentityId
output apiSimFqdn string = containerApps.outputs.applicationFqdn

output logAnalyticsName string = monitor.outputs.logAnalyticsName

output keyVaultName string = keyVaultName
