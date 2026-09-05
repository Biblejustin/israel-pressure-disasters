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
import csv, random, sys, json, hashlib
from datetime import datetime, timezone
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
    with open(DATA / "noaa_billion_dollar_events.csv") as handle:
        rows = list(csv.reader(handle))
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

def eligible_interval(start, end, lo, hi):
    """Inclusive candidate event dates with fully observed response windows."""
    return start - timedelta(days=min(lo, 0)), end - timedelta(days=max(hi, 0))


def eligible_events(events, start, end, lo, hi):
    first, last = eligible_interval(start, end, lo, hi)
    return [event for event in events if first <= event <= last]


def hit_days(onset_set, lo, hi, start, end):
    return {onset-timedelta(days=k) for onset in onset_set for k in range(lo,hi+1)
            if start <= onset-timedelta(days=k) <= end}


def perm_p(event_dates, onset_set, lo, hi, start, end, rng, mode, tail="upper"):
    if tail not in {"upper", "lower"}:
        raise ValueError("Hypothesis tail must be upper or lower")
    first, last = eligible_interval(start, end, lo, hi)
    event_dates = eligible_events(event_dates, start, end, lo, hi)
    period = (last-first).days+1
    if period < 2 or not event_dates:
        raise ValueError("Insufficient fully observed exposure")
    possible = hit_days(onset_set, lo, hi, first, last)
    hit_offsets = {(day-first).days for day in possible}
    event_offsets = [(day-first).days for day in event_dates]
    obs = sum(day in possible for day in event_dates)
    extreme = 0
    # Each candidate year must keep the whole window inside coverage.
    year_options = []
    for event in event_dates:
        options=[]
        for year in range(first.year, last.year+1):
            try: candidate=date(year,event.month,event.day)
            except ValueError: candidate=date(year,event.month,28)
            if first <= candidate <= last: options.append(candidate)
        year_options.append(options)
    for _ in range(N_PERM):
        if mode == "shift":
            offset=rng.randrange(period)  # identity included in uniform null
            sim=sum((event+offset)%period in hit_offsets for event in event_offsets)
        elif mode == "yshuf":
            sim=sum(rng.choice(options) in possible for options in year_options)
        else:
            raise ValueError("Unknown null mode")
        extreme += (sim >= obs) if tail == "upper" else (sim <= obs)
    return obs, (extreme+1)/(N_PERM+1)

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
    first,last=eligible_interval(start,end,lo,hi)
    return len(hit_days(onset_set,lo,hi,first,last))/((last-first).days+1)


def coverage():
    return json.loads((DATA / "coverage.json").read_text())


def historical_datasets():
    meta=coverage()
    start=d(meta["study_start"])
    end=d(meta["study_end"])
    out=[]
    for key,label,loader in [("noaa","NOAA billion-dollar",load_noaa),("fema","FEMA declarations",load_fema)]:
        first=max(start,d(meta[key]["start"]))
        last=min(end,d(meta[key]["end"]))
        out.append((label,set(day for day in loader() if first<=day<=last),first,last))
    return out

def main():
    rng = random.Random(SEED)
    meta=coverage()
    datasets=historical_datasets()
    print(f"Frozen historical study: {meta['study_start']} through {meta['study_end']} (inclusive)")
    print("Pressure hypothesis: upper tail; pro-Israel deficit hypothesis: lower tail.")
    print("Only complete response windows; missing exposure excluded from events AND null.")
    print(f"Curation: {meta['curation_status']}")

    tests = []
    for list_name, fname in [("PRESSURE", "us_pressure_events.csv"),
                             ("PRO-ISRAEL", "us_proisrael_events.csv")]:
        for ds_name, onsets, start, end in datasets:
            events = load_events(fname, end)
            for wlab, lo, hi in WINDOWS:
                selected = eligible_events(events, start, end, lo, hi)
                tail = meta["tails"][list_name]
                obs, p = perm_p(selected, onsets, lo, hi, start, end, rng, "shift", tail)
                _, p_ys = perm_p(selected, onsets, lo, hi, start, end, rng, "yshuf", tail)
                br = base_rate(onsets, lo, hi, start, end)
                tests.append(dict(lst=list_name, ds=ds_name, w=wlab, tail=tail, n=len(selected), excluded=len(events)-len(selected),
                                  start=start.isoformat(), end=end.isoformat(),
                                  obs=obs, exp=br * len(selected), p=p, p_ys=p_ys))

    qs = bh_fdr([t["p"] for t in tests])
    for t, q, q_ys in zip(tests, qs, bh_fdr([t["p_ys"] for t in tests])):
        t["q"], t["q_ys"] = q, q_ys
    with open(DATA / "test_results.csv", "w") as handle:
        writer=csv.DictWriter(handle, fieldnames=list(tests[0]))
        writer.writeheader(); writer.writerows(tests)
    manifest={"generated_at":datetime.now(timezone.utc).isoformat(), "design":meta, "tests":len(tests), "permutations":N_PERM, "seed":SEED,
              "input_sha256":{name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in ["coverage.json","noaa_billion_dollar_events.csv","fema_declarations.csv","us_pressure_events.csv","us_proisrael_events.csv"]}}
    (DATA/"analysis_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")

    print(f"\n{'list':<11}{'dataset':<22}{'win':>4}{'hits':>7}{'expected':>10}"
          f"{'p(shift)':>10}{'p(yshuf)':>10}{'q(FDR)':>9}")
    for t in tests:
        print(f"{t['lst']:<11}{t['ds']:<22}{t['w']:>4}"
              f"{t['obs']:>4}/{t['n']:<3}{t['exp']:>9.1f}"
              f"{t['p']:>10.4f}{t['p_ys']:>10.4f}{t['q']:>9.4f}")

    # Transparency: per-event nearest NOAA onset for the pressure list
    print("\nPer-event nearest NOAA billion-dollar onset (pressure list, days after event):")
    onsets = sorted(datasets[0][1])
    for e in load_events("us_pressure_events.csv", datasets[0][3]):
        after = [(o - e).days for o in onsets if 0 <= (o - e).days]
        print(f"  {e}  next onset in {min(after) if after else 'n/a':>4} days")

if __name__ == "__main__":
    main()
