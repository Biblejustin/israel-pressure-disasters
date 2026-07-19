# israel-pressure-disasters

Statistical test of the Koenig/McTernan claim (*Eye to Eye: Facing the
Consequences of Dividing Israel*) that US disasters follow US diplomatic
pressure on Israel within days.

## Design

The claim's published form is an anthology of hits with no denominator. This
test supplies both denominators:

1. **A neutral diplomatic event list** ([data/us_pressure_events.csv](data/us_pressure_events.csv)),
   compiled from the documented diplomatic record **before consulting any
   disaster data**. Inclusion criteria, 1991-2024:
   - (a) US-convened or US-brokered negotiation milestones premised on Israeli
     territorial concession;
   - (b) public US demands, proposals, or speeches calling for Israeli
     territorial concession or settlement halt;
   - (c) UNSC actions where the US supported or declined to veto such measures;
   - (d) material pressure (loan-guarantee or arms conditioning, ceasefire
     ultimatums).

   Every event Koenig's ecosystem claims as a "hit" that meets these criteria
   is included (flagged `koenig_claimed=1`), alongside the comparable events
   his anthology omits.
2. **Complete disaster records**, two severity tiers:
   - NOAA billion-dollar weather/climate disasters (onset = Begin Date;
     note: excludes earthquakes by design, coverage through 2024);
   - FEMA major disaster declarations, natural incident types only, deduped
     to unique incident-onset days.

**Controls:** a pro-Israel action list ([data/us_proisrael_events.csv](data/us_proisrael_events.csv))
run through the identical test (the thesis predicts a deficit there), plus
[data/koenig_claimed_pairs.csv](data/koenig_claimed_pairs.csv), which documents
the anthology's own pairs with notes on category elasticity (non-disasters like
the Lewinsky story and the Lehman collapse; disasters that began *before* their
claimed trigger; flagship storms below the billion-dollar threshold).

**Test:** for windows +3/+7/+14 days after each event (and ±3/±7 symmetric,
since several claimed pairs have the disaster preceding the action), count
events with at least one disaster onset in window. Null distribution: 20,000
circular shifts of the whole event list across 1991-present (preserves event
spacing and disaster seasonality/clustering); robustness null: year-shuffle
keeping month/day. Benjamini-Hochberg FDR across all 20 tests, matching the
`../correlations` convention.

## Result (run 2026-07-19)

**No test survives FDR correction (min q = 0.17).** Full table in
[results/run_2026-07-19.txt](results/run_2026-07-19.txt).

- At the billion-dollar tier, where the claim's flagship disasters live,
  pressure events are followed by disasters at almost exactly the chance rate
  (e.g. +7d: 7 hits observed, 7.9 expected, p = 0.69).
- The single suggestive cell is FEMA declarations at +7d (27/37 observed vs
  19.4 expected, raw p = 0.010) but it does not survive correction
  (q = 0.17), does not replicate at the severity tier the claim is actually
  about, and FEMA-declaration onsets are so frequent (~41 onset-days/year)
  that 52% of *all* weeks contain one.
- The pro-Israel control shows no significant blessing-deficit either
  (4/12 vs 6.3 expected at +7d, p = 0.94; n = 12 is underpowered).

Interpretation: the anthology's famous pairings are genuine coincidences of
timing, but the *rate* of such pairings is indistinguishable from what a
dartboard produces once every pressure event is counted instead of only the
memorable ones.

## Rerun

```
bash update.sh        # guarded NOAA/FEMA refresh -> analyze -> figure
python3 analyze.py    # analysis only (stdlib, deterministic/seeded)
```

Latest results: [data/latest_run.txt](data/latest_run.txt) and
[figures/figure.png](figures/figure.png); the 2026-07-19 baseline run is
archived in `results/`.

This repo is part of the signs-tracking family: the VPS `signs-update.timer`
runs `correlations/weekly_update.sh` weekly, which fetches, re-tests,
regenerates the figure, and commits data deltas here automatically. Append
post-2024 diplomatic events to the CSVs by hand as they occur (e.g. the
2025-26 peace-plan milestones); the update never edits the curated lists.
