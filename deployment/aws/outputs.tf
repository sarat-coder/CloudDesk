output "backend_url" {
  description = "Public URL for the CloudDesk backend API"
  value       = module.load_balancer.backend_url
}

output "frontend_url" {
  description = "Public URL for the CloudDesk frontend"
  value       = module.load_balancer.frontend_url
}

output "backend_repository_url" {
  description = "ECR repository URL for the backend image"
  value       = module.registry.backend_repository_url
}

output "frontend_repository_url" {
  description = "ECR repository URL for the frontend image"
  value       = module.registry.frontend_repository_url
}
