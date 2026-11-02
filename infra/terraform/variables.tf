variable "aws_region" {
  type        = string
  description = "AWS deployment region"
  default     = "ap-southeast-1"
}

variable "environment" {
  type        = string
  description = "Deployment environment name"
  default     = "prod"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the ScamShield VPC"
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "Two distinct availability zones for High Availability (R-D1)"
  default     = ["ap-southeast-1a", "ap-southeast-1b"]
}

variable "cloudfront_secret_header" {
  type        = string
  description = "Secret token injected by CloudFront and validated by ALB to enforce origin shielding (TO BE PROVEN #27)"
  sensitive   = true
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t4g.micro"
}

variable "db_name" {
  type        = string
  description = "PostgreSQL initial database name"
  default     = "scamshield"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL master username"
  default     = "scamshield_admin"
}

variable "db_password" {
  type        = string
  description = "PostgreSQL master password"
  sensitive   = true
}

variable "ecr_image_uri" {
  type        = string
  description = "ECR Docker image URI for Django backend container"
}

variable "domain_name" {
  type        = string
  description = "Apex domain name for CloudFront distribution"
  default     = "scamshield.cloud"
}
