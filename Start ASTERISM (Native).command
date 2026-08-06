#!/bin/bash
# Double-click to launch ASTERISM in a native desktop window (macOS).
cd "$(dirname "$0")" || exit 1
exec python3 -m asterism_dash.desktop
