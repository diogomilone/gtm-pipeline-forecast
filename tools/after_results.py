"""The analyses added after the results (CHANGES-r1.md): where the wins come from, the late-recording correction,
intervals from past misses and the capacity plan. Writes results/after.json. Usage: python3 -B tools/after_results.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402

ROOT = P.ROOT
PROTO = json.loads((ROOT / "protocol-r1.json").read_text(encoding="utf-8"))
S_ = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
AS = json.loads((ROOT / "assumptions.json").read_text(encoding="utf-8"))
FAR = 10 ** 7


def r(x, d=2):
    return None if x is None else round(x, d)


def completeness_fn(rows, s):
    """F(x): share of wins awarded 365 to 730 days before s (published before s) whose publication came under x days"""
    lags = sorted(o["won_known_at"] - o["won_at"] for o in rows
                  if o["won_at"] is not None and s - 730 <= o["won_at"] < s - 365
                  and o["won_known_at"] is not None and o["won_known_at"] < s)
    n = len(lags)
    import bisect

    def F(x):
        return bisect.bisect_left(lags, x) / n
    return F, n


def quarter_completeness(F, s, h):
    he = P.quarter_start(h, 1)
    vals = [F(s - t) for t in range(h, he)]
    return sum(vals) / len(vals)


def main():
    rows = P.load()
    snaps = PROTO["snapshots_scored"]
    out = {"where_wins_come_from": [], "stage_calibration": [], "corrected": [], "completeness": []}
    cache = {}
    for sname in snaps:
        s = P.day(sname)
        e = P.quarter_start(s, 1)
        pipe = P.pipeline(rows, s)
        split = {"inside": 0, "past_due": 0, "later": 0, "no_date": 0}
        for o, st, d in pipe:
            if not P.won_in(o, s, e, FAR):
                continue
            x = P.expected_close(o)
            k = "no_date" if x is None else "inside" if s <= x < e else "past_due" if x < s else "later"
            split[k] += 1
        tot = sum(split.values())
        out["where_wins_come_from"].append({"snapshot": sname, **split, "total": tot,
                                            "inside_pct": r(100 * split["inside"] / tot, 1)})
        cal = {}
        for stg in ("open", "await"):
            for inw in (True, False):
                grp = [o for o, st, d in pipe if st == stg and P.in_window(o, s, e) == inw]
                if not grp:
                    continue
                cal[f"{stg}:{'dated_in_quarter' if inw else 'not_dated_in_quarter'}"] = {
                    "deals": len(grp),
                    "won_in_quarter_pct": r(100 * sum(P.won_in(o, s, e, FAR) for o in grp) / len(grp), 1),
                    "ever_won_pct": r(100 * sum(1 for o in grp if o["won_at"] is not None and o["won_at"] >= s) / len(grp), 1)}
        out["stage_calibration"].append({"snapshot": sname, **cal})
        F, n = completeness_fn(rows, s)
        comp = {P.iso(P.quarter_start(s, -k)): quarter_completeness(F, s, P.quarter_start(s, -k)) for k in range(1, 5)}
        out["completeness"].append({"snapshot": sname, "reference_wins": n, **{k: r(v, 3) for k, v in comp.items()}})
        f = P.forecast_all(rows, s, cache=cache, label_weight=lambda h: 1.0 / comp[P.iso(h)])
        a = S_["snapshots"][snaps.index(sname)]["actual"]["pipeline_wins"]
        rec = {"snapshot": sname, "actual": a}
        for arm in ("time_in_stage", "run_rate"):
            sc = P.score(f[arm]["forecast"], a)
            rec[arm] = {"forecast": r(f[arm]["forecast"]), **{k: r(v) for k, v in sc.items()}}
        out["corrected"].append(rec)
        print(sname, out["where_wins_come_from"][-1]["inside_pct"], {k: rec[k]["pct_error"] for k in ("time_in_stage", "run_rate")}, n)

    def agg(recs):
        return {"mape": r(sum(x["abs_pct_error"] for x in recs) / len(recs)),
                "bias_pct": r(sum(x["pct_error"] for x in recs) / len(recs)),
                "worst_abs_pct": r(max(x["abs_pct_error"] for x in recs))}
    main = PROTO["main_snapshot"]
    out["corrected_backtest"] = {arm: {"all8": agg([c[arm] for c in out["corrected"]]),
                                       "earlier7": agg([c[arm] for c in out["corrected"] if c["snapshot"] != main])}
                                 for arm in ("time_in_stage", "run_rate")}
    # intervals from past misses, rolling, at least 3 earlier quarters
    series = {"fixed": [p["arms"]["fixed"] for p in S_["snapshots"]],
              "time_in_stage_corrected": [c["time_in_stage"] for c in out["corrected"]]}
    ints = {}
    for arm, recs in series.items():
        rows_i = []
        for i in range(3, len(recs)):
            past = [x["pct_error"] for x in recs[:i]]
            lo_e, hi_e = P.quantile(past, 0.1), P.quantile(past, 0.9)
            # forecast = actual * (1 + e/100), so actual = forecast / (1 + e/100)
            fc, act = recs[i]["forecast"], S_["snapshots"][i]["actual"]["pipeline_wins"]
            lo, hi = fc / (1 + hi_e / 100), fc / (1 + lo_e / 100)
            rows_i.append({"snapshot": snaps[i], "forecast": fc, "lo80": r(lo, 1), "hi80": r(hi, 1), "actual": act,
                           "covered": lo <= act <= hi})
        ints[arm] = {"quarters": rows_i, "covered": sum(x["covered"] for x in rows_i), "of": len(rows_i)}
    out["intervals_from_past_misses"] = ints
    # capacity plan for the main quarter
    m = next(c for c in out["corrected"] if c["snapshot"] == main)
    mi = next(x for x in ints["time_in_stage_corrected"]["quarters"] if x["snapshot"] == main)
    hrs = AS["capacity"]["onboarding_hours_per_start"]
    fte_h = AS["capacity"]["hours_per_person_quarter"]
    plan = {"forecast_wins": m["time_in_stage"]["forecast"], "lo80": mi["lo80"], "hi80": mi["hi80"],
            "actual": m["actual"], "hours_per_start": hrs, "hours_per_person_quarter": fte_h,
            "people": {str(h): {"forecast": r(m["time_in_stage"]["forecast"] * h / fte_h, 1),
                                "lo80": r(mi["lo80"] * h / fte_h, 1), "hi80": r(mi["hi80"] * h / fte_h, 1),
                                "actual": r(m["actual"] * h / fte_h, 1)} for h in hrs["range"]}}
    out["capacity_plan"] = plan
    (ROOT / "results" / "after.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["corrected_backtest"]), json.dumps({k: (v["covered"], v["of"]) for k, v in ints.items()}))


if __name__ == "__main__":
    main()
