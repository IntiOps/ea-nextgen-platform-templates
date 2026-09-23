terraform {
  required_version = "= 1.14.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 4.62.0"
    }
  }
  backend "azurerm" {}
}

provider "azurerm" {
  features {
    resource_group { prevent_deletion_if_contains_resources = true }
  }
  subscription_id                 = var.subscription_id
  use_oidc                        = true
  resource_provider_registrations = "none"
}

locals {
  app_name = "ea-${var.instance}-${substr(sha256("${var.subscription_id}:${var.owner_id}:${var.instance}"), 0, 8)}"
  tags = {
    managed_by = "ea-nextgen-demo"
    instance   = var.instance
    owner_id   = var.owner_id
  }
}

resource "azurerm_resource_group" "demo" {
  name     = "rg-ea-demo-${var.instance}-${substr(sha256(var.owner_id), 0, 6)}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_service_plan" "demo" {
  name                = "${local.app_name}-plan"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  os_type             = "Linux"
  sku_name            = "B1"
  tags                = local.tags
}

resource "azurerm_linux_web_app" "demo" {
  name                                           = local.app_name
  resource_group_name                            = azurerm_resource_group.demo.name
  location                                       = azurerm_resource_group.demo.location
  service_plan_id                                = azurerm_service_plan.demo.id
  https_only                                     = true
  public_network_access_enabled                  = true
  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false
  tags                                           = local.tags

  site_config {
    always_on                         = true
    minimum_tls_version               = "1.2"
    ftps_state                        = "Disabled"
    health_check_eviction_time_in_min = 2
    health_check_path                 = "/health"
    app_command_line                  = "python -m uvicorn main:app --host 0.0.0.0 --port 8000"
    application_stack { python_version = "3.12" }
  }
  app_settings = {
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    ENABLE_ORYX_BUILD              = "true"
  }
}

output "application_url" { value = "https://${azurerm_linux_web_app.demo.default_hostname}" }
output "application_name" { value = azurerm_linux_web_app.demo.name }
output "resource_group_name" { value = azurerm_resource_group.demo.name }
output "resource_ids" {
  value = [azurerm_resource_group.demo.id, azurerm_service_plan.demo.id, azurerm_linux_web_app.demo.id]
}
