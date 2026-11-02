# ScamShield Operational Runbook (D149)

This runbook outlines standard operating procedures (SOPs) for the engineering and ops team managing the ScamShield Cloud infrastructure on AWS.

---

## 1. Zero-Downtime Rolling Deployment Procedure

ScamShield implements a **zero-downtime rolling update strategy** combining database forward-compatible schema migrations with AWS Auto Scaling Group (ASG) Instance Refreshes using `min_healthy_percentage = 50`.

### Deployment Workflow
1. **Pre-flight & Database Migration:**
   - Database migrations must always be backward-compatible (expand before contract).
   - In CI/CD or via an administrative ECS task / bastion host:
     ```bash
     docker run --rm --env-file /etc/scamshield/env ${ECR_REGISTRY}/scamshield-backend:${IMAGE_TAG} python manage.py migrate --noinput
     ```
2. **ECR Image Publish:**
   - Docker image built from `Dockerfile` with `requirements/base.lock.txt`.
   - Vulnerability check with `pip-audit` and image tagged with commit SHA and `latest`.
3. **Launch Template Version Bump:**
   - Update EC2 Launch Template with new ECR image tag URI:
     ```bash
     aws ec2 create-launch-template-version \
       --launch-template-name scamshield-prod-lt \
       --source-version '$Latest' \
       --launch-template-data "{\"UserData\":\"$(base64 -w 0 userdata.sh)\"}"
     ```
4. **ASG Rolling Instance Refresh:**
   - Initiate instance refresh with a `min_healthy_percentage` of 50%:
     ```bash
     aws autoscaling start-instance-refresh \
       --auto-scaling-group-name scamshield-prod-asg \
       --preferences '{"MinHealthyPercentage": 50, "InstanceWarmup": 300}'
     ```
   - The ALB health check probe (`/api/v1/health/`) verifies new instances before taking old instances out of rotation.

---

## 2. Single-Command Rollback Procedure

In case of application regressions or unhealthy instances:

### Fast Rollback Command
```bash
bash infra/scripts/rollback.sh <PREVIOUS_IMAGE_TAG>
```

### Manual Rollback Steps
1. Re-point the ASG Launch Template to the previous known-good ECR image tag.
2. Cancel any running instance refresh:
   ```bash
   aws autoscaling cancel-instance-refresh --auto-scaling-group-name scamshield-prod-asg
   ```
3. Trigger an immediate rolling refresh targeting the previous image:
   ```bash
   aws autoscaling start-instance-refresh \
     --auto-scaling-group-name scamshield-prod-asg \
     --preferences '{"MinHealthyPercentage": 50, "InstanceWarmup": 180}'
   ```
4. **Database Rollback Note:** Because all migrations follow expand-contract rules, the previous container version continues running cleanly against the expanded database schema without requiring an immediate database rollback.

---

## 3. RDS Point-in-Time Recovery (PITR) & Multi-AZ Failover Drill

### Multi-AZ Automated Failover Mechanics
- **Topology:** Primary PostgreSQL DB instance in `ap-southeast-1a`, synchronous physical standby in `ap-southeast-1b`.
- **Failover Trigger:** Hardware failure, AZ loss, or administrative reboot with failover.
- **Failover SLA:** Recovery Time Objective (RTO) is 60–120 seconds. Recovery Point Objective (RPO) is ~0 seconds due to synchronous block replication.
- **Failover Drill Command:**
  ```bash
  aws rds reboot-db-instance \
    --db-instance-identifier scamshield-prod-postgres \
    --force-failover
  ```
  *Monitor ALB response codes; backend automatically reconnects to new primary once DNS switches.*

### Point-in-Time Recovery (PITR) Drill
To restore the database to an exact historical timestamp (up to 7 days back):
```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier scamshield-prod-postgres \
  --target-db-instance-identifier scamshield-prod-postgres-restored \
  --restore-time "2026-11-02T12:00:00.000Z" \
  --db-subnet-group-name scamshield-prod-db-subnet-group \
  --vpc-security-group-ids sg-xxxxxx
```
Validate the restored instance, verify table data integrity, and re-point SSM parameter `DATABASE_URL` during scheduled maintenance.

---

## 4. Zero-Downtime Secret Rotation Procedure

ScamShield manages production secrets via AWS Systems Manager (SSM) Parameter Store with SecureString encryption.

### Rotatable Secrets
1. `DJANGO_SECRET_KEY`
2. `JWT_SIGNING_KEY`
3. `SCANNER_SHARED_SECRET`
4. `X-CloudFront-Secret` (Origin Shield)

### Rotation Sequence for `X-CloudFront-Secret` (ALB Origin Shield)
1. Add new secret value to ALB listener rule condition (permitting both OLD and NEW secrets during transition):
   ```bash
   aws elbv2 modify-rule --rule-arn <RULE_ARN> --conditions ...
   ```
2. Update CloudFront custom origin header to inject the NEW secret:
   ```bash
   aws cloudfront update-distribution --id <DIST_ID> ...
   ```
3. Wait for CloudFront global distribution rollout (3–5 minutes).
4. Remove OLD secret from ALB listener rule condition, leaving only NEW secret.

---

## 5. Scheduled Operations & Cron Jobs

ScamShield executes automated operational maintenance through Django's `run_jobs` management command using advisory locking:

```bash
python manage.py run_jobs
```

### Configured Jobs:
1. `flush_expired_tokens`: Purges blacklisted JWT tokens whose refresh lifetime has elapsed.
2. `recover_stalled_scans`: Detects pending heuristic scan dispatches older than 5 minutes and marks failed or retries.
3. `purge_expired_audit_logs`: Removes audit log records exceeding retention policy using session bypass setting `scamshield.audit_purge_allowed = 'on'`.
4. `aggregate_ops_metrics`: CloudWatch metric fallback and daily SLA aggregations.

In production, run this command every 5 minutes via AWS EventBridge triggering an ECS RunTask or an EC2 crontab entry.

---

## 6. Cost-Control Teardown / Scale-Down Procedure

To optimize cloud costs between testing sessions or outside university grading windows:

### Immediate Scale-Down Script
```bash
bash infra/scripts/cost_down.sh
```

### Actions Performed:
1. **Auto Scaling Group:** Reduces `min_size` to 0, `desired_capacity` to 0. (Stops EC2 instance charges).
2. **RDS PostgreSQL:** Stop DB instance (persists data and storage, pauses hourly compute charge for up to 7 days):
   ```bash
   aws rds stop-db-instance --db-instance-identifier scamshield-prod-postgres
   ```
3. **NAT Gateway:** For extended breaks, teardown NAT Gateway to avoid the ~$32/month idle fee.
