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

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  type    = string
  default = "us-central1"
}

variable "image_tag" {
  description = "Docker image tag (git SHA) — passed via TF_VAR_image_tag"
  type        = string
}
