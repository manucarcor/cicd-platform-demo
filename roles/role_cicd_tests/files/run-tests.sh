#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-cicd-tests"
REQ_FILE="$ROOT_DIR/files/requirements.txt"

TARGET="jenkins"
JUNIT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="$2"; shift 2;;
    --junitxml)
      JUNIT="$2"; shift 2;;
    --help)
      echo "Usage: $0 [--target <jenkins|nexus|gitlab|gitlab_runner>] [--junitxml <path>]"; exit 0;;
    *)
      echo "Unknown arg: $1"; exit 2;;
  esac
done

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r "$REQ_FILE"

PYTEST_ARGS=( -q )
if [[ -n "$JUNIT" ]]; then
  PYTEST_ARGS+=( --junitxml "$JUNIT" )
fi

PYTEST_ARGS+=( -m "$TARGET" )

# Run from the role directory so the tests/ path is correct
cd "$ROOT_DIR"

pytest "${PYTEST_ARGS[@]}" tests
