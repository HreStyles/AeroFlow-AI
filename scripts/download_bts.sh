#!/usr/bin/env bash
# Download BTS On-Time Performance data (Reporting Carrier On-Time Performance)
# from transtats.bts.gov for the given year/months.
#
# Usage:  ./scripts/download_bts.sh [YEAR] [MONTHS...]
# Example: ./scripts/download_bts.sh 2024 1 2 3
# Default: 2024, months 1-6
set -euo pipefail

YEAR="${1:-2024}"
shift || true
MONTHS=("$@")
if [ ${#MONTHS[@]} -eq 0 ]; then
  MONTHS=(1 2 3 4 5 6)
fi

DEST="$(cd "$(dirname "$0")/.." && pwd)/backend/data/raw/bts"
mkdir -p "$DEST"

BASE="https://transtats.bts.gov/PREZIP"

for MONTH in "${MONTHS[@]}"; do
  FILE="On_Time_Reporting_Carrier_On_Time_Performance_1987_present_${YEAR}_${MONTH}.zip"
  OUT="$DEST/$FILE"
  if [ -f "$OUT" ]; then
    echo "✓ already have $FILE"
    continue
  fi
  echo "↓ downloading $FILE …"
  # transtats serves a legacy TLS config; --insecure is commonly required
  curl -fL --retry 3 --insecure -o "$OUT" "$BASE/$FILE"
  echo "  unzipping…"
  unzip -o -d "$DEST" "$OUT" "*.csv"
done

echo
echo "Done. CSVs in $DEST"
echo "Next: ./scripts/download_noaa.sh, then backend/.venv/bin/python scripts/train_all.py"
