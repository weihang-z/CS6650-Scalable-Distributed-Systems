resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"
}