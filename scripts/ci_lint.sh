#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python -m unittest discover -s tests
helm lint charts/ai-stack --strict
helm lint charts/ai-stack --strict -f charts/ai-stack/values-ci.yaml
helm lint charts/ai-stack --strict -f charts/ai-stack/values-gpu.yaml
helm lint monitoring --strict
docker run --rm --entrypoint /bin/promtool \
    -v "$PWD/monitoring/prometheus:/rules:ro" prom/prometheus:v3.5.1 \
    check rules /rules/llm_slo_alerts.yml
docker run --rm --entrypoint /bin/promtool \
    -v "$PWD/monitoring/prometheus:/rules:ro" -w /rules prom/prometheus:v3.5.1 \
    test rules llm_slo_alerts.test.yml

terraform fmt -check -recursive terraform
for root in terraform/envs/*/* terraform/oidc/*; do
  terraform -chdir="$root" init -backend=false -input=false
  terraform -chdir="$root" validate
  tflint --chdir="$root" --config="$PWD/.tflint.hcl"
done

(
  cd ansible
  export ANSIBLE_CONFIG="$PWD/ansible.cfg"
  ansible-galaxy collection install -r requirements.yml
  ansible-playbook -i inventory.example.ini playbooks/harden_and_deploy.yml --syntax-check
)
