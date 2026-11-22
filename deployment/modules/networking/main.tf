# Networking module — VPC, subnets, NAT gateway (AWS) / VNet (Azure) / VPC (GCP)
# Cloud-specific resources are created via cloud-specific sub-modules or conditional blocks.

variable "project"     { type = string }
variable "environment" { type = string }
variable "cloud"       { type = string; default = "aws" }
variable "vpc_cidr"    { type = string; default = "10.0.0.0/16" }

output "vpc_id"              { value = "placeholder-vpc-id" }
output "private_subnet_ids"  { value = ["placeholder-subnet-1", "placeholder-subnet-2"] }
output "public_subnet_ids"   { value = ["placeholder-public-1", "placeholder-public-2"] }
