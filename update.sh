#!/bin/bash
# Refresh disaster data, rerun the permutation test, regenerate the figure.
# Guarded fetches: a failed or truncated download never clobbers good data.
# Diplomatic event lists are hand-curated and never touched by this script.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HERE/../venv/bin/python"
[ -x "$PY" ] || PY=python3
export MPLBACKEND=Agg

echo "==> israel-pressure-disasters refresh $(date '+%Y-%m-%d %H:%M')"

TMP=$(mktemp)
if curl -sL --max-time 120 \
    "https://www.ncei.noaa.gov/access/billions/events-US-1980-2025.csv" \
    -o "$TMP" && grep -q "Billion-Dollar" "$TMP" \
    && [ "$(wc -l < "$TMP")" -gt 300 ]; then
    mv "$TMP" "$HERE/data/noaa_billion_dollar_events.csv"
    echo "    NOAA ok ($(wc -l < "$HERE/data/noaa_billion_dollar_events.csv") lines)"
else
    rm -f "$TMP"; echo "    ! NOAA fetch failed, keeping existing data"
fi

TMP=$(mktemp)
if curl -sL --max-time 300 \
    "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?\$filter=declarationType%20eq%20%27DR%27%20and%20incidentBeginDate%20ge%20%271991-01-01T00:00:00.000Z%27&\$select=disasterNumber,state,incidentType,declarationTitle,incidentBeginDate,declarationDate&\$allrecords=true&\$format=csv" \
    -o "$TMP" && [ "$(wc -l < "$TMP")" -gt 30000 ]; then
    mv "$TMP" "$HERE/data/fema_declarations.csv"
    echo "    FEMA ok ($(wc -l < "$HERE/data/fema_declarations.csv") lines)"
else
    rm -f "$TMP"; echo "    ! FEMA fetch failed, keeping existing data"
fi

cd "$HERE"
"$PY" analyze.py > data/latest_run.txt 2>&1 \
    && echo "    analysis ok ($(grep -c . data/latest_run.txt) lines)" \
    || echo "    ! analyze.py failed, see data/latest_run.txt"
"$PY" make_plots.py && echo "    figure ok" || echo "    ! make_plots.py failed"
