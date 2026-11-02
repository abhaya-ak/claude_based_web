# S3 Buckets (evidence, media, frontend) and CloudFront Distribution with 3 cache behaviors per docs/02 §12 & §15

# Origin Access Control (OAC) for CloudFront -> S3 security
resource "aws_cloudfront_origin_access_control" "default" {
  name                              = "scamshield-${var.environment}-oac"
  description                       = "OAC for ScamShield Media and Frontend S3 buckets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# KMS Key for Evidence Bucket
resource "aws_kms_key" "evidence" {
  description             = "KMS key for evidence vault private bucket"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "scamshield-${var.environment}-evidence-kms"
  }
}

# 1. Evidence Bucket (Completely Private, No CloudFront, Accessed via 15-min presigned URLs)
resource "aws_s3_bucket" "evidence" {
  bucket = "scamshield-${var.environment}-evidence-vault"

  tags = {
    Name = "scamshield-${var.environment}-evidence-vault"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.evidence.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 2. Media Assets Bucket (Served through CloudFront /media/* with OAC)
resource "aws_s3_bucket" "media" {
  bucket = "scamshield-${var.environment}-media-assets"

  tags = {
    Name = "scamshield-${var.environment}-media-assets"
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 3. Frontend Web Assets Bucket (Served through CloudFront /* with OAC)
resource "aws_s3_bucket" "frontend" {
  bucket = "scamshield-${var.environment}-web-assets"

  tags = {
    Name = "scamshield-${var.environment}-web-assets"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "scamshield" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  # Origin 1: ALB for /api/*
  origin {
    domain_name = aws_lb.api.dns_name
    origin_id   = "ALB-API-Origin"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    # Inject origin-shield secret header to satisfy ALB listener rule (TO BE PROVEN #27)
    custom_header {
      name  = "X-CloudFront-Secret"
      value = var.cloudfront_secret_header
    }
  }

  # Origin 2: S3 Media Assets
  origin {
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_id                = "S3-Media-Origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.default.id
  }

  # Origin 3: S3 Frontend Web Assets
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3-Frontend-Origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.default.id
  }

  # Behavior 1: Default /* routes to Frontend S3 with OAC
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-Frontend-Origin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400
    max_ttl                = 31536000
    compress               = true
  }

  # Behavior 2: /api/* routes to ALB, no caching, forwards cookies & headers
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods   = ["GET", "HEAD", "OPTIONS"]
    target_origin_id = "ALB-API-Origin"

    forwarded_values {
      query_string = true
      headers      = ["*"]
      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "https-only"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
    compress               = true
  }

  # Behavior 3: /media/* routes to S3 Media Bucket with OAC
  ordered_cache_behavior {
    path_pattern     = "/media/*"
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-Media-Origin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400
    max_ttl                = 604800
    compress               = true
  }

  # Single Page Application (SPA) Error Responses: return index.html on 403 or 404
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "scamshield-${var.environment}-cdn"
  }
}
