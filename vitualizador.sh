#!/usr/bin/env bash
# Abre o Termux Lab (GUI para QEMU).
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 não encontrado. Instale com: sudo apt install python3" >&2
    exit 1
fi

if ! python3 -c "import PyQt6" >/dev/null 2>&1; then
    echo "PyQt6 não encontrado. Instale com: sudo apt install python3-pyqt6" >&2
    exit 1
fi

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo "Sem sessão gráfica (DISPLAY/WAYLAND_DISPLAY vazios)." >&2
    echo "Abra pelo menu de aplicativos ou rode dentro do terminal do desktop." >&2
    exit 1
fi

exec python3 -m vitualizador "$@"
