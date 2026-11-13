"""Further changes (method page): every forecast rebuilt from the notices published before each snapshot, deals amended
after the snapshot flagged and dropped in a sensitivity run, same-target scores, the past-due split, ranges from past
misses as known then, head-to-head counts, and the declared predictions R1 to R5.
Writes results/summary-r2.json. Usage: python3 -B tools/run_study_r2.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402
from after_results import completeness_fn, quarter_completeness  # noqa: E402

ROOT = P.ROOT
PROTO = json.loads((ROOT / "protocol-r1.json").read_text(encoding="utf-8"))
V1 = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
V1A = json.loads((ROOT / "results" / "after.json").read_text(encoding="utf-8"))
ARMS = ["fixed", "learned_stage", "time_in_stage", "run_rate"]
FAR = 10 ** 7


def r(x, d=2):
    return None if x is None else round(x, d)


def agg(recs):
    return {"mape": r(sum(x["abs_pct_error"] for x in recs) / len(recs)),
            "bias_pct": r(sum(x["pct_error"] for x in recs) / len(recs)),
            "worst_abs_pct": r(max(x["abs_pct_error"] for x in recs)),
            "best_abs_pct": r(min(x["abs_pct_error"] for x in recs)),
            "too_high_quarters": sum(1 for x in recs if x["pct_error"] > 0)}


def scored(f, a):
    return {"forecast": r(f), **{k: r(v) for k, v in P.score(f, a).items()}}


def past_due_split(pipe, s, e):
    out = {"inside": 0, "later": 0, "no_date": 0, "past_due_start_given": 0, "past_due_bid_close": 0}
    for o, st, d in pipe:
        if not P.won_in(o, s, e, FAR):
            continue
        x = P.expected_close(o)
        if x is None:
            out["no_date"] += 1
        elif s <= x < e:
            out["inside"] += 1
        elif x >= e:
            out["later"] += 1
        elif o["expected_start"] is not None:
            out["past_due_start_given"] += 1
        else:
            out["past_due_bid_close"] += 1
    out["total"] = sum(out.values())
    out["past_due"] = out["past_due_start_given"] + out["past_due_bid_close"]
    out["not_inside"] = out["total"] - out["inside"]
    out["not_inside_pct"] = r(100 * out["not_inside"] / out["total"], 1)
    return out


def run(rows, view, snaps, fx):
    """all arms, ranges, same target, corrected arms and the pipeline wins of each quarter, for one view"""
    cache, per = {}, []
    for sname in snaps:
        s = P.day(sname)
        e = P.quarter_start(s, 1)
        a = P.actual(rows, s, view=view)["pipeline_wins"]
        pipe = P.pipeline(rows, s, view)
        f = P.forecast_all(rows, s, fixed=(fx["weights"]["open_for_bids"], fx["weights"]["awaiting_award"]),
                           cache=cache, view=view)
        rng = [P.forecast_all(rows, s, fixed=(v["open_for_bids"], v["awaiting_award"]), cache=cache, view=view)["fixed"]
               for v in fx["range"]]
        F, n = completeness_fn(rows, s)
        comp = {P.iso(P.quarter_start(s, -k)): quarter_completeness(F, s, P.quarter_start(s, -k)) for k in range(1, 5)}
        fc = P.forecast_all(rows, s, cache=cache, view=view, label_weight=lambda h: 1.0 / comp[P.iso(h)])
        dated_wins = sum(P.won_in(o, s, e, FAR) for o, st, d in pipe if P.in_window(o, s, e))
        flagged = [o for o, st, d in pipe if o.get("amended_after")]
        cal = {}
        for stg in ("open", "await"):
            grp = [o for o, st, d in pipe if st == stg and P.in_window(o, s, e)]
            cal[stg] = r(100 * sum(P.won_in(o, s, e, FAR) for o in grp) / len(grp), 1) if grp else None
        rec = {"snapshot": sname, "pipeline_wins": a, "pipeline": f["_pipeline"],
               "arms": {k: scored(f[k]["forecast"], a) for k in ARMS},
               "covered80": {k: f[k]["lo80"] <= a <= f[k]["hi80"] for k in ("fixed", "learned_stage", "time_in_stage")},
               "fixed_range": [{"weights": v, **scored(x["forecast"], a)} for v, x in zip(fx["range"], rng)],
               "corrected": {k: scored(fc[k]["forecast"], a) for k in ("time_in_stage", "run_rate")},
               "same_target": {"wins_from_dated_deals": dated_wins,
                               **{k: scored(f[k]["forecast"], dated_wins) for k in ("fixed", "learned_stage")}},
               "where_wins_come_from": past_due_split(pipe, s, e),
               "dated_in_quarter_won_pct": cal, "learned_weights": f["_weights"]["learned_stage"],
               "flagged": {"deals": len(flagged), "of": len(pipe), "pct": r(100 * len(flagged) / len(pipe), 1) if pipe else None,
                           "wins": sum(P.won_in(o, s, e, FAR) for o in flagged)},
               "_pipe": pipe}
        per.append(rec)
    return per


def summarise(per):
    out = {k: agg([p["arms"][k] for p in per]) for k in ARMS}
    for p in per:
        best = min(ARMS, key=lambda k: p["arms"][k]["abs_pct_error"])
        out[best]["best_in_quarters"] = out[best].get("best_in_quarters", 0) + 1
    for k in ARMS:
        out[k].setdefault("best_in_quarters", 0)
    for k in ("fixed", "learned_stage", "time_in_stage"):
        out[k]["covered80"] = sum(1 for p in per if p["covered80"][k])
    out["corrected"] = {k: agg([p["corrected"][k] for p in per]) for k in ("time_in_stage", "run_rate")}
    out["same_target"] = {k: agg([p["same_target"][k] for p in per]) for k in ("fixed", "learned_stage")}
    out["fixed_range"] = [{"weights": per[0]["fixed_range"][i]["weights"], **agg([p["fixed_range"][i] for p in per])}
                          for i in range(len(per[0]["fixed_range"]))]
    nin = [p["where_wins_come_from"]["not_inside_pct"] for p in per]
    out["not_inside_pct_range"] = [min(nin), max(nin)]
    return out


def head_to_head(fixed, tis_c, rr_c):
    return {"tis_corrected_closer_than_defaults": sum(1 for a, b in zip(tis_c, fixed) if a["abs_pct_error"] < b["abs_pct_error"]),
            "tis_corrected_closer_than_run_rate_corrected": sum(1 for a, b in zip(tis_c, rr_c) if a["abs_pct_error"] < b["abs_pct_error"]),
            "of": len(fixed)}


def intervals_known_then(rows, per, arm_get, snaps):
    """Further changes, item 5: earlier quarters' errors computed against the wins published before the forecast date"""
    out = []
    for i in range(3, len(per)):
        s_i = P.day(snaps[i])
        past = []
        for j in range(i):
            s_j = P.day(snaps[j])
            e_j = P.quarter_start(s_j, 1)
            known = sum(P.won_in(o, s_j, e_j, s_i) for o, st, d in per[j]["_pipe"])
            past.append(100 * (arm_get(per[j])["forecast"] - known) / known)
        lo_e, hi_e = P.quantile(past, 0.1), P.quantile(past, 0.9)
        fc, act = arm_get(per[i])["forecast"], per[i]["pipeline_wins"]
        lo, hi = fc / (1 + hi_e / 100), fc / (1 + lo_e / 100)
        out.append({"snapshot": snaps[i], "forecast": fc, "lo80": r(lo, 1), "hi80": r(hi, 1), "actual": act,
                    "covered": lo <= act <= hi})
    return {"quarters": out, "covered": sum(x["covered"] for x in out), "of": len(out)}


def main():
    rows = P.load()
    notices = P.load_notices()
    snaps = PROTO["snapshots_scored"]
    fx = PROTO["arms"]["fixed"]
    main_s = PROTO["main_snapshot"]
    v_all = P.make_view(rows, notices)
    v_drop = P.make_view(rows, notices, drop_flagged=True)
    r2 = run(rows, v_all, snaps, fx)
    drop = run(rows, v_drop, snaps, fx)
    v1 = run(rows, None, snaps, fx)  # version 1's table, for the splits and head-to-head on the same footing
    # version 1 reproduced: the arms here must equal results/summary.json
    for p, q in zip(v1, V1["snapshots"]):
        for k in ARMS:
            assert abs(p["arms"][k]["forecast"] - q["arms"][k]["forecast"]) < 0.01, (p["snapshot"], k)
    for p, q in zip(v1, V1A["corrected"]):
        for k in ("time_in_stage", "run_rate"):
            assert abs(p["corrected"][k]["forecast"] - q[k]["forecast"]) < 0.01, (p["snapshot"], k)
    S2, SD, S1 = summarise(r2), summarise(drop), summarise(v1)
    h2h = {"r2": head_to_head([p["arms"]["fixed"] for p in r2], [p["corrected"]["time_in_stage"] for p in r2],
                              [p["corrected"]["run_rate"] for p in r2]),
           "v1": head_to_head([p["arms"]["fixed"] for p in v1], [p["corrected"]["time_in_stage"] for p in v1],
                              [p["corrected"]["run_rate"] for p in v1])}
    ints = {"r2": {"fixed": intervals_known_then(rows, r2, lambda p: p["arms"]["fixed"], snaps),
                   "time_in_stage_corrected": intervals_known_then(rows, r2, lambda p: p["corrected"]["time_in_stage"], snaps)},
            "v1": {"fixed": intervals_known_then(rows, v1, lambda p: p["arms"]["fixed"], snaps),
                   "time_in_stage_corrected": intervals_known_then(rows, v1, lambda p: p["corrected"]["time_in_stage"], snaps)}}
    mr = next(p for p in r2 if p["snapshot"] == main_s)
    m1 = next(p for p in v1 if p["snapshot"] == main_s)
    moved = {k: r(S2[k]["mape"] - V1["backtest"]["all8"][k]["mape"]) for k in ARMS}
    moved["time_in_stage_corrected"] = r(S2["corrected"]["time_in_stage"]["mape"] - V1A["corrected_backtest"]["time_in_stage"]["all8"]["mape"])
    moved["run_rate_corrected"] = r(S2["corrected"]["run_rate"]["mape"] - V1A["corrected_backtest"]["run_rate"]["all8"]["mape"])
    preds = {
        "R1": {"held": abs(moved["fixed"]) < 5 and min(ARMS, key=lambda k: S2[k]["mape"]) == "fixed",
               "observed": {"fixed_mape_r2": S2["fixed"]["mape"], "moved": moved["fixed"],
                            "closest_on_average": min(ARMS, key=lambda k: S2[k]["mape"])}},
        "R2": {"held": mr["flagged"]["pct"] < 20, "observed": mr["flagged"]},
        "R3": {"held": S2["same_target"]["learned_stage"]["mape"] < S2["same_target"]["fixed"]["mape"],
               "observed": {k: S2["same_target"][k]["mape"] for k in ("fixed", "learned_stage")}},
        "R4": {"held": mr["where_wins_come_from"]["past_due_bid_close"] >= 0.5 * mr["where_wins_come_from"]["past_due"],
               "observed": mr["where_wins_come_from"]},
        "R5": {"held": ints["r2"]["time_in_stage_corrected"]["covered"] <= 3,
               "observed": {"covered": ints["r2"]["time_in_stage_corrected"]["covered"],
                            "of": ints["r2"]["time_in_stage_corrected"]["of"]}}}
    page_version = "v1" if all(abs(v) < 2 for k, v in moved.items() if k in ARMS) else "r2"
    for per in (r2, drop, v1):
        for p in per:
            p.pop("_pipe")
    out = {"declaration": "CHANGES-r2.md", "page_version": page_version, "mape_moved_vs_v1": moved,
           "r2": {"summary": S2, "quarters": r2}, "drop_flagged": {"summary": SD, "quarters": drop},
           "v1_rerun": {"summary": S1, "quarters": v1}, "head_to_head": h2h, "intervals_known_then": ints,
           "main": {"r2": {k: mr[k] for k in ("where_wins_come_from", "dated_in_quarter_won_pct", "learned_weights", "flagged", "pipeline_wins")},
                    "v1": {k: m1[k] for k in ("where_wins_come_from", "dated_in_quarter_won_pct", "learned_weights", "pipeline_wins")}},
           "predictions": preds}
    (ROOT / "results" / "summary-r2.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"moved": moved, "page_version": page_version,
                      "r2": {k: S2[k]["mape"] for k in ARMS}, "r2_corrected": {k: v["mape"] for k, v in S2["corrected"].items()},
                      "drop": {k: SD[k]["mape"] for k in ARMS}, "drop_corrected": {k: v["mape"] for k, v in SD["corrected"].items()},
                      "same_target_r2": {k: v["mape"] for k, v in S2["same_target"].items()},
                      "h2h": h2h, "ints": {a: {k: (v["covered"], v["of"]) for k, v in b.items()} for a, b in ints.items()},
                      "preds": {k: v["held"] for k, v in preds.items()}}, indent=None))


if __name__ == "__main__":
    main()
