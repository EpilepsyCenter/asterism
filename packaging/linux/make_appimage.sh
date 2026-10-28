#!/bin/bash
# Make dist/ASTERISM-<version>-linux-x86_64.AppImage from dist/ASTERISM (after pyinstaller).
# Needs appimagetool on PATH (the release workflow downloads it).
set -euo pipefail
cd "$(dirname "$0")/../.."
VERSION=$(python3 -c "import re;print(re.search(r'__version__ = \"([^\"]+)\"', open('asterism/__init__.py').read()).group(1))")
APPDIR=$(mktemp -d)/ASTERISM.AppDir
mkdir -p "$APPDIR/usr/lib/asterism" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/512x512/apps"
cp -R dist/ASTERISM/. "$APPDIR/usr/lib/asterism/"
cp packaging/linux/AppRun "$APPDIR/AppRun"
cp packaging/linux/asterism.desktop "$APPDIR/asterism.desktop"
cp packaging/linux/asterism.desktop "$APPDIR/usr/share/applications/"
cp asterism/app/assets/asterism.png "$APPDIR/asterism.png"
cp asterism/app/assets/asterism.png "$APPDIR/usr/share/icons/hicolor/512x512/apps/asterism.png"
ARCH=x86_64 appimagetool "$APPDIR" "dist/ASTERISM-$VERSION-linux-x86_64.AppImage"
echo "dist/ASTERISM-$VERSION-linux-x86_64.AppImage"
