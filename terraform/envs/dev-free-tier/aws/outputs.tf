output "artifact_bucket" {
  value = module.storage.bucket
}

output "private_ip" {
  value = module.compute.private_ip
}

output "public_ip" {
  value = module.compute.public_ip
}
