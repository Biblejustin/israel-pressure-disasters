#!/usr/bin/env python3
"""Permutation test: are US disasters more likely in the days after US
pressure-on-Israel diplomatic events than chance predicts?

Datasets:
  - NOAA billion-dollar weather/climate disasters (onset = Begin Date)
  - FEMA major disaster declarations, natural incident types only
    (onset = incidentBeginDate, deduped by disaster number, collapsed to
    unique onset days)

Test statistic: number of diplomatic events with >=1 disaster onset in
[d, d+W] for windows W. Null: 20,000 circular shifts of the whole
diplomatic-event set across the study period (preserves both the events'
internal spacing and the disaster record's seasonality/clustering).
Robustness: year-shuffle null (keep month/day, randomize year).
Multiple testing: Benjamini-Hochberg FDR across all (list x dataset x
window) tests, matching the correlations-hub convention.

Stdlib only. Deterministic (seeded).
"""
import csv, random, sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
WINDOWS = [("+3d", 0, 3), ("+7d", 0, 7), ("+14d", 0, 14),
           ("±3d", -3, 3), ("±7d", -7, 7)]
N_PERM = 20000
SEED = 20260719

FEMA_EXCLUDE = {"Biological", "Terrorist", "Chemical", "Toxic Substances",
                "Other", "Human Cause", "Fishing Losses"}

def d(s):
    s = s.strip()
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return date.fromisoformat(s[:10])

def load_noaa():
    rows = list(csv.reader(open(DATA / "noaa_billion_dollar_events.csv")))
    hdr = next(i for i, r in enumerate(rows) if r and r[0] == "Name")
    cols = {c: j for j, c in enumerate(rows[hdr])}
    out = []
    for r in rows[hdr + 1:]:
        if len(r) <= cols["Begin Date"] or not r[cols["Begin Date"]].strip():
            continue
        out.append(d(r[cols["Begin Date"]]))
    return sorted(set(out))

def load_fema():
    seen, out = set(), []
    with open(DATA / "fema_declarations.csv") as f:
        for row in csv.DictReader(f):
            num = row["disasterNumber"]
            if num in seen or row["incidentType"] in FEMA_EXCLUDE:
                continue
            seen.add(num)
            out.append(d(row["incidentBeginDate"]))
    return sorted(set(out))

def load_events(name, end_cap):
    out = []
    with open(DATA / name) as f:
        for row in csv.DictReader(f):
            dt = d(row["date"])
            if dt <= end_cap:
                out.append(dt)
    return out

def hits(event_dates, onset_set, lo, hi):
    n = 0
    for e in event_dates:
        if any((e + timedelta(days=k)) in onset_set for k in range(lo, hi + 1)):
            n += 1
    return n

def circ_shift(event_dates, start, period, offset):
    out = []
    for e in event_dates:
        k = ((e - start).days + offset) % period
        out.append(start + timedelta(days=k))
    return out

def year_shuffle(event_dates, rng, y0, y1):
    out = []
    for e in event_dates:
        y = rng.randint(y0, y1)
        try:
            out.append(date(y, e.month, e.day))
        except ValueError:                       # Feb 29
            out.append(date(y, e.month, 28))
    return out

def perm_p(event_dates, onset_set, lo, hi, start, end, rng, mode):
    period = (end - start).days
    obs = hits(event_dates, onset_set, lo, hi)
    ge = 0
    for _ in range(N_PERM):
        if mode == "shift":
            fake = circ_shift(event_dates, start, period, rng.randint(1, period - 1))
        else:
            fake = year_shuffle(event_dates, rng, start.year, end.year - 1)
        if hits(fake, onset_set, lo, hi) >= obs:
            ge += 1
    return obs, (ge + 1) / (N_PERM + 1)

def bh_fdr(pvals):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank_from_end, i in enumerate(reversed(order)):
        rank = m - rank_from_end
        prev = min(prev, pvals[i] * m / rank)
        q[i] = prev
    return q

def base_rate(onset_set, lo, hi, start, end):
    n_days = (end - start).days
    covered = sum(
        1 for k in range(n_days)
        if any((start + timedelta(days=k + j)) in onset_set for j in range(lo, hi + 1))
    )
    return covered / n_days

def main():
    rng = random.Random(SEED)
    noaa = load_noaa()
    fema = load_fema()
    noaa_end = max(noaa)
    fema_end = max(fema)
    start = date(1991, 1, 1)
    datasets = [
        ("NOAA billion-dollar", set(x for x in noaa if x >= start), min(noaa_end, date(2024, 12, 31))),
        ("FEMA declarations", set(x for x in fema if x >= start), min(fema_end, date(2025, 12, 31))),
    ]
    print(f"NOAA onsets since 1991: {sum(1 for x in noaa if x >= start)} (through {noaa_end})")
    print(f"FEMA unique natural-disaster onset days since 1991: {sum(1 for x in fema if x >= start)} (through {fema_end})")

    tests = []
    for list_name, fname in [("PRESSURE", "us_pressure_events.csv"),
                             ("PRO-ISRAEL", "us_proisrael_events.csv")]:
        for ds_name, onsets, end in datasets:
            events = load_events(fname, end)
            for wlab, lo, hi in WINDOWS:
                obs, p = perm_p(events, onsets, lo, hi, start, end, rng, "shift")
                _, p_ys = perm_p(events, onsets, lo, hi, start, end, rng, "yshuf")
                br = base_rate(onsets, lo, hi, start, end)
                tests.append(dict(lst=list_name, ds=ds_name, w=wlab, n=len(events),
                                  obs=obs, exp=br * len(events), p=p, p_ys=p_ys))

    qs = bh_fdr([t["p"] for t in tests])
    for t, q in zip(tests, qs):
        t["q"] = q

    print(f"\n{'list':<11}{'dataset':<22}{'win':>4}{'hits':>7}{'expected':>10}"
          f"{'p(shift)':>10}{'p(yshuf)':>10}{'q(FDR)':>9}")
    for t in tests:
        print(f"{t['lst']:<11}{t['ds']:<22}{t['w']:>4}"
              f"{t['obs']:>4}/{t['n']:<3}{t['exp']:>9.1f}"
              f"{t['p']:>10.4f}{t['p_ys']:>10.4f}{t['q']:>9.4f}")

    # Transparency: per-event nearest NOAA onset for the pressure list
    print("\nPer-event nearest NOAA billion-dollar onset (pressure list, days after event):")
    onsets = sorted(datasets[0][1])
    for e in load_events("us_pressure_events.csv", datasets[0][2]):
        after = [(o - e).days for o in onsets if 0 <= (o - e).days]
        print(f"  {e}  next onset in {min(after) if after else 'n/a':>4} days")

if __name__ == "__main__":
    main()
