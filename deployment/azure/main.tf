terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
}

module "networking" {
  source      = "../modules/networking"
  project     = var.project
  environment = var.environment
  cloud       = "azure"
}

module "registry" {
  source      = "../modules/container-registry"
  project     = var.project
  environment = var.environment
  cloud       = "azure"
}

module "secrets" {
  source      = "../modules/secrets"
  project     = var.project
  environment = var.environment
  cloud       = "azure"
}

module "redis" {
  source      = "../modules/redis"
  project     = var.project
  environment = var.environment
  cloud       = "azure"
}

module "compute" {
  source         = "../modules/compute"
  project        = var.project
  environment    = var.environment
  cloud          = "azure"
  backend_image  = "${module.registry.backend_repository_url}:${var.image_tag}"
  frontend_image = "${module.registry.frontend_repository_url}:${var.image_tag}"
  redis_url      = module.redis.connection_url
  secrets_arn    = module.secrets.secrets_arn
}

module "load_balancer" {
  source      = "../modules/load-balancer"
  project     = var.project
  environment = var.environment
  cloud       = "azure"
}

module "monitoring" {
  source      = "../modules/monitoring"
  project     = var.project
  environment = var.environment
  cloud       = "azure"
}
