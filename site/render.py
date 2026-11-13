"""Render index.html and the three detail pages. Every number comes from results/summary.json, results/after.json or
assumptions.json, and the claims the text makes are asserted here, so a change in the results fails the build instead of
leaving the text stale.
Usage: python3 -I -B site/render.py
"""
import html
import json
from decimal import ROUND_HALF_UP, Decimal
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
A = json.loads((ROOT / "results" / "after.json").read_text(encoding="utf-8"))
AS = json.loads((ROOT / "assumptions.json").read_text(encoding="utf-8"))
PRED = json.loads((ROOT / "predictions-r1.json").read_text(encoding="utf-8"))
PROTO = json.loads((ROOT / "protocol-r1.json").read_text(encoding="utf-8"))
CSS = (ROOT / "site" / "page.css").read_text(encoding="utf-8")
STUDY_TITLE = "Forecasting a sales pipeline: stage win chances and close dates"
MINUS = "−"
DATA_LABEL = ("Public data: CanadaBuys tender and award notices, Government of Canada, under the Open Government "
              "Licence (Canada).")


def e(t):
    return html.escape(str(t), quote=True)


def hu(v, d=0):
    """round half up (away from zero), as written figures are read"""
    q = Decimal(1).scaleb(-d)
    return float(Decimal(repr(v)).quantize(q, rounding=ROUND_HALF_UP))


def pc(v, d=0):
    return f"{hu(v, d):.{d}f}%"


def spc(v, d=0):
    """signed percent with a true minus sign"""
    r = hu(v, d)
    s = f"{abs(r):.{d}f}%"
    return ("+" if r > 0 else MINUS if r < 0 else "") + s


def n0(v):
    return f"{v:,.0f}"


def cad(v):
    return f"CA${v:,.0f}"


QUARTER_NAME = {"01": "January to March", "04": "April to June", "07": "July to September", "10": "October to December"}


def qname(snap):
    y, m, _ = snap.split("-")
    return f"{QUARTER_NAME[m]} {y}"


def qshort(snap):
    y, m, _ = snap.split("-")
    return {"01": "Q1", "04": "Q2", "07": "Q3", "10": "Q4"}[m] + " " + y


# ---------- the declared results ----------
SN = S["snapshots"]
assert len(SN) == 8
BT = S["backtest"]["all8"]
MAPE = {k: BT[k]["mape"] for k in BT}
assert (round(MAPE["fixed"]), round(MAPE["learned_stage"]), round(MAPE["time_in_stage"]), round(MAPE["run_rate"])) == (23, 61, 28, 33)
assert all(p["arms"]["fixed"]["pct_error"] > 0 for p in SN)            # the defaults always over-forecast
assert all(p["arms"]["learned_stage"]["pct_error"] < 0 for p in SN)    # learned weights always under-forecast
assert all(p["arms"]["time_in_stage"]["pct_error"] < 0 for p in SN)
FIXED_BEST = BT["fixed"]["best_in_quarters"]
assert FIXED_BEST == 6
MAIN = next(p for p in SN if p["snapshot"] == S["main_snapshot"])
MA = MAIN["actual"]["pipeline_wins"]
MF = {k: MAIN["arms"][k] for k in MAIN["arms"]}
assert MA == 426 and round(MF["fixed"]["forecast"]) == 440 and round(MF["learned_stage"]["forecast"]) == 169
RANGE = [{"w": SN[0]["fixed_range"][i]["weights"],
          "mape": sum(abs(p["fixed_range"][i]["pct_error"]) for p in SN) / 8} for i in range(2)]
assert round(RANGE[0]["mape"]) == 16 and round(RANGE[1]["mape"]) == 52
LEAK = S["backtest"]["leaky_all8"]
COV = {k: BT[k]["covered80"] for k in ("fixed", "learned_stage", "time_in_stage")}
assert max(COV.values()) <= 1
MIN_ACT, MAX_ACT = min(p["actual"]["pipeline_wins"] for p in SN), max(p["actual"]["pipeline_wins"] for p in SN)
SHARE_NEW = S["share_new_by_quarter_pct"]
PREDS = S["predictions"]
N_HELD = sum(1 for v in PREDS.values() if v["held"])
assert N_HELD == 6 and not PREDS["P1"]["held"] and not PREDS["P2"]["held"]
SRC = S["sources"]
OPPS = SRC["opportunities"]["opportunities"]
GL = S["go_live"]
AM = S["amounts"]
CH = S["channels"]
AC = S["accounts"]
OV = S["overall_cohort"]

# ---------- added after the results ----------
WW = {w["snapshot"]: w for w in A["where_wins_come_from"]}
MW = WW[S["main_snapshot"]]
NOT_DATED = MW["total"] - MW["inside"]
assert MW["total"] == MA and NOT_DATED == 209 and MW["past_due"] == 192
SHARE_OUT = [100 * (w["total"] - w["inside"]) / w["total"] for w in A["where_wins_come_from"]]
OUT_LO, OUT_HI = min(SHARE_OUT), max(SHARE_OUT)
assert round(OUT_LO) == 45 and round(OUT_HI) == 54
CAL = next(c for c in A["stage_calibration"] if c["snapshot"] == S["main_snapshot"])
OD, AD, AS_ = CAL["open:dated_in_quarter"], CAL["await:dated_in_quarter"], CAL["await:not_dated_in_quarter"]
# awaiting-award deals dated outside the main quarter that were won in it: 181 (176 past due, 5 dated later),
# counted with tools/pipeline.py; the share stored in after.json must agree with it
AWAIT_OUT_WINS = 181
assert round(100 * AWAIT_OUT_WINS / AS_["deals"], 1) == AS_["won_in_quarter_pct"]
CB = A["corrected_backtest"]
TISC = CB["time_in_stage"]["all8"]["mape"]
RUNC = CB["run_rate"]["all8"]["mape"]
assert round(TISC) == 16 and round(RUNC) == 18
TISC_MAIN = next(c for c in A["corrected"] if c["snapshot"] == S["main_snapshot"])["time_in_stage"]
PMI = A["intervals_from_past_misses"]
CAP = A["capacity_plan"]

# ---------- further changes: notices as known then, same target, splits, ranges as known then ----------
R2 = json.loads((ROOT / "results" / "summary-r2.json").read_text(encoding="utf-8"))
assert R2["page_version"] == "v1"  # declared rule: every average moved by under 2 points, so the pages keep version 1
MOVED = max(abs(R2["mape_moved_vs_v1"][k]) for k in ("fixed", "learned_stage", "time_in_stage", "run_rate"))
assert MOVED < 1 and f"{MOVED:.2f}" == "0.51"
R2S = R2["r2"]["summary"]
FLAG = [q["flagged"]["pct"] for q in R2["r2"]["quarters"]]
FLAG_LO, FLAG_HI = min(FLAG), max(FLAG)
DROP = R2["drop_flagged"]["summary"]
ORDER = lambda s_: sorted(("fixed", "time_in_stage", "run_rate", "learned_stage"), key=lambda k: s_[k]["mape"])
assert ORDER(DROP) == ORDER(BT) == ORDER(R2S)
V1R = R2["v1_rerun"]["summary"]
SAME = V1R["same_target"]
assert round(SAME["learned_stage"]["mape"]) == 24 and round(SAME["fixed"]["mape"]) == 140
assert SAME["fixed"]["too_high_quarters"] == 8 and SAME["learned_stage"]["too_high_quarters"] == 0
SPLIT = R2["main"]["v1"]["where_wins_come_from"]
assert SPLIT["past_due"] == MW["past_due"] and SPLIT["past_due_bid_close"] == 105 and SPLIT["past_due_start_given"] == 87
H2H = R2["head_to_head"]["v1"]
assert H2H["tis_corrected_closer_than_defaults"] == 4 and H2H["tis_corrected_closer_than_run_rate_corrected"] == 4
IKT = R2["intervals_known_then"]["v1"]
R2P = R2["predictions"]
RUNC_BIAS = CB["run_rate"]["all8"]["bias_pct"]
GENUINE = [100 * (q["where_wins_come_from"]["past_due_start_given"] + q["where_wins_come_from"]["later"])
           / q["where_wins_come_from"]["total"] for q in R2["v1_rerun"]["quarters"]]
GEN_LO, GEN_HI = min(GENUINE), max(GENUINE)
GEN_MAIN = SPLIT["past_due_start_given"] + SPLIT["later"]
assert GEN_MAIN == 104 and GEN_LO > 20 and round(GEN_LO) == 21 and round(GEN_HI) == 32
FLAGW = [100 * q["flagged"]["wins"] / q["pipeline_wins"] for q in R2["r2"]["quarters"]]
FLAGW_LO, FLAGW_HI = min(FLAGW), max(FLAGW)
DROP_HIGH = DROP["fixed"]["too_high_quarters"]
assert DROP_HIGH == 2 and DROP["learned_stage"]["too_high_quarters"] == 0
ALLW = MAIN["actual"]["all_wins"]
NEWW = MAIN["actual"]["wins_created_in_quarter"]
assert ALLW - MA == 212 and NEWW == 205
SWITCH_AT = 7  # of 8 replayed quarters: a coin flip reaches 7 or more less than 1 time in 25
# added later, not declared before it was run: the deals dated outside each quarter, by days at their stage
STALE = json.loads((ROOT / "results" / "stale-deals.json").read_text(encoding="utf-8"))
STALE_MAIN = next(q_ for q_ in STALE["quarters"] if q_["snapshot"] == S["main_snapshot"])
OLD_DEALS, OLD_WINS = STALE_MAIN["await_over_a_year"]["deals"], STALE_MAIN["await_over_a_year"]["won_in_quarter"]
assert (STALE_MAIN["deals"], STALE_MAIN["won_in_quarter"], OLD_DEALS, OLD_WINS) == (11126, 209, 7297, 2)
OLD_FIRST = STALE["quarters"][0]["await_over_a_year"]["deals"]
assert OLD_FIRST == 441 and [q_["snapshot"] for q_ in STALE["quarters"]] == [p_["snapshot"] for p_ in SN]
assert all(q_["deals"] == c_["open:not_dated_in_quarter"]["deals"] + c_["await:not_dated_in_quarter"]["deals"]
           for q_, c_ in zip(STALE["quarters"], A["stage_calibration"]))

# ---------- money and capacity, from declared assumptions ----------
HRS = AS["capacity"]["onboarding_hours_per_start"]["base"]
HRS_RANGE = AS["capacity"]["onboarding_hours_per_start"]["range"]
HPQ = AS["capacity"]["hours_per_person_quarter"]
PQC = AS["capacity"]["person_quarter_cost_cad"]["base"]


def people(wins, h=HRS):
    return wins * h / HPQ


MEAN_ABS_WINS = {k: sum(abs(p["arms"][k]["error"]) for p in SN) / 8 for k in ("fixed", "learned_stage", "time_in_stage", "run_rate")}
MEAN_ABS_WINS["tisc"] = sum(abs(c["time_in_stage"]["error"]) for c in A["corrected"]) / 8
COST_Q = {k: people(v) * PQC for k, v in MEAN_ABS_WINS.items()}
NEED_MAIN = people(MA)
STAFF_LEARNED = people(MF["learned_stage"]["forecast"])
assert round(NEED_MAIN) == 38 and round(STAFF_LEARNED) == 15


def r10k(v):
    return round(v / 10000) * 10000


LEARN_EXTRA = COST_Q["learned_stage"] - COST_Q["fixed"]

# ---------- headline and first screen ----------
# no caveat in the headline, the lead or any section above the limits
assert 45 <= OUT_LO and OUT_HI <= 55  # "about half" of the wins dated outside the quarter
assert sum(abs(p_["arms"]["learned_stage"]["pct_error"]) > abs(p_["arms"]["fixed"]["pct_error"]) for p_ in SN) == 7  # worse in 7 of 8, and on average
H1 = ("On 8 quarters of public tenders, CRM default win chances beat re-learned ones only by making up for wins "
      "dated outside the quarter, so fix close dates first.")
assert len(H1.split()) <= 28 and ":" not in H1 and ";" not in H1, len(H1.split())
for bad in ("learned probabilities", "time in stage", "Learned", "Time in stage", "%"):
    assert bad not in H1
LIMIT = "Tenders stand in for CRM deals, and tender dates for close dates."  # card qualifier; verbatim once, in Limits
DEK = ("Every quarter, a sales leader is asked how many open deals will close. The answer usually comes from the CRM, "
       "the sales team's database of deals. Each deal has a stage, with a win chance, and a close date, when the seller "
       "expects a decision. The forecast adds up the deals with a close date this quarter, at those chances. One common "
       "fix is to re-learn the chances from how past deals closed. I tested both ways on 8 quarters of Canadian "
       "government tenders, each treated as a deal in a supplier's pipeline.")
assert BT["fixed"]["bias_pct"] > 0 and all(p_["arms"]["learned_stage"]["pct_error"] < 0 for p_ in SN)
assert SAME["fixed"]["too_high_quarters"] == 8 and SAME["learned_stage"]["too_high_quarters"] == 0
assert all(p_["arms"]["fixed"]["pct_error"] > 0 for p_ in SN)  # defaults too high every quarter on the declared run


# ---------- takeaway bars ----------
# 8-quarter averages, in wins a quarter: the wins from open deals split by date, and the two forecasts
AVG_IN = sum(w["inside"] for w in A["where_wins_come_from"]) / 8
AVG_OUT = sum(w["total"] - w["inside"] for w in A["where_wins_come_from"]) / 8
AVG_ALL = sum(p_["actual"]["pipeline_wins"] for p_ in SN) / 8
AVG_F = sum(p_["arms"]["fixed"]["forecast"] for p_ in SN) / 8
AVG_L = sum(p_["arms"]["learned_stage"]["forecast"] for p_ in SN) / 8
assert abs(AVG_IN + AVG_OUT - AVG_ALL) < 1e-9
assert (round(AVG_IN), round(AVG_OUT), round(AVG_ALL), round(AVG_F), round(AVG_L)) == (199, 193, 392, 476, 150)
# every quarter has the same sign, so the gap between averages is the average miss in wins
assert round(AVG_F - AVG_ALL) == round(MEAN_ABS_WINS["fixed"]) == 84
assert round(AVG_ALL - AVG_L) == round(MEAN_ABS_WINS["learned_stage"]) == 242
SPAN8 = "a quarter on average over 8 quarters"
BARS = [("Wins from deals dated in the quarter", "", AVG_IN, 0, "counted", "",
         f"Wins from deals open at the quarter's start and dated in it: {round(AVG_IN)} {SPAN8}. Both forecasts count "
         "only these deals."),
        ("Wins from deals dated outside it", "", AVG_OUT, AVG_IN, "not counted", "key",
         f"Wins from deals open at the quarter's start but dated outside it: {round(AVG_OUT)} {SPAN8}. Neither "
         "forecast counts them."),
        ("Forecast at CRM default win chances", "60% and 80% by stage", AVG_F, 0,
         f"{round(AVG_F - AVG_ALL)} too many", "ref",
         f"Forecast at CRM default win chances (60% and 80% by stage): {round(AVG_F)} wins {SPAN8}, "
         f"{round(AVG_F - AVG_ALL)} more than all {round(AVG_ALL)} wins from open deals."),
        ("Forecast at re-learned win chances", "each stage's past closing rate", AVG_L, 0,
         f"{round(AVG_ALL - AVG_L)} too few", "",
         f"Forecast at win chances re-learned from past quarters (each stage's past closing rate): {round(AVG_L)} wins "
         f"{SPAN8}, {round(AVG_ALL - AVG_L)} fewer than all {round(AVG_ALL)} wins from open deals.")]
SCALE = 500.0
assert max(b[2] + b[3] for b in BARS) < SCALE


def bars(fig_id, animated):
    rows = []
    for i, (label, sub, v, start, dir_, kind, text) in enumerate(BARS):
        mark = "bar" + ((" tk-mark" + (" tk-key" if kind == "key" else "")) if animated else "")
        style = (f"width:{v / SCALE * 100:.1f}%" + (f";margin-left:{start / SCALE * 100:.1f}%" if start else "")
                 + (f";--tk-i:{i}" if animated else ""))
        cls = "bar-row pt" + {"key": " is-key", "ref": " is-ref", "after": " is-after", "": ""}[kind]
        val_cls = "bar-value num" + (" tk-key-value" if (animated and kind == "key") else "")
        note = f' <span class="bar-note">{e(sub)}</span>' if sub else ""
        rows.append(f'<li class="{cls}" tabindex="0" data-readout="{e(text)}" title="{e(text)}"><span class="bar-label">'
                    f'{e(label)}{note}</span><span class="bar-track" aria-hidden="true">'
                    f'<span class="{mark}" style="{style}"></span></span><span class="{val_cls}">{round(v)}'
                    f'<span class="bar-dir">{e(dir_)}</span></span></li>')
    return (f'<ol class="bars" id="{fig_id}-bars" data-hover-chart data-readout-default="Each bar is wins a quarter, on '
            f'average over 8 quarters: point at one to read it.">' + "".join(rows) + "</ol>")


CAPTION = ("The defaults' surplus made up for the wins from deals dated outside the quarter, which the re-learned "
           "forecast never counted.")
UNIT = "Wins a quarter from deals open at its start, average of 8 quarters to September 2025"

# ---------- shared page parts ----------
HEAD_LINKS = ('<link rel="icon" href="data:,">'
              '<link rel="preload" href="vendor/viz-design-system/assets/fonts/newsreader-latin-500-normal.woff2" as="font" type="font/woff2" crossorigin>'
              '<link rel="preload" href="vendor/viz-design-system/assets/fonts/public-sans-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>'
              '<link rel="preload" href="vendor/viz-design-system/assets/fonts/public-sans-latin-600-normal.woff2" as="font" type="font/woff2" crossorigin>'
              '<link rel="stylesheet" href="vendor/viz-design-system/tokens.css"><link rel="stylesheet" href="vendor/viz-design-system/kit/kit.css">'
              '<link rel="stylesheet" href="vendor/viz-design-system/kit/takeaway.css"><link rel="stylesheet" href="vendor/viz-design-system/kit/wayfinding.css">')
SCRIPTS = ('<script src="vendor/viz-design-system/kit/kit.js"></script>'
           '<script src="vendor/viz-design-system/kit/takeaway.js"></script>'
           '<script src="vendor/viz-design-system/kit/wayfinding.js" defer></script>')
SITE_HEADER = ('<a class="kit-skip" href="#main">Skip to content</a><header class="site"><div class="kit-wrap site-row">'
               '<p class="site-id"><a class="site-name" href="../">Diogo Travassos</a><span class="site-role">Data '
               'leadership · Analytics · Decision-making</span></p><nav aria-label="Site"><a href="../#studies">Studies</a>'
               '<a href="https://www.linkedin.com/in/diogo-travassos/">LinkedIn</a><a href="mailto:hello@diogotravassos.dev">'
               'Email</a><button class="theme-toggle" type="button" data-theme-toggle>Theme: auto</button></nav></div></header>')
FOOTER = ('<footer class="site"><div class="kit-wrap"><p><span>Public data</span><a href="../#studies">Back to all '
          'studies</a></p></div></footer>')
NEXT_STUDY = ('<nav class="next-study kit-wrap" data-next-study aria-label="Next study"><a href="../#studies">All '
              'studies</a></nav>')


def page(fname, title, desc, body, sections):
    nav = "".join(f'<a href="#{i}">{e(t)}</a>' for i, t in sections)
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            'initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="robots" content="noindex">'
            f'<meta name="description" content="{e(desc)}"><title>{e(title)}</title>{HEAD_LINKS}<style>{CSS}</style>'
            f'{SCRIPTS}</head><body>')
    bar = (f'<div class="kit-section-bar"><nav class="page-nav" aria-label="Page sections">{nav}</nav>'
           '<span class="kit-progress" aria-hidden="true"></span></div>')
    html_ = head + SITE_HEADER + '<main id="main">' + body.replace("{SECTION_BAR}", bar) + "</main>" + FOOTER + "</body></html>\n"
    visible = html_.split("<style>")[0] + html_.split("</style>")[1]
    assert "{" not in visible and "}" not in visible, fname
    (ROOT / fname).write_text(html_, encoding="utf-8")
    print(f"wrote {fname} ({len(html_):,} bytes)")


def hero(h1, piece, limit=None, extra=""):
    lim = f'<p class="limitation"><strong>Main limitation</strong> {e(limit)}</p>' if limit else ""
    return (f'<section class="hero kit-wrap" aria-labelledby="hero-title"><p class="hero-tags"><span class="tag tag-data">'
            f'Public data</span></p><p class="hero-piece">{e(piece)}</p><h1 id="hero-title">{e(h1)}</h1>{lim}{extra}'
            '</section>')


def back_links():
    return ('<p class="links"><a href="index.html">The summary</a><a href="backtest.html">Eight quarters, one at a time</a>'
            '<a href="results.html">All results</a><a href="method.html">Method and checks</a></p>')


# =====================================================================================================================
# Entry page
# =====================================================================================================================
for h in (H1, LIMIT, DEK, CAPTION):
    for ch in ("\u2014", "\u2013"):
        assert ch not in h

WORST_FIXED = BT["fixed"]["worst_abs_pct"]
assert hu(WORST_FIXED) == 50
TOO_HIGH = [p_["arms"]["fixed"]["pct_error"] for p_ in SN]
assert hu(min(TOO_HIGH)) == 3 and hu(max(TOO_HIGH)) == 50
what_to_do = (
    '<section id="do" class="block kit-wrap" aria-labelledby="do-title"><h2 id="do-title">What to do</h2>'
    '<p><strong>Fix close dates, then re-learn the win chances.</strong> Until both are done, keep the CRM\'s default '
    'chances on the pipeline as it stands. They did better here, but by luck. Their optimism made up for wins the '
    'forecast never counted. Re-dating deals under those same chances would push the forecast too high.</p>'
    '</section>')

# the sales calls, from the per-quarter outcomes and the department results on results.html
DEPT_HI = [("National Research Council Canada", 62), ("Parks Canada", 49), ("Fisheries and Oceans Canada", 49)]
for name_, v_ in DEPT_HI:
    assert hu(AC[name_]["win_rate_pct"]) == v_, name_
DEPT_LO = "Shared Services Canada"
assert hu(AC[DEPT_LO]["win_rate_pct"]) == 19 and min(v["win_rate_pct"] for v in AC.values()) == AC[DEPT_LO]["win_rate_pct"]
assert max(v["win_rate_pct"] for v in AC.values()) == AC["National Research Council Canada"]["win_rate_pct"]
assert SAME["fixed"]["mape"] > 100 and SAME["fixed"]["too_high_quarters"] == 8
assert abs(SPLIT["past_due_bid_close"] / NOT_DATED - 0.5) < 0.05
CAL = [c_ for c_ in A["stage_calibration"] if c_["snapshot"] == S["main_snapshot"]][0]
OUT_DEALS = CAL["open:not_dated_in_quarter"]["deals"] + CAL["await:not_dated_in_quarter"]["deals"]
assert OUT_DEALS == 11126 and abs(NOT_DATED - sum(CAL[k_]["deals"] * CAL[k_]["won_in_quarter_pct"] / 100
                                                  for k_ in ("open:not_dated_in_quarter", "await:not_dated_in_quarter"))) < 5
LIVE_DEALS, LIVE_WINS = OUT_DEALS - OLD_DEALS, NOT_DATED - OLD_WINS
assert (LIVE_DEALS, LIVE_WINS) == (3829, 207) and 45 < 100 * LIVE_WINS / MA < 55  # about half
call = (
    '<section id="call" class="block kit-wrap" aria-labelledby="call-title"><h2 id="call-title">Next quarter, for '
    'the revenue team</h2><ul class="notes">'
    '<li><strong>Close out stale deals, and give the live ones a real close date.</strong> Of the open deals dated '
    f'outside the latest quarter, the {OLD_DEALS:,} that had waited over a year for an award gave {OLD_WINS} wins. The '
    f'other {LIVE_DEALS:,} gave {LIVE_WINS}, about half of that quarter\'s wins from open deals.</li>'
    '<li><strong>Check how often a buyer\'s tenders end in an award to anyone before you bid there.</strong> A '
    'tender with no '
    f'award wastes every bid on it. Since August 2022, {pc(AC["National Research Council Canada"]["win_rate_pct"])} of '
    'tenders at the National Research Council ended in a published award, and '
    f'{pc(AC[DEPT_LO]["win_rate_pct"])} at Shared Services Canada. Then weigh your own win rate and bid cost there '
    'before moving bids.</li>'
    '<li><strong>Plan the quarter against a range, not the forecast.</strong> In each of the 8 quarters, the defaults\' '
    f'forecast ran {pc(min(TOO_HIGH))} to {pc(max(TOO_HIGH))} above the wins from open deals. Test any range on your '
    'own past quarters before you plan on it.</li></ul></section>')

assert round(MEAN_ABS_WINS["fixed"]) == 84 and round(MEAN_ABS_WINS["learned_stage"]) == 242
MED_K, Q1_K, Q3_K = round(AM["median_cad"] / 1000), round(AM["q1_cad"] / 1000), round(AM["q3_cad"] / 1000)
assert (MED_K, Q1_K, Q3_K) == (195, 74, 724)
worth = (
    '<section id="worth" class="block kit-wrap" aria-labelledby="worth-title"><h2 id="worth-title">What it is worth</h2>'
    f'<p>Over the 8 quarters, the defaults missed by {round(MEAN_ABS_WINS["fixed"])} wins a quarter on average, and '
    f'the re-learned chances by {round(MEAN_ABS_WINS["learned_stage"])}. A typical win is a contract of about '
    f'CA${MED_K},000.</p></section>')

team = (
    '<section id="team" class="block kit-wrap" aria-labelledby="team-title"><h2 id="team-title">How I would put this to '
    'work with a team</h2><ol class="notes">'
    '<li><strong>Week one, revenue operations.</strong> Export every deal with its stage and close-date history '
    'and the date each win was booked.</li>'
    '<li><strong>Weeks two and three, an analyst.</strong> Replay the last 8 quarters as here, and count the wins from '
    'deals dated outside each quarter.</li>'
    '<li><strong>Week four, the sales leader and finance.</strong> Publish both forecasts until the switch rule below is '
    'met.</li></ol></section>')

numbers = (
    '<section id="numbers" class="block kit-wrap" aria-labelledby="numbers-title"><h2 id="numbers-title">The two '
    'numbers that matter</h2><ol class="notes">'
    f'<li><strong>The miss on all wins from open deals.</strong> Over the 8 quarters, the defaults missed those wins by '
    f'{pc(MAPE["fixed"])} on average, and the re-learned chances by {pc(MAPE["learned_stage"])} on average. The '
    'defaults were too high every quarter, and the re-learned chances too low.</li>'
    f'<li><strong>The miss on the deals each forecast counts.</strong> Over the 8 quarters, the defaults missed the '
    f'wins from deals dated in the quarter by {pc(SAME["fixed"]["mape"])} on average, too high. Over the same 8 '
    f'quarters, the re-learned chances missed them by {pc(SAME["learned_stage"]["mape"])} on average, too low.</li></ol>'
    '<p>The two numbers measure misses on different wins, so they do not conflict.</p></section>')

LEAK_GAP = BT["learned_stage"]["mape"] - LEAK["learned_stage"]["mape"]
assert round(LEAK_GAP) == 9
assert round(RANGE[0]["mape"]) == 16 and round(RANGE[1]["mape"]) == 52
assert 0 < GEN_LO - 20 < 2
OPP_SRC = S["sources"]["opportunities"]
assert (OPP_SRC["opportunities"], OPP_SRC["won"]) == (27589, 10059)
assert RANGE[0]["mape"] < TISC and TISC - RANGE[0]["mape"] < 0.5  # level with the defaults one stage lower
LOW_HIGH = sum(p_["fixed_range"][0]["pct_error"] > 0 for p_ in SN)
assert LOW_HIGH == 2 and SN[0]["fixed_range"][0]["weights"] == {"open_for_bids": 0.4, "awaiting_award": 0.6}
assert hu(FLAGW_LO) == 29 and hu(FLAGW_HI) == 44
change = (
    '<section id="change" class="block kit-wrap" aria-labelledby="change-title"><h2 id="change-title">What would change '
    'the conclusion</h2><ul class="notes">'
    '<li>If under one in five wins from open deals came from deals dated outside the quarter, test re-learned chances '
    'next. Here, leaving out deals dated only by a past bid deadline, it was '
    f'{pc(GEN_LO)} to {pc(GEN_HI)} of the wins from open deals in each of the 8 quarters. The lowest was just above '
    'the line.</li>'
    '<li>If cleaner close dates do not bring your forecast closer within two quarters, dates alone are not the fix. '
    'Test dates and chances one at a time.</li>'
    f'<li>Switch from the defaults only to a forecast that beats them in at least {SWITCH_AT} of your last 8 quarters. '
    f'The best alternative here beat them in {H2H["tis_corrected_closer_than_defaults"]}.</li>'
    '</ul></section>')

limit_sec = (
    '<section id="limit" class="block kit-wrap" aria-labelledby="limit-title"><h2 id="limit-title">Limits</h2>'
    f'<p><strong>{e(LIMIT)}</strong> About half of the wins dated outside the quarter came from tenders with no date '
    'of their own, where a past bid deadline stood in.</p>'
    '<p><strong>A win is a published award, and tenders have no lost stage.</strong> Only '
    f'{OPP_SRC["won"]:,} of the {OPP_SRC["opportunities"]:,} tenders link to an award. The rest stay open unless '
    'cancelled, so deals waiting over a year for an award grew from '
    f'{OLD_FIRST:,} to {OLD_DEALS:,} over the 8 quarters. An award made through a route not published here never '
    'counts, which may be why Shared Services Canada\'s rate is low.</p>'
    '<p><strong>I chose the stage mapping.</strong> I gave the CRM\'s 60% win chance to tenders open for bids, and its '
    '80% to those awaiting an award. One stage either way, the defaults\' average miss over the 8 quarters would be '
    f'{pc(RANGE[0]["mape"])} or {pc(RANGE[1]["mape"])}. One stage lower, they ran low in {8 - LOW_HIGH} of the 8 '
    'quarters.</p>'
    '<p><strong>Some choices came after the results.</strong> Only the first of the two numbers was planned before '
    'them. The other, and every count of wins and deals dated outside the quarter, came after. The one-in-five line '
    'and the 7-of-8 rule are my judgment too.</p>'
    '<p><strong>Notices keep only their last version.</strong> Deals amended later held '
    f'{pc(FLAGW_LO)} to {pc(FLAGW_HI)} of the wins from open deals in each of the 8 quarters. Leaving them out kept the '
    f'forecasts\' order, but the defaults ran too high in only {DROP_HIGH} of the 8.</p>'
    f'<p><strong>Awards are published late.</strong> That adds about {round(LEAK_GAP)} points to the re-learned '
    'chances\' average miss over the 8 quarters. A CRM usually books wins sooner, so its gap would be smaller.</p>'
    '<p><strong>A third forecast came close.</strong> It used how long each deal had sat at its stage, with late '
    f'awards counted. It missed by {pc(TISC)} on average over the 8 quarters, level with the defaults one stage lower, '
    'but I chose that correction after the results.</p>'
    '<p><strong>Few wins carry an amount.</strong> The typical contract is the median of the '
    f'{pc(AM["share_with_amount_pct"])} of wins that carry one. Half of those amounts fall between '
    f'CA${Q1_K},000 and CA${Q3_K},000.</p>'
    '</section>')

details = (
    '<section id="details" class="block kit-wrap" aria-labelledby="details-title"><h2 id="details-title">Detail pages'
    '</h2><ul class="pages">'
    '<li><a href="backtest.html">Eight quarters, one at a time</a>: every forecast by quarter, where re-learned '
    'chances are called learned probabilities.</li>'
    '<li><a href="results.html">All results</a>: every table, buyers included.</li>'
    '<li><a href="method.html">Method and checks</a>: data, bets and downloads.</li>'
    '<li>Related studies: <a href="../marketplace-revenue-forecast/">a driver-based revenue forecast</a> and '
    '<a href="../arr-reconciliation/">one ARR number across systems</a>.</li></ul></section>')

takeaway = (f'<div class="kit-wrap"><figure class="chart takeaway tk-bars" id="takeaway"><figcaption>{e(CAPTION)}'
            f'</figcaption><p class="chart-unit">{e(UNIT)}</p><div class="chart-plot">{bars("takeaway", True)}'
            '</div><p class="takeaway-source">'
            f'{e(DATA_LABEL)}</p></figure></div>')

entry_body = (hero(H1, STUDY_TITLE) + takeaway
              + f'<section class="kit-wrap hero-more" aria-label="The question"><p class="hero-dek">{e(DEK)}</p></section>'
              + "{SECTION_BAR}"
              + what_to_do + call + worth + team + numbers + change + limit_sec + details + NEXT_STUDY)
page("index.html", STUDY_TITLE,
     "How far off is a stage-weighted pipeline forecast? CRM default win chances against chances re-learned from past "
     "quarters, scored on 8 quarters of public tender data.",
     entry_body, [("do", "What to do"), ("call", "Next quarter"), ("worth", "Worth"), ("team", "With a team"),
                  ("numbers", "Two numbers"), ("change", "What would change it"), ("limit", "Limits"),
                  ("details", "Detail pages")])



# =====================================================================================================================
# Follow-up: eight quarters
# =====================================================================================================================
def lines_svg():
    W, H, left, right, top, bot = 640, 300, 60, 16, 14, 54
    lo, hi = -80, 60
    snaps = [p["snapshot"] for p in SN]
    ser = {"fixed": [p["arms"]["fixed"]["pct_error"] for p in SN],
           "learned": [p["arms"]["learned_stage"]["pct_error"] for p in SN],
           "tis": [p["arms"]["time_in_stage"]["pct_error"] for p in SN],
           "tisc": [c["time_in_stage"]["pct_error"] for c in A["corrected"]]}
    assert all(lo <= v <= hi for vs in ser.values() for v in vs)
    names = {"fixed": "CRM default probabilities", "learned": "Learned stage probabilities", "tis": "Time in stage",
             "tisc": "Time in stage, late wins counted"}

    def x(i):
        return left + i / (len(snaps) - 1) * (W - left - right)

    def y(v):
        return top + (hi - v) / (hi - lo) * (H - top - bot)
    out = [f'<svg class="lines" viewBox="0 0 {W} {H}" role="img" aria-labelledby="q-t" data-hover-chart '
           'data-readout-default="Each point is one forecast for one quarter: point at one to read it.">',
           '<title id="q-t">Percent miss of each forecast in each of 8 quarters; above zero is too high, below too low</title>']
    for t in range(lo, hi + 1, 20):
        cls = "zero" if t == 0 else "grid"
        out.append(f'<line class="{cls}" x1="{left}" x2="{W - right}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                   f'<text class="tick" x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end">'
                   f'{(MINUS + str(abs(t))) if t < 0 else ("+" + str(t) if t > 0 else "0")}%</text>')
    for i, s in enumerate(snaps):
        out.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 30}" text-anchor="middle">{qshort(s).split()[0]}</text>'
                   f'<text class="tick" x="{x(i):.1f}" y="{H - 8}" text-anchor="middle">{qshort(s).split()[1]}</text>')
    for k, vs in ser.items():
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vs))
        out.append(f'<polyline class="ser s-{k}" points="{pts}"/>')
    for k, vs in ser.items():
        for i, v in enumerate(vs):
            act = SN[i]["actual"]["pipeline_wins"]
            rd = f"{names[k]}, {qname(snaps[i])}: {spc(v)} against {act} wins."
            out.append(f'<g class="pt" tabindex="0" data-readout="{e(rd)}"><title>{e(rd)}</title>'
                       f'<circle class="m-{k}" cx="{x(i):.1f}" cy="{y(v):.1f}" r="4.5"/></g>')
    out.append("</svg>")
    return "".join(out)


def quarter_table():
    rows = []
    for p, c in zip(SN, A["corrected"]):
        a = p["arms"]
        rows.append(f'<tr><th scope="row">{e(qname(p["snapshot"]))}</th><td class="num">{p["actual"]["pipeline_wins"]}</td>'
                    f'<td class="num">{a["fixed"]["forecast"]:.0f} ({spc(a["fixed"]["pct_error"])})</td>'
                    f'<td class="num">{a["learned_stage"]["forecast"]:.0f} ({spc(a["learned_stage"]["pct_error"])})</td>'
                    f'<td class="num">{a["time_in_stage"]["forecast"]:.0f} ({spc(a["time_in_stage"]["pct_error"])})</td>'
                    f'<td class="num">{a["run_rate"]["forecast"]:.0f} ({spc(a["run_rate"]["pct_error"])})</td>'
                    f'<td class="num">{c["time_in_stage"]["forecast"]:.0f} ({spc(c["time_in_stage"]["pct_error"])})</td></tr>')
    rows.append(f'<tr class="key"><th scope="row">Average miss</th><td class="num"></td>'
                f'<td class="num">{pc(MAPE["fixed"], 1)}</td><td class="num">{pc(MAPE["learned_stage"], 1)}</td>'
                f'<td class="num">{pc(MAPE["time_in_stage"], 1)}</td><td class="num">{pc(MAPE["run_rate"], 1)}</td>'
                f'<td class="num">{pc(TISC, 1)}</td></tr>')
    return ('<div class="table-scroll" role="region" aria-label="Forecasts by quarter" tabindex="0"><table class="data">'
            '<caption class="visually-hidden">Forecasts by quarter</caption><thead><tr><th scope="col">Quarter</th>'
            '<th scope="col" class="num">Wins from the pipeline</th><th scope="col" class="num">CRM defaults</th>'
            '<th scope="col" class="num">Learned probabilities</th><th scope="col" class="num">Time in stage</th>'
            '<th scope="col" class="num">Last quarter\'s wins</th><th scope="col" class="num">Time in stage, late wins '
            'counted</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


E7 = S["backtest"]["earlier7"]
IKT_MAIN = IKT["time_in_stage_corrected"]["quarters"][-1]
assert IKT_MAIN["snapshot"] == S["main_snapshot"]
BH1 = (f"Forecast at the start of each of 8 quarters, the CRM defaults missed by {pc(MAPE['fixed'])} on average and "
       f"learned probabilities by {pc(MAPE['learned_stage'])}, on public tender data.")
assert len(BH1.split()) <= 30
bt_body = (
    hero(BH1, "Eight quarters, one at a time") + "{SECTION_BAR}" +
    '<section id="what" class="block kit-wrap" aria-labelledby="what-title"><h2 id="what-title">What this adds</h2>'
    f'<p>One quarter can flatter a forecast. In July to September 2025, the latest quarter scored, the CRM defaults '
    f'called {MF["fixed"]["forecast"]:.0f} wins and {MA} came, a miss of {spc(MF["fixed"]["pct_error"])}. Run from the '
    f'start of each of the 7 quarters before it as well, the defaults were too high '
    f'every time, by {pc(min(p["arms"]["fixed"]["pct_error"] for p in SN))} to '
    f'{pc(max(p["arms"]["fixed"]["pct_error"] for p in SN))}, and {pc(MAPE["fixed"])} on average.</p>'
    f'<p>The defaults were the closest in {FIXED_BEST} of 8 quarters. Learned '
    f'probabilities were too low every time, by {pc(min(abs(p["arms"]["learned_stage"]["pct_error"]) for p in SN))} to '
    f'{pc(max(abs(p["arms"]["learned_stage"]["pct_error"]) for p in SN))}. Time in stage was too low every time too, '
    f'{pc(MAPE["time_in_stage"])} on average, and last quarter\'s wins missed by {pc(MAPE["run_rate"])}. On the 7 earlier '
    f'quarters alone the averages were {pc(E7["fixed"]["mape"])}, {pc(E7["learned_stage"]["mape"])}, '
    f'{pc(E7["time_in_stage"]["mape"])} and {pc(E7["run_rate"]["mape"])}.</p>'
    f'<p>Why the forecasts that learn from history all fall short: they learn from wins on record at the quarter\'s '
    f'start, and many recent wins were not on record yet. Given every win known today, a backtest that ignores when wins '
    f'were recorded, time in stage would have missed by only {pc(LEAK["time_in_stage"]["mape"])} and last quarter\'s wins '
    f'by {pc(LEAK["run_rate"]["mape"])}. No team could have had those numbers at the time.</p>'
    f'<p>A correction scales each past quarter\'s wins by the share that would have been on '
    f'record by then, using only older wins. Time in stage then missed by {pc(TISC)} on average and last quarter\'s wins '
    f'by {pc(RUNC)}. Quarter by quarter, '
    f'time in stage with late wins counted was closer than the defaults in {H2H["tis_corrected_closer_than_defaults"]} of 8 '
    f'and closer than last quarter\'s wins with the same count in {H2H["tis_corrected_closer_than_run_rate_corrected"]} '
    'of 8, so these 8 quarters cannot tell the three apart.</p>'
    f'<p>Why the defaults look good. Over the 8 quarters, scored only on the wins from deals dated in the quarter, the '
    f'only deals they count, the defaults were too high every time, by {pc(SAME["fixed"]["mape"])} on average. Over the '
    f'same 8 quarters, learned probabilities missed those wins by {pc(SAME["learned_stage"]["mape"])} on average, too '
    'low every time. These misses are on different wins from the averages above, so they do not conflict. The '
    'overrating fills in for the wins from deals dated outside the quarter, '
    f'{pc(OUT_LO)} to {pc(OUT_HI)} of the wins from open deals in each of the 8 quarters.</p>'
    f'<p>Ranges did not hold. An 80% range from each deal\'s odds covered the actual count in {COV["fixed"]} of 8 '
    f'quarters for the defaults and {COV["time_in_stage"]} for time in stage. The data cannot say why: the forecasts are biased, the defaults count fewer deals than they '
    f'are scored on, the odds are estimates treated as known, and deals may move together. '
    f'A range from the earlier quarters\' misses covered '
    f'{PMI["time_in_stage_corrected"]["covered"]} of {PMI["time_in_stage_corrected"]["of"]}, but those misses were '
    f'scored with wins published later. Scored with only the wins published by each forecast date, the same range covered '
    f'{IKT["time_in_stage_corrected"]["covered"]} of {IKT["time_in_stage_corrected"]["of"]} for time in stage with late '
    f'wins counted and {IKT["fixed"]["covered"]} of {IKT["fixed"]["of"]} for the defaults. '
    f'For the latest quarter it ran from {IKT_MAIN["lo80"]:.0f} to '
    f'{IKT_MAIN["hi80"]:.0f} around a forecast of {IKT_MAIN["forecast"]:.0f}.</p></section>'
    '<section id="quarters" class="block kit-wrap" aria-labelledby="quarters-title"><h2 id="quarters-title">Every '
    'quarter</h2><figure class="chart" id="quarters-fig"><figcaption>Forecasts from learned probabilities came in too low in '
    'every quarter, and those from the CRM defaults too high in every quarter.</figcaption><p class="chart-unit">Percent miss of the wins that '
    'came from the pipeline, each forecast made at the quarter\'s start</p><p class="key">'
    '<span><i class="sw sw-fixed"></i>CRM defaults</span><span><i class="sw sw-learned"></i>Learned probabilities</span>'
    '<span><i class="sw sw-tis"></i>Time in stage</span><span><i class="sw sw-tisc"></i>Time in stage, late wins counted'
    '</span></p>'
    f'<div class="chart-plot">{lines_svg()}</div></figure>'
    f'<p>Forecast and, in brackets, its miss against the wins that came from the pipeline.</p>{quarter_table()}</section>'
    '<section id="limits" class="block kit-wrap" aria-labelledby="limits-title"><h2 id="limits-title">Limits</h2>'
    f'<p>Each forecast used the awards as published by its quarter\'s start, but tender fields as last amended. '
    f'Rebuilding those fields moved no average miss by more than {MOVED:.2f} points.</p>'
    f'<p>With the deals whose notices were amended later left out, the defaults came in too high in only {DROP_HIGH} of '
    'the 8 quarters, so their direction is not firm.</p>'
    '<p>The defaults\' accuracy depends on the stage mapping. One stage lower on each side (40% and 60%), they missed '
    f'by {pc(RANGE[0]["mape"])} on average over the 8 quarters, and ran low in {8 - LOW_HIGH} of them.</p>'
    '<p>Each range from earlier quarters\' misses rests on only 3 to 7 of them, so it is wide. That the time in '
    'stage range covered 5 of 5 shows it was not too narrow, not that it is well sized.</p>'
    '<p>Added after the results: the late-wins correction, with its line in the chart, the miss on the deals dated in '
    'the quarter, and the range from earlier quarters\' misses.</p></section>'
    f'<section class="block kit-wrap">{back_links()}</section>' + NEXT_STUDY)
page("backtest.html", "Eight quarters, one at a time: " + STUDY_TITLE,
     "Pipeline forecasts made at the start of each of 8 quarters of public tender data, scored against what closed.",
     bt_body, [("what", "What this adds"), ("quarters", "Every quarter"), ("limits", "Limits")])


# =====================================================================================================================
# All results
# =====================================================================================================================
def tr(cells, head=False, key=False):
    tag = "th" if head else "td"
    first = f'<th scope="{"col" if head else "row"}">{cells[0]}</th>'
    rest = "".join(f'<{tag}{" scope=\"col\"" if head else ""} class="num">{c}</{tag}>' for c in cells[1:])
    return f'<tr{" class=\"key\"" if key else ""}>{first}{rest}</tr>'


def table(label, header, rows):
    return (f'<div class="table-scroll" role="region" aria-label="{e(label)}" tabindex="0"><table class="data">'
            f'<caption class="visually-hidden">{e(label)}</caption><thead>{tr(header, head=True)}</thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")


wins_rows = [tr([e(qname(w["snapshot"])), w["total"], w["inside"], w["past_due"], w["later"],
                 pc(100 * (w["total"] - w["inside"]) / w["total"])]) for w in A["where_wins_come_from"]]
cal_rows = []
for key_, lab in (("open:dated_in_quarter", "Open for bids, dated in the quarter"),
                  ("open:not_dated_in_quarter", "Open for bids, not dated in it"),
                  ("await:dated_in_quarter", "Closed for bids, dated in the quarter"),
                  ("await:not_dated_in_quarter", "Closed for bids, not dated in it")):
    c = CAL[key_]
    default = "60%" if key_.startswith("open") else "80%"
    cal_rows.append(tr([e(lab), n0(c["deals"]), default if "not" not in key_ else "not counted",
                        pc(c["won_in_quarter_pct"], 1), pc(c["ever_won_pct"], 1)]))
ch_order = ["Open request for proposal", "Against a supply arrangement", "Standing offer request",
            "Advance contract award notice", "Other"]
CH_NAME = {"Open request for proposal": "Open bids (request for proposal)",
           "Against a supply arrangement": "Pre-qualified supplier pool (supply arrangement)",
           "Standing offer request": "Standing offer request",
           "Advance contract award notice": "Supplier named in advance (advance award notice)",
           "Other": "Other notice types"}
ch_rows = [tr([e(CH_NAME[k]), n0(CH[k]["opportunities"]), pc(CH[k]["win_rate_pct"], 1), f'{CH[k]["median_days_to_win"]:.0f}',
               pc(CH[k]["cancelled_pct"], 1)]) for k in ch_order]
ac_rows = [tr([e(k), n0(v["opportunities"]), pc(v["win_rate_pct"], 1), f'{v["median_days_to_win"]:.0f}',
               f'{v["wins_per_quarter"]:.0f}']) for k, v in AC.items()]
leak_rows = [tr([e(n), pc(BT[k]["mape"], 1), pc(LEAK[k]["mape"], 1)]) for k, n in
             (("learned_stage", "Learned probabilities"), ("time_in_stage", "Time in stage"), ("run_rate", "Last quarter's wins"))]
pmi_rows = [tr([e(qname(q["snapshot"])), f'{q["forecast"]:.0f}', f'{q["lo80"]:.0f} to {q["hi80"]:.0f}', q["actual"],
                "yes" if q["covered"] else "no"]) for q in PMI["time_in_stage_corrected"]["quarters"]]
ikt_rows = [tr([e(qname(q["snapshot"])), f'{q["forecast"]:.0f}', f'{q["lo80"]:.0f} to {q["hi80"]:.0f}', q["actual"],
                "yes" if q["covered"] else "no"]) for q in IKT["time_in_stage_corrected"]["quarters"]]
assert len(PMI["time_in_stage_corrected"]["quarters"]) == 5 and PMI["time_in_stage_corrected"]["quarters"][0]["snapshot"] == SN[3]["snapshot"]
V1Q = R2["v1_rerun"]["quarters"]
split_rows = [tr([e(qname(q["snapshot"])), q["where_wins_come_from"]["past_due"], q["where_wins_come_from"]["past_due_start_given"],
                  q["where_wins_come_from"]["past_due_bid_close"]]) for q in V1Q]
same_rows = [tr([e(qname(q["snapshot"])), q["same_target"]["wins_from_dated_deals"],
                 f'{q["same_target"]["fixed"]["forecast"]:.0f} ({spc(q["same_target"]["fixed"]["pct_error"])})',
                 f'{q["same_target"]["learned_stage"]["forecast"]:.0f} ({spc(q["same_target"]["learned_stage"]["pct_error"])})']) for q in V1Q]
same_rows.append(tr(["Average miss", "", pc(SAME["fixed"]["mape"], 1), pc(SAME["learned_stage"]["mape"], 1)], key=True))
RH1 = (f"Every forecast and quarter: the CRM defaults were closest in {FIXED_BEST} of 8 quarters and learned "
       "probabilities too low in all 8, on public tender data.")
assert len(RH1.split()) <= 30
res_body = (
    hero(RH1, "All results") + "{SECTION_BAR}" +
    '<section id="forecasts" class="block kit-wrap" aria-labelledby="forecasts-title"><h2 id="forecasts-title">The '
    'forecasts</h2><p>Each forecast counts the wins expected from deals open at the quarter\'s start. The table is in '
    '<a href="backtest.html#quarters">the eight-quarter page</a>; the averages are below, with the two neighbouring sets '
    'of default probabilities.</p>' +
    table("Average miss by forecast", ["Forecast", "Average miss", "Average signed miss", "Closest in quarters"],
          [tr(["CRM defaults, 60% and 80%", pc(MAPE["fixed"], 1), spc(BT["fixed"]["bias_pct"], 1), BT["fixed"]["best_in_quarters"]]),
           tr(["CRM defaults one stage lower, 40% and 60%", pc(RANGE[0]["mape"], 1), "", ""]),
           tr(["CRM defaults one stage higher, 80% and 90%", pc(RANGE[1]["mape"], 1), "", ""]),
           tr(["Learned probabilities", pc(MAPE["learned_stage"], 1), spc(BT["learned_stage"]["bias_pct"], 1), BT["learned_stage"]["best_in_quarters"]]),
           tr(["Time in stage", pc(MAPE["time_in_stage"], 1), spc(BT["time_in_stage"]["bias_pct"], 1), BT["time_in_stage"]["best_in_quarters"]]),
           tr(["Last quarter's wins", pc(MAPE["run_rate"], 1), spc(BT["run_rate"]["bias_pct"], 1), BT["run_rate"]["best_in_quarters"]]),
           tr(["Time in stage, late wins counted (added after the results)", pc(TISC, 1), spc(CB["time_in_stage"]["all8"]["bias_pct"], 1), ""]),
           tr(["Last quarter's wins, late wins counted (added after the results)", pc(RUNC, 1), spc(CB["run_rate"]["all8"]["bias_pct"], 1), ""])]) +
    '<h3>What knowing every win would have done</h3><p>The same forecasts given every win on record today, which no team '
    'had at the quarter\'s start. The gap is what a backtest that ignores recording dates would overstate.</p>' +
    table("Average miss with and without later records", ["Forecast", "With what was on record", "With every win known"], leak_rows) +
    '</section>'
    '<section id="where" class="block kit-wrap" aria-labelledby="where-title"><h2 id="where-title">Where the wins came '
    'from</h2><p>Added after the results. Each quarter\'s wins from the pipeline, split by where the deal\'s expected '
    'close date sat at the quarter\'s start: inside the quarter, already past, or later.</p>' +
    table("Where the wins came from", ["Quarter", "Wins", "Dated in the quarter", "Past due", "Dated later",
                                       "Not dated in the quarter"], wins_rows) +
    f'<p>How the default probabilities compare with what happened, for deals open in {qname(S["main_snapshot"])}. '
    f'{n0(AS_["deals"])} deals had closed for bids with no award on record and were dated outside the quarter; each '
    f'was won in the quarter {pc(AS_["won_in_quarter_pct"], 1)} of the time, yet together they gave {AWAIT_OUT_WINS} of '
    f'the {MA} wins.</p>' +
    table("Default probabilities against outcomes", ["Deals at the quarter's start", "Deals", "Default probability",
                                                      "Won in the quarter", "Won by the end of the data"], cal_rows) +
    '<p>Added after the results. A past-due deal either had a promised contract start that slipped, or gave no start date, so its '
    'close date is the bid closing date, which passes while the award is pending.</p>' +
    table("Past-due wins by kind of date", ["Quarter", "Past-due wins", "Promised start slipped", "No start date given"],
          split_rows) +
    '<p>Added after the results. The two forecasts that count only the deals dated in the quarter, scored against the wins from those '
    'deals alone.</p>' +
    table("Forecasts on the deals they count", ["Quarter", "Wins from deals dated in the quarter", "CRM defaults",
                                                 "Learned probabilities"], same_rows) +
    '</section>'
    '<section id="golive" class="block kit-wrap" aria-labelledby="golive-title"><h2 id="golive-title">From signed to live'
    f'</h2><p>For {n0(GL["with_start"])} of the {n0(GL["wins"])} wins awarded from August 2022 to September 2025 with a '
    f'contract start on record: the median start came {GL["median_days"]:.0f} days after the award. '
    f'{pc(GL["share_same_day_pct"], 1)} started on the award day, {pc(GL["share_before_award_pct"], 1)} before it, which '
    f'means the paperwork followed the work, and {pc(GL["share_30plus_pct"], 1)} started 30 or more days after. For '
    f'{n0(GL["with_expected"])} wins with an expected start on the tender, {pc(GL["slip_share_within_7_pct"], 1)} started '
    f'within a week of it, {pc(GL["slip_share_30plus_late_pct"], 1)} 30 or more days late and '
    f'{pc(GL["slip_share_30plus_early_pct"], 1)} 30 or more days early. The award itself was published a median '
    f'{GL["publish_lag_median_days"]:.0f} days after it was made, and {pc(GL["publish_lag_share_90plus_pct"], 1)} came 90 '
    'or more days after.</p></section>'
    '<section id="channels" class="block kit-wrap" aria-labelledby="channels-title"><h2 id="channels-title">Channels and '
    f'accounts</h2><p>Tenders published from August 2022 to June 2025 ({n0(OV["cohort"])}, of which '
    f'{pc(OV["win_rate_pct"], 1)} ended in an award by the end of the data). A pre-qualified supplier pool stands in for '
    'a partner channel, and a supplier named in advance for a referral. Days count from publication to award. A '
    'tender that ended in an award was won by some supplier, so this is the buyer\'s award rate, not one supplier\'s '
    'win rate.</p>' +
    table("By channel", ["Channel", "Tenders", "Ended in an award", "Median days to award", "Cancelled"], ch_rows) +
    '<p>The 8 largest buying departments stand in for accounts. The data names no sales reps, so the department is the '
    'nearest unit of productivity. A low share can also mean awards made through a route that is not published here.</p>' +
    table("By department", ["Department", "Tenders", "Ended in an award", "Median days to award", "Awards a quarter"], ac_rows) +
    '</section>'
    '<section id="ranges" class="block kit-wrap" aria-labelledby="ranges-title"><h2 id="ranges-title">Ranges</h2>'
    f'<p>An 80% range from each deal\'s own odds covered the actual count in {COV["fixed"]} of 8 quarters for the defaults, '
    f'{COV["learned_stage"]} for learned probabilities and {COV["time_in_stage"]} for time in stage. Added after the results, '
    'a range from the earlier quarters\' misses of time in stage with late wins counted, from the fourth quarter on. '
    'The first table scores those earlier misses with every win known today; the other, added later, with only the wins '
    'published by each forecast date, which is what a team would have had.</p>' +
    table("Ranges from earlier misses", ["Quarter", "Forecast", "80% range", "Wins", "Covered"], pmi_rows) +
    table("Ranges from earlier misses as known then", ["Quarter", "Forecast", "80% range", "Wins", "Covered"], ikt_rows) +
    '</section>'
    '<section id="amounts" class="block kit-wrap" aria-labelledby="amounts-title"><h2 id="amounts-title">Amounts</h2>'
    f'<p>Only {pc(AM["share_with_amount_pct"], 1)} of wins carry a usable amount in Canadian dollars; the rest are blank, '
    f'zero or one dollar. That is why every forecast here counts wins, not dollars. Among wins with an amount, the median '
    f'was {cad(AM["median_cad"])} and the middle half ran from {cad(AM["q1_cad"])} to {cad(AM["q3_cad"])}.</p></section>'
    f'<section class="block kit-wrap">{back_links()}</section>' + NEXT_STUDY)
page("results.html", "All results: " + STUDY_TITLE,
     "Every pipeline forecast and quarter, where the wins came from, go-live lags, channels and departments, on public "
     "tender data.", res_body,
     [("forecasts", "Forecasts"), ("where", "Where wins came from"), ("golive", "Signed to live"),
      ("channels", "Channels and accounts"), ("ranges", "Ranges"), ("amounts", "Amounts")])


# =====================================================================================================================
# Method and checks
# =====================================================================================================================
PLAIN_PRED = {
    "P1": "The defaults forecast the latest quarter more than 40% too high.",
    "P2": "Learned probabilities cut the latest quarter's miss to under half of the defaults' miss.",
    "P3": "Over the 8 quarters, time in stage misses by less on average than learned probabilities.",
    "P4": "Over the 8 quarters, learned probabilities and time in stage are both too low on average.",
    "P5": "Given every win known today, time in stage looks at least 5 points better than it could have at the time.",
    "P6": "In a typical quarter (the median of the 8), at least 30% of the wins come from deals created after it began.",
    "P7": "Time in stage misses by less on average than last quarter's wins.",
    "P8": "Time in stage's 80% range covers the actual count in at most 4 of the 8 quarters."}
assert set(PLAIN_PRED) == set(PREDS)
pred_items = "".join(f'<li><strong>{"Held" if v["held"] else "Missed"}.</strong> {e(PLAIN_PRED[k])}</li>'
                     for k, v in PREDS.items())
R2_PLAIN = {
    "R1": f"Rebuilt from the notices published before each quarter, the defaults' average miss stays within 5 points of "
          f"{pc(MAPE['fixed'], 1)} and stays the lowest of the four.",
    "R2": "Deals amended after the latest quarter's start are under 20% of its open deals.",
    "R3": "Scored on the deals they count, learned probabilities miss by less than the defaults.",
    "R4": "At least half of the latest quarter's past-due wins gave no contract start date.",
    "R5": "A range from earlier misses, scored with only the wins published by then, covers at most 3 of 5 quarters."}
R2_OBS = {"R1": f"{pc(R2S['fixed']['mape'], 1)}, still the lowest",
          "R2": f"{pc(R2P['R2']['observed']['pct'], 1)}",
          "R3": f"{pc(R2S['same_target']['learned_stage']['mape'], 1)} against {pc(R2S['same_target']['fixed']['mape'], 1)}",
          "R4": f"{R2P['R4']['observed']['past_due_bid_close']} of {R2P['R4']['observed']['past_due']}",
          "R5": f"{R2['intervals_known_then']['r2']['time_in_stage_corrected']['covered']} of 5"}
r2_items = "".join(f'<li><strong>{"Held" if R2P[k]["held"] else "Missed"}.</strong> {e(R2_PLAIN[k])} Result: {e(R2_OBS[k])}.</li>'
                   for k in R2_PLAIN)
MH1 = (f"Four pipeline forecasts of a quarter's wins on {n0(OPPS)} public tenders, each made at the quarter's start "
       "and scored against the wins that followed.")
assert len(MH1.split()) <= 30
meth_body = (
    hero(MH1, "Method and checks") + "{SECTION_BAR}" +
    '<section id="plain" class="block kit-wrap" aria-labelledby="plain-title"><h2 id="plain-title">In plain words</h2>'
    '<p>Every quarter a sales leader is asked how many deals will close. The usual answer comes from the CRM. Each open '
    'deal sits at a stage, each stage carries a probability, and the deals dated to close this quarter are added up at '
    'those odds. Finance plans hiring and onboarding on that number.</p>'
    '<p>A company\'s CRM is private, so this study uses a public pipeline that works the same way. The Government of '
    'Canada publishes every federal tender with its dates, and every contract award. A supplier that sells to government '
    'watches exactly this pipeline. A tender is a deal, the buying department is the account, the award is the signed '
    'deal and the contract start is go-live.</p>'
    '<dl class="glossary"><dt>Pipeline</dt><dd>The deals open at a given date.</dd><dt>Stage probability</dt><dd>The chance '
    'a CRM gives a deal at each step of the sale. HubSpot\'s default pipeline uses 20%, 40%, 60%, 80% and 90%.</dd>'
    '<dt>Close date</dt><dd>The date a deal is expected to close; here the tender\'s expected contract start, or its bid '
    'closing date when none is given.</dd><dt>Time in stage</dt><dd>How long a deal has sat at its current step.</dd>'
    '<dt>Win</dt><dd>A tender with a published contract award. A tender with no linked award counts as not won.</dd><dt>Backtest</dt><dd>Making the forecast as it would '
    'have been made at a past date, then scoring it against what happened.</dd><dt>On record</dt><dd>Published before the '
    'date the forecast is made. A win made but not yet published is not on record.</dd><dt>Average miss</dt><dd>The gap '
    'between forecast and wins as a percent of the wins, averaged over quarters.</dd></dl></section>'
    '<section id="data" class="block kit-wrap" aria-labelledby="data-title"><h2 id="data-title">Data</h2>'
    f'<p>CanadaBuys open data: {n0(SRC["rows"]["tender_notices"])} tender notices published from August 2022, and '
    f'{n0(SRC["rows"]["award_rows"])} award notice rows, joined on the solicitation number. Requests for information are '
    f'left out, and notices sharing a solicitation number are one deal, which leaves {n0(OPPS)} deals. Contact, supplier '
    'and address fields are never loaded. The data runs to November 2026, and the latest quarter scored ends in September '
    '2025, because about one award in five is published 90 or more days late and the scored quarters need their wins on '
    'record. Contains information licensed under the Open Government Licence (Canada).</p>'
    '<p>The table is shaped like a CRM\'s opportunity object: one row per deal with its account, channel, created date, '
    'stage dates, expected close date, won flag and date, amount and go-live date. In Salesforce terms, the stage is '
    'StageName, its probability is Probability and the won flag is IsWon. Three defects of CRM data show up here as in any '
    f'CRM: amounts missing on {pc(100 - AM["share_with_amount_pct"])} of wins, wins booked long after they happened, and '
    'deals that stay open long after anyone expects them to close.</p></section>'
    '<section id="how" class="block kit-wrap" aria-labelledby="how-title"><h2 id="how-title">How the forecasts work</h2>'
    '<p>At the start of each quarter, every deal is put in a stage from what was published by then: open for bids until '
    'its closing date, then closed for bids until an award or a cancellation is on record. Every forecast counts the '
    'wins in the quarter from those deals.</p><ul class="notes">'
    '<li><strong>CRM defaults.</strong> Fixed weights mapped from two CRM stages: deals whose close date falls in the '
    'quarter, at 60% if open for bids and 80% if closed for bids, the probabilities of HubSpot\'s "Presentation '
    'scheduled" and "Decision maker bought-in". The mapping is a choice; the neighbouring stages, 40% and 60% or 80% and '
    '90%, are shown as a range. These are chances of ever winning, scored here as wins within the quarter.</li>'
    '<li><strong>Learned probabilities.</strong> The same deals, each stage at the share of such deals that won within '
    'the quarter over the 4 previous quarters, counting only wins on record.</li>'
    '<li><strong>Time in stage.</strong> Every open deal, at the share of deals of the same stage and the same age (0 to '
    '14 days, 15 to 30, 31 to 60, 61 to 120, 121 to 365, over 365) that won within a quarter over the 4 previous '
    'quarters, counting only wins on record. An age group with fewer than 20 past deals uses its stage\'s share.</li>'
    '<li><strong>Last quarter\'s wins.</strong> The wins on record from the previous quarter\'s pipeline.</li>'
    '<li><strong>Late wins counted</strong> (added after the results). Each past quarter\'s wins divided by the share of '
    'wins that would have been on record by the forecast date, estimated from wins made one to two years earlier.</li>'
    '</ul><p>Scores: the miss as a percent of the wins that came from the pipeline, averaged over the 8 quarters; ranges '
    'at 80% from treating deals as independent. The latest quarter, July to September 2025, was the main run; the other '
    '7 quarters are the backtest that followed.</p></section>'
    '<section id="declared" class="block kit-wrap" aria-labelledby="declared-title"><h2 id="declared-title">Declared '
    'before the run, and after</h2>'
    f'<p>The design, the forecasts, the stages, the quarters and these predictions were written down before any forecast was '
    f'computed, after a first look at the files: row counts, the share of tenders with an award, about 40%, the spread '
    f'of lags and the missing amounts. {N_HELD} of {len(PREDS)} predictions held.</p>'
    f'<p>The expected finding was that the defaults over-forecast widely and learned probabilities fix most of it. The '
    f'opposite was that the defaults land within 15%, or learned probabilities do no better. The defaults missed the main '
    f'quarter by {spc(MF["fixed"]["pct_error"])}, so the opposite held there.</p><ul class="notes">{pred_items}</ul>'
    '<p>Added after the results, and written down before they were run: where the wins came from, the '
    'late-wins correction, ranges from earlier misses, and an onboarding plan, whose figures stay in the results files. Nothing declared before the run was changed.'
    '</p></section>'
    '<section id="changes" class="block kit-wrap" aria-labelledby="changes-title"><h2 id="changes-title">Changes after '
    'the results</h2>'
    '<p>The further changes below and their bets were written down before they were run. The declared results above '
    'are untouched and still reported.</p>'
    '<ul class="notes">'
    f'<li><strong>Notices as known then.</strong> The tender file holds each notice only as last amended, and the first '
    f'run built each deal once from all its notices, so a quarter could see closing dates and start dates published or '
    f'amended later. Every quarter was rebuilt from the notices published before it. No average miss moved by more than '
    f'{MOVED:.2f} points, so the results keep the first-run numbers, as declared beforehand. {pc(FLAG_LO)} to {pc(FLAG_HI)} of the '
    f'open deals, holding {pc(FLAGW_LO)} to {pc(FLAGW_HI)} of the wins, had a notice amended after the quarter\'s start, '
    f'whose earlier values are lost. Leaving them out moved '
    f'learned probabilities to {pc(DROP["learned_stage"]["mape"])}, the defaults to {pc(DROP["fixed"]["mape"])} and time '
    f'in stage with late wins counted to {pc(DROP["corrected"]["time_in_stage"]["mape"])}, with the order unchanged, but '
    f'the defaults then ran too high in only {DROP_HIGH} of 8 quarters. One '
    'solicitation number, "N/A", had merged three unrelated tenders and was dropped.</li>'
    '<li><strong>Same target.</strong> The defaults and learned probabilities scored on the deals they count. '
    '<strong>Past due, split.</strong> Slipped start dates apart from bid closing dates standing in. <strong>Ranges as '
    'known then.</strong> Earlier misses scored with only the wins published by the forecast date. <strong>Head to '
    'head.</strong> Quarters in which time in stage with late wins counted beat the defaults.</li></ul>'
    f'<p>The bets, written before the run, and their results. They were scored on the rebuilt notices, so their figures '
    f'differ slightly from the first-run figures in the results.</p><ul class="notes">{r2_items}</ul>'
    '<p>Two more came later, and were not written down before they were run.</p><ul class="notes">'
    '<li><strong>The age of the deals dated outside the quarter.</strong> Tenders have no lost stage, so these deals '
    f'pile up. At the latest quarter\'s start, {OLD_DEALS:,} of the {OUT_DEALS:,} had waited over a year for an '
    f'award, and they gave {OLD_WINS} of the {NOT_DATED} wins from those deals in the quarter.</li>'
    '<li><strong>Dashes in the shipped tables.</strong> 33 solicitation numbers and 6 buyer names held an en or em '
    'dash, and each is now a hyphen in both tables. No two values merged, and the three runs give the same results '
    'files, byte for byte, on the tables before and after.</li></ul></section>'
    '<section id="wrong" class="block kit-wrap" aria-labelledby="wrong-title"><h2 id="wrong-title">What went wrong or '
    'was missed</h2><ul class="notes">'
    '<li><strong>The design treated the probabilities as the problem.</strong> Two of the predictions assumed the defaults '
    'were too high and that learning them would fix the forecast. They were too high, but the close-date rule hid about '
    'half the wins: about one in four for real, the rest because bid closing dates stood in for close dates. So '
    'learning them made the forecast worse.</li>'
    '<li><strong>Late records pull every learned forecast down.</strong> Learning from wins on record at the time is the '
    'only honest backtest, and it is biased low whenever wins are booked late. The design measured this but did not '
    'correct it; the correction came after the results.</li>'
    '<li><strong>Ranges were far too narrow.</strong> Treating deals as independent ignores that a whole quarter can run '
    'hot or cold. The ranges covered at most 1 quarter in 8.</li>'
    '<li><strong>No reps and few amounts.</strong> The data names no sales reps, so productivity is by department, and '
    'most wins carry no usable amount, so the forecasts count wins rather than dollars.</li>'
    '<li><strong>Earliest quarters have thin history.</strong> The data starts in August 2022, so the first quarters '
    'scored learn from a pipeline only a few months old; the late-wins correction there rests on '
    f'{A["completeness"][0]["reference_wins"]} older wins.</li></ul></section>'
    '<section id="checks" class="block kit-wrap" aria-labelledby="checks-title"><h2 id="checks-title">Checks</h2>'
    '<ul class="notes"><li>Tests on small made-up pipelines check every stage rule, that a win not yet on record keeps its '
    'deal open, that a cancelled deal leaves the pipeline the day after its notice, the age groups and the quarter '
    'arithmetic, and that the opportunity table carries no contact, supplier or address field.</li>'
    '<li>With the late-wins option off, the forecasts give exactly the declared results.</li>'
    '<li>Rebuilding the opportunity table from the one-row-per-notice file gives back every deal, first publication date, '
    'closing date and notice count of the table used for the declared run.</li>'
    '<li>Given the original table, the forecasts built from notices as known then give exactly the declared '
    'results.</li></ul></section>'
    '<section id="files" class="block kit-wrap" aria-labelledby="files-title"><h2 id="files-title">Reproduce it</h2>'
    '<p>Python 3.12 with DuckDB to reduce the source files; the forecasts and tests need only the standard library. The '
    'steps are in the README.</p><p class="links"><a href="README.md">README</a><a href="tools/get_data.py">Data '
    'download and reduction</a><a href="tools/pipeline.py">Stages and forecasts</a><a href="tools/run_study.py">Declared '
    'run</a><a href="tools/after_results.py">Added after the results</a><a href="data/opportunities.csv.gz">The '
    'opportunity table</a><a href="results/summary.json">Declared results</a><a href="results/after.json">Results added '
    'after</a><a href="predictions-r1.json">Predictions as declared</a><a href="protocol-r1.json">Protocol</a>'
    '<a href="DESIGN-r1.md">Design</a><a href="CHANGES-r1.md">Analyses added after the results</a>'
    '<a href="tools/get_notices.py">Notice table</a>'
    '<a href="tools/run_study_r2.py">Run with the further changes</a><a href="data/notices.csv.gz">The notices</a>'
    '<a href="results/summary-r2.json">Results of the further changes</a><a href="tools/stale_deals.py">Age of the '
    'deals dated outside the quarter</a><a href="results/stale-deals.json">Its results</a>'
    '<a href="tools/dash_free.py">Dashes in the tables</a><a href="assumptions.json">Assumptions</a></p></section>'
    f'<section class="block kit-wrap">{back_links()}</section>' + NEXT_STUDY)
page("method.html", "Method and checks: " + STUDY_TITLE,
     "Data, forecasts, predictions and checks for four pipeline forecasts on public tender data.", meth_body,
     [("plain", "In plain words"), ("data", "Data"), ("how", "How it works"), ("declared", "Declared"),
      ("changes", "Changes"), ("wrong", "What went wrong"), ("checks", "Checks"), ("files", "Reproduce")])
