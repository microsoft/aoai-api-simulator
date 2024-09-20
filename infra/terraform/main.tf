terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.0"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
  }
  subscription_id = var.azure_subscription_id
}

locals {
  root_name            = "${var.resource_group_name}-${var.base_name}"
  root_name_normalized = replace("${local.root_name}", "-", "")
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_key_vault" "kv" {
  name                            = local.root_name_normalized
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
  tenant_id                       = data.azurerm_client_config.current.tenant_id
  sku_name                        = "standard"
  soft_delete_retention_days      = 90
  purge_protection_enabled        = true
  enabled_for_deployment          = false
  enabled_for_disk_encryption     = false
  enabled_for_template_deployment = false
  enable_rbac_authorization       = true

  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }
}

resource "azurerm_key_vault_secret" "openaikey" {
  depends_on = [
    azurerm_role_assignment.kv_sp_secrets_user,
    azurerm_role_assignment.kv_user_secrets_user,
    azurerm_role_assignment.kv_user_secrets_officer
  ]
  name         = "azure-openai-key"
  value        = var.azure_openai_key
  key_vault_id = azurerm_key_vault.kv.id
}

resource "azurerm_key_vault_secret" "simulatorapikey" {
  depends_on = [
    azurerm_role_assignment.kv_sp_secrets_user,
    azurerm_role_assignment.kv_user_secrets_user,
    azurerm_role_assignment.kv_user_secrets_officer
  ]
  name         = "simulator-api-key"
  value        = var.simulator_api_key
  key_vault_id = azurerm_key_vault.kv.id
}

resource "azurerm_key_vault_secret" "appinsights" {
  depends_on = [
    azurerm_role_assignment.kv_sp_secrets_user,
    azurerm_role_assignment.kv_user_secrets_user,
    azurerm_role_assignment.kv_user_secrets_officer
  ]
  name         = "app-insights-connection-string"
  value        = azurerm_application_insights.app_insights.connection_string
  key_vault_id = azurerm_key_vault.kv.id
}

resource "azurerm_storage_account" "storage" {
  name                     = local.root_name_normalized
  location                 = azurerm_resource_group.rg.location
  resource_group_name      = var.resource_group_name
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
}

resource "azurerm_storage_share" "simulator" {
  name                 = "simulator"
  storage_account_name = azurerm_storage_account.storage.name
  quota                = 5120 # Set quota as needed
}

resource "azurerm_container_registry" "acr" {
  name                = local.root_name_normalized
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
}

resource "azurerm_log_analytics_workspace" "log_analytics" {
  name                = local.root_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "app_insights" {
  name                = local.root_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
}

resource "azurerm_user_assigned_identity" "identity" {
  name                = "${var.resource_group_name}-identity"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_role_assignment" "kv_user_secrets_user" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = data.azurerm_client_config.current.object_id
  principal_type       = "User"
  description          = "Assign Key Vault Secrets Reader role to current identity"
}

resource "azurerm_role_assignment" "kv_user_secrets_officer" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
  principal_type       = "User"
  description          = "Assign Key Vault Secrets Officer role to current user"
}

resource "azurerm_role_assignment" "acr_user_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "acr_user_push" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPush"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "acr_sp_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.identity.principal_id
}

resource "azurerm_role_assignment" "kv_sp_secrets_user" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.identity.principal_id
  principal_type       = "ServicePrincipal"
  description          = "Assign Key Vault Secrets Reader role to ACA identity"
}

resource "azurerm_container_app_environment" "aca_env" {
  name                       = local.root_name
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id
}

resource "azurerm_container_app_environment_storage" "storage" {
  name                         = "simulator"
  container_app_environment_id = azurerm_container_app_environment.aca_env.id
  account_name                 = azurerm_storage_account.storage.name
  share_name                   = azurerm_storage_share.simulator.name
  access_key                   = azurerm_storage_account.storage.primary_access_key
  access_mode                  = "ReadOnly"
}

resource "azurerm_container_app" "container_app" {
  name                         = "${var.resource_group_name}-app"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca_env.id
  revision_mode                = "Single"

  depends_on = [
    null_resource.docker,
    azurerm_key_vault_secret.appinsights,
    azurerm_key_vault_secret.openaikey,
    azurerm_key_vault_secret.simulatorapikey
  ]

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.identity.id]
  }
  ingress {
    target_port      = 8000
    external_enabled = true
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.identity.id
  }

  dynamic "secret" {
    for_each = ["azure-openai-key", "app-insights-connection-string", "simulator-api-key"]
    content {
      name                = secret.value
      key_vault_secret_id = "${azurerm_key_vault.kv.vault_uri}secrets/${secret.value}"
      identity            = azurerm_user_assigned_identity.identity.id
    }
  }

  secret {
    name  = "deployment-config"
    value = var.simulator_api_key
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "aoai-api-simulator"
      image  = "${azurerm_container_registry.acr.login_server}/aoai-api-simulator:${var.simulator_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        for_each = {
          AZURE_OPENAI_ENDPOINT = var.azure_openai_endpoint
          SIMULATOR_MODE        = var.simulator_mode
          RECORDING_DIR         = var.recording_dir
          RECORDING_AUTO_SAVE   = var.recording_auto_save
          EXTENSION_PATH        = var.extension_path
          LOG_LEVEL             = var.log_level
        }
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = [
          {
            name        = "APPINSIGHTS_INSTRUMENTATIONKEY"
            secret_name = "app-insights-connection-string"
          },
          {
            name        = "AZURE_OPENAI_KEY"
            secret_name = "azure-openai-key"
          },
          {
            name        = "SIMULATOR_API_KEY"
            secret_name = "simulator-api-key"
          }
        ]
        content {
          name        = env.value.name
          secret_name = env.value.secret_name
        }
      }

      volume_mounts {
        name = "deployment-config"
        path = "/mnt/deployment-config"
      }

      volume_mounts {
        name = "simulator-storage"
        path = "/mnt/simulator"
      }

    }
    volume {
      name         = "deployment-config"
      storage_type = "Secret"
    }

    volume {
      name         = "simulator-storage"
      storage_name = azurerm_storage_share.simulator.name
      storage_type = "AzureFile"
    }
  }
}

# create a zip file from the source code so its hash can be used to trigger the build/push
data "archive_file" "init" {
  type        = "zip"
  source_dir = "${path.module}/../../src/aoai-api-simulator/"
  output_path = "data.zip"
}

resource "null_resource" "docker" {
  depends_on = [
    azurerm_container_registry.acr,
    azurerm_role_assignment.acr_user_push
  ]
  provisioner "local-exec" {
    command = <<-EOT
      terraform output -json | jq 'with_entries(.value |= .value)' > "../output.json"
      az acr login --name "${azurerm_container_registry.acr.login_server}"
      ../../scripts/docker-build-and-push.sh
    EOT
  }
  triggers = {
    src_hash = "${data.archive_file.init.output_sha}"
  }
}
