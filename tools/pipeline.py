"""The opportunity table, stages at a snapshot, the four forecasts and their scores. Standard library only.

Every rule here is the one written in protocol-r1.json. Version 1 builds each opportunity once from all its notices;
the further changes (method page) pass a view that rebuilds it at each snapshot from the notices published before it.
"""
import csv
import datetime as dt
import gzip
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Z80 = 1.2816
BANDS = [(0, 14), (15, 30), (31, 60), (61, 120), (121, 365), (366, None)]
MIN_CELL = 20


def day(s):
    return dt.date.fromisoformat(s).toordinal() if s else None


def iso(n):
    return dt.date.fromordinal(n).isoformat()


def quarter_start(n, k=0):
    """the quarter start k quarters after the quarter holding ordinal n"""
    d = dt.date.fromordinal(n)
    m = (d.year * 12 + (d.month - 1) // 3 * 3) + 3 * k
    return dt.date(m // 12, m % 12 + 1, 1).toordinal()


def account(name):
    """normalise spelling variants of a department name: drop a trailing (ABC), a leading 'Department of', 'Agency'"""
    s = (name or "").strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    s = re.sub(r"^Department of (the )?", "", s)
    s = s.replace(" of Canada", " Canada").replace(" Agency", "")
    if s in ("Public Works and Government Services Canada", "Public Services and Procurement Canada"):
        s = "Public Services and Procurement Canada"
    return s or "Unknown"


FIELDS_DATE = ["created_at", "bid_close_at", "expected_start", "cancelled_at", "won_at", "won_known_at", "go_live_at"]


def load(path=None):
    path = path or ROOT / "data" / "opportunities.csv.gz"
    rows = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            o = {k: day(r[k]) for k in FIELDS_DATE}
            o["id"] = r["opportunity_id"]
            o["amount"] = float(r["amount_cad"]) if r["amount_cad"] else None
            o["channel"] = r["channel"]
            o["category"] = r["category"]
            o["account"] = account(r["account_raw"])
            o["status"] = r["status"]
            rows.append(o)
    assert rows, "empty opportunity table"
    return rows


def stage(o, s):
    """(stage, days in stage) at snapshot s, or None when not in the pipeline. Facts published before s only."""
    if o["created_at"] is None or o["created_at"] >= s:
        return None
    if o["won_known_at"] is not None and o["won_known_at"] < s:
        return None
    if o["cancelled_at"] is not None and o["cancelled_at"] < s:
        return None
    if o["bid_close_at"] is not None and s <= o["bid_close_at"]:
        return ("open", s - o["created_at"])
    since = o["bid_close_at"] if o["bid_close_at"] is not None else o["created_at"]
    return ("await", s - since)


def band(days):
    for i, (lo, hi) in enumerate(BANDS):
        if days >= lo and (hi is None or days <= hi):
            return i
    raise ValueError(days)


def expected_close(o):
    return o["expected_start"] if o["expected_start"] is not None else o["bid_close_at"]


def in_window(o, s, e):
    d = expected_close(o)
    return d is not None and s <= d < e


def won_in(o, s, e, known_by):
    """won within [s, e), counting only awards published on or before known_by (exclusive bound: before known_by)"""
    return (o["won_at"] is not None and s <= o["won_at"] < e and o["won_known_at"] is not None
            and o["won_known_at"] < known_by)


def load_notices(path=None):
    """version 2: notices by opportunity id, each (published, bid close, expected start, status, last amendment)"""
    path = path or ROOT / "data" / "notices.csv.gz"
    out = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["opportunity_id"], []).append(
                (day(r["published_at"]), day(r["bid_close_at"]), day(r["expected_start"]), r["status"],
                 day(r["last_amendment_at"])))
    assert out, "empty notice table"
    for v in out.values():
        v.sort(key=lambda n: (n[0], n[1] or 0))
    return out


DROPPED_IDS = {"N/A"}


def make_view(rows, notices, drop_flagged=False):
    """further changes, items 1 and 2: view(s) is the opportunity table as it stood before s. Each row is
    rebuilt from the notices published before s; 'amended_after' marks a row with a notice amended on or after s,
    whose values at s cannot be recovered. drop_flagged leaves those rows out."""
    memo = {}

    def view(s):
        if s in memo:
            return memo[s]
        out = []
        for o in rows:
            if o["id"] in DROPPED_IDS:
                continue
            ns = [n for n in notices[o["id"]] if n[0] is not None and n[0] < s]
            if not ns:
                continue
            last = max(ns, key=lambda n: n[0])
            closes = [n[1] for n in ns if n[1] is not None]
            flagged = any(n[4] is not None and n[4] >= s for n in ns)
            if drop_flagged and flagged:
                continue
            v = dict(o)
            v["created_at"] = ns[0][0]
            v["bid_close_at"] = max(closes) if closes else None
            v["expected_start"] = last[2]
            v["status"] = last[3]
            v["cancelled_at"] = (last[4] if last[4] is not None else last[1]) if last[3] == "Cancelled" else None
            v["amended_after"] = flagged
            out.append(v)
        memo[s] = out
        return out
    return view


def pipeline(rows, s, view=None):
    out = []
    for o in (view(s) if view is not None else rows):
        st = stage(o, s)
        if st:
            out.append((o, st[0], st[1]))
    return out


def poisson_binomial(ps):
    mu = sum(ps)
    sd = math.sqrt(sum(p * (1 - p) for p in ps))
    return mu, max(0.0, mu - Z80 * sd), mu + Z80 * sd


def forecast_all(rows, s, history=4, fixed=(0.60, 0.80), known_by=None, cache=None, label_weight=None, view=None):
    """Every arm's forecast for the quarter starting at s. known_by: the publication bound for history labels
    (s for point in time; a later date for the leakage contrast). label_weight(h): what one known win in the history
    quarter starting at h counts for (1 when None; the late-recording correction passes 1 / completeness)."""
    lw = (lambda h: 1.0) if label_weight is None else label_weight
    known_by = s if known_by is None else known_by
    e = quarter_start(s, 1)
    pipe = pipeline(rows, s, view)
    hist = []
    for k in range(1, history + 1):
        h = quarter_start(s, -k)
        he = quarter_start(h, 1)
        hp = cache[h] if cache is not None and h in cache else pipeline(rows, h, view)
        if cache is not None:
            cache[h] = hp
        hist.append((h, he, hp))
    # fixed stage weights with the date rule
    w_fixed = {"open": fixed[0], "await": fixed[1]}
    ps_fixed = [w_fixed[st] for o, st, d in pipe if in_window(o, s, e)]
    # learned stage weights with the date rule
    num, den = {"open": 0, "await": 0}, {"open": 0, "await": 0}
    for h, he, hp in hist:
        for o, st, d in hp:
            if in_window(o, h, he):
                den[st] += 1
                num[st] += won_in(o, h, he, known_by) * lw(h)
    w_learn = {k: (num[k] / den[k] if den[k] else 0.0) for k in num}
    ps_learn = [w_learn[st] for o, st, d in pipe if in_window(o, s, e)]
    # time in stage, no date rule
    cn, cd, sn, sd = {}, {}, {"open": 0, "await": 0}, {"open": 0, "await": 0}
    for h, he, hp in hist:
        for o, st, d in hp:
            key = (st, band(d))
            w = won_in(o, h, he, known_by) * lw(h)
            cd[key] = cd.get(key, 0) + 1
            cn[key] = cn.get(key, 0) + w
            sd[st] += 1
            sn[st] += w
    def w_tis(st, d):
        key = (st, band(d))
        if cd.get(key, 0) >= MIN_CELL:
            return cn[key] / cd[key]
        return sn[st] / sd[st] if sd[st] else 0.0
    ps_tis = [w_tis(st, d) for o, st, d in pipe]
    # run rate: last quarter's pipeline wins, as known
    h1, h1e, hp1 = hist[0]
    run_rate = sum(won_in(o, h1, h1e, known_by) for o, st, d in hp1) * lw(h1)
    res = {}
    for name, ps in (("fixed", ps_fixed), ("learned_stage", ps_learn), ("time_in_stage", ps_tis)):
        mu, lo, hi = poisson_binomial(ps)
        res[name] = {"forecast": mu, "lo80": lo, "hi80": hi, "deals_counted": len(ps)}
    res["run_rate"] = {"forecast": float(run_rate), "lo80": None, "hi80": None, "deals_counted": None}
    res["_weights"] = {"learned_stage": w_learn,
                       "time_in_stage": {f"{st}:{band_label(b)}": (cn[(st, b)] / cd[(st, b)], cd[(st, b)])
                                         for (st, b) in sorted(cd)},
                       "stage_pooled": {k: (sn[k] / sd[k] if sd[k] else None) for k in sn}}
    res["_pipeline"] = {"open": sum(1 for _, st, _ in pipe if st == "open"),
                        "await": sum(1 for _, st, _ in pipe if st == "await"),
                        "in_window": len(ps_fixed)}
    return res


def band_label(b):
    lo, hi = BANDS[b]
    return f"{lo}+" if hi is None else f"{lo}-{hi}"


def actual(rows, s, far_future=10 ** 7, view=None):
    """pipeline-at-s wins in the quarter, every award known; and all wins in the quarter"""
    e = quarter_start(s, 1)
    pipe = pipeline(rows, s, view)
    from_pipe = sum(won_in(o, s, e, far_future) for o, st, d in pipe)
    all_wins = [o for o in rows if o["won_at"] is not None and s <= o["won_at"] < e]
    new = sum(1 for o in all_wins if o["created_at"] >= s)
    return {"pipeline_wins": from_pipe, "all_wins": len(all_wins), "wins_created_in_quarter": new,
            "pipeline_open": sum(1 for _, st, _ in pipe if st == "open"),
            "pipeline_await": sum(1 for _, st, _ in pipe if st == "await")}


def score(f, a):
    err = f - a
    return {"error": err, "pct_error": 100 * err / a, "abs_pct_error": 100 * abs(err) / a}


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return None if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = q * (len(xs) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)
