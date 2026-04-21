data "aws_caller_identity" "current" {}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["137112412989"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

locals {
  project_root         = abspath("${path.module}/../../../../../../../../")
  app_image_tag        = var.app_image_tag
  app_image_uri        = "${module.ecr.repository_url}:${local.app_image_tag}"
  ecr_registry         = split("/", module.ecr.repository_url)[0]
  local_build_image    = "${var.project_name}:${local.app_image_tag}"
}

module "network" {
  source = "./modules/network"

  name_prefix = local.name_prefix
}

module "security" {
  source = "./modules/security"

  name_prefix       = local.name_prefix
  vpc_id            = module.network.vpc_id
  admin_cidr_blocks = var.admin_cidr_blocks
}

module "rds" {
  source = "./modules/rds"

  name_prefix            = local.name_prefix
  db_name                = var.db_name
  db_username            = var.db_username
  db_password            = var.db_password
  db_subnet_ids          = module.network.private_subnet_ids
  rds_security_group_id  = module.security.rds_sg_id
}

module "ecr" {
  source = "./modules/ecr"

  name_prefix = local.name_prefix
}

resource "terraform_data" "build_and_push_app_image" {
  triggers_replace = {
    repository_url = module.ecr.repository_url
    image_tag      = local.app_image_tag
    # Rebuild on each apply to avoid plan/apply drift from filesystem hashing.
    build_token    = plantimestamp()
  }

  provisioner "local-exec" {
    working_dir = local.project_root
    interpreter = ["/bin/bash", "-lc"]
    command     = <<-EOT
      set -euo pipefail

      if [ -x "./mvnw" ]; then
        ./mvnw -q -DskipTests spring-boot:build-image -Dspring-boot.build-image.imageName="${local.local_build_image}"
      else
        mvn -q -DskipTests spring-boot:build-image -Dspring-boot.build-image.imageName="${local.local_build_image}"
      fi

      aws ecr get-login-password --region "${var.aws_region}" | docker login --username AWS --password-stdin "${local.ecr_registry}"
      docker tag "${local.local_build_image}" "${local.app_image_uri}"
      docker push "${local.app_image_uri}"
    EOT
  }

  depends_on = [module.ecr]
}

module "ecs_cluster" {
  source = "./modules/ecs-cluster"

  name_prefix = local.name_prefix
}

module "ec2_kafka" {
  source = "./modules/ec2-kafka"

  name_prefix       = local.name_prefix
  subnet_id         = module.network.public_subnet_ids[0]
  security_group_id = module.security.kafka_ec2_sg_id
  key_name          = var.ec2_key_name
  ami_id            = data.aws_ami.amazon_linux_2023.id
}

module "alb" {
  source = "./modules/alb"

  name_prefix           = local.name_prefix
  vpc_id                = module.network.vpc_id
  public_subnet_ids     = module.network.public_subnet_ids
  alb_security_group_id = module.security.alb_sg_id
}

module "ecs_ingress" {
  source = "./modules/ecs-ingress"

  name_prefix               = local.name_prefix
  cluster_id                = module.ecs_cluster.cluster_id
  cluster_name              = module.ecs_cluster.cluster_name
  private_subnet_ids        = module.network.public_subnet_ids
  ecs_service_sg_id         = module.security.ingress_service_sg_id
  target_group_arn          = module.alb.ingress_target_group_arn
  ingress_image_uri         = local.app_image_uri

  db_host                   = module.rds.db_endpoint
  db_port                   = module.rds.db_port
  db_name                   = var.db_name
  db_username               = var.db_username
  db_password               = var.db_password
  kafka_bootstrap_servers   = "${module.ec2_kafka.private_ip}:9092"
  task_execution_role_arn   = var.ecs_task_execution_role_arn

  depends_on = [terraform_data.build_and_push_app_image]
}

module "email_worker" {
  source = "./modules/ecs-worker"

  name_prefix             = local.name_prefix
  worker_name             = "email-worker"
  channel                 = "EMAIL"
  cluster_id              = module.ecs_cluster.cluster_id
  private_subnet_ids      = module.network.public_subnet_ids
  worker_service_sg_id    = module.security.worker_service_sg_id
  worker_image_uri        = local.app_image_uri
  db_host                 = module.rds.db_endpoint
  db_port                 = module.rds.db_port
  db_name                 = var.db_name
  db_username             = var.db_username
  db_password             = var.db_password
  kafka_bootstrap_servers = "${module.ec2_kafka.private_ip}:9092"
  desired_count           = 1
  task_execution_role_arn = var.ecs_task_execution_role_arn

  depends_on = [terraform_data.build_and_push_app_image]
}

module "inapp_worker" {
  source = "./modules/ecs-worker"

  name_prefix             = local.name_prefix
  worker_name             = "inapp-worker"
  channel                 = "INAPP"
  cluster_id              = module.ecs_cluster.cluster_id
  private_subnet_ids      = module.network.public_subnet_ids
  worker_service_sg_id    = module.security.worker_service_sg_id
  worker_image_uri        = local.app_image_uri
  db_host                 = module.rds.db_endpoint
  db_port                 = module.rds.db_port
  db_name                 = var.db_name
  db_username             = var.db_username
  db_password             = var.db_password
  kafka_bootstrap_servers = "${module.ec2_kafka.private_ip}:9092"
  desired_count           = 1
  task_execution_role_arn = var.ecs_task_execution_role_arn

  depends_on = [terraform_data.build_and_push_app_image]
}