terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

resource "google_storage_bucket" "this" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }
  lifecycle_rule {
    condition {
      num_newer_versions = 4
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }
}
