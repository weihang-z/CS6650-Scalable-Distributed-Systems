output "ecs_cluster_name" {
  description = "Name of the created ECS cluster"
  value       = aws_ecs_cluster.this.name
}

output "order_receiver_service_name" {
  description = "Name of the order receiver ECS service"
  value       = module.order_receiver_ecs.service_name
}

output "order_processor_service_name" {
  description = "Name of the order processor ECS service"
  value       = module.order_processor_ecs.service_name
}

output "order_processing_topic_arn" {
  value = aws_sns_topic.order_processing_events.arn
}

output "order_processing_queue_arn" {
  value = aws_sqs_queue.order_processing_queue.arn
}

output "order_processing_queue_url" {
  value = aws_sqs_queue.order_processing_queue.id
}
