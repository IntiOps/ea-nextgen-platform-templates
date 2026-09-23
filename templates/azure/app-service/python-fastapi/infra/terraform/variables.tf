variable "subscription_id" {
  type = string
  validation {
    condition     = can(regex("^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$", var.subscription_id))
    error_message = "A subscription UUID is required."
  }
}
variable "instance" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.instance))
    error_message = "Instance must contain 3–24 lowercase letters, digits or hyphens, starting with a letter."
  }
}
variable "location" {
  type    = string
  default = "westeurope"
  validation {
    condition     = can(regex("^[a-z0-9]{3,32}$", var.location))
    error_message = "Use an Azure region identifier."
  }
}

variable "owner_id" {
  type = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9-]{1,64}$", var.owner_id))
    error_message = "Use an immutable repository or Azure DevOps project identifier as owner_id."
  }
}

variable "purpose" {
  type    = string
  default = "development"
  validation {
    condition     = contains(["poc", "development", "staging", "production"], var.purpose)
    error_message = "Choose an explicit environment purpose."
  }
}
variable "retention_days" {
  type    = number
  default = 7
  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 365
    error_message = "Retention must be between 1 and 365 days."
  }
}
