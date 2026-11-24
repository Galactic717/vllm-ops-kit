terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
  backend "gcs" {}
}

provider "google" {
  region  = var.region
  project = var.project_id
  zone    = var.zone
}

module "network" {
  source       = "../../../modules/network/gcp"
  name         = var.name
  subnet_cidr  = "10.43.1.0/24"
  admin_cidrs  = var.admin_cidrs
  client_cidrs = var.client_cidrs
  region       = var.region
}

module "storage" {
  source      = "../../../modules/storage/gcp"
  bucket_name = var.bucket_name
  region      = var.region
}

module "compute" {
  source       = "../../../modules/compute/gcp"
  name         = var.name
  public_ip    = var.public_ip
  disk_gb      = 30
  machine_type = "e2-micro"
  zone         = var.zone
  subnetwork   = module.network.subnet
  disk_type    = "pd-standard"
  gpu          = false
}
