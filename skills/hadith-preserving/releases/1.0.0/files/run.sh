#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 INPUT.txt|INPUT_DIR OUTPUT.docx [extra options]" >&2
  exit 2
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT="$1"
OUTPUT="$2"
shift 2
if [[ -d "$INPUT" ]]; then
  python "$SCRIPT_DIR/scripts/format_hadith_batch.py" "$INPUT" "$OUTPUT" "$@"
else
  python "$SCRIPT_DIR/scripts/format_hadith.py" "$INPUT" "$OUTPUT" "$@"
fi
