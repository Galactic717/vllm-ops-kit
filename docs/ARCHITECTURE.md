# Architecture

~~~mermaid
flowchart LR
  Win["Windows llama.cpp and GGUF"] --> Local["Temporary Verifine container"]
  Client --> Traefik["Traefik Ingress"]
  Traefik --> API["Verstak API"]
  Traefik --> GW["Verifine gateway"]
  API --> PG["PostgreSQL / pgvector"]
  API --> Redis
  Beat["Celery Beat"] --> Redis
  Worker["Celery worker"] --> Redis
  Worker --> PG
  Worker -. "OpenAI-compatible profile" .-> GW
  GW --> Model["Fixture or vLLM"]
  Exporter["Dependency exporter"] --> PG
  Exporter --> Redis
  Prometheus --> API
  Prometheus --> GW
  Prometheus --> Model
  Prometheus --> Exporter
  Prometheus --> Alertmanager
  Grafana --> Prometheus
~~~

Ingress routes exact inference endpoints to Verifine and explicit API prefixes to Verstak. The gateway and Verstak require bearer credentials for inference and workflow operations. Prometheus scrapes an authenticated Verstak endpoint and in-cluster endpoints on Verifine, the model server and the dependency exporter. Kubernetes secrets are provided outside Helm. The lab generates a separate credential for each purpose. Use an encrypted cluster secret store and RBAC around Secret reads in a deployed environment. Postgres and Redis passwords must be URL-safe because Kubernetes interpolates them into connection strings.

The Calico policy test checks that an unrelated pod can resolve the API service and still cannot open its socket. Application pods run with restricted admission, non-root users, read-only root filesystems and bounded resources. Their egress is limited to Kubernetes DNS and the ports needed by each component. The external backend profile requires a destination CIDR and port if network policy is enabled.

The API can roll with maxUnavailable 0 when there is spare capacity and both API revisions understand the active database schema. Alembic uses the upstream advisory lock, and each new API replica runs the migrations before becoming ready. The API uses an explicit 5+5 SQLAlchemy pool per replica. The Celery deployment retains upstream per-task connections. Keep the configured maximum number of API replicas within the database connection budget.

The reference GPU backend consumes one NVIDIA allocation with its model mounted read-only. Its Recreate strategy has a model restart window. PostgreSQL and Redis are single-replica StatefulSets. Their PVCs provide persistence and require a separate tested backup and restore process. Deploy multi-replica dependencies and model capacity if your availability objectives require them.

## Signals

| Signal | Source |
|---|---|
| TTFT p95 and TPOT p95 | vLLM histograms |
| KV-cache utilization | vLLM cache fraction |
| API 5xx burn rate | Verstak status counters and 5m/1h and 30m/6h windows for a 99% good-response objective |
| Gateway duration and token volume | Native Verifine metrics |
| Celery backlog | Redis LLEN on the default Celery list, excluding running and reserved tasks |
| PostgreSQL connection pressure | Per-API-replica pool and total postgres client slots |
| Dependency health | Independent Redis and PostgreSQL client probes |

The fixture emits its own counters. GPU latency and cache panels populate when Prometheus scrapes vLLM. Alertmanager receives alerts in the lab. Configure receiver routing and credentials for delivery in a deployed environment. The k6 test targets short non-streaming requests and samples API CPU HPA during execution. It measures end-to-end HTTP duration. Use vLLM histograms for TTFT instead.

## CI runners

GitHub Actions runs infrastructure lint, the live lab and image scans on Ubuntu. The GitLab template uses a project-locked Linux amd64 shell runner tagged docker-shell, with Docker Engine 28+, Python 3.12 and access to the needed registries. Reserve it for trusted refs because jobs can control its Docker daemon. CI exports run evidence and scanner results as artifacts. The optional cloud plan workflow requires a configured GitHub environment and uses expiring OIDC credentials. Set up the environment and its protection rules before dispatching a plan.
