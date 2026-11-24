# Measured verification

Run on 24 November 2026 using Windows with Docker Desktop, kind v0.30.0, Kubernetes v1.34.0 and k6 v1.3.0.

## Kubernetes CPU fixture

A clean kind cluster passed the Helm test, Ingress authentication, SSE and structured extraction. Verstak dispatched a Celery workflow through Verifine to the fixture and reached the human approval gate. The unauthorized pod resolved the API service and was denied its TCP connection. Prometheus collected the application, pool and dependency metrics. Alertmanager and both Grafana dashboards responded.

Helm install and readiness for the application release took **20.48 s**. The timer starts after kind and the platform addons are running and the application images are imported.

| Profile | Requests | HTTP req/s | Chat p50 | Chat p95 | Chat p99 | HTTP failures |
|---|---:|---:|---:|---:|---:|---:|
| Baseline, 5 iterations/s, 12 s | 122 | 10.16 | 4.23 ms | 4.77 ms | 7.16 ms | 0% |
| 3× spike, 15 iterations/s, 35 s | 1,052 | 30.05 | 3.52 ms | 4.26 ms | 4.66 ms | 0% |

Each iteration calls chat and the authenticated workflows endpoint. The CPU HPA held two API replicas. Its maximum sampled utilization was 7% of requested CPU against a 60% target.

[k6 baseline JSON](kind-smoke.json) · [k6 spike JSON](kind-spike.json) · [Kubernetes and HPA evidence](kind-verification.json)

## Real Windows inference

| Model | Gateway chat latency | SSE | Gateway metrics | llama.cpp metrics |
|---|---:|---|---|---|
| Existing verifine-qwen-q4 server | 201.6 ms | Passed | Available | Disabled in the running server |
| Gemma 4 E4B GGUF, CPU | 497.4 ms | Passed | Available | Available |

Each latency is one non-streaming request through Verifine. The managed Gemma test used an existing GGUF, a 2,048-token context and a temporary CPU server.

[Existing llama.cpp server JSON](windows-llama.json) · [Gemma E4B JSON](windows-gemma-e4b.json)

## Infrastructure and image checks

All six Terraform roots passed terraform validate and TFLint. The Ansible play passed syntax validation. Helm lint passed for the CPU and GPU profiles. The GPU chart passed a Kubernetes server dry run. Promtool loaded all six alert rules and passed the alert timing test.

Checkov reported 105 passes and 12 advisory findings. The configured blocking checks passed, including OIDC, public ingress checks and the selected AWS and GCP safeguards. Advisory findings include flow logs, bucket access logging and customer-managed encryption choices. Review them when planning a deployment.

Trivy v0.69.3 found zero HIGH or CRITICAL issues with published fixes in the five CPU images. The full scan also reported the following HIGH or CRITICAL issues without a published fix. Counts are unique vulnerability ID and package pairs within each image.

| CPU image | HIGH without a fix | CRITICAL without a fix |
|---|---:|---:|
| Fixture | 99 | 2 |
| Verstak | 99 | 2 |
| Verifine | 53 | 0 |
| PostgreSQL | 72 | 1 |
| Redis | 0 | 0 |

The live tests covered Windows inference and the CPU Kubernetes lab. AWS/GCP deployment, the Ubuntu VM play and vLLM inference on a GPU still require verification on the target infrastructure. GitHub Actions uploads k6 and security artifacts for each hosted run. [Workflow history](https://github.com/Galactic717/vllm-ops-kit/actions/workflows/ci.yml)
