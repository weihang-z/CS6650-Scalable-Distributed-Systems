locals {
  use_existing_lambda_role = var.existing_lambda_role_arn != null && var.existing_lambda_role_arn != ""
  lambda_role_arn          = local.use_existing_lambda_role ? var.existing_lambda_role_arn : var.shared_lab_role_arn
}

resource "aws_iam_role" "order_processing_lambda_role" {
  count = 0
  name  = "${var.service_name}-order-processing-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "order_processing_lambda_basic_logs" {
  count      = 0
  role       = aws_iam_role.order_processing_lambda_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "order_processing_lambda" {
  name              = "/aws/lambda/${var.service_name}-order-processing-lambda"
  retention_in_days = 7
}

resource "aws_lambda_function" "order_processing_lambda" {
  function_name = "${var.service_name}-order-processing-lambda"
  role          = local.lambda_role_arn

  runtime       = "provided.al2"
  handler       = "bootstrap"
  architectures = ["x86_64"]

  filename         = "${path.module}/../part3-lambda/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../part3-lambda/lambda.zip")

  memory_size = 512
  timeout     = 10

  depends_on = [
    aws_iam_role_policy_attachment.order_processing_lambda_basic_logs,
    aws_cloudwatch_log_group.order_processing_lambda
  ]
}

resource "aws_lambda_permission" "allow_sns_invoke_lambda" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.order_processing_lambda.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.order_processing_events.arn
}

resource "aws_sns_topic_subscription" "order_processing_lambda_subscription" {
  topic_arn = aws_sns_topic.order_processing_events.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.order_processing_lambda.arn

  depends_on = [
    aws_lambda_permission.allow_sns_invoke_lambda
  ]
}
