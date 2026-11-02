output "vpc_id" {
  description = "ID of the ScamShield VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs for ALB"
  value       = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  description = "Private app subnet IDs for ASG"
  value       = aws_subnet.private_app[*].id
}

output "private_db_subnet_ids" {
  description = "Private database subnet IDs for RDS"
  value       = aws_subnet.private_db[*].id
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.api.dns_name
}

output "rds_endpoint" {
  description = "Primary endpoint for RDS PostgreSQL Multi-AZ"
  value       = aws_db_instance.postgres.endpoint
}

output "cloudfront_domain_name" {
  description = "Domain name of CloudFront CDN distribution"
  value       = aws_cloudfront_distribution.scamshield.domain_name
}

output "lambda_scanner_arn" {
  description = "ARN of Heuristic Scanner Lambda function"
  value       = aws_lambda_function.heuristic_scanner.arn
}

output "sns_alerts_topic_arn" {
  description = "ARN of SNS threat alerts topic"
  value       = aws_sns_topic.alerts.arn
}
