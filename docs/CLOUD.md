# Cloud deployment

The Terraform roots in terraform/envs/dev-free-tier and terraform/envs/prod-gpu each have an aws and gcp subdirectory. The modules create networking, an Ubuntu 24.04 VM and encrypted private artifact storage. The dev roots are sized for the lightweight VM fixture. The GPU roots use AWS g6.xlarge or GCP g2-standard-4 and provide a host for self-managed Kubernetes. The Helm GPU profile also works on an existing Kubernetes GPU node pool.

AWS eligibility depends on account age, account plan, region and credits. The GCP dev profile uses e2-micro, pd-standard and a Free Tier region by default. Public IPv4, transfer, storage version retention and all GPU resources can incur charges. Verify eligibility and quotas in your account before applying. [AWS EC2 Free Tier](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html) · [Google Cloud Free Program](https://docs.cloud.google.com/free/docs/free-cloud-features)

## Terraform and remote state

1. Create a private, versioned state bucket using a bootstrap identity. Use a different bucket from the artifact bucket managed by this kit. Create the AWS SSH key pair beforehand or configure GCP OS Login permissions and API access.
2. In the selected environment root, copy backend.hcl.example to backend.hcl and terraform.tfvars.example to terraform.tfvars. Fill in your IDs and the real operator and client CIDRs. Private addressing is the default. Provide a private path and outbound access, or set public_ip=true for the example VM and account for its cost.
3. Initialize and review the plan. Apply a saved plan only on the account designated for this deployment.

~~~sh
terraform init -backend-config=backend.hcl
terraform plan -out=ops.tfplan
terraform apply ops.tfplan
~~~

After use, review a destroy plan with the same root and variable values. Keep a copy of artifacts you need before removing any bucket versions.

## GitHub OIDC plan

Use terraform/oidc/aws for an exact GitHub repository and environment role. It takes an existing AWS GitHub identity provider ARN and an existing permission policy for plan reads and S3 state locking. The GCP root creates a workload-identity pool and a provider constrained to the owner login, repository name, numeric owner and repository IDs, and the GitHub environment. It delegates to an existing service account with status read access, state object access and locking. Run these bootstrap roots as an authorized administrator. AWS and GCP trust setup is separate from the application roots. [AWS GitHub OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws) · [Google pipeline identity federation](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)

Create and protect the GitHub environment cloud-plan. Set DEV_TFVARS_JSON and GPU_TFVARS_JSON as environment variables in the form {"aws":{"bucket_name":"...","ssh_key_name":"..."},"gcp":{"bucket_name":"...","project_id":"..."}}. Add the state bucket variables and the identity coordinates for the provider you plan to use.

| Provider | GitHub environment variables |
|---|---|
| AWS | AWS_PLAN_ROLE_ARN, AWS_REGION, AWS_STATE_BUCKET, AWS_STATE_REGION |
| GCP | GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_PLAN_SERVICE_ACCOUNT, GCP_STATE_BUCKET |

Run Cloud Terraform plan and choose the target. The workflow has no apply step. Keep credentials and private keys outside these variables.

## Ubuntu CPU fixture

Provide a reachable Ubuntu 24.04 VM with a known host key, an operator who can already SSH using a public key and sudo, and a deployed TLS certificate and private key. For an AWS VM with HTTPS-only egress, configure the Ubuntu apt source URIs to https before the first play. Copy inventory.example.ini to inventory.ini and group_vars/ops_nodes.example.yml to group_vars/ops_nodes.yml. Fill in the real hostname, key source and allowed CIDRs.

~~~sh
cd ansible
export ANSIBLE_CONFIG="$PWD/ansible.cfg"
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventory.ini playbooks/harden_and_deploy.yml --syntax-check
ansible-playbook -i inventory.ini playbooks/harden_and_deploy.yml
~~~

Check https://your-host/health from an allowed client. The play configures UFW, SSH, fail2ban, Docker, systemd, Nginx and a loopback Node Exporter. The fixture has no model weights and is reachable through Nginx from the configured client CIDR.

## NVIDIA Kubernetes

Provision Kubernetes with a CNI that enforces NetworkPolicy, NVIDIA drivers, the NVIDIA device plugin or GPU Operator, Metrics Server, dynamic storage and a suitable GPU node. Run these commands using your target context. Check that node allocatable resources include nvidia.com/gpu. If using a runtime class, set backend.runtimeClassName to its name.

Build and push the two upstream images and the kit's PostgreSQL image to your registry using scripts/images.py. Create a namespace and a PVC called vllm-model in it. Place your model’s Safetensors, configuration and tokenizer there. The PVC must be readable by UID 2000. The model and maximum context must fit the GPU. Provide a CRD-capable monitoring stack and use the settings in cluster/observability.yaml as a starting point.

~~~sh
kubectl --context "$KUBE_CONTEXT" create namespace ai-stack
kubectl --context "$KUBE_CONTEXT" label namespace ai-stack pod-security.kubernetes.io/enforce=restricted
python scripts/runtime_secret.py --context "$KUBE_CONTEXT"
helm --kube-context "$KUBE_CONTEXT" upgrade --install ops-slo monitoring -n monitoring
helm --kube-context "$KUBE_CONTEXT" upgrade --install ops charts/ai-stack \
  -n ai-stack -f charts/ai-stack/values-gpu.yaml \
  --set images.verstak="$VERSTAK_IMAGE" --set images.verifine="$VERIFINE_IMAGE" \
  --set images.postgres="$POSTGRES_IMAGE" \
  --wait --timeout 15m
helm --kube-context "$KUBE_CONTEXT" test ops -n ai-stack
kubectl --context "$KUBE_CONTEXT" -n ai-stack port-forward svc/ops-gateway 18088:8088
~~~

Call /v1/models and /v1/chat/completions with VERIFINE_GATEWAY_KEY and check /metrics on the backend from Prometheus. Before enabling Ingress, supply the intended class, controller namespace, host and TLS Secret in values. Update the policy selectors for your CNI, Ingress and Prometheus deployment. After the first live GPU run, verify that TTFT, TPOT and KV cache metrics populate in Grafana. [vLLM v0.18.0 deployment](https://docs.vllm.ai/en/v0.18.0/deployment/docker/) · [vLLM metrics](https://docs.vllm.ai/en/v0.18.0/usage/metrics/)
