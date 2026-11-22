variable "project" {
  description = "Project name used in resource naming"
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Deployment environment: dev, staging, or prod"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod"
  }
}

variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "image_tag" {
  description = "Docker image tag (git SHA) to deploy — image_tag = git SHA"
  type        = string
}
