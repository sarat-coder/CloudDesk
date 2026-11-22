variable "project" {
  type    = string
  default = "clouddesk"
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod"
  }
}

variable "azure_location" {
  type    = string
  default = "East US"
}

variable "image_tag" {
  description = "Docker image tag (git SHA) — passed via TF_VAR_image_tag"
  type        = string
}
