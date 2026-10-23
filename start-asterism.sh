#!/bin/bash
# Launch ASTERISM (macOS/Linux). First time:  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python -m asterism "$@"
