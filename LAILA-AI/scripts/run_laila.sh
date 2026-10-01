#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export OLLAMA_NO_CLOUD=1 HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
