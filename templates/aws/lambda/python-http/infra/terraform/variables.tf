variable "region" { type = string }
variable "account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "An explicit AWS account ID is required."
  }
}
variable "owner_id" { type = string }
variable "instance" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.instance))
    error_message = "Instance must contain 3-24 lowercase letters, digits or hyphens."
  }
}
variable "purpose" {
  type = string
  validation {
    condition     = contains(["poc", "development", "staging", "production"], var.purpose)
    error_message = "Choose an explicit environment purpose."
  }
}
variable "revision" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.revision))
    error_message = "Use the immutable source commit."
  }
}
variable "retention_days" {
  type = number
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.retention_days)
    error_message = "Select a supported CloudWatch retention period."
  }
}
