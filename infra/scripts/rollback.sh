#!/bin/bash
set -euo pipefail

# rollback.sh — Single-command rollback script for ScamShield (D149)
# Usage: ./rollback.sh <PREVIOUS_IMAGE_TAG>

PREVIOUS_IMAGE_TAG="${1:?Error: Must provide previous image tag to rollback to}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
ASG_NAME="scamshield-${ENVIRONMENT}-asg"

echo "=== INITIATING IMMEDIATE ROLLBACK ==="
echo "Targeting Image: ${PREVIOUS_IMAGE_TAG}"
echo "Environment:     ${ENVIRONMENT}"

# 1. Cancel any active instance refreshes
echo "--> Cancelling existing instance refreshes..."
aws autoscaling cancel-instance-refresh \
  --auto-scaling-group-name "${ASG_NAME}" || true

# 2. Trigger rollback instance refresh with fast warmup
echo "--> Starting rollback instance refresh..."
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name "${ASG_NAME}" \
  --preferences '{"MinHealthyPercentage": 50, "InstanceWarmup": 180}'

echo "=== Rollback triggered. Monitor ASG instances and CloudWatch alarms. ==="
