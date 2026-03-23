resource "aws_sns_topic" "order_processing_events" {
  name = "order-processing-events"
}

resource "aws_sqs_queue" "order_processing_queue" {
  name                       = "order-processing-queue"
  visibility_timeout_seconds = 30
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
}

resource "aws_sns_topic_subscription" "order_processing_queue_subscription" {
  topic_arn            = aws_sns_topic.order_processing_events.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.order_processing_queue.arn
  raw_message_delivery = true
}

data "aws_iam_policy_document" "order_processing_queue_policy" {
  statement {
    sid    = "AllowSNSToSendToSQS"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.order_processing_queue.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.order_processing_events.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "order_processing_queue_policy" {
  queue_url = aws_sqs_queue.order_processing_queue.id
  policy    = data.aws_iam_policy_document.order_processing_queue_policy.json
}