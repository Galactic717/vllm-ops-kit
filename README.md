# vllm-ops-kit

[Українська версія](README.uk.md)

A deployment and verification kit for [Verstak Agent](https://github.com/Galactic717/verstak-agent) and [Verifine SLM](https://github.com/Galactic717/verifine-slm). Use an existing Windows llama.cpp server, run the full software stack in a CPU-only kind cluster, or deploy a local Safetensors model to vLLM on NVIDIA Kubernetes nodes.

| Profile | Inference | What it exercises |
|---|---|---|
| Windows | Existing GGUF through llama.cpp | Real chat, SSE, token usage and Verifine metrics |
| kind | Deterministic CPU fixture | Ingress, Verstak OAuth and Celery, Postgres, Redis, network isolation, Prometheus, Grafana, HPA and k6 |
| Ubuntu VM | CPU fixture | Terraform, Ansible, Docker Compose, systemd, TLS proxy and Node Exporter |
| GPU Kubernetes | vLLM with a model PVC | The same APIs with LLM serving metrics and a dedicated GPU resource |

## Windows with llama.cpp

With Docker Desktop running, build the images from sibling checkouts. On a standalone clone, use `python scripts/images.py --fetch` to build from the pinned upstream revisions.

~~~powershell
python scripts/images.py
pwsh -File scripts/local.ps1 -Port 9941
~~~

Use the port from the launcher you started. The script reads the model ID from /v1/models. It creates a temporary Verifine container and checks both normal and streaming inference. Set LLAMA_API_KEY in the process environment if the upstream requires authentication.

The installed launchers use ports such as 9931 for Gemma E4B, 9932 for Gemma 12B, 9933 for GPT-OSS 20B and 9939 for GPT-OSS 120B. The Gemma 26B and GLM launchers share port 9934. Verify the port in your launcher if you changed its settings.

To start a temporary CPU server with an explicit model from the local installation, select a free port and supply the GGUF path.

~~~powershell
$model = Get-ChildItem "$env:LOCALAPPDATA/Programs/llama.cpp/models" -Recurse -Filter 'gemma-4-E4B-it-UD-Q8_K_XL.gguf' | Select-Object -First 1
pwsh -File scripts/local.ps1 -Port 18091 -ModelPath $model.FullName
~~~

## Ubuntu or Windows Docker Desktop with kind

Use amd64, Linux containers, Docker Engine 28+ with API 1.48, Python 3.10+, Git, kind 0.30.0, kubectl 1.34, Helm 3.19 and k6 1.3. Allocate at least 4 CPUs and 8 GiB of RAM to Docker. On Linux, [scripts/ci_tools.sh](scripts/ci_tools.sh) installs the pinned CLI versions into a directory you choose.

On Windows, the installer keeps tool binaries inside the project. Add them to the current PowerShell session.

~~~powershell
pwsh -File scripts/install-windows-tools.ps1
$env:PATH = "$(Join-Path $PWD '.tools/bin');$env:PATH"
~~~

~~~sh
python scripts/images.py --fetch
python scripts/kind_lab.py
~~~

The lab uses a dedicated kubeconfig called .kubeconfig-kind and listens on 127.0.0.1:18080. The runner creates runtime credentials in Kubernetes and checks Ingress, protected routes, SSE, the Celery workflow, live Prometheus series, Alertmanager, Grafana and enforced network isolation. It records the Helm wait time, k6 summaries and HPA samples in loadtest/results/latest.

~~~sh
kubectl --kubeconfig .kubeconfig-kind -n monitoring port-forward svc/kps-grafana 13000:80
python scripts/kind_lab.py --verify-only --profiles smoke spike
python scripts/kind_lab.py --verify-only --profiles soak --base-rate 5
~~~

Use user admin and the admin-password key of Secret kps-grafana to sign in at http://127.0.0.1:13000. Delete the disposable lab after use with `kind delete cluster --name vllm-ops-kit --kubeconfig .kubeconfig-kind`.

## Cloud and operations

- [Cloud deployment](docs/CLOUD.md) covers AWS and GCP Terraform state, GitHub OIDC, the CPU VM playbook and the GPU Kubernetes profile.
- [Architecture](docs/ARCHITECTURE.md) covers traffic, dependency isolation, secrets, rollouts and metrics.
- [Linux disk pressure](docs/runbooks/disk-pressure.md), [worker OOM](docs/runbooks/oomkilled.md), [Redis unavailable](docs/runbooks/redis-down.md), [PostgreSQL locks](docs/runbooks/db-lock.md) and [upstream HTTP 429](docs/runbooks/llm-429.md).

## Measured

See [verification results](loadtest/results/README.md) for the local Windows inference runs and the kind baseline and 3× spike. The GitHub Actions and GitLab jobs rerun the checks and upload verification artifacts and scan reports.
