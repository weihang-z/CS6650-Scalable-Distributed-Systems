output "subnet_ids" {
  description = "IDs of the default VPC subnets"
  value       = data.aws_subnets.default.ids
}

output "vpc_id" {
  value = data.aws_vpc.default.id
}
