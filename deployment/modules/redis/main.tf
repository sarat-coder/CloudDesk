# Redis module — ElastiCache (AWS) / Azure Cache for Redis / Memorystore (GCP)

variable "project"     { type = string }
variable "environment" { type = string }
variable "cloud"       { type = string; default = "aws" }
variable "vpc_id"      { type = string; default = "" }
variable "subnet_ids"  { type = list(string); default = [] }

output "connection_url" { value = "redis://placeholder:6379/0" }
