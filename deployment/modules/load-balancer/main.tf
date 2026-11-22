# Load balancer module — ALB (AWS) / Azure Load Balancer / Cloud Load Balancing (GCP)

variable "project"         { type = string }
variable "environment"     { type = string }
variable "cloud"           { type = string; default = "aws" }
variable "vpc_id"          { type = string; default = "" }
variable "public_subnets"  { type = list(string); default = [] }
variable "backend_target"  { type = string; default = "" }
variable "frontend_target" { type = string; default = "" }

output "backend_url"  { value = "https://api.${var.environment}.clouddesk.example.com" }
output "frontend_url" { value = "https://app.${var.environment}.clouddesk.example.com" }
