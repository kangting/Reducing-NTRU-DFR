#!/usr/bin/env bash
# Only CPU controls and scoped PMU opening use sudo; the benchmark stays unprivileged.
set -euo pipefail
PAPER_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PAPER_STUDY="${1:-single-double}"
PAPER_NAME="${2:-}"
PAPER_CPU="${3:-4}"
PAPER_FREQUENCY="${4:-3000000}"
if [[ $# -gt 4 || ! "$PAPER_STUDY" =~ ^(single-double|ntru512|ntru1024|family|q211|levels)$ || ! "$PAPER_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ || ! "$PAPER_CPU" =~ ^[0-9]+$ || ! "$PAPER_FREQUENCY" =~ ^[0-9]+$ ]]; then
    printf '%s\n' 'Usage: bash benchmarks/run_controlled.sh {single-double|ntru512|ntru1024|family|q211|levels} NEW_RUN_NAME [CPU] [FREQUENCY_KHZ]' >&2
    exit 2
fi
if [[ $EUID == 0 ]]; then
    printf '%s\n' 'Run this entrypoint as the ordinary user.' >&2
    exit 2
fi
PAPER_OUTPUT="$PAPER_DIR/local-results/$PAPER_NAME.json.gz"
PAPER_ENVIRONMENT="$PAPER_DIR/local-results/environment-$PAPER_NAME.json"
if [[ -e "$PAPER_OUTPUT" || -e "$PAPER_ENVIRONMENT" || -e "${PAPER_OUTPUT%.gz}.records.jsonl" ]]; then
    printf '%s\n' 'Evidence already exists; choose a fresh run name.' >&2
    exit 2
fi
PAPER_PYTHON=/usr/bin/python3
if [[ ! -x "$PAPER_PYTHON" || "$(stat -Lc '%u' -- "$PAPER_PYTHON")" != 0 ]]; then
    printf '%s\n' 'The system Python interpreter must be executable and root-owned.' >&2
    exit 2
fi
"$PAPER_PYTHON" "$PAPER_DIR/run.py" --study "$PAPER_STUDY" --check
sudo -- "$PAPER_PYTHON" -I "$PAPER_DIR/environment.py" --execute \
    --cpu "$PAPER_CPU" --frequency-khz "$PAPER_FREQUENCY" --out "$PAPER_ENVIRONMENT" -- \
    "$PAPER_PYTHON" "$PAPER_DIR/run.py" --study "$PAPER_STUDY" --cpu "$PAPER_CPU" --out "$PAPER_OUTPUT"
"$PAPER_PYTHON" "$PAPER_DIR/run.py" --out "$PAPER_OUTPUT" --finalize-environment "$PAPER_ENVIRONMENT"
"$PAPER_PYTHON" "$PAPER_DIR/analyze.py" "$PAPER_OUTPUT" --out "$PAPER_DIR/local-results/$PAPER_NAME.csv"
