#!/usr/bin/env bash
set -eu
set -o pipefail

readonly PORT=8000

nohup code serve-web --without-connection-token --accept-server-license-terms --port=$PORT &

nohup sudo tailscale serve --https=$PORT 127.0.0.1:$PORT &
