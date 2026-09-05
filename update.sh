#!/bin/bash
# Stage fetched inputs and analyses together. Failures preserve published files.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-$HERE/../venv/bin/python}"
[ -x "$PY" ] || PY=python3
export MPLBACKEND=Agg
STAGE="$(mktemp -d "$HERE/.refresh.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/data" "$STAGE/figures"
cp "$HERE/analyze.py" "$HERE/make_plots.py" "$STAGE/"
cp -R "$HERE/data/." "$STAGE/data/"

echo "==> israel-pressure-disasters refresh $(date '+%Y-%m-%d %H:%M')"
if ! curl --fail --silent --show-error --location --max-time 120 \
    "https://www.ncei.noaa.gov/access/billions/events-US-1980-2025.csv" \
    -o "$STAGE/data/noaa_billion_dollar_events.csv"; then
    echo "ERROR: NOAA fetch failed; existing data and results preserved" >&2
    exit 1
fi
if ! curl --fail --silent --show-error --location --max-time 300 \
    "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?\$filter=declarationType%20eq%20%27DR%27%20and%20incidentBeginDate%20ge%20%271991-01-01T00:00:00.000Z%27&\$select=disasterNumber,state,incidentType,declarationTitle,incidentBeginDate,declarationDate&\$allrecords=true&\$format=csv" \
    -o "$STAGE/data/fema_declarations.csv"; then
    echo "ERROR: FEMA fetch failed; existing data and results preserved" >&2
    exit 1
fi

# Validate schema and truncation guards before running against either download.
"$PY" - "$STAGE/data" <<'PY'
import csv
from pathlib import Path
import sys
folder = Path(sys.argv[1])
noaa = list(csv.reader((folder/'noaa_billion_dollar_events.csv').open()))
headers = [row for row in noaa if row and row[0] == 'Name']
if len(noaa) <= 300 or not headers or not {'Name','Begin Date'}.issubset(headers[0]):
    raise SystemExit('ERROR: NOAA response failed schema/size guard; existing files preserved')
with (folder/'fema_declarations.csv').open() as handle:
    reader = csv.DictReader(handle)
    if not {'disasterNumber','incidentType','incidentBeginDate'}.issubset(reader.fieldnames or []):
        raise SystemExit('ERROR: FEMA response missing required columns; existing files preserved')
    if sum(1 for _ in reader) <= 30000:
        raise SystemExit('ERROR: FEMA response failed size guard; existing files preserved')
PY

if ! (cd "$STAGE" && "$PY" analyze.py > data/latest_run.txt 2>&1); then
    cat "$STAGE/data/latest_run.txt" >&2
    echo "ERROR: analysis failed; existing data and results preserved" >&2
    exit 1
fi
if ! (cd "$STAGE" && "$PY" make_plots.py); then
    echo "ERROR: figure generation failed; existing data and results preserved" >&2
    exit 1
fi

# Promote only generated inputs/results after both computations passed. Staging
# lives on the same filesystem, so each changed file replaces its target atomically.
for relative in data/noaa_billion_dollar_events.csv data/fema_declarations.csv \
    data/test_results.csv data/analysis_manifest.json data/latest_run.txt figures/figure.png; do
    if [ ! -f "$STAGE/$relative" ]; then
        echo "ERROR: expected output missing: $relative; promotion stopped" >&2
        exit 1
    fi
done
for relative in data/noaa_billion_dollar_events.csv data/fema_declarations.csv \
    data/test_results.csv data/analysis_manifest.json data/latest_run.txt figures/figure.png; do
    if ! cmp -s "$STAGE/$relative" "$HERE/$relative"; then
        mkdir -p "$(dirname "$HERE/$relative")"
        mv "$STAGE/$relative" "$HERE/$relative"
    fi
done
echo "Refresh passed; fetched data, analysis and figure promoted"
