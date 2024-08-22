targetScope = 'resourceGroup'

@description('The base name for the deployment')
param baseName string

@description('The supported Azure location (region) where the resources will be deployed')
param location string

@description('The mode the simulator should run in')
param simulatorMode string

@description('The API key the simulator will use to authenticate requests')
@secure()
param simulatorApiKey string

param recordingDir string

param recordingAutoSave string

param extensionPath string

param azureOpenAIEndpoint string

@secure()
param azureOpenAIKey string

param openAIDeploymentConfigPath string

param logLevel string

param simulatorImageTag string

param currentUserPrincipalId string

// extract these to a common module to have a single, shared place for these across base/infra?
var containerRegistryName = replace('aoaisim-${baseName}', '-', '')
var containerAppEnvName = 'aoaisim-${baseName}'
var logAnalyticsName = 'aoaisim-${baseName}'
var appInsightsName = 'aoaisim-${baseName}'
var keyVaultName = replace('aoaisim-${baseName}', '-', '')
var storageAccountName = replace('aoaisim${baseName}', '-', '')

var apiSimulatorName = 'aoai-api-simulator'

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-12-01-preview' existing = {
  name: containerRegistryName
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}
var keyVaultUri = vault.properties.vaultUri

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}
resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' existing = {
  parent: storageAccount
  name: 'default'
}
resource simulatorFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' existing = {
  parent: fileService
  name: 'simulator'
}

resource acrPullRoleDefinition 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: subscription()
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d' // https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#acrpull
}
resource assignAcrPullToAca 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, containerRegistry.name, managedIdentity.name, 'AssignAcrPullToAks')
  scope: containerRegistry
  properties: {
    description: 'Assign AcrPull role to ACA identity'
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinition.id
  }
}
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2021-12-01-preview' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${containerAppEnvName}-identity'
  location: location
}

resource keyVaultSecretsUserRoleDefinition 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: subscription()
  name: '4633458b-17de-408a-b874-0445c86b69e6' // https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-guide?tabs=azure-cli
}
resource assignSecretsReaderRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, vault.name, managedIdentity.name, 'assignSecretsReaderRole')
  scope: vault
  properties: {
    description: 'Assign Key Vault Secrets Reader role to ACA identity'
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinition.id
  }
}

resource assignSecretsReaderRole_CurrentUser 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, vault.name, currentUserPrincipalId, 'assignSecretsReaderRole')
  scope: vault
  properties: {
    description: 'Assign Key Vault Secrets Reader role to current user'
    principalId: currentUserPrincipalId
    principalType: 'User'
    roleDefinitionId: keyVaultSecretsUserRoleDefinition.id
  }
}



resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-11-02-preview' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}
resource containerAppStorage 'Microsoft.App/managedEnvironments/storages@2023-05-01' = {
  parent: containerAppEnv
  name: 'simulator-storage'
  properties: {
    azureFile: {
      shareName: simulatorFileShare.name
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      accessMode: 'ReadWrite'
    }
  }
}

resource simulatorApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'simulator-api-key'
  properties: {
    value: simulatorApiKey
  }
}
resource azureOpenAIKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'azure-openai-key'
  properties: {
    value: azureOpenAIKey
  }
}
resource appInsightsConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'app-insights-connection-string'
  properties: {
    value: appInsights.properties.ConnectionString
  }
}

resource apiSim 'Microsoft.App/containerApps@2023-05-01' = {
  name: apiSimulatorName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {} // use this for accessing ACR, secrets
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'single'
      // setting maxInactiveRevisions to 0 makes it easier when iterating and fixing issues by preventing 
      // old revisions showing in logs etc
      maxInactiveRevisions: 0
      ingress: {
        external: true
        targetPort: 8000
      }
      secrets: [
        {
          name: 'simulator-api-key'
          keyVaultUrl: '${keyVaultUri}secrets/simulator-api-key'
          identity: managedIdentity.id
        }
        {
          name: 'azure-openai-key'
          keyVaultUrl: '${keyVaultUri}secrets/azure-openai-key'
          identity: managedIdentity.id
        }
        {
          name: 'app-insights-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/app-insights-connection-string'
          identity: managedIdentity.id
        }
      ]
      registries: [
        {
          identity: managedIdentity.id
          server: containerRegistry.properties.loginServer
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'aoai-api-simulator'
          image: '${containerRegistry.properties.loginServer}/aoai-api-simulator:${simulatorImageTag}'
          resources: {
            cpu: json('1')
            memory: '2Gi'
          }
          env: [
            { name: 'SIMULATOR_API_KEY', secretRef: 'simulator-api-key' }
            { name: 'SIMULATOR_MODE', value: simulatorMode }
            { name: 'RECORDING_DIR', value: recordingDir }
            { name: 'RECORDING_AUTO_SAVE', value: recordingAutoSave }
            { name: 'EXTENSION_PATH', value: extensionPath }
            { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAIEndpoint }
            { name: 'AZURE_OPENAI_KEY', secretRef: 'azure-openai-key' }
            { name: 'OPENAI_DEPLOYMENT_CONFIG_PATH', value: openAIDeploymentConfigPath }
            { name: 'LOG_LEVEL', value: logLevel }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'app-insights-connection-string' }
            // Ensure cloudRoleName is set in telemetry
            // https://opentelemetry-python.readthedocs.io/en/latest/sdk/environment_variables.html#opentelemetry.sdk.environment_variables.OTEL_SERVICE_NAME
            { name: 'OTEL_SERVICE_NAME', value: apiSimulatorName }
            { name: 'OTEL_METRIC_EXPORT_INTERVAL', value: '10000' } // metric export interval in milliseconds
          ]
          volumeMounts: [
            {
              volumeName: 'simulator-storage'
              mountPath: '/mnt/simulator'
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'simulator-storage'
          storageName: containerAppStorage.name
          storageType: 'AzureFile'
          mountOptions: 'uid=1000,gid=1000,nobrl,mfsymlinks,cache=none'
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output rgName string = resourceGroup().name
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerRegistryName string = containerRegistry.name
output storageAccountName string = storageAccount.name
output fileShareName string = simulatorFileShare.name

output acaName string = apiSim.name
output acaEnvName string = containerAppEnv.name
output acaIdentityId string = managedIdentity.id
output apiSimFqdn string = apiSim.properties.configuration.ingress.fqdn

output logAnalyticsName string = logAnalyticsName

output keyVaultName string = vault.name
