# Wire together four focused modules: network, ecr, logging, ecs.

module "network" {
  source         = "./modules/network"
  service_name   = var.service_name
  container_port = var.container_port
}

module "ecr" {
  source          = "./modules/ecr"
  repository_name = var.ecr_repository_name
}

module "logging" {
  source            = "./modules/logging"
  service_name      = var.service_name
  retention_in_days = var.log_retention_days
}

module "alb" {
  source           = "./modules/alb"
  service_name     = var.service_name
  vpc_id           = module.network.vpc_id
  subnet_ids       = module.network.subnet_ids
  target_port      = var.container_port
  health_check_path = "/health"
}

# Reuse an existing IAM role for ECS tasks
data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

module "ecs" {
  source             = "./modules/ecs"
  service_name       = var.service_name
  image              = "${module.ecr.repository_url}:latest"
  container_port     = var.container_port
  subnet_ids         = module.network.subnet_ids
  security_group_ids = [module.network.security_group_id]
  execution_role_arn = data.aws_iam_role.lab_role.arn
  task_role_arn      = data.aws_iam_role.lab_role.arn
  log_group_name     = module.logging.log_group_name
  ecs_count          = 2
  region             = var.aws_region
  cpu                = "256"
  memory             = "512"
  target_group_arn   = module.alb.target_group_arn

  depends_on = [
    docker_registry_image.app,
    module.alb,
    module.network
  ]
}

module "autoscaling" {
  source       = "./modules/autoscaling"
  cluster_name = module.ecs.cluster_name
  service_name = module.ecs.service_name

  min_capacity      = 2
  max_capacity      = 6
  cpu_target_value  = 60
  scale_in_cooldown = 15
  scale_out_cooldown = 15

  depends_on = [module.ecs]
}

// Build & push the Go app image into ECR
resource "docker_image" "app" {
  # Use the URL from the ecr module, and tag it "latest"
  name = "${module.ecr.repository_url}:latest"

  build {
    # relative path from terraform/ → src/
    context = ".."
    # Dockerfile defaults to "Dockerfile" in that context
  }
}

resource "docker_registry_image" "app" {
  # this will push :latest → ECR
  name = docker_image.app.name
}
