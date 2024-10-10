output "acaEnvName" {
  description = "The name of the Azure Container Apps environment."
  value       = azurerm_container_app_environment.aca_env.name
}

output "acaIdentityId" {
  description = "The ID of the Azure Container Apps managed identity."
  value       = azurerm_user_assigned_identity.identity.id
}

output "acaName" {
  description = "The name of the Azure Container App."
  value       = azurerm_container_app.container_app.name
}

output "apiSimFqdn" {
  description = "The FQDN of the API simulator."
  value       = azurerm_container_app.container_app.ingress[0].fqdn
}

output "containerRegistryLoginServer" {
  description = "The login server of the container registry."
  value       = azurerm_container_registry.acr.login_server
}

output "containerRegistryName" {
  description = "The name of the container registry."
  value       = azurerm_container_registry.acr.name
}

output "fileShareName" {
  description = "The name of the file share."
  value       = azurerm_storage_share.simulator.name
}

output "keyVaultName" {
  description = "The name of the key vault."
  value       = azurerm_key_vault.kv.name
}

output "logAnalyticsName" {
  description = "The name of the log analytics workspace."
  value       = azurerm_log_analytics_workspace.log_analytics.name
}

output "rgName" {
  description = "The name of the resource group."
  value       = azurerm_resource_group.rg.name
}

output "storageAccountName" {
  description = "The name of the storage account."
  value       = azurerm_storage_account.storage.name
}
