#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies"
if ! command -v node >/dev/null && [ -x "$RUNTIME/node/bin/node" ]; then export PATH="$RUNTIME/node/bin:$PATH"; fi
if ! command -v pg_config >/dev/null && [ -d /opt/homebrew/opt/postgresql@14/bin ]; then export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"; fi
if ! command -v pg_config >/dev/null; then echo 'Нужен PostgreSQL (pg_config, initdb, pg_ctl) или Docker Compose.'; exit 1; fi
PG_BIN="$(pg_config --bindir)"
mkdir -p runtime
if [ ! -x .venv/bin/python ]; then
  PYTHON_BIN="$(command -v python3.12 || true)"
  if [ -z "$PYTHON_BIN" ] && [ -x "$RUNTIME/python/bin/python3" ]; then PYTHON_BIN="$RUNTIME/python/bin/python3"; fi
  if [ -z "$PYTHON_BIN" ]; then echo 'Нужен Python 3.12'; exit 1; fi
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/python -m pip install -r backend/requirements.lock.txt
fi
if [ ! -f runtime/pgdata/PG_VERSION ]; then "$PG_BIN/initdb" -D runtime/pgdata -A trust -U alfa --encoding=UTF8 --locale=C; fi
if ! "$PG_BIN/pg_ctl" -D runtime/pgdata status >/dev/null 2>&1; then
 "$PG_BIN/pg_ctl" -D runtime/pgdata -l runtime/postgres.log -o '-h 127.0.0.1 -p 55432 -k /tmp' start
fi
if ! "$PG_BIN/psql" -h 127.0.0.1 -p 55432 -U alfa -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='alfa_insight'" | tr -d ' ' | grep -q '^1$'; then
 "$PG_BIN/createdb" -h 127.0.0.1 -p 55432 -U alfa alfa_insight
fi
export PYTHONPATH=backend
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
if [ ! -d frontend/node_modules ]; then
 echo 'Установите зависимости интерфейса: cd frontend && corepack pnpm install --frozen-lockfile'; exit 1
fi
(cd frontend && node node_modules/typescript/bin/tsc --noEmit && node node_modules/vite/bin/vite.js build)
echo 'Альфа Инсайт: http://127.0.0.1:8000'
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
