#!/bin/bash
# Double-click in Finder to launch ASTERISM.
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python -m asterism
