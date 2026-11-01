#!/bin/sh
# Start PackScope from its own checkout.
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -m packscope.app "$@"
