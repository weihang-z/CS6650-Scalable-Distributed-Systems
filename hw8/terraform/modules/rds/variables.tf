variable "project_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "ecs_task_security_group_id" {
  type = string
}

variable "db_name" {
  type    = string
  default = "store"
}

variable "db_username" {
  type    = string
  default = "appuser"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "engine_version" {
  type    = string
  default = "8.0.45"
}