"""Scrape the Redis dispatch queue and PostgreSQL connection utilization independently."""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg
import redis


def postgres_metrics():
    with psycopg.connect(os.environ["VERSTAK_DATABASE_URL"], connect_timeout=2,
                         options="-c statement_timeout=2000") as conn:
        active, maximum = conn.execute(
            "SELECT count(*) FILTER (WHERE backend_type = 'client backend'), "
            "current_setting('max_connections')::int FROM pg_stat_activity"
        ).fetchone()
    return {"ops_postgres_up": 1, "ops_postgres_connections": active,
            "ops_postgres_max_connections": maximum}


def redis_metrics():
    with redis.Redis.from_url(os.environ["VERSTAK_REDIS_URL"], socket_timeout=2,
                              socket_connect_timeout=2) as client:
        return {"ops_redis_up": int(client.ping()),
                "ops_celery_queue_depth": client.llen("celery")}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {"/health", "/metrics"}:
            self.send_error(404)
            return
        metrics = {}
        if self.path == "/metrics":
            try:
                metrics.update(postgres_metrics())
            except psycopg.Error:
                metrics["ops_postgres_up"] = 0
            try:
                metrics.update(redis_metrics())
            except redis.RedisError:
                metrics["ops_redis_up"] = 0
        body = "".join(f"# TYPE {name} gauge\n{name} {value}\n"
                       for name, value in metrics.items()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


ThreadingHTTPServer(("0.0.0.0", 9108), Handler).serve_forever()
