#!/bin/sh
# Build a wheel first (including the web UI), then pass its exact path here.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/build_deb.py" "$@"
