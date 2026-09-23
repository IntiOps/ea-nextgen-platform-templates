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
    condition     = can(regex("^[0-9]{1,20}$", var.owner_id))
    error_message = "Use the immutable GitHub repository ID as owner_id."
  }
}
