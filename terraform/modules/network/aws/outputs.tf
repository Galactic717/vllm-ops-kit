output "subnet" {
  value = aws_subnet.this.id
}

output "security_group" {
  value = aws_security_group.this.id
}
