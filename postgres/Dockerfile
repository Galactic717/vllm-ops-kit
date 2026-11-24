FROM pgvector/pgvector:0.8.7-pg16-trixie

# Kubernetes starts PostgreSQL as UID 999, so the root-only privilege
# dropping executable is unnecessary in this image.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* /usr/local/bin/gosu

USER 999:999
