#!/usr/bin/env bash
set -euo pipefail

destination=$1
mkdir -p "$destination"
destination=$(cd "$destination" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cd "$work"

fetch() {
  curl --fail --location --retry 3 --silent --show-error "$1" --output "$2"
}
verify() {
  local filename=$1 checksums=$2
  awk -v name="$filename" '$2 == name || $2 == "*" name {print $1 "  " name}' "$checksums" |
    sha256sum --check -
}

kind_url=https://github.com/kubernetes-sigs/kind/releases/download/v0.30.0
fetch "$kind_url/kind-linux-amd64" kind-linux-amd64
fetch "$kind_url/kind-linux-amd64.sha256sum" kind.sum
verify kind-linux-amd64 kind.sum
install -m 0755 kind-linux-amd64 "$destination/kind"

kube_url=https://dl.k8s.io/release/v1.34.1/bin/linux/amd64
fetch "$kube_url/kubectl" kubectl
fetch "$kube_url/kubectl.sha256" kubectl.sha256
printf '%s  kubectl\n' "$(cat kubectl.sha256)" | sha256sum --check -
install -m 0755 kubectl "$destination/kubectl"

helm_file=helm-v3.19.0-linux-amd64.tar.gz
fetch "https://get.helm.sh/$helm_file" "$helm_file"
fetch "https://get.helm.sh/$helm_file.sha256sum" helm.sum
verify "$helm_file" helm.sum
tar -xzf "$helm_file" linux-amd64/helm
install -m 0755 linux-amd64/helm "$destination/helm"

k6_url=https://github.com/grafana/k6/releases/download/v1.3.0
k6_file=k6-v1.3.0-linux-amd64.tar.gz
fetch "$k6_url/$k6_file" "$k6_file"
fetch "$k6_url/k6-v1.3.0-checksums.txt" k6.sum
verify "$k6_file" k6.sum
tar -xzf "$k6_file"
install -m 0755 k6-v1.3.0-linux-amd64/k6 "$destination/k6"

tf_url=https://releases.hashicorp.com/terraform/1.13.4
tf_file=terraform_1.13.4_linux_amd64.zip
fetch "$tf_url/$tf_file" "$tf_file"
fetch "$tf_url/terraform_1.13.4_SHA256SUMS" terraform.sum
verify "$tf_file" terraform.sum
python3 -m zipfile -e "$tf_file" .
install -m 0755 terraform "$destination/terraform"

lint_url=https://github.com/terraform-linters/tflint/releases/download/v0.60.0
fetch "$lint_url/tflint_linux_amd64.zip" tflint_linux_amd64.zip
fetch "$lint_url/checksums.txt" tflint.sum
verify tflint_linux_amd64.zip tflint.sum
python3 -m zipfile -e tflint_linux_amd64.zip .
install -m 0755 tflint "$destination/tflint"

trivy_url=https://github.com/aquasecurity/trivy/releases/download/v0.69.3
trivy_file=trivy_0.69.3_Linux-64bit.tar.gz
fetch "$trivy_url/$trivy_file" "$trivy_file"
fetch "$trivy_url/trivy_0.69.3_checksums.txt" trivy.sum
verify "$trivy_file" trivy.sum
tar -xzf "$trivy_file" trivy
install -m 0755 trivy "$destination/trivy"
