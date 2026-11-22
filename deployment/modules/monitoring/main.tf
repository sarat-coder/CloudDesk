# Monitoring module — CloudWatch (AWS) / Log Analytics (Azure) / Cloud Logging (GCP)

variable "project"     { type = string }
variable "environment" { type = string }
variable "cloud"       { type = string; default = "aws" }
variable "gcp_project" { type = string; default = "" }

output "log_group_name" { value = "/clouddesk/${var.environment}" }
