terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.region
}

module "network" {
  source       = "../../../modules/network/aws"
  name         = var.name
  subnet_cidr  = "10.43.1.0/24"
  admin_cidrs  = var.admin_cidrs
  client_cidrs = var.client_cidrs
  vpc_cidr     = "10.43.0.0/16"
  zone         = var.zone
  public_ip    = var.public_ip
}

module "storage" {
  source      = "../../../modules/storage/aws"
  bucket_name = var.bucket_name
}

module "compute" {
  source              = "../../../modules/compute/aws"
  name                = var.name
  public_ip           = var.public_ip
  disk_gb             = 70
  instance_type       = var.instance_type
  subnet_id           = module.network.subnet
  security_group      = module.network.security_group
  ssh_key_name        = var.ssh_key_name
  detailed_monitoring = true
}
