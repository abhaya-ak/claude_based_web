# RDS PostgreSQL 16 Multi-AZ with automated backups and KMS encryption per docs/02 §14

resource "aws_security_group" "db" {
  name        = "scamshield-${var.environment}-db-sg"
  description = "Allow inbound PostgreSQL from app instances only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL port 5432 from App Security Group only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    description = "No outbound required for DB"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "scamshield-${var.environment}-db-sg"
  }
}

resource "aws_db_subnet_group" "db" {
  name        = "scamshield-${var.environment}-db-subnet-group"
  subnet_ids  = aws_subnet.private_db[*].id
  description = "Subnets for Multi-AZ PostgreSQL 16 database"

  tags = {
    Name = "scamshield-${var.environment}-db-subnet-group"
  }
}

resource "aws_kms_key" "rds" {
  description             = "KMS CMK for ScamShield RDS PostgreSQL encryption at rest"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "scamshield-${var.environment}-rds-kms-key"
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = "scamshield-${var.environment}-postgres"
  engine         = "postgres"
  engine_version = "16.1"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  # High Availability across 2 AZs (docs/02 §14)
  multi_az               = true
  db_subnet_group_name   = aws_db_subnet_group.db.name
  vpc_security_group_ids = [aws_security_group.db.id]

  # Backup & Disaster Recovery
  backup_retention_period   = 7
  backup_window             = "03:00-04:00"
  maintenance_window        = "Mon:04:30-Mon:05:30"
  copy_tags_to_snapshot     = true
  deletion_protection       = false # Set to true in real production, false for educational tear-down
  skip_final_snapshot       = true

  auto_minor_version_upgrade = true

  tags = {
    Name = "scamshield-${var.environment}-postgres"
  }
}
