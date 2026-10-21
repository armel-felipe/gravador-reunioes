#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec /usr/bin/env python3 "$ROOT_DIR/native_host/server_control.py"
