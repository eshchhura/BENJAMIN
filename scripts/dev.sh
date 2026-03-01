#!/usr/bin/env sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-python}"
"$PYTHON_BIN" scripts/check.py || {
  echo "[dev] Environment check failed. Fix errors above and retry."
  exit 1
}

API_HOST="${BENJAMIN_API_HOST:-127.0.0.1}"
API_PORT="${BENJAMIN_API_PORT:-8000}"
API_BASE="http://${API_HOST}:${API_PORT}"
UI_URL="${API_BASE}/ui"
INTEGRATIONS_URL="${API_BASE}/integrations/status"

PROVIDER="$(printf '%s' "${BENJAMIN_LLM_PROVIDER:-off}" | tr '[:upper:]' '[:lower:]')"
START_VLLM="$(printf '%s' "${BENJAMIN_DEV_START_VLLM:-off}" | tr '[:upper:]' '[:lower:]')"
STATE_DIR="${BENJAMIN_STATE_DIR:-$HOME/.benjamin}"

child_pids=""

start_process() {
  label="$1"
  shift
  "$@" &
  pid=$!
  child_pids="${child_pids} ${pid}"
  echo "[dev] started ${label} (pid=${pid})"
}

cleanup() {
  echo "[dev] stopping child processes..."
  for pid in $child_pids; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait || true
}

trap cleanup INT TERM EXIT

echo "[dev] state dir: ${STATE_DIR}"
echo "[dev] API base: ${API_BASE}"
echo "[dev] UI URL: ${UI_URL}"
echo "[dev] Integrations status URL: ${INTEGRATIONS_URL}"

for feature in PLANNER SUMMARIZER DRAFTER RULE_BUILDER RETRIEVAL; do
  var="BENJAMIN_LLM_${feature}"
  eval "value=\${$var:-}"
  if [ -z "$value" ]; then
    if [ "$PROVIDER" = "off" ]; then
      value="off"
    else
      value="on"
    fi
  fi
  echo "[dev] feature ${feature}: ${value}"
done

if [ "$PROVIDER" = "vllm" ] && [ "$START_VLLM" = "on" ]; then
  if [ -n "${BENJAMIN_DEV_VLLM_CMD:-}" ]; then
    echo "[dev] vLLM endpoint: ${BENJAMIN_VLLM_URL:-http://127.0.0.1:8001/v1/chat/completions}"
    start_process "vLLM" sh -c "${BENJAMIN_DEV_VLLM_CMD}"
  else
    echo "[dev] BENJAMIN_DEV_START_VLLM=on but BENJAMIN_DEV_VLLM_CMD is not set; skipping vLLM startup."
    echo "[dev] Example command: vllm serve \"${BENJAMIN_LLM_MODEL:-zai-org/GLM-4.7}\" --host 127.0.0.1 --port 8001 --dtype auto --max-model-len 8192 --gpu-memory-utilization 0.90"
  fi
elif [ "$PROVIDER" = "vllm" ]; then
  echo "[dev] vLLM endpoint: ${BENJAMIN_VLLM_URL:-http://127.0.0.1:8001/v1/chat/completions} (external)"
fi

start_process "benjamin-api" benjamin-api
start_process "benjamin-worker" benjamin-worker

echo "[dev] Running. Press Ctrl+C to stop."
wait
