#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON:-python3}"
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
  "$python_bin" -m unittest discover -s "$suite" -p 'test_*.py' -v
done
