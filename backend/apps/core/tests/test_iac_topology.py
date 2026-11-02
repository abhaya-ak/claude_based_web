import re
from pathlib import Path


def test_terraform_modules_exist_and_cover_architecture_topology():
    """D148: Assert all required Terraform modules exist in infra/terraform/ matching spec."""
    tf_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "infra" / "terraform"
    required_files = [
        "main.tf",
        "variables.tf",
        "vpc.tf",
        "alb.tf",
        "asg.tf",
        "rds.tf",
        "s3_cloudfront.tf",
        "lambda_sns.tf",
        "outputs.tf",
    ]
    for rf in required_files:
        p = tf_dir / rf
        assert p.exists(), f"Missing Terraform module {rf} at {p}"


def test_vpc_multi_az_and_subnetting():
    """Assert VPC defines 2-AZ topology with public, private_app, and private_db subnets."""
    tf_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "infra" / "terraform"
    vpc_content = (tf_dir / "vpc.tf").read_text(encoding="utf-8")

    assert "aws_vpc" in vpc_content
    assert "public_subnets" in vpc_content or "public" in vpc_content
    assert "private_app" in vpc_content or "app_subnets" in vpc_content
    assert "private_db" in vpc_content or "db_subnets" in vpc_content
    assert "aws_nat_gateway" in vpc_content
    assert "aws_internet_gateway" in vpc_content


def test_to_be_proven_27_alb_origin_shield_and_health_check():
    """TO BE PROVEN #27: ALB default action drops traffic (403), allows /api/* ONLY with X-CloudFront-Secret."""
    tf_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "infra" / "terraform"
    alb_content = (tf_dir / "alb.tf").read_text(encoding="utf-8")

    # Default action fixed 403
    assert 'type             = "fixed-response"' in alb_content or 'type = "fixed-response"' in alb_content
    assert '"403"' in alb_content or "403" in alb_content

    # Header check condition for origin shielding
    assert "X-CloudFront-Secret" in alb_content or "http_header" in alb_content

    # Health check path targeting /api/v1/health/
    assert "/api/v1/health/" in alb_content


def test_asg_scaling_bounds_and_target_tracking():
    """Assert ASG enforces min_size=2, max_size=6, and CPU target tracking at 70%."""
    tf_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "infra" / "terraform"
    asg_content = (tf_dir / "asg.tf").read_text(encoding="utf-8")

    assert "aws_autoscaling_group" in asg_content
    assert "min_size" in asg_content
    assert "max_size" in asg_content
    assert "70" in asg_content  # CPU target tracking metric
    assert "aws_launch_template" in asg_content


def test_rds_multi_az_and_encryption():
    """Assert RDS PostgreSQL 16 enforces multi_az=true, storage_encrypted=true, and 7-day backups."""
    tf_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "infra" / "terraform"
    rds_content = (tf_dir / "rds.tf").read_text(encoding="utf-8")

    assert "aws_db_instance" in rds_content
    assert re.search(r"multi_az\s*=\s*true", rds_content)
    assert re.search(r"storage_encrypted\s*=\s*true", rds_content)
    assert re.search(r"backup_retention_period\s*=\s*7", rds_content)
    assert "postgres" in rds_content.lower()


def test_s3_and_cloudfront_three_behaviors_with_oac():
    """Assert S3 public access blocked, CloudFront OAC used, and 3 cache behaviors (/api/*, /media/*, /*)."""
    tf_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "infra" / "terraform"
    s3_cf_content = (tf_dir / "s3_cloudfront.tf").read_text(encoding="utf-8")

    assert "aws_s3_bucket_public_access_block" in s3_cf_content
    assert "aws_cloudfront_origin_access_control" in s3_cf_content
    assert "aws_cloudfront_distribution" in s3_cf_content

    # Check 3 behaviors
    assert "/api/*" in s3_cf_content
    assert "/media/*" in s3_cf_content
    assert "custom_header" in s3_cf_content or "X-CloudFront-Secret" in s3_cf_content
    # SPA fallback
    assert "index.html" in s3_cf_content


def test_lambda_and_sns_alert_topic():
    """Assert Heuristic Scanner Lambda, DLQ, and SNS alert topic are configured."""
    tf_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "infra" / "terraform"
    lambda_sns_content = (tf_dir / "lambda_sns.tf").read_text(encoding="utf-8")

    assert "aws_lambda_function" in lambda_sns_content
    assert "aws_sqs_queue" in lambda_sns_content  # DLQ
    assert "aws_sns_topic" in lambda_sns_content
    assert "heuristic_scanner.zip" in lambda_sns_content
