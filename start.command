#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"
source ./.vnv/bin/activate && python3 app.py
