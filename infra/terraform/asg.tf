# EC2 Launch Template and Auto Scaling Group (min 2, max 6, target tracking CPU 70%) per docs/02 §13

resource "aws_security_group" "app" {
  name        = "scamshield-${var.environment}-app-sg"
  description = "Inbound from ALB only, outbound to RDS/NAT/S3"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Inbound port 8000 from ALB SG only"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Outbound egress via NAT Gateway"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "scamshield-${var.environment}-app-sg"
  }
}

resource "aws_iam_role" "app_instance" {
  name = "scamshield-${var.environment}-app-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "app_instance_policy" {
  name = "scamshield-${var.environment}-app-policy"
  role = aws_iam_role.app_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/scamshield/${var.environment}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = "arn:aws:s3:::scamshield-${var.environment}-*/*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = "arn:aws:sns:${var.aws_region}:*:scamshield-${var.environment}-*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:*:function:scamshield-${var.environment}-heuristic-scanner"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "app" {
  name = "scamshield-${var.environment}-app-profile"
  role = aws_iam_role.app_instance.name
}

resource "aws_launch_template" "app" {
  name_prefix   = "scamshield-${var.environment}-lt-"
  image_id      = "ami-0c55b159cbfafe1f0" # Amazon Linux 2023 or standard ECS-optimized AMI
  instance_type = "t4g.small"

  iam_instance_profile {
    name = aws_iam_instance_profile.app.name
  }

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = [aws_security_group.app.id]
  }

  user_data = base64encode(<<-EOF
    #!/bin/bash
    yum update -y
    yum install -y docker
    systemctl start docker
    systemctl enable docker
    usermod -a -G docker ec2-user

    # Pull and run the hardened production container as non-root appuser
    docker run -d \
      --name scamshield-backend \
      --restart always \
      -p 8000:8000 \
      --env-file /etc/scamshield/env \
      ${var.ecr_image_uri}
  EOF
  )

  monitoring {
    enabled = true
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "scamshield-${var.environment}-backend-instance"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "app" {
  name_prefix         = "scamshield-${var.environment}-asg-"
  vpc_zone_identifier = aws_subnet.private_app[*].id
  target_group_arns   = [aws_lb_target_group.api.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  min_size         = 2
  max_size         = 6
  desired_capacity = 2

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
      instance_warmup        = 300
    }
  }

  tag {
    key                 = "Name"
    value               = "scamshield-${var.environment}-asg-worker"
    propagate_at_launch = true
  }
}

# Dynamic Scaling Policy: Target Tracking CPU at 70%
resource "aws_autoscaling_policy" "cpu_target_tracking" {
  name                   = "scamshield-${var.environment}-cpu-target-tracking"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
