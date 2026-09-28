#!/usr/bin/env bash
# Run the isolated, one-source synthetic demo without touching the main dev DB.
set -euo pipefail

nwis_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$nwis_repo_root"
if [[ ! -f .env ]]; then
  echo "Missing local .env; see .env.example" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

export NWIS_DATABASE_URL="postgresql+psycopg://nwis:${NWIS_DB_PASSWORD}@127.0.0.1:${NWIS_DB_PORT:-5432}/nwis_demo_clean"
export NWIS_STORAGE_ROOT="$nwis_repo_root/backend/storage/demo-clean"
export NWIS_SEMANTIC_CACHE_DIR="$nwis_repo_root/backend/storage/models"
export NWIS_SEMANTIC_ENABLED=true

for nwis_port in 18083 13003; do
  if lsof -nP -iTCP:"$nwis_port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $nwis_port is already in use; stop that preview before starting another." >&2
    exit 1
  fi
done

cd "$nwis_repo_root/backend"
.venv/bin/python -m nwis.initialize
.venv/bin/python -m nwis.demo_guard --allow-unindexed
.venv/bin/python -m nwis.synthetic_survey_demo
.venv/bin/python -m nwis.semantic index --dataset-id 0075c04f-2395-5617-a2bd-a752e8ce508e
.venv/bin/python -m nwis.demo_guard

.venv/bin/uvicorn nwis.main:app --host 127.0.0.1 --port 18083 &
nwis_api_pid=$!
.venv/bin/python -m nwis.worker &
nwis_worker_pid=$!
.venv/bin/python -m nwis.operations_worker &
nwis_replay_pid=$!
cd "$nwis_repo_root/frontend"
NWIS_DEV_API_URL=http://127.0.0.1:18083 ./node_modules/.bin/vite --host 127.0.0.1 --port 13003 --strictPort &
nwis_web_pid=$!

cleanup() {
  kill "$nwis_api_pid" "$nwis_worker_pid" "$nwis_replay_pid" "$nwis_web_pid" 2>/dev/null || true
  wait "$nwis_api_pid" "$nwis_worker_pid" "$nwis_replay_pid" "$nwis_web_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_for_demo_service() {
  local nwis_name="$1"
  local nwis_url="$2"
  local nwis_attempt
  for ((nwis_attempt = 1; nwis_attempt <= 30; nwis_attempt++)); do
    if ! kill -0 "$nwis_api_pid" 2>/dev/null || ! kill -0 "$nwis_worker_pid" 2>/dev/null \
      || ! kill -0 "$nwis_replay_pid" 2>/dev/null || ! kill -0 "$nwis_web_pid" 2>/dev/null; then
      echo "A demo process exited before $nwis_name became ready." >&2
      return 1
    fi
    if curl --fail --silent --show-error --max-time 2 --output /dev/null "$nwis_url" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "$nwis_name did not become ready within 30 seconds." >&2
  return 1
}

wait_for_demo_service "API" "http://127.0.0.1:18083/healthz"
wait_for_demo_service "web preview" "http://127.0.0.1:13003/"
echo "Synthetic one-source demo: http://127.0.0.1:13003/"
echo "Uses local role tokens from .env; press Ctrl-C to stop only these four processes."
while kill -0 "$nwis_api_pid" 2>/dev/null && kill -0 "$nwis_worker_pid" 2>/dev/null \
  && kill -0 "$nwis_replay_pid" 2>/dev/null && kill -0 "$nwis_web_pid" 2>/dev/null; do
  sleep 2
done
echo "A demo process exited; stopping the remaining processes." >&2
exit 1
