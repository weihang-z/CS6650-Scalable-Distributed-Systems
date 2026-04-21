output "alb_dns_name" {
  value = module.alb.alb_dns_name
}

output "rds_endpoint" {
  value = module.rds.db_endpoint
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "app_image_uri" {
  value = local.app_image_uri
}

output "kafka_public_ip" {
  value = module.ec2_kafka.public_ip
}

output "kafka_private_ip" {
  value = module.ec2_kafka.private_ip
}