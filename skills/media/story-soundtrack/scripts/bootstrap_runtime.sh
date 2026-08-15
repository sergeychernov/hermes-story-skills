#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${1:-${STORY_SOUNDTRACK_RUNTIME:-${XDG_CACHE_HOME:-$HOME/.cache}/story-soundtrack/v2}}"
VENV_DIR="$RUNTIME_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PYTHON_REQUEST="${STORY_SOUNDTRACK_PYTHON:-3.13}"

command -v uv >/dev/null 2>&1 || {
  printf 'error: uv is required to bootstrap story-soundtrack runtime\n' >&2
  exit 127
}

mkdir -p "$RUNTIME_DIR"
if [[ ! -x "$PYTHON_BIN" ]]; then
  uv venv --python "$PYTHON_REQUEST" "$VENV_DIR"
fi

uv pip sync --python "$PYTHON_BIN" "$SCRIPT_DIR/requirements.lock"
"$PYTHON_BIN" -c 'import numpy; print("story-soundtrack runtime: numpy=" + numpy.__version__)'
printf '%s\n' "$PYTHON_BIN"
