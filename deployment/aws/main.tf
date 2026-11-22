terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Remote state — configure backend.hcl (git-ignored, never commit)
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# Shared modules
# ---------------------------------------------------------------------------

module "networking" {
  source      = "../modules/networking"
  project     = var.project
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
}

module "registry" {
  source      = "../modules/container-registry"
  project     = var.project
  environment = var.environment
  cloud       = "aws"
}

module "secrets" {
  source      = "../modules/secrets"
  project     = var.project
  environment = var.environment
  cloud       = "aws"
}

module "redis" {
  source         = "../modules/redis"
  project        = var.project
  environment    = var.environment
  cloud          = "aws"
  subnet_ids     = module.networking.private_subnet_ids
  vpc_id         = module.networking.vpc_id
}

module "compute" {
  source            = "../modules/compute"
  project           = var.project
  environment       = var.environment
  cloud             = "aws"
  backend_image     = "${module.registry.backend_repository_url}:${var.image_tag}"
  frontend_image    = "${module.registry.frontend_repository_url}:${var.image_tag}"
  subnet_ids        = module.networking.private_subnet_ids
  vpc_id            = module.networking.vpc_id
  secrets_arn       = module.secrets.secrets_arn
  redis_url         = module.redis.connection_url
}

module "load_balancer" {
  source         = "../modules/load-balancer"
  project        = var.project
  environment    = var.environment
  cloud          = "aws"
  vpc_id         = module.networking.vpc_id
  public_subnets = module.networking.public_subnet_ids
  backend_target = module.compute.backend_target_group_arn
  frontend_target = module.compute.frontend_target_group_arn
}

module "monitoring" {
  source      = "../modules/monitoring"
  project     = var.project
  environment = var.environment
  cloud       = "aws"
}
