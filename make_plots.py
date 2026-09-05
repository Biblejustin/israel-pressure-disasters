#!/usr/bin/env python3
"""Regenerate results/figure.png: timeline of pressure events vs disaster
onsets, plus permutation-null distributions for the headline tests.

Follows the sibling-repo convention (make_plots.py, headless Agg).
"""
import random
import csv
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import analyze as A

# palette (validated: dataviz reference instance, light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
BLUE = "#2a78d6"     # pressure events
GREEN = "#008300"    # pro-Israel events

N_PERM_FIG = 5000
SEED = 20260719


def null_counts(events, onsets, lo, hi, start, end, rng):
    start, end = A.eligible_interval(start, end, lo, hi)
    events = [event for event in events if start <= event <= end]
    period = (end - start).days + 1
    out = []
    for _ in range(N_PERM_FIG):
        fake = A.circ_shift(events, start, period, rng.randrange(period))
        out.append(A.hits(fake, onsets, lo, hi))
    return out


def year_frac(dt):
    return dt.year + (dt.timetuple().tm_yday - 1) / 365.25


def main():
    rng = random.Random(SEED)
    datasets = A.historical_datasets()
    _, noaa, start, noaa_end = datasets[0]
    _, fema, _, fema_end = datasets[1]
    press = A.load_events("us_pressure_events.csv", noaa_end)
    press_f = A.load_events("us_pressure_events.csv", fema_end)
    pro = A.load_events("us_proisrael_events.csv", noaa_end)
    pro_f = A.load_events("us_proisrael_events.csv", fema_end)
    results = list(csv.DictReader(open(A.DATA / "test_results.csv")))
    def ptext(list_name, dataset, window):
        row=next(r for r in results if r['lst']==list_name and r['ds']==dataset and r['w']==window)
        return f"{row['tail']} p={float(row['p']):.3f}; q={float(row['q']):.3f}"

    def near(e, onsets, lo, hi):
        return any((e + timedelta(days=k)) in onsets for k in range(lo, hi + 1))

    fig = plt.figure(figsize=(12.5, 7.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    gs = fig.add_gridspec(2, 4, height_ratios=[1.05, 1.0],
                          hspace=0.42, wspace=0.28,
                          left=0.06, right=0.985, top=0.84, bottom=0.08)

    # ---- Panel A: timeline ----------------------------------------------
    ax = fig.add_subplot(gs[0, :])
    ax.set_facecolor(SURFACE)
    for o in sorted(noaa):
        ax.vlines(year_frac(o), 2.28, 2.72, color=BASE, lw=0.7, zorder=1)
    for evs, y, col in [(press, 1.5, BLUE), (pro, 0.7, GREEN)]:
        for e in evs:
            hit = near(e, noaa, -7, 7)
            ax.plot(year_frac(e), y, "o", ms=7.5,
                    mfc=(col if hit else SURFACE), mec=col,
                    mew=1.4, zorder=3, clip_on=False)
    ax.set_xlim(1990.7, 2026.2)
    ax.set_ylim(0.2, 3.35)
    ax.set_yticks([])
    for label, y, col in [("Billion-dollar disaster onsets (NOAA)", 2.88, MUTED),
                          (f"US pressure on Israel ({len(press)} curated events)", 1.78, BLUE),
                          (f"US pro-Israel actions ({len(pro)} curated events)", 0.98, GREEN)]:
        ax.text(1991.0, y, label, fontsize=9.5, color=col, va="bottom")
    ax.tick_params(axis="x", colors=MUTED, labelsize=9)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.set_title("Curated diplomatic events and disaster onsets, 1991–2024",
                 loc="left", fontsize=11, color=INK, pad=24)
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", mfc=BLUE, mec=BLUE, ms=7,
               label="filled = billion-dollar onset within ±7 days"),
        Line2D([], [], marker="o", ls="", mfc=SURFACE, mec=BLUE, ms=7,
               label="open = none within ±7 days"),
    ], loc="lower right", bbox_to_anchor=(1.0, 1.02), ncol=2, frameon=False,
        fontsize=8.5, labelcolor=INK2, handletextpad=0.2, columnspacing=1.4)

    # ---- Panel B: null distributions vs observed ------------------------
    tests = [
        ("Pressure → NOAA, +7d", press, noaa, 0, 7, start, noaa_end, BLUE,
         ptext("PRESSURE", "NOAA billion-dollar", "+7d")),
        ("Pressure → NOAA, ±3d", press, noaa, -3, 3, start, noaa_end, BLUE,
         ptext("PRESSURE", "NOAA billion-dollar", "±3d")),
        ("Pressure → FEMA, +7d", press_f, fema, 0, 7, start, fema_end, BLUE,
         ptext("PRESSURE", "FEMA declarations", "+7d")),
        ("Pro-Israel → FEMA, +7d", pro_f, fema, 0, 7, start, fema_end, GREEN,
         ptext("PRO-ISRAEL", "FEMA declarations", "+7d")),
    ]
    for i, (title, evs, ons, lo, hi, s0, s1, col, ptxt) in enumerate(tests):
        axb = fig.add_subplot(gs[1, i])
        axb.set_facecolor(SURFACE)
        evs = A.eligible_events(evs, s0, s1, lo, hi)
        obs = A.hits(evs, ons, lo, hi)
        nc = null_counts(evs, ons, lo, hi, s0, s1, rng)
        kmin, kmax = min(nc + [obs]), max(nc + [obs])
        ks = list(range(kmin, kmax + 1))
        freq = [nc.count(k) / len(nc) for k in ks]
        axb.bar(ks, freq, width=0.9, color=GRID, edgecolor=SURFACE,
                linewidth=0.5, zorder=2)
        axb.axvline(obs, color=col, lw=2, zorder=3)
        left_side = obs >= (kmin + kmax) / 2
        axb.annotate(f"observed {obs}/{len(evs)}",
                     xy=(obs, max(freq) * 0.98),
                     xytext=(-5 if left_side else 5, 0),
                     textcoords="offset points", fontsize=8.5, color=col,
                     ha="right" if left_side else "left", va="top")
        axb.set_title(f"{title}\n{ptxt}",
                      loc="left", fontsize=9, color=INK2, pad=6)
        axb.tick_params(colors=MUTED, labelsize=8, length=3)
        for s in ("top", "right", "left"):
            axb.spines[s].set_visible(False)
        axb.spines["bottom"].set_color(BASE)
        axb.set_yticks([])
        if i == 0:
            axb.set_ylabel("share of 5,000 shuffles", fontsize=8.5,
                           color=MUTED)
        axb.set_xlabel("events with a disaster in window", fontsize=8.5,
                       color=MUTED)

    fig.suptitle("US diplomacy and disasters: historical association tests"
                 f" (minimum shift BH q = {min(float(r['q']) for r in results):.3f})",
                 x=0.06, ha="left", fontsize=13.5, color=INK, y=0.965)
    (A.HERE / "figures").mkdir(exist_ok=True)
    out = A.HERE / "figures" / "figure.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
