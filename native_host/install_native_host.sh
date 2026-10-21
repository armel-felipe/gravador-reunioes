#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXTENSION_ID="${EXTENSION_ID:-}"
USER_HOME="${HOME:?HOME não definido}"
HOST_NAME="com.armel.gravador.server"
TARGET_DIR="${NATIVE_MESSAGING_DIR:-$USER_HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts}"
HOST_PATH="$ROOT_DIR/native_host/native_host.sh"
MANIFEST_PATH="$TARGET_DIR/$HOST_NAME.json"

if [[ ! "$EXTENSION_ID" =~ ^[a-p]{32}$ ]]; then
  echo "Use EXTENSION_ID com o ID de 32 letras em chrome://extensions." >&2
  exit 1
fi

chmod +x "$HOST_PATH"
mkdir -p "$TARGET_DIR"
TEMP_MANIFEST="$(mktemp "$TARGET_DIR/.$HOST_NAME.XXXXXX")"
trap 'rm -f "$TEMP_MANIFEST"' EXIT

printf '%s\n' \
  '{' \
  "  \"name\": \"$HOST_NAME\"," \
  '  "description": "Controle local do servidor do Gravador de Reuniões",' \
  '  "path": "'"$HOST_PATH"'",' \
  '  "type": "stdio",' \
  '  "allowed_origins": ["chrome-extension://'"$EXTENSION_ID"'/"]' \
  '}' > "$TEMP_MANIFEST"

mv "$TEMP_MANIFEST" "$MANIFEST_PATH"
trap - EXIT
echo "Host instalado em: $MANIFEST_PATH"
echo "Recarregue a extensão no chrome://extensions."
