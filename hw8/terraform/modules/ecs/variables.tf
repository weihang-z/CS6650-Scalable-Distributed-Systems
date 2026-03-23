variable "cluster_id" {
  type        = string
  description = "ID or ARN of the ECS cluster that should run this service"
}

variable "service_name" {
  type        = string
  description = "Name for the ECS service and task definition family"
}

variable "container_name" {
  type        = string
  description = "Container name inside the task definition"
}

variable "image" {
  type        = string
  description = "ECR image URI (with tag)"
}

variable "container_port" {
  type        = number
  default     = null
  description = "Port your app listens on; leave null for non-HTTP workers"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnets for FARGATE tasks"
}

variable "security_group_ids" {
  type        = list(string)
  description = "SGs for FARGATE tasks"
}

variable "execution_role_arn" {
  type        = string
  description = "ECS Task Execution Role ARN"
}

variable "task_role_arn" {
  type        = string
  description = "IAM Role ARN for app permissions"
}

variable "log_group_name" {
  type        = string
  description = "CloudWatch log group name"
}

variable "log_stream_prefix" {
  type        = string
  default     = "ecs"
  description = "CloudWatch logs stream prefix"
}

variable "environment" {
  type = list(object({
    name  = string
    value = string
  }))
  default     = []
  description = "Environment variables for the container"
}

variable "command" {
  type        = list(string)
  default     = null
  description = "Optional container command override"
}

variable "desired_count" {
  type        = number
  default     = 1
  description = "Desired Fargate task count"
}

variable "region" {
  type        = string
  description = "AWS region (for awslogs driver)"
}

variable "cpu" {
  type        = string
  default     = "256"
  description = "vCPU units"
}

variable "memory" {
  type        = string
  default     = "512"
  description = "Memory (MiB)"
}

variable "target_group_arn" {
  type        = string
  default     = null
  description = "ALB target group ARN for ECS service attachment"
}

variable "health_check_grace_period_seconds" {
  type        = number
  default     = 30
  description = "Grace period before ECS starts ALB health checks"
}

variable "assign_public_ip" {
  type        = bool
  default     = true
  description = "Whether to assign a public IP to the task ENI"
}
