variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "subnet_cidr" {
  type = string
}

variable "admin_cidrs" {
  type = set(string)
}

variable "client_cidrs" {
  type = set(string)
}
