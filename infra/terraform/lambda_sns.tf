# Heuristic Scanner Lambda function, SQS Dead Letter Queue (DLQ), and SNS alerts topic per docs/02 §15

# SNS Topic for Staff and Citizen Threat Alerts
resource "aws_sns_topic" "alerts" {
  name = "scamshield-${var.environment}-alerts"

  tags = {
    Name = "scamshield-${var.environment}-alerts"
  }
}

# SQS Dead Letter Queue (DLQ) for failed Lambda heuristic scan executions
resource "aws_sqs_queue" "lambda_dlq" {
  name                      = "scamshield-${var.environment}-scanner-dlq"
  message_retention_seconds = 1209600 # 14 days retention

  tags = {
    Name = "scamshield-${var.environment}-scanner-dlq"
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_scanner" {
  name = "scamshield-${var.environment}-lambda-scanner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_scanner_policy" {
  name = "scamshield-${var.environment}-lambda-scanner-policy"
  role = aws_iam_role.lambda_scanner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.lambda_dlq.arn
      }
    ]
  })
}

# AWS Lambda Heuristic Scanner Function (zero DB, zero VPC, pure Python)
resource "aws_lambda_function" "heuristic_scanner" {
  function_name = "scamshield-${var.environment}-heuristic-scanner"
  role          = aws_iam_role.lambda_scanner.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.13"

  filename         = "${path.module}/../lambda/heuristic_scanner.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda/heuristic_scanner.zip")

  memory_size = 128
  timeout     = 10

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }

  environment {
    variables = {
      SCANNER_CALLBACK_URL    = "https://${var.domain_name}/internal/scan-results/"
      SCANNER_CALLBACK_SECRET = var.cloudfront_secret_header
    }
  }

  tags = {
    Name = "scamshield-${var.environment}-heuristic-scanner"
  }
}
