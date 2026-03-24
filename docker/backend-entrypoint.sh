#!/usr/bin/env bash
set -euo pipefail

data_root="${PIPELINE_DATA_ROOT:-/data}"
current_link="${data_root}/current"
db_path="${HARDCOVER_DB_PATH:-${current_link}/hardcover.db}"
model_path="${HARDCOVER_MODEL_PATH:-${current_link}/svd_model.npz}"
host="${BACKEND_HOST:-0.0.0.0}"
port="${BACKEND_PORT:-8000}"

if [[ ! -L "${current_link}" && ! -d "${current_link}" ]]; then
  echo "backend: ${current_link} is missing; run pipeline-init first" >&2
  exit 1
fi

if [[ ! -f "${db_path}" || ! -f "${model_path}" ]]; then
  echo "backend: missing runtime artifacts at ${db_path} and/or ${model_path}" >&2
  exit 1
fi

current_target="$(readlink -f "${current_link}")"

cleanup() {
  if [[ -n "${uvicorn_pid:-}" ]]; then
    kill "${uvicorn_pid}" 2>/dev/null || true
    wait "${uvicorn_pid}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

python -m uvicorn backend.main:app --host "${host}" --port "${port}" &
uvicorn_pid=$!

while kill -0 "${uvicorn_pid}" 2>/dev/null; do
  sleep 5
  next_target="$(readlink -f "${current_link}" 2>/dev/null || true)"
  if [[ -n "${next_target}" && "${next_target}" != "${current_target}" ]]; then
    echo "backend: detected release change from ${current_target} to ${next_target}; restarting" >&2
    kill "${uvicorn_pid}" 2>/dev/null || true
    wait "${uvicorn_pid}" 2>/dev/null || true
    exit 0
  fi
done

wait "${uvicorn_pid}"
