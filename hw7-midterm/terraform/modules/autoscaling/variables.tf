variable "cluster_name" {
  type = string
}

variable "service_name" {
  type = string
}

variable "min_capacity" {
  type    = number
  default = 2
}

variable "max_capacity" {
  type    = number
  default = 6
}

variable "cpu_target_value" {
  type    = number
  default = 60
}

variable "scale_in_cooldown" {
  type    = number
  default = 15
}

variable "scale_out_cooldown" {
  type    = number
  default = 15
}
