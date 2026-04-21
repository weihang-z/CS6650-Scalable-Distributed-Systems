output "alb_sg_id" {
  value = aws_security_group.alb.id
}

output "ingress_service_sg_id" {
  value = aws_security_group.ingress_service.id
}

output "worker_service_sg_id" {
  value = aws_security_group.worker_service.id
}

output "rds_sg_id" {
  value = aws_security_group.rds.id
}

output "kafka_ec2_sg_id" {
  value = aws_security_group.kafka_ec2.id
}