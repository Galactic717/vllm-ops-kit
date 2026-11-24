terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

variable "project_id" {
  type = string
}

variable "github_repository_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_id))
    error_message = "Use the numeric GitHub repository ID."
  }
}

variable "github_repository_owner" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+$", var.github_repository_owner))
    error_message = "Use the GitHub owner login."
  }
}

variable "github_repository_name" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+$", var.github_repository_name))
    error_message = "Use the unqualified GitHub repository name."
  }
}

variable "github_owner_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+$", var.github_owner_id))
    error_message = "Use the numeric GitHub organization or user ID."
  }
}

variable "plan_service_account_id" {
  type = string
}

variable "github_environment" {
  type    = string
  default = "cloud-plan"
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+$", var.github_environment))
    error_message = "Use the protected GitHub environment name."
  }
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "vllm-ops-github"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
  }
  attribute_condition = <<-CEL
    assertion.repository_id == "${var.github_repository_id}" &&
    assertion.repository_owner_id == "${var.github_owner_id}" &&
    assertion.sub == "repo:${var.github_repository_owner}/${var.github_repository_name}:environment:${var.github_environment}"
  CEL
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "plan" {
  service_account_id = var.plan_service_account_id
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}
