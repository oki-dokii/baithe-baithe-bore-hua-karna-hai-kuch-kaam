#!/usr/bin/env bash
# Local reviewer-only preview of the isolated public-report staging database.
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

export NWIS_DATABASE_URL="postgresql+psycopg://nwis:${NWIS_DB_PASSWORD}@127.0.0.1:${NWIS_DB_PORT:-5432}/nwis_public_benchmark"
export NWIS_STORAGE_ROOT="$nwis_repo_root/backend/storage/public-benchmark"
export NWIS_DOCUMENT_MAX_PAGES=200
export NWIS_EXTRACTION_PROVIDER=local_rules
export NWIS_SEMANTIC_ENABLED=false

for nwis_port in 18084 13004; do
  if lsof -nP -iTCP:"$nwis_port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $nwis_port is already in use; stop that preview before starting another." >&2
    exit 1
  fi
done

cd "$nwis_repo_root/backend"
.venv/bin/python -m nwis.public_benchmark_ingest status >/dev/null
.venv/bin/uvicorn nwis.main:app --host 127.0.0.1 --port 18084 &
nwis_api_pid=$!
cd "$nwis_repo_root/frontend"
NWIS_DEV_API_URL=http://127.0.0.1:18084 ./node_modules/.bin/vite --host 127.0.0.1 --port 13004 --strictPort &
nwis_web_pid=$!

cleanup() {
  kill "$nwis_api_pid" "$nwis_web_pid" 2>/dev/null || true
  wait "$nwis_api_pid" "$nwis_web_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_for_service() {
  local nwis_url="$1"
  local nwis_attempt
  for ((nwis_attempt = 1; nwis_attempt <= 30; nwis_attempt++)); do
    if ! kill -0 "$nwis_api_pid" 2>/dev/null || ! kill -0 "$nwis_web_pid" 2>/dev/null; then
      echo "Public review process exited before readiness." >&2
      return 1
    fi
    if curl --fail --silent --show-error --max-time 2 --output /dev/null "$nwis_url" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "Public review preview did not become ready." >&2
  return 1
}

wait_for_service "http://127.0.0.1:18084/healthz"
wait_for_service "http://127.0.0.1:13004/"
echo "Unreviewed public-report workspace: http://127.0.0.1:13004/"
echo "Use the local reviewer token. Approvals are blocked; source inspection and draft corrections remain available."
echo "Press Ctrl-C to stop only these two processes."
while kill -0 "$nwis_api_pid" 2>/dev/null && kill -0 "$nwis_web_pid" 2>/dev/null; do
  sleep 2
done
echo "A public-review process exited; stopping the other process." >&2
exit 1
