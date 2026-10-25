#!/bin/bash
set -e
cd "$(dirname "$0")"
.venv/bin/python scripts/manage_local.py start --open
