"""Tests for the stage rules, the point-in-time rule and the forecasts. Run: python3 -B tests/test_pipeline.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import pipeline as P  # noqa: E402

D = P.day


def opp(created, close, won=None, known=None, cancelled=None, exp=None, live=None):
    return {"id": f"{created}-{close}-{won}", "created_at": D(created), "bid_close_at": D(close),
            "expected_start": D(exp) if exp else None, "cancelled_at": D(cancelled) if cancelled else None,
            "won_at": D(won) if won else None, "won_known_at": D(known) if known else None,
            "go_live_at": D(live) if live else None, "amount": None, "channel": "Other", "category": "SRV",
            "account": "X", "status": "Expired"}


class Stages(unittest.TestCase):
    def test_open_and_await(self):
        o = opp("2024-01-10", "2024-02-10")
        self.assertEqual(P.stage(o, D("2024-01-10")), None)          # created that day: not yet
        self.assertEqual(P.stage(o, D("2024-02-01")), ("open", 22))
        self.assertEqual(P.stage(o, D("2024-02-10")), ("open", 31))  # closing day still open
        self.assertEqual(P.stage(o, D("2024-03-01")), ("await", 20))

    def test_point_in_time_award(self):
        o = opp("2024-01-10", "2024-02-10", won="2024-02-20", known="2024-06-01")
        self.assertEqual(P.stage(o, D("2024-04-01"))[0], "await")   # won, but nobody knew yet
        self.assertIsNone(P.stage(o, D("2024-06-02")))
        self.assertFalse(P.won_in(o, D("2024-01-01"), D("2024-04-01"), D("2024-04-01")))
        self.assertTrue(P.won_in(o, D("2024-01-01"), D("2024-04-01"), D("2024-06-02")))

    def test_cancelled_leaves(self):
        o = opp("2024-01-10", "2024-02-10", cancelled="2024-03-05")
        self.assertEqual(P.stage(o, D("2024-03-05"))[0], "await")
        self.assertIsNone(P.stage(o, D("2024-03-06")))

    def test_bands(self):
        self.assertEqual([P.band(x) for x in (0, 14, 15, 30, 31, 365, 366, 2000)], [0, 0, 1, 1, 2, 4, 5, 5])

    def test_quarters(self):
        self.assertEqual(P.iso(P.quarter_start(D("2025-08-15"))), "2025-07-01")
        self.assertEqual(P.iso(P.quarter_start(D("2025-07-01"), 1)), "2025-10-01")
        self.assertEqual(P.iso(P.quarter_start(D("2025-01-01"), -1)), "2024-10-01")

    def test_account_names(self):
        self.assertEqual(P.account("Department of National Defence (DND)"), "National Defence")
        self.assertEqual(P.account("Department of National Defence"), "National Defence")
        self.assertEqual(P.account("National Research Council of Canada (NRC)"), P.account("National Research Council Canada"))
        self.assertEqual(P.account("Parks Canada Agency (PC)"), "Parks Canada")


class Forecasts(unittest.TestCase):
    def rows(self):
        rows = []
        # each quarter (four of history, then the scored one) has 10 deals awaiting award at its start; 4 win inside it, published fast
        for q in ("2024-10-01", "2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01"):
            s = D(q)
            for i in range(10):
                c = P.iso(s - 40)
                cl = P.iso(s - 5)
                w = P.iso(s + 10) if i < 4 else None
                rows.append(opp(c, cl, won=w, known=P.iso(s + 12) if w else None, exp=P.iso(s + 20)))
        return rows

    def test_learned_weights_and_actual(self):
        rows = self.rows()
        s = D("2025-10-01")
        f = P.forecast_all(rows, s)
        self.assertAlmostEqual(f["_weights"]["learned_stage"]["await"], 0.4)
        self.assertEqual(f["fixed"]["deals_counted"], 10)
        self.assertAlmostEqual(f["fixed"]["forecast"], 8.0)
        self.assertAlmostEqual(f["learned_stage"]["forecast"], 4.0)
        self.assertEqual(f["run_rate"]["forecast"], 4.0)
        a = P.actual(rows, s)
        self.assertEqual(a["pipeline_wins"], 4)
        sc = P.score(f["fixed"]["forecast"], a["pipeline_wins"])
        self.assertAlmostEqual(sc["pct_error"], 100.0)

    def test_point_in_time_hides_late_awards(self):
        rows = self.rows()
        for o in rows:  # every award published a year late
            if o["won_known_at"]:
                o["won_known_at"] += 365
        s = D("2025-10-01")
        honest = P.forecast_all(rows, s)
        leaky = P.forecast_all(rows, s, known_by=10 ** 7)
        self.assertEqual(honest["run_rate"]["forecast"], 0.0)
        self.assertEqual(leaky["run_rate"]["forecast"], 4.0)
        self.assertLess(honest["learned_stage"]["forecast"], leaky["learned_stage"]["forecast"])

    def test_interval_brackets_mean(self):
        mu, lo, hi = P.poisson_binomial([0.5] * 100)
        self.assertAlmostEqual(mu, 50)
        self.assertAlmostEqual(hi - mu, 1.2816 * 5)
        self.assertLess(lo, mu)


class NoticesAsKnownThen(unittest.TestCase):
    """further changes: each snapshot rebuilds a deal from the notices published before it"""

    def setUp(self):
        self.o = opp("2024-01-10", "2024-04-30")
        self.o["id"] = "A"
        # first notice closes 2024-02-10; a later notice published 2024-02-05 moves the close to 2024-04-30 and is
        # amended in place on 2024-03-20; it is the latest notice, cancelled with that amendment
        self.notices = {"A": [(D("2024-01-10"), D("2024-02-10"), None, "Expired", None),
                              (D("2024-02-05"), D("2024-04-30"), D("2024-06-01"), "Cancelled", D("2024-03-20"))]}

    def test_later_notice_invisible(self):
        v = P.make_view([self.o], self.notices)
        a = v(D("2024-02-01"))[0]
        self.assertEqual(a["bid_close_at"], D("2024-02-10"))
        self.assertIsNone(a["expected_start"])
        self.assertIsNone(a["cancelled_at"])
        self.assertFalse(a["amended_after"])
        self.assertEqual(P.pipeline([self.o], D("2024-02-01"), v)[0][1], "open")
        self.assertEqual(v(D("2024-01-10")), [])  # nothing published before the first notice's day

    def test_amended_after_flag_and_drop(self):
        v = P.make_view([self.o], self.notices)
        a = v(D("2024-03-01"))[0]
        self.assertEqual(a["bid_close_at"], D("2024-04-30"))
        self.assertTrue(a["amended_after"])  # amended on 2024-03-20, after this snapshot
        self.assertEqual(P.make_view([self.o], self.notices, drop_flagged=True)(D("2024-03-01")), [])
        self.assertEqual(P.pipeline([self.o], D("2024-03-01"), v)[0][1], "open")  # not yet cancelled
        self.assertEqual(P.pipeline([self.o], D("2024-03-21"), v), [])  # cancelled the day before

    def test_no_view_is_version_one(self):
        self.assertEqual(P.pipeline([self.o], D("2024-02-01")), P.pipeline([self.o], D("2024-02-01"), None))

    def test_real_notices_have_no_personal_fields(self):
        import gzip
        head = gzip.open(P.ROOT / "data" / "notices.csv.gz", "rt", encoding="utf-8").readline().lower()
        for banned in ("contact", "email", "phone", "supplier", "address"):
            self.assertNotIn(banned, head)


class RealTable(unittest.TestCase):
    def test_loads_and_has_no_personal_fields(self):
        import gzip
        head = gzip.open(P.ROOT / "data" / "opportunities.csv.gz", "rt", encoding="utf-8").readline().lower()
        for banned in ("contact", "email", "phone", "supplier", "address"):
            self.assertNotIn(banned, head)
        rows = P.load()
        self.assertGreater(len(rows), 20000)

    def test_shipped_tables_hold_no_long_dash(self):
        import gzip
        from dash_free import DASHES
        for t in ("opportunities.csv.gz", "notices.csv.gz"):
            text = gzip.decompress((P.ROOT / "data" / t).read_bytes()).decode("utf-8")
            self.assertFalse(any(ord(ch) in DASHES for ch in text), t)


class DashFree(unittest.TestCase):
    def test_refuses_a_rewrite_that_merges_values(self):
        import gzip
        import tempfile
        from dash_free import rewrite
        en = chr(0x2013)
        with tempfile.TemporaryDirectory() as d:
            ok = Path(d) / "ok.csv.gz"
            ok.write_bytes(gzip.compress(f"opportunity_id,n\nA {en} 1,1\nB,2\n".encode("utf-8"), mtime=0))
            self.assertEqual(rewrite(ok), 1)
            self.assertEqual(gzip.decompress(ok.read_bytes()).decode("utf-8"), "opportunity_id,n\nA - 1,1\nB,2\n")
            self.assertEqual(rewrite(ok), 0)  # running it again changes nothing
            bad = Path(d) / "bad.csv.gz"
            before = gzip.compress(f"opportunity_id,n\nA {en} 1,1\nA - 1,2\n".encode("utf-8"), mtime=0)
            bad.write_bytes(before)
            with self.assertRaises(AssertionError):
                rewrite(bad)
            self.assertEqual(bad.read_bytes(), before)  # left untouched


if __name__ == "__main__":
    unittest.main(verbosity=1)
