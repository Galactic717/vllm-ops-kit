variable "name" {
  type = string
}

variable "zone" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "subnet_cidr" {
  type = string
}

variable "public_ip" {
  type = bool
}

variable "admin_cidrs" {
  type = set(string)
}

variable "client_cidrs" {
  type = set(string)
}
