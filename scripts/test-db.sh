#!/usr/bin/env bash
# Start (or reuse) the local pgvector Postgres used by supabase/tests.
set -euo pipefail
if docker ps -a --format '{{.Names}}' | grep -qx rag-pg; then
  docker start rag-pg >/dev/null
else
  docker run -d --name rag-pg -p 54329:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg17 >/dev/null
fi
until docker exec rag-pg pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done
echo "rag-pg ready on localhost:54329"
