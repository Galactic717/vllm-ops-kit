terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

resource "google_compute_network" "this" {
  name                    = var.name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "this" {
  name                     = var.name
  region                   = var.region
  ip_cidr_range            = var.subnet_cidr
  network                  = google_compute_network.this.id
  private_ip_google_access = true
}

resource "google_compute_firewall" "ssh" {
  count         = length(var.admin_cidrs) > 0 ? 1 : 0
  name          = "${var.name}-ssh"
  network       = google_compute_network.this.id
  source_ranges = var.admin_cidrs
  target_tags   = [var.name]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_firewall" "tls" {
  count         = length(var.client_cidrs) > 0 ? 1 : 0
  name          = "${var.name}-tls"
  network       = google_compute_network.this.id
  source_ranges = var.client_cidrs
  target_tags   = [var.name]
  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
}
