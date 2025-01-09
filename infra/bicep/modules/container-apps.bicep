@description('The base name for the deployment')
param baseName string

@description('The supported Azure location (region) where the resources will be deployed')
param location string

param logAnalyticsName string
param storageAccountName string
param keyVaultName string
param containerRegistryName string
param managedIdentityName string

param simulatorImageTag string
param simulatorMode string
param recordingDir string
param recordingAutoSave string
param extensionPath string
param azureOpenAIEndpoint string
param logLevel string

var containerAppEnvName = 'aoaisim-${baseName}'
var apiSimulatorName = 'aoai-api-simulator'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2021-12-01-preview' existing = {
  name: logAnalyticsName
}

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

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-12-01-preview' existing = {
  name: containerRegistryName
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
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
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/simulator-api-key'
          identity: managedIdentity.id
        }
        {
          name: 'azure-openai-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/azure-openai-key'
          identity: managedIdentity.id
        }
        {
          name: 'app-insights-connection-string'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/app-insights-connection-string'
          identity: managedIdentity.id
        }
        {
          name: 'deployment-config'
          value: loadTextContent('../../.openai_deployment_config.json')
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
            { name: 'OPENAI_DEPLOYMENT_CONFIG_PATH', value: '/mnt/deployment-config/simulator_deployment_config.json' }
            { name: 'LOG_LEVEL', value: logLevel }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'app-insights-connection-string' }
            // Ensure cloudRoleName is set in telemetry
            // https://opentelemetry-python.readthedocs.io/en/latest/sdk/environment_variables.html#opentelemetry.sdk.environment_variables.OTEL_SERVICE_NAME
            { name: 'OTEL_SERVICE_NAME', value: apiSimulatorName }
            { name: 'OTEL_METRIC_EXPORT_INTERVAL', value: '10000' } // metric export interval in milliseconds
          ]
          volumeMounts: [
            {
              volumeName: 'deployment-config'
              mountPath: '/mnt/deployment-config'
            }
            {
              volumeName: 'simulator-storage'
              mountPath: '/mnt/simulator'
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'deployment-config'
          storageType: 'Secret'
          secrets:[
            {
              secretRef:'deployment-config'
              path:'simulator_deployment_config.json'
            }
          ]
        }
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

output containerAppName string = apiSim.name
output containerAppEnvName string = containerAppEnv.name
output applicationFqdn string = apiSim.properties.configuration.ingress.fqdn
output simulatorFileShareName string = simulatorFileShare.name
