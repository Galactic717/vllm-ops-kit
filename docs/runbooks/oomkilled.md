# Worker or model OOM

1. Run `kubectl -n ai-stack describe pod <pod>` and `kubectl -n ai-stack logs <pod> --previous`. Check the termination reason, container memory limit and timestamps. Check node events for eviction. A CUDA allocation failure may appear only in vLLM logs while the container remains under its RAM limit.
2. For a worker, compare input sizes and memory across the failing jobs. Keep the solo pool while investigating and raise the memory limit only after checking node headroom. For vLLM, reduce context or batch pressure, or select a model and KV-cache configuration that fit the GPU.
3. Watch ready replicas, retries, Celery queue drain and a new workflow or chat. Confirm processing resumes before increasing traffic. Record the affected pod revision, memory high-water mark and whether jobs had to be replayed.
