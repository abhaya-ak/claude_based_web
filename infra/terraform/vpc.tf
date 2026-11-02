# 2-AZ VPC Topology with 3-tier subnets (public, private_app, private_db) per docs/02 §11

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "scamshield-${var.environment}-vpc"
  }
}

# Internet Gateway for public traffic
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "scamshield-${var.environment}-igw"
  }
}

# Public Subnets (2 AZs) for ALB and NAT Gateway
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "scamshield-${var.environment}-public-${var.availability_zones[count.index]}"
    Tier = "public"
  }
}

# Elastic IP and NAT Gateway for private egress (Lambda callbacks, S3, SSM)
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "scamshield-${var.environment}-nat-eip"
  }
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "scamshield-${var.environment}-nat"
  }
  depends_on = [aws_internet_gateway.igw]
}

# Private App Subnets (2 AZs) for EC2 Auto Scaling Group
resource "aws_subnet" "private_app" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 2)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "scamshield-${var.environment}-private-app-${var.availability_zones[count.index]}"
    Tier = "app"
  }
}

# Private DB Subnets (2 AZs) strictly for RDS PostgreSQL Multi-AZ
resource "aws_subnet" "private_db" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "scamshield-${var.environment}-private-db-${var.availability_zones[count.index]}"
    Tier = "db"
  }
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "scamshield-${var.environment}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }

  tags = {
    Name = "scamshield-${var.environment}-private-rt"
  }
}

resource "aws_route_table_association" "private_app" {
  count          = 2
  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table" "database" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "scamshield-${var.environment}-database-rt"
  }
}

resource "aws_route_table_association" "private_db" {
  count          = 2
  subnet_id      = aws_subnet.private_db[count.index].id
  route_table_id = aws_route_table.database.id
}
