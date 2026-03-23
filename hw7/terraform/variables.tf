# Region to deploy into
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

# ECR & ECS settings
variable "ecr_repository_name" {
  type    = string
  default = "ecr_service"
}

variable "service_name" {
  type    = string
  default = "CS6650L2"
}

variable "container_port" {
  type    = number
  default = 8080
}

variable "ecs_count" {
  type    = number
  default = 2
}

# How long to keep logs
variable "log_retention_days" {
  type    = number
  default = 7
}

variable "existing_lambda_role_arn" {
  type        = string
  default     = "arn:aws:iam::654385348207:role/LabRole"
  description = "Existing Lambda execution role ARN to reuse when the account cannot create IAM roles"
}

variable "shared_lab_role_arn" {
  type        = string
  default     = "arn:aws:iam::654385348207:role/LabRole"
  description = "Existing LabRole ARN reused for ECS task and Lambda execution roles"
}
