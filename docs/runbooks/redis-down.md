# Redis unavailable

1. Confirm ops_redis_up and look at `kubectl -n ai-stack get pods ops-redis-0 ops-postgres-0`. Inspect Redis logs, PVC binding and recent NetworkPolicy or Secret changes.
2. Run `kubectl -n ai-stack exec ops-redis-0 -- redis-cli ping`. The container supplies REDISCLI_AUTH to redis-cli. If local PONG succeeds but the API returns 503, inspect service endpoints, the policy rules and the application credentials.
3. Repair connectivity or the backing volume. Preserve append-only files. After PONG and API readiness recover, confirm Celery dispatch and inspect queued workflows for expired leases. Record outage start, queue depth and recovery time.
