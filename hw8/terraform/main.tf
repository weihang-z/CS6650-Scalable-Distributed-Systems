locals {
  cluster_name = "${var.service_name}-cluster"
  app_source_files = sort(concat(
    tolist(fileset("${path.module}/..", "*.go")),
    [
      "go.mod",
      "go.sum",
      "Dockerfile",
      ".dockerignore"
    ]
  ))
  app_image_tag = substr(sha256(join("", [
    for file in local.app_source_files : filesha256("${path.module}/../${file}")
  ])), 0, 12)
  app_image = "${module.ecr.repository_url}:${local.app_image_tag}"
}

module "network" {
  source = "./modules/network"
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
  source            = "./modules/alb"
  service_name      = var.service_name
  vpc_id            = module.network.vpc_id
  subnet_ids        = module.network.subnet_ids
  target_port       = var.container_port
  health_check_path = "/health"
}

resource "aws_ecs_cluster" "this" {
  name = local.cluster_name
}

resource "aws_security_group" "ecs_service" {
  name        = "${var.service_name}-ecs-sg"
  description = "Allow the ALB to reach the ECS service"
  vpc_id      = module.network.vpc_id

  ingress {
    description     = "HTTP from the ALB"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [module.alb.security_group_id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

module "ecs" {
  source             = "./modules/ecs"
  cluster_id         = aws_ecs_cluster.this.id
  service_name       = var.service_name
  container_name     = var.service_name
  image              = local.app_image
  container_port     = var.container_port
  subnet_ids         = module.network.subnet_ids
  security_group_ids = [aws_security_group.ecs_service.id]
  execution_role_arn = var.shared_lab_role_arn
  task_role_arn      = var.shared_lab_role_arn
  log_group_name     = module.logging.log_group_name
  log_stream_prefix  = var.service_name
  desired_count      = var.ecs_count
  region             = var.aws_region
  cpu                = "256"
  memory             = "512"
  target_group_arn   = module.alb.target_group_arn
  environment = [
    {
      name  = "AWS_REGION"
      value = var.aws_region
    },
    {
      name  = "DYNAMODB_TABLE"
      value = aws_dynamodb_table.shopping_carts.name
    }
  ]

  depends_on = [
    docker_registry_image.app,
    module.alb,
    module.network
  ]
}

module "rds" {
  source = "./modules/rds"

  project_name               = "online-store"
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  ecs_task_security_group_id = aws_security_group.ecs_service.id

  db_name        = "store"
  db_username    = "appuser"
  db_password    = var.db_password
  engine_version = "8.0.45"
}

module "autoscaling" {
  source       = "./modules/autoscaling"
  cluster_name = aws_ecs_cluster.this.name
  service_name = module.ecs.service_name

  min_capacity       = 1
  max_capacity       = 1
  cpu_target_value   = 60
  scale_in_cooldown  = 15
  scale_out_cooldown = 15

  depends_on = [module.ecs]
}

resource "aws_dynamodb_table" "shopping_carts" {
  name         = "${var.service_name}-shopping-carts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "cart_id"

  attribute {
    name = "cart_id"
    type = "N"
  }

  tags = {
    Name = "${var.service_name}-shopping-carts"
  }
}

resource "docker_image" "app" {
  name = local.app_image

  build {
    context = ".."
  }
}

resource "docker_registry_image" "app" {
  name = docker_image.app.name
}
