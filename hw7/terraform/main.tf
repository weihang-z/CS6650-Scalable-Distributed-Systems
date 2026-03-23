
locals {
  cluster_name         = "${var.service_name}-cluster"
  order_receiver_name  = "${var.service_name}-order-receiver"
  order_processor_name = "${var.service_name}-order-processor"

  # The repo currently builds a single image. Keep the service split in Terraform,
  # and swap these image URIs independently once receiver/processor images diverge.
  app_image = "${module.ecr.repository_url}:latest"
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

resource "aws_security_group" "order_receiver_service" {
  name        = "${local.order_receiver_name}-sg"
  description = "Allow the ALB to reach the order receiver service"
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

resource "aws_security_group" "order_processor_service" {
  name        = "${local.order_processor_name}-sg"
  description = "Worker service does not accept inbound traffic"
  vpc_id      = module.network.vpc_id

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

module "order_receiver_ecs" {
  source             = "./modules/ecs"
  cluster_id         = aws_ecs_cluster.this.id
  service_name       = local.order_receiver_name
  container_name     = "order-receiver"
  image              = local.app_image
  container_port     = var.container_port
  subnet_ids         = module.network.subnet_ids
  security_group_ids = [aws_security_group.order_receiver_service.id]
  execution_role_arn = var.shared_lab_role_arn
  task_role_arn      = var.shared_lab_role_arn
  log_group_name     = module.logging.log_group_name
  log_stream_prefix  = "order-receiver"
  desired_count      = 1
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
      name  = "ORDER_EVENTS_TOPIC_ARN"
      value = aws_sns_topic.order_processing_events.arn
    },
    {
      name  = "APP_MODE"
      value = "receiver"
    }
  ]

  depends_on = [
    docker_registry_image.app,
    module.alb,
    module.network
  ]
}

module "order_processor_ecs" {
  source             = "./modules/ecs"
  cluster_id         = aws_ecs_cluster.this.id
  service_name       = local.order_processor_name
  container_name     = "order-processor"
  image              = local.app_image
  container_port     = null
  subnet_ids         = module.network.subnet_ids
  security_group_ids = [aws_security_group.order_processor_service.id]
  execution_role_arn = var.shared_lab_role_arn
  task_role_arn      = var.shared_lab_role_arn
  log_group_name     = module.logging.log_group_name
  log_stream_prefix  = "order-processor"
  desired_count      = 1
  region             = var.aws_region
  cpu                = "256"
  memory             = "512"
  environment = [
    {
      name  = "AWS_REGION"
      value = var.aws_region
    },
    {
      name  = "ORDER_PROCESSING_QUEUE_URL"
      value = aws_sqs_queue.order_processing_queue.id
    },
    {
      name  = "WORKER_COUNT"
      value = "100"
    },
    {
      name  = "APP_MODE"
      value = "processor"
    }
  ]

  depends_on = [
    docker_registry_image.app,
    module.network
  ]
}

module "autoscaling" {
  source       = "./modules/autoscaling"
  cluster_name = aws_ecs_cluster.this.name
  service_name = module.order_receiver_ecs.service_name

  min_capacity       = 1
  max_capacity       = 1
  cpu_target_value   = 60
  scale_in_cooldown  = 15
  scale_out_cooldown = 15

  depends_on = [module.order_receiver_ecs]
}

// Build & push the Go app image into ECR
resource "docker_image" "app" {
  # Use the URL from the ecr module, and tag it "latest"
  name = local.app_image

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
