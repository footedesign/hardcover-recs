#!/usr/bin/env bash
set -euo pipefail

data_root="${PIPELINE_DATA_ROOT:-/data}"

if [[ "$(id -u)" -eq 0 ]]; then
  mkdir -p "${data_root}"
  chown -R appuser:appuser "${data_root}"
  exec gosu appuser "$@"
fi

exec "$@"
