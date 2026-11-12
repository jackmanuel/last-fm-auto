#!/bin/sh
# Run from the project directory, even when launched from elsewhere.
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
    echo "ERROR: Python virtual environment not found at $PROJECT_DIR/.venv" >&2
    echo "Follow the Linux setup steps in README.md first." >&2
    exit 1
fi

export PYTHONIOENCODING=utf-8
exec "$PROJECT_DIR/.venv/bin/python" -m last_fm_auto.main "$@"
