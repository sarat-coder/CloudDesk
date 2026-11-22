# Secrets module — Secrets Manager (AWS) / Key Vault (Azure) / Secret Manager (GCP)
# Secrets are injected via TF_VAR_* environment variables in CI — never in committed files.

variable "project"     { type = string }
variable "environment" { type = string }
variable "cloud"       { type = string; default = "aws" }
variable "gcp_project" { type = string; default = "" }

output "secrets_arn" { value = "placeholder-secrets-arn" }
