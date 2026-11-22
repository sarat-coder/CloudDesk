# Compute module — ECS Fargate (AWS) / Container Apps (Azure) / Cloud Run (GCP)

variable "project"        { type = string }
variable "environment"    { type = string }
variable "cloud"          { type = string; default = "aws" }
variable "backend_image"  { type = string }
variable "frontend_image" { type = string }
variable "redis_url"      { type = string }
variable "secrets_arn"    { type = string }
variable "vpc_id"         { type = string; default = "" }
variable "subnet_ids"     { type = list(string); default = [] }
variable "gcp_project"    { type = string; default = "" }
variable "gcp_region"     { type = string; default = "" }

output "backend_target_group_arn"  { value = "placeholder-backend-tg" }
output "frontend_target_group_arn" { value = "placeholder-frontend-tg" }
