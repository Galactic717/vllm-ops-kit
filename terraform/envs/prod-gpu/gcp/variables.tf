variable "project_id" {
  type = string
}

variable "bucket_name" {
  type = string
}

variable "name" {
  type    = string
  default = "ops-gpu"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "public_ip" {
  type    = bool
  default = false
}

variable "admin_cidrs" {
  type    = set(string)
  default = []
  validation {
    condition     = alltrue([for cidr in var.admin_cidrs : try(cidrnetmask(cidr) != "0.0.0.0", false)])
    error_message = "Use restricted IPv4 CIDRs for administrative SSH."
  }
}

variable "client_cidrs" {
  type    = set(string)
  default = []
  validation {
    condition     = alltrue([for cidr in var.client_cidrs : try(cidrnetmask(cidr) != "0.0.0.0", false)])
    error_message = "Use restricted IPv4 CIDRs for TLS clients."
  }
}
