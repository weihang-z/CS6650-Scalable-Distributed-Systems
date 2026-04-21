resource "aws_ecr_repository" "ingress" {
  name = "${var.name_prefix}-ingress"
}