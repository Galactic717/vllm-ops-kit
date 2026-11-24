"""Add per-replica PostgreSQL pool metrics to the upstream Verstak app."""
from contextlib import asynccontextmanager

from fastapi import Response
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from verstak.api import app
from verstak.config import settings
from verstak.db import get_session

# Pool HTTP sessions only. The Celery worker keeps the upstream NullPool.
POOL_SIZE, MAX_OVERFLOW = 5, 5
engine = create_async_engine(
    settings().database_url.replace("postgresql://", "postgresql+psycopg://", 1),
    pool_size=POOL_SIZE, max_overflow=MAX_OVERFLOW, pool_timeout=3, pool_pre_ping=True,
)
sessions = async_sessionmaker(engine, expire_on_commit=False)


async def api_session():
    async with sessions() as session:
        yield session


app.dependency_overrides[get_session] = api_session
upstream_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(application):
    try:
        async with upstream_lifespan(application) as state:
            yield state
    finally:
        await engine.dispose()


app.router.lifespan_context = lifespan


@app.get("/ops/pool-metrics", include_in_schema=False)
def pool_metrics():
    return Response(
        "# TYPE verstak_db_pool_checked_out gauge\n"
        f"verstak_db_pool_checked_out {engine.pool.checkedout()}\n"
        "# TYPE verstak_db_pool_size gauge\n"
        f"verstak_db_pool_size {POOL_SIZE + MAX_OVERFLOW}\n",
        media_type="text/plain",
    )


@app.get("/ops/live", include_in_schema=False)
def live():
    return {"status": "ok"}
