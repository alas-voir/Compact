#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

export PYINSTALLER_CONFIG_DIR="$PWD/.pyinstaller"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

if [[ -x ".vnv/bin/python" ]]; then
  PYTHON_BIN=".vnv/bin/python"
else
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m pip install -r requirements.txt pyinstaller
ICON_PATH="assets/icons/Elenveil.icns"
ICON_ARGS=()
if [[ -f "$ICON_PATH" ]]; then
  ICON_ARGS=(--icon "$ICON_PATH")
else
  echo "Warning: icon not found at $ICON_PATH (build will continue without .icns icon)"
fi

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --windowed \
  --name Elenveil \
  --collect-all yt_dlp \
  --add-data "assets:assets" \
  --add-data "bin:bin" \
  "${ICON_ARGS[@]}" \
  app.py

echo "Build complete: dist/Elenveil.app"
