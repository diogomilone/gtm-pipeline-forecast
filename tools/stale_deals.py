"""Added later, not written down before it was run (method page): how old are the deals dated outside each quarter?

Tenders have no lost stage. One with no published award and no cancellation stays in the pipeline, awaiting an award,
for good. This counts, at each of the 8 quarter starts, the deals dated outside the quarter by how long they had sat at
their stage (the same age groups as the time-in-stage forecast), how many were won in the quarter (every award known)
and how many were ever won. It reads the shipped opportunity table only and writes results/stale-deals.json.

Usage: python3 -B tools/stale_deals.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402

ROOT = P.ROOT
FAR = 10 ** 7


def main():
    rows = P.load()
    summary = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
    out = {"what": "deals dated outside the quarter, by stage and days at that stage, at each quarter start",
           "bands": [P.band_label(b) for b in range(len(P.BANDS))], "quarters": []}
    for snap in summary["snapshots"]:
        s = P.day(snap["snapshot"])
        e = P.quarter_start(s, 1)
        groups = {}
        for o, st, d in P.pipeline(rows, s):
            if P.in_window(o, s, e):
                continue
            g = groups.setdefault(f"{st}:{P.band_label(P.band(d))}", {"deals": 0, "won_in_quarter": 0, "ever_won": 0})
            g["deals"] += 1
            g["won_in_quarter"] += int(P.won_in(o, s, e, FAR))
            g["ever_won"] += int(o["won_at"] is not None and o["won_at"] >= s)
        deals = sum(g["deals"] for g in groups.values())
        wins = sum(g["won_in_quarter"] for g in groups.values())
        over_year = {k: sum(g[k] for n, g in groups.items() if n.startswith("await:") and n.endswith("366+"))
                     for k in ("deals", "won_in_quarter", "ever_won")}
        out["quarters"].append({"snapshot": snap["snapshot"], "deals": deals, "won_in_quarter": wins,
                                "await_over_a_year": over_year, "groups": dict(sorted(groups.items()))})
        print(snap["snapshot"], deals, wins, json.dumps(over_year))
    (ROOT / "results" / "stale-deals.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
