variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "scalable-notification-system"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "db_name" {
  type    = string
  default = "notification_db"
}

variable "db_username" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "admin_cidr_blocks" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "ec2_key_name" {
  type = string
}

variable "app_image_tag" {
  type    = string
  default = "latest"
}

variable "ecs_task_execution_role_arn" {
  type    = string
  default = null
}