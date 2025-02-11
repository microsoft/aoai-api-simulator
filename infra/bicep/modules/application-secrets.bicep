@description('The API key the simulator will use to authenticate requests')
@secure()
param simulatorApiKey string

@secure()
param azureOpenAIKey string

param keyVaultName string
param appInsightsName string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

resource simulatorApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'simulator-api-key'
  properties: {
    value: simulatorApiKey
  }
}

resource azureOpenAIKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'azure-openai-key'
  properties: {
    // workaround to deployment issue https://github.com/microsoft/aoai-api-simulator/issues/28
    value: empty(azureOpenAIKey) ? 'place-holder-API-key' : azureOpenAIKey
  }
}

resource appInsightsConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'app-insights-connection-string'
  properties: {
    value: appInsights.properties.ConnectionString
  }
}
