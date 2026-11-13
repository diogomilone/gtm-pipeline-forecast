"""Run every forecast on every scored snapshot, score them, describe go-live lags and segments, and score the declared
predictions. Writes results/summary.json. Usage: python3 -B tools/run_study.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402

ROOT = P.ROOT
PROTO = json.loads((ROOT / "protocol-r1.json").read_text(encoding="utf-8"))
PRED = json.loads((ROOT / "predictions-r1.json").read_text(encoding="utf-8"))
SRC = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
ARMS = ["fixed", "learned_stage", "time_in_stage", "run_rate"]
FAR = 10 ** 7


def r(x, d=2):
    return None if x is None else round(x, d)


def main():
    rows = P.load()
    cutoff = SRC["cutoff_latest_tender_publication"]
    fx = PROTO["arms"]["fixed"]
    snaps = PROTO["snapshots_scored"]
    cache = {}
    per = []
    for sname in snaps:
        s = P.day(sname)
        a = P.actual(rows, s)
        honest = P.forecast_all(rows, s, fixed=(fx["weights"]["open_for_bids"], fx["weights"]["awaiting_award"]), cache=cache)
        leaky = P.forecast_all(rows, s, known_by=FAR, cache=cache)
        rng = [P.forecast_all(rows, s, fixed=(v["open_for_bids"], v["awaiting_award"]), cache=cache)["fixed"]
               for v in fx["range"]]
        rec = {"snapshot": sname, "actual": a, "arms": {}, "leaky": {}, "fixed_range": [], "weights": honest["_weights"],
               "pipeline": honest["_pipeline"]}
        for arm in ARMS:
            f = honest[arm]
            sc = P.score(f["forecast"], a["pipeline_wins"])
            cov = None if f["lo80"] is None else (f["lo80"] <= a["pipeline_wins"] <= f["hi80"])
            rec["arms"][arm] = {**{k: r(v) for k, v in f.items()}, **{k: r(v) for k, v in sc.items()}, "covered80": cov}
            if arm != "fixed":
                lf = leaky[arm]
                rec["leaky"][arm] = {"forecast": r(lf["forecast"]), **{k: r(v) for k, v in P.score(lf["forecast"], a["pipeline_wins"]).items()}}
        for v, f in zip(fx["range"], rng):
            rec["fixed_range"].append({"weights": v, "forecast": r(f["forecast"]),
                                       **{k: r(x) for k, x in P.score(f["forecast"], a["pipeline_wins"]).items()}})
        rec["weights_leaky"] = leaky["_weights"]
        per.append(rec)
        print(sname, a["pipeline_wins"], {k: rec["arms"][k]["forecast"] for k in ARMS})

    def agg(sel, which="arms"):
        out = {}
        for arm in ARMS:
            if which == "leaky" and arm == "fixed":
                continue
            recs = [p[which][arm] for p in sel]
            out[arm] = {"mape": r(sum(x["abs_pct_error"] for x in recs) / len(recs)),
                        "bias_pct": r(sum(x["pct_error"] for x in recs) / len(recs)),
                        "worst_abs_pct": r(max(x["abs_pct_error"] for x in recs)),
                        "best_in_quarters": None}
            if which == "arms" and arm != "run_rate":
                out[arm]["covered80"] = sum(1 for x in recs if x["covered80"])
        if which == "arms":
            for p in sel:
                best = min(ARMS, key=lambda k: p["arms"][k]["abs_pct_error"])
                out[best]["best_in_quarters"] = (out[best]["best_in_quarters"] or 0) + 1
            for arm in ARMS:
                out[arm]["best_in_quarters"] = out[arm]["best_in_quarters"] or 0
        return out

    main_rec = next(p for p in per if p["snapshot"] == PROTO["main_snapshot"])
    earlier = [p for p in per if p["snapshot"] != PROTO["main_snapshot"]]
    backtest = {"all8": agg(per), "earlier7": agg(earlier), "leaky_all8": agg(per, "leaky")}
    share_new = [100 * p["actual"]["wins_created_in_quarter"] / p["actual"]["all_wins"] for p in per]

    # ---------- description: go-live ----------
    lo, hi = P.day("2022-08-08"), P.day("2025-09-30")
    wins = [o for o in rows if o["won_at"] is not None and lo <= o["won_at"] <= hi]
    lag = [o["go_live_at"] - o["won_at"] for o in wins if o["go_live_at"] is not None]
    slip = [o["go_live_at"] - o["expected_start"] for o in wins if o["go_live_at"] is not None and o["expected_start"] is not None]
    pub = [o["won_known_at"] - o["won_at"] for o in wins if o["won_known_at"] is not None]
    golive = {"wins": len(wins), "with_start": len(lag), "median_days": P.median(lag), "q1": P.quantile(lag, .25),
              "q3": P.quantile(lag, .75), "p90": P.quantile(lag, .9),
              "share_before_award_pct": r(100 * sum(1 for x in lag if x < 0) / len(lag), 1),
              "share_same_day_pct": r(100 * sum(1 for x in lag if x == 0) / len(lag), 1),
              "share_30plus_pct": r(100 * sum(1 for x in lag if x >= 30) / len(lag), 1),
              "with_expected": len(slip), "slip_median_days": P.median(slip),
              "slip_share_30plus_late_pct": r(100 * sum(1 for x in slip if x >= 30) / len(slip), 1),
              "slip_share_30plus_early_pct": r(100 * sum(1 for x in slip if x <= -30) / len(slip), 1),
              "slip_share_within_7_pct": r(100 * sum(1 for x in slip if abs(x) <= 7) / len(slip), 1),
              "publish_lag_median_days": P.median(pub),
              "publish_lag_share_90plus_pct": r(100 * sum(1 for x in pub if x >= 90) / len(pub), 1)}

    # ---------- description: segments ----------
    clo, chi = P.day("2022-08-08"), P.day("2025-06-30")
    cohort = [o for o in rows if clo <= o["created_at"] <= chi]

    def seg(key):
        groups = {}
        for o in cohort:
            groups.setdefault(key(o), []).append(o)
        out = {}
        for g, os_ in groups.items():
            w = [o for o in os_ if o["won_at"] is not None]
            out[g] = {"opportunities": len(os_), "won": len(w), "win_rate_pct": r(100 * len(w) / len(os_), 1),
                      "cancelled_pct": r(100 * sum(1 for o in os_ if o["cancelled_at"] is not None and o["won_at"] is None) / len(os_), 1),
                      "median_days_to_win": P.median([o["won_at"] - o["created_at"] for o in w]),
                      "wins_per_quarter": r(len(w) / ((chi - clo) / 91.31), 1)}
        return out

    channels = seg(lambda o: o["channel"])
    accts = seg(lambda o: o["account"])
    top = sorted(accts, key=lambda k: -accts[k]["opportunities"])[:8]
    accounts = {k: accts[k] for k in top}
    amounts = [o["amount"] for o in wins]
    usable = [x for x in amounts if x is not None]
    amt = {"wins": len(wins), "with_amount": len(usable), "share_with_amount_pct": r(100 * len(usable) / len(wins), 1),
           "median_cad": r(P.median(usable), 0), "q1_cad": r(P.quantile(usable, .25), 0), "q3_cad": r(P.quantile(usable, .75), 0)}
    overall = {"cohort": len(cohort), "won": sum(1 for o in cohort if o["won_at"] is not None)}
    overall["win_rate_pct"] = r(100 * overall["won"] / overall["cohort"], 1)

    # ---------- predictions, scored as declared ----------
    m = main_rec["arms"]
    b8 = backtest["all8"]
    pv = {}
    pv["P1"] = (m["fixed"]["pct_error"] > 40, {"fixed_pct_error_main": m["fixed"]["pct_error"]})
    pv["P2"] = (abs(m["learned_stage"]["error"]) < 0.5 * abs(m["fixed"]["error"]),
                {"learned_abs_error": abs(m["learned_stage"]["error"]), "fixed_abs_error": abs(m["fixed"]["error"])})
    pv["P3"] = (b8["time_in_stage"]["mape"] < b8["learned_stage"]["mape"],
                {"tis_mape": b8["time_in_stage"]["mape"], "learned_mape": b8["learned_stage"]["mape"]})
    pv["P4"] = (b8["learned_stage"]["bias_pct"] < 0 and b8["time_in_stage"]["bias_pct"] < 0,
                {"learned_bias": b8["learned_stage"]["bias_pct"], "tis_bias": b8["time_in_stage"]["bias_pct"]})
    pv["P5"] = (b8["time_in_stage"]["mape"] - backtest["leaky_all8"]["time_in_stage"]["mape"] >= 5,
                {"tis_mape": b8["time_in_stage"]["mape"], "tis_leaky_mape": backtest["leaky_all8"]["time_in_stage"]["mape"]})
    pv["P6"] = (P.median(share_new) >= 30, {"median_share_new_pct": r(P.median(share_new), 1)})
    pv["P7"] = (b8["time_in_stage"]["mape"] < b8["run_rate"]["mape"],
                {"tis_mape": b8["time_in_stage"]["mape"], "run_rate_mape": b8["run_rate"]["mape"]})
    pv["P8"] = (b8["time_in_stage"]["covered80"] <= 4, {"tis_covered80": b8["time_in_stage"]["covered80"]})
    preds = {p["id"]: {"text": p["text"], "held": bool(pv[p["id"]][0]), "observed": pv[p["id"]][1]} for p in PRED["predictions"]}

    summary = {"cutoff": cutoff, "sources": SRC, "snapshots": per, "main_snapshot": PROTO["main_snapshot"],
               "backtest": backtest, "share_new_by_quarter_pct": [r(x, 1) for x in share_new],
               "go_live": golive, "channels": channels, "accounts": accounts, "amounts": amt, "overall_cohort": overall,
               "predictions": preds}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print("predictions held:", [k for k, v in preds.items() if v["held"]], "missed:", [k for k, v in preds.items() if not v["held"]])


if __name__ == "__main__":
    main()
