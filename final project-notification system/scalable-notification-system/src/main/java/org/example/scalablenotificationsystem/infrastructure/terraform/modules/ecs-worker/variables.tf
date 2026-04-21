variable "name_prefix" {
  type = string
}

variable "worker_name" {
  type = string
}

variable "channel" {
  type = string
}

variable "cluster_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "worker_service_sg_id" {
  type = string
}

variable "worker_image_uri" {
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

variable "desired_count" {
  type    = number
  default = 1
}

variable "task_execution_role_arn" {
  type    = string
  default = null
}
