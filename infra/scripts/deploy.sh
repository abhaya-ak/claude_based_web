#!/bin/bash
set -euo pipefail

# deploy.sh — Zero-downtime rolling deployment script for ScamShield (D149)
# Usage: ./deploy.sh <IMAGE_TAG>

IMAGE_TAG="${1:-latest}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
ASG_NAME="scamshield-${ENVIRONMENT}-asg"
ECR_REGISTRY="${ECR_REGISTRY:-123456789012.dkr.ecr.ap-southeast-1.amazonaws.com}"

echo "=== Starting ScamShield Zero-Downtime Deployment ==="
echo "Target Image Tag: ${IMAGE_TAG}"
echo "Environment:      ${ENVIRONMENT}"

# 1. Run database migrations first
echo "--> Step 1: Executing forward-compatible database migrations..."
docker run --rm \
  --env-file "/etc/scamshield/${ENVIRONMENT}.env" \
  "${ECR_REGISTRY}/scamshield-backend:${IMAGE_TAG}" \
  python manage.py migrate --noinput

# 2. Update Launch Template with new image tag
echo "--> Step 2: Updating Launch Template..."
# In practice: aws ec2 create-launch-template-version ...

# 3. Trigger ASG Rolling Instance Refresh
echo "--> Step 3: Triggering ASG Rolling Instance Refresh..."
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name "${ASG_NAME}" \
  --preferences '{"MinHealthyPercentage": 50, "InstanceWarmup": 300}'

echo "=== Deployment initiated successfully. Monitor via ALB health checks. ==="
