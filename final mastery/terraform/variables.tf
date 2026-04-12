variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "instance_type" {
  type    = string
  default = "t3.medium"
}

variable "public_key_path" {
  type    = string
  default = "~/.ssh/album_store_key.pub"
}

variable "private_key_path" {
  type    = string
  default = "~/.ssh/album_store_key"
}

variable "app_binary_path" {
  type    = string
  default = "../album-store"
}

variable "ssh_user" {
  type    = string
  default = "ubuntu"
}