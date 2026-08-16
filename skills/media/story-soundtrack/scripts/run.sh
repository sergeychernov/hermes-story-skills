#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${STORY_SOUNDTRACK_RUNTIME:-${XDG_CACHE_HOME:-$HOME/.cache}/story-soundtrack/v2}"

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <script-name> [args...]\n' "$0" >&2
  exit 64
fi

SCRIPT_NAME="$1"
shift
case "$SCRIPT_NAME" in
  render_story_score.py|mix_story_audio.py|apply_feedback_revision.py|approve_story_soundtrack.py|verify_story_soundtrack.py|make_demo_sources.py)
    ;;
  *)
    printf 'error: unsupported story-soundtrack script: %s\n' "$SCRIPT_NAME" >&2
    exit 64
    ;;
esac

"$SCRIPT_DIR/bootstrap_runtime.sh" "$RUNTIME_DIR" >/dev/null
exec "$RUNTIME_DIR/venv/bin/python" "$SCRIPT_DIR/$SCRIPT_NAME" "$@"
