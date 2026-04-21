resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name_prefix}-ingress"
  retention_in_days = 7
}

locals {
  create_task_execution_role   = var.task_execution_role_arn == null
  effective_execution_role_arn = local.create_task_execution_role ? aws_iam_role.task_execution_role[0].arn : var.task_execution_role_arn
}

resource "aws_iam_role" "task_execution_role" {
  count = local.create_task_execution_role ? 1 : 0
  name  = "${var.name_prefix}-ingress-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "exec_role_policy" {
  count      = local.create_task_execution_role ? 1 : 0
  role       = aws_iam_role.task_execution_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_task_definition" "this" {
  family                   = "${var.name_prefix}-ingress"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = local.effective_execution_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "ingress-api"
      image     = var.ingress_image_uri
      essential = true
      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "SPRING_PROFILES_ACTIVE", value = "aws" },
        { name = "APP_ROLE", value = "ingress" },
        { name = "DB_HOST", value = var.db_host },
        { name = "DB_PORT", value = tostring(var.db_port) },
        { name = "DB_NAME", value = var.db_name },
        { name = "DB_USERNAME", value = var.db_username },
        { name = "DB_PASSWORD", value = var.db_password },
        { name = "KAFKA_BOOTSTRAP_SERVERS", value = var.kafka_bootstrap_servers },
        { name = "KAFKA_CONSUMER_GROUP_ID", value = "notification-requested-consumer-group" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "this" {
  name            = "${var.name_prefix}-ingress-service"
  cluster         = var.cluster_id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_service_sg_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "ingress-api"
    container_port   = 8080
  }
  depends_on = [aws_iam_role_policy_attachment.exec_role_policy]
}

data "aws_region" "current" {}
