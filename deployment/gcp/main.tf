terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {}
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

module "networking" {
  source      = "../modules/networking"
  project     = var.project
  environment = var.environment
  cloud       = "gcp"
}

module "registry" {
  source      = "../modules/container-registry"
  project     = var.project
  environment = var.environment
  cloud       = "gcp"
  gcp_project = var.gcp_project_id
}

module "secrets" {
  source      = "../modules/secrets"
  project     = var.project
  environment = var.environment
  cloud       = "gcp"
  gcp_project = var.gcp_project_id
}

module "redis" {
  source      = "../modules/redis"
  project     = var.project
  environment = var.environment
  cloud       = "gcp"
}

module "compute" {
  source         = "../modules/compute"
  project        = var.project
  environment    = var.environment
  cloud          = "gcp"
  backend_image  = "${module.registry.backend_repository_url}:${var.image_tag}"
  frontend_image = "${module.registry.frontend_repository_url}:${var.image_tag}"
  redis_url      = module.redis.connection_url
  secrets_arn    = module.secrets.secrets_arn
  gcp_project    = var.gcp_project_id
  gcp_region     = var.gcp_region
}

module "load_balancer" {
  source      = "../modules/load-balancer"
  project     = var.project
  environment = var.environment
  cloud       = "gcp"
}

module "monitoring" {
  source      = "../modules/monitoring"
  project     = var.project
  environment = var.environment
  cloud       = "gcp"
  gcp_project = var.gcp_project_id
}
