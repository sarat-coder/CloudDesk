# Container registry module — ECR (AWS) / ACR (Azure) / Artifact Registry (GCP)

variable "project"     { type = string }
variable "environment" { type = string }
variable "cloud"       { type = string; default = "aws" }
variable "gcp_project" { type = string; default = "" }

output "backend_repository_url"  { value = "placeholder/${var.project}-backend" }
output "frontend_repository_url" { value = "placeholder/${var.project}-frontend" }
