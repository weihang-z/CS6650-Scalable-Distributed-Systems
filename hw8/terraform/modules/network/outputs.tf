output "subnet_ids" {
  description = "IDs of the default VPC subnets"
  value       = data.aws_subnets.default.ids
}

output "private_subnet_ids" {
  description = "Subnet IDs used by private resources in the default VPC"
  value       = data.aws_subnets.default.ids
}

output "vpc_id" {
  value = data.aws_vpc.default.id
}
