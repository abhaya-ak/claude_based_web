#!/bin/bash
set -euo pipefail

# cost_down.sh — Cost-saving scale down script between demo sessions (D149)
# Usage: ./cost_down.sh

ENVIRONMENT="${ENVIRONMENT:-prod}"
ASG_NAME="scamshield-${ENVIRONMENT}-asg"
DB_IDENTIFIER="scamshield-${ENVIRONMENT}-postgres"

echo "=== Scaling down ScamShield infrastructure for cost preservation ==="

# 1. Scale ASG to 0
echo "--> Scaling Auto Scaling Group instances to 0..."
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name "${ASG_NAME}" \
  --min-size 0 \
  --max-size 0 \
  --desired-capacity 0

# 2. Stop RDS database instance (pauses compute billing)
echo "--> Stopping RDS PostgreSQL database instance..."
aws rds stop-db-instance \
  --db-instance-identifier "${DB_IDENTIFIER}" || echo "RDS already stopped or busy"

echo "=== Scale-down complete. Compute charges minimized. ==="
