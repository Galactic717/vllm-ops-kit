variable "name" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "security_group" {
  type = string
}

variable "disk_gb" {
  type = number
}

variable "public_ip" {
  type = bool
}

variable "ssh_key_name" {
  type = string
}

variable "detailed_monitoring" {
  type = bool
}
