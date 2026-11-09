#!/usr/bin/env bash
# Portable entry point. No shell startup files or global Git settings are edited.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${RECOVERY_PYTHON:-python3}" "$HERE/recover.py" "$@"
