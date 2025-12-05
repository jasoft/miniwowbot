#!/bin/bash
set -euo pipefail

SCRIPT_DIR="/Users/weiwang/Projects/miniwow"
cd "$SCRIPT_DIR"

export PATH="/opt/homebrew/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
  uv run "$SCRIPT_DIR/cron_run_all_dungeons.py"
else
  PYTHONPATH="$SCRIPT_DIR" python3 "$SCRIPT_DIR/cron_run_all_dungeons.py"
fi
