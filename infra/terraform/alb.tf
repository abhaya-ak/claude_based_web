# Application Load Balancer with Origin Shielding (X-CloudFront-Secret validation) per docs/02 §12

resource "aws_security_group" "alb" {
  name        = "scamshield-${var.environment}-alb-sg"
  description = "Allow inbound HTTPS from CloudFront edge and drop unauthenticated direct requests"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Inbound HTTPS from CloudFront IPs or internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound to app tier"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "scamshield-${var.environment}-alb-sg"
  }
}

resource "aws_lb" "api" {
  name               = "scamshield-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  drop_invalid_header_fields = true

  tags = {
    Name = "scamshield-${var.environment}-alb"
  }
}

resource "aws_lb_target_group" "api" {
  name        = "scamshield-${var.environment}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"

  health_check {
    enabled             = true
    path                = "/api/v1/health/"
    protocol            = "HTTP"
    port                = "8000"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = {
    Name = "scamshield-${var.environment}-api-tg"
  }
}

# Default listener action: 403 Forbidden to block direct ALB bypass (TO BE PROVEN #27)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = "arn:aws:acm:${var.aws_region}:123456789012:certificate/dummy-cert-id"

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "application/json"
      message_body = "{\"error\":{\"code\":\"origin_shield_denied\",\"message\":\"Direct ALB requests are forbidden. Route via CloudFront.\"}}"
      status_code  = "403"
    }
  }
}

# Listener rule: Forward /api/* ONLY when custom header X-CloudFront-Secret matches
resource "aws_lb_listener_rule" "api_forward" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }

  condition {
    http_header {
      http_header_name = "X-CloudFront-Secret"
      values           = [var.cloudfront_secret_header]
    }
  }
}
