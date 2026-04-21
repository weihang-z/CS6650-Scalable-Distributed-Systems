variable "name_prefix" {
  type = string
}

variable "cluster_id" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "ecs_service_sg_id" {
  type = string
}

variable "target_group_arn" {
  type = string
}

variable "ingress_image_uri" {
  type = string
}

variable "db_host" {
  type = string
}

variable "db_port" {
  type = number
}

variable "db_name" {
  type = string
}

variable "db_username" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "kafka_bootstrap_servers" {
  type = string
}

variable "task_execution_role_arn" {
  type    = string
  default = null
}
