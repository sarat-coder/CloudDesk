output "backend_url" {
  value = module.load_balancer.backend_url
}

output "frontend_url" {
  value = module.load_balancer.frontend_url
}

output "backend_repository_url" {
  value = module.registry.backend_repository_url
}

output "frontend_repository_url" {
  value = module.registry.frontend_repository_url
}
