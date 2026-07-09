#!/usr/bin/env bash
# Download historical METAR observations for ATL and JFK from the Iowa
# Environmental Mesonet (IEM) ASOS archive.
#
# Usage:  ./scripts/download_noaa.sh [START_DATE] [END_DATE]
# Dates in YYYY-MM-DD. Default: 2024-01-01 to 2024-07-01
set -euo pipefail

START="${1:-2024-01-01}"
END="${2:-2024-07-01}"

DEST="$(cd "$(dirname "$0")/.." && pwd)/backend/data/raw/noaa"
mkdir -p "$DEST"

BASE="https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

Y1=$(echo "$START" | cut -d- -f1); M1=$(echo "$START" | cut -d- -f2); D1=$(echo "$START" | cut -d- -f3)
Y2=$(echo "$END"   | cut -d- -f1); M2=$(echo "$END"   | cut -d- -f2); D2=$(echo "$END"   | cut -d- -f3)

for STATION in ATL JFK; do
  OUT="$DEST/metar_${STATION}_${START}_${END}.csv"
  if [ -f "$OUT" ]; then
    echo "✓ already have $(basename "$OUT")"
    continue
  fi
  echo "↓ downloading METAR for $STATION ($START → $END)…"
  curl -fL --retry 3 -o "$OUT" \
    "$BASE?station=${STATION}&data=vsby&data=sknt&data=skyl1&data=p01i&data=wxcodes&year1=${Y1}&month1=${M1}&day1=${D1}&year2=${Y2}&month2=${M2}&day2=${D2}&tz=America%2FNew_York&format=onlycomma&latlon=no&elev=no&missing=M&trace=T&direct=yes&report_type=3"
done

echo
echo "Done. CSVs in $DEST"
echo "Next: backend/.venv/bin/python scripts/train_all.py"
