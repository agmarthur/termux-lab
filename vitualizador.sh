#!/usr/bin/env bash
# Abre o Vitualizador (GUI para QEMU).
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m vitualizador "$@"
