terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

resource "google_compute_instance" "this" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.name]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      type  = var.disk_type
      size  = var.disk_gb
    }
  }

  network_interface {
    subnetwork = var.subnetwork
    dynamic "access_config" {
      for_each = var.public_ip ? [1] : []
      content {}
    }
  }

  dynamic "guest_accelerator" {
    for_each = var.gpu ? [1] : []
    content {
      type  = "nvidia-l4"
      count = 1
    }
  }
  scheduling {
    on_host_maintenance = var.gpu ? "TERMINATE" : "MIGRATE"
    automatic_restart   = true
  }
  metadata = {
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
    serial-port-enable     = "FALSE"
  }
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
}
