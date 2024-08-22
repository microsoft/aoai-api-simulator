@description('The base name for the deployment')
param baseName string

@description('The supported Azure location (region) where the resources will be deployed')
param location string

//
// base.bicep deploys a container registry so that images can be pushed to it
// for use in other deployments.
//

var containerRegistryName = replace('aoaisim-${baseName}', '-', '')
var keyVaultName = replace('aoaisim-${baseName}', '-', '')
var storageAccountName = replace('aoaisim${baseName}', '-', '')

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-12-01-preview' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    accessPolicies:[]
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: false
    tenantId: subscription().tenantId
    sku: {
      name: 'standard'
      family: 'A'
    }
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'

}
resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent:storageAccount
  name: 'default'

}
resource simulatorFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileService
  name: 'simulator'
}

output rgName string = resourceGroup().name
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerRegistryName string = containerRegistry.name
output storageAccountName string = storageAccount.name
output fileShareName string = simulatorFileShare.name
