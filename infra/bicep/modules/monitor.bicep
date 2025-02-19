@description('The base name for the deployment')
param baseName string

@description('The supported Azure location (region) where the resources will be deployed')
param location string

var logAnalyticsName = 'aoaisim-${baseName}'
var appInsightsName = 'aoaisim-${baseName}'

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

output logAnalyticsName string = logAnalyticsName
