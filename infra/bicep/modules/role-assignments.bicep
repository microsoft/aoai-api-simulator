param currentUserPrincipalId string

param keyVaultName string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

resource assignSecretsReaderRole_CurrentUser 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, keyVault.name, currentUserPrincipalId, 'assignSecretsReaderRole')
  scope: keyVault
  properties: {
    description: 'Assign Key Vault Secrets Reader role to current user'
    principalId: currentUserPrincipalId
    principalType: 'User'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}
