#!/bin/bash
# Make dist/ASTERISM-<version>-mac.dmg from dist/ASTERISM.app (after pyinstaller).
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python3 -c "import re;print(re.search(r'__version__ = \"([^\"]+)\"', open('asterism/__init__.py').read()).group(1))")
STAGE=$(mktemp -d)
cp -R dist/ASTERISM.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp packaging/README-mac.txt "$STAGE/Read me first.txt"
rm -f "dist/ASTERISM-$VERSION-mac.dmg"
hdiutil create -volname "ASTERISM $VERSION" -srcfolder "$STAGE" -ov -format UDZO "dist/ASTERISM-$VERSION-mac.dmg"
rm -rf "$STAGE"
echo "dist/ASTERISM-$VERSION-mac.dmg"
