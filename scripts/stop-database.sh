#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PG_BIN="${PG_BIN:-/opt/homebrew/opt/postgresql@14/bin}"
"$PG_BIN/pg_ctl" -D runtime/pgdata -m fast stop
