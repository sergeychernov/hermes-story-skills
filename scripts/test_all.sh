#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON:-python3}"
uv_bin="${UV:-uv}"
pil_suite="skills/media/static-cover-collage/scripts/tests"
suites=(
  scripts/tests
  skills/media/still-image-animation/scripts/tests
  skills/media/story/scripts/tests
  skills/media/animated-collage/scripts/tests
  skills/media/scene-group/tests
  skills/media/media-voiceover/tests
  skills/media/static-cover-collage/scripts/tests
  skills/media/shorts-assembly/scripts/tests
  skills/media/social-publisher/scripts
)

soundtrack_suite="skills/media/story-soundtrack/scripts/tests"
if [[ "${RUN_STORY_SOUNDTRACK_TESTS:-0}" == "1" ]]; then
  suites+=("$soundtrack_suite")
else
  printf 'SKIP %s (set RUN_STORY_SOUNDTRACK_TESTS=1 to enable)\n' "$soundtrack_suite"
fi

for suite in "${suites[@]}"; do
  printf '\n=== %s ===\n' "$suite"
  if [[ "$suite" == "$pil_suite" ]]; then
    command -v "$uv_bin" >/dev/null 2>&1 || {
      printf 'ERROR: uv is required to run %s with Pillow\n' "$suite" >&2
      exit 1
    }
    printf 'dependency: Pillow via uv\n'
    "$uv_bin" run --with Pillow --no-project -- python -m unittest discover -s "$suite" -p 'test_*.py' -v
  else
    "$python_bin" -m unittest discover -s "$suite" -p 'test_*.py' -v
  fi
done
