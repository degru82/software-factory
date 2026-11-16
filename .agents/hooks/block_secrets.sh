#!/usr/bin/env bash
# block_secrets Hook 진입점. 판정 로직은 _hookio.py에 있다 (Claude·Cursor 공용).
set -euo pipefail
exec python3 -I "$(dirname "$0")/_hookio.py" block_secrets
