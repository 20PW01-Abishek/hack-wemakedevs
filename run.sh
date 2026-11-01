#!/usr/bin/env bash
cd "$(dirname "$0")"
source vars.sh
docker compose up -d database
trap 'kill 0' EXIT
uv run uvicorn api:app --port 8000 &
(cd web && npm install --silent && npm run dev) &
wait
