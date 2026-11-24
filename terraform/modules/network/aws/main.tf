terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = var.name }
}

resource "aws_internet_gateway" "this" {
  count  = var.public_ip ? 1 : 0
  vpc_id = aws_vpc.this.id
}

resource "aws_subnet" "this" {
  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.zone
  cidr_block              = var.subnet_cidr
  map_public_ip_on_launch = false
  tags                    = { Name = var.name }
}

resource "aws_default_security_group" "deny" {
  vpc_id = aws_vpc.this.id
}

resource "aws_route_table" "public" {
  count  = var.public_ip ? 1 : 0
  vpc_id = aws_vpc.this.id
}

resource "aws_route" "public" {
  count                  = var.public_ip ? 1 : 0
  route_table_id         = aws_route_table.public[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this[0].id
}

resource "aws_route_table_association" "public" {
  count          = var.public_ip ? 1 : 0
  subnet_id      = aws_subnet.this.id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_security_group" "this" {
  name        = var.name
  description = "SSH and TLS from approved CIDRs, outbound HTTPS"
  vpc_id      = aws_vpc.this.id
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  for_each          = var.admin_cidrs
  security_group_id = aws_security_group.this.id
  description       = "Administrative SSH"
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_vpc_security_group_ingress_rule" "tls" {
  for_each          = var.client_cidrs
  security_group_id = aws_security_group.this.id
  description       = "Approved TLS clients"
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "tls" {
  security_group_id = aws_security_group.this.id
  description       = "HTTPS packages and registries"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
