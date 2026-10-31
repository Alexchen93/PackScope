#!/bin/sh
# Start the PackScope read-only interface from its own checkout.
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -m packscope.app "$@"
