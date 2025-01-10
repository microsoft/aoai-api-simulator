@description('The base name for the deployment')
param baseName string

@description('The supported Azure location (region) where the resources will be deployed')
param location string

@description('Disk size (in GiB) to provision for each of the agent pool nodes. This value ranges from 0 to 1023. Specifying 0 will apply the default disk size for that agentVMSize.')
@minValue(0)
@maxValue(1023)
param osDiskSizeGB int = 0

@description('The number of nodes for the cluster. 1 Node is enough for Dev/Test and minimum 3 nodes, is recommended for Production')
@minValue(1)
@maxValue(100)
param agentCount int = 3

@description('The size of the Virtual Machine.')
param agentVMSize string = 'Standard_D2s_v3'

@description('The type of operating system.')
@allowed([
  'Linux'
  'Windows'
])
param osType string = 'Linux'

param managedIdentityName string
param containerRegistryName string

var aksClusterName = 'aoaisim-${baseName}'

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2021-12-01-preview' existing = {
  name: containerRegistryName
}

resource aksCluster 'Microsoft.ContainerService/managedClusters@2024-02-01' = {
  location: location
  name: aksClusterName
  tags: {
    displayname: 'AKS Cluster'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    enableRBAC: true
    dnsPrefix: aksClusterName
    agentPoolProfiles: [
      {
        name: 'agentpool'
        osDiskSizeGB: osDiskSizeGB
        count: agentCount
        vmSize: agentVMSize
        osType: osType
        type: 'VirtualMachineScaleSets'
        mode: 'System'
      }
    ]
  }
}

var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aksCluster.id, acrPullRoleDefinitionId)
  scope: containerRegistry
  properties: {
    principalId: aksCluster.properties.identityProfile.kubeletidentity.objectId
    roleDefinitionId: acrPullRoleDefinitionId
    principalType: 'ServicePrincipal'
  }
}

output aksClusterName string = aksClusterName
output controlPlaneFQDN string = aksCluster.properties.fqdn
