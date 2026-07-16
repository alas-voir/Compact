#!/bin/zsh
set -euo pipefail
unalias rm 2>/dev/null || true

cd "$(dirname "$0")"

export PYINSTALLER_CONFIG_DIR="$PWD/.pyinstaller"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

APP_NAME="Compact"
DMG_NAME="${APP_NAME}.dmg"
DMG_STAGING_DIR="$PWD/build/dmg"
APP_BUNDLE_PATH="$PWD/dist/${APP_NAME}.app"
DMG_PATH="$PWD/dist/${DMG_NAME}"

if [[ -x ".vnv/bin/python" ]]; then
  PYTHON_BIN=".vnv/bin/python"
else
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m pip install -r requirements.txt pyinstaller
/bin/rm -rf -- build dist

"$PYTHON_BIN" -m PyInstaller \
  --clean \
  --noconfirm \
  Compact.spec

mkdir -p "$DMG_STAGING_DIR"
/bin/rm -rf -- "$DMG_STAGING_DIR"
mkdir -p "$DMG_STAGING_DIR"
cp -R "$APP_BUNDLE_PATH" "$DMG_STAGING_DIR/"
ln -s /Applications "$DMG_STAGING_DIR/Applications"
/bin/rm -f -- "$DMG_PATH"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$DMG_STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Build complete: dist/${APP_NAME}.app"
echo "DMG complete: dist/${DMG_NAME}"
