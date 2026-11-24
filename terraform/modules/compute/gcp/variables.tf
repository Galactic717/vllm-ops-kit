variable "name" {
  type = string
}

variable "machine_type" {
  type = string
}

variable "zone" {
  type = string
}

variable "subnetwork" {
  type = string
}

variable "disk_gb" {
  type = number
}

variable "disk_type" {
  type = string
}

variable "public_ip" {
  type = bool
}

variable "gpu" {
  type = bool
}
