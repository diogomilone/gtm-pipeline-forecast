"""Further changes (method page): one row per tender notice, so each snapshot can rebuild an opportunity from the notices
published before it. Reads the same tender file as get_data.py and checks it is the same file (sha256 in
data/sources.json), then checks that the notices rebuild the shipped opportunity table's tender fields exactly. The
check reads solicitation numbers as dash_free.py leaves them, so it holds before and after that step.

Usage: python3 -I -B tools/get_notices.py <download dir> [--no-download]
Writes data/notices.csv.gz. Needs DuckDB. Contact, supplier and address fields are never selected.
"""
import gzip
import csv
import json
import subprocess
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from get_data import FILES, PROTO, ROOT, sha256  # noqa: E402
from dash_free import DASHES  # noqa: E402


def main():
    dl = Path(sys.argv[1]).resolve()
    dl.mkdir(parents=True, exist_ok=True)
    path = dl / Path(FILES["tenders"]).name
    if "--no-download" not in sys.argv:
        subprocess.run(["curl", "-fsSL", "-o", str(path), FILES["tenders"]], check=True)
    src = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    got = sha256(path)
    assert got == src["files"]["tenders"]["sha256"], f"tender file differs from the one used: {got}"
    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='1GB'")
    opts = "header=true, all_varchar=true, strict_mode=false, ignore_errors=true, max_line_size=20000000"
    excl = PROTO["opportunity"]["excluded_notice_types"]
    con.execute(f"""CREATE TABLE n AS SELECT
        coalesce(nullif(trim("solicitationNumber-numeroSollicitation"), ''), "referenceNumber-numeroReference") oid,
        try_cast("publicationDate-datePublication" AS DATE) pub,
        try_cast(try_cast("tenderClosingDate-appelOffresDateCloture" AS TIMESTAMP) AS DATE) clo,
        try_cast("expectedContractStartDate-dateDebutContratPrevue" AS DATE) exs,
        "tenderStatus-appelOffresStatut-eng" st,
        try_cast("amendmentDate-dateModification" AS DATE) amdd,
        "amendmentNumber-numeroModification" amn,
        "noticeType-avisType-eng" nt
        FROM read_csv('{path}', {opts})""")
    con.execute(f"""CREATE TABLE out AS SELECT oid opportunity_id, pub published_at, clo bid_close_at,
        exs expected_start, st status, amdd last_amendment_at, amn amendment_number FROM n
        WHERE nt IS NULL OR nt NOT IN ({', '.join(repr(v) for v in excl)})
        ORDER BY oid, pub, clo""")
    out = ROOT / "data" / "notices.csv.gz"
    con.execute(f"COPY out TO '{out}' (HEADER, DELIMITER ',', COMPRESSION gzip)")
    # check: grouping all notices reproduces the shipped table's tender fields
    with gzip.open(ROOT / "data" / "opportunities.csv.gz", "rt", encoding="utf-8", newline="") as f:
        shipped = {r["opportunity_id"].translate(DASHES): r for r in csv.DictReader(f)}
    grp = {}
    with gzip.open(out, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            grp.setdefault(r["opportunity_id"].translate(DASHES), []).append(r)
    bad = 0
    for oid, ns in grp.items():
        o = shipped.get(oid)
        if o is None or o["created_at"] != min(n["published_at"] for n in ns) or \
                o["bid_close_at"] != max((n["bid_close_at"] for n in ns if n["bid_close_at"]), default="") or \
                int(o["notices"]) != len(ns):
            bad += 1
    print(json.dumps({"notices": sum(len(v) for v in grp.values()), "opportunities": len(grp),
                      "shipped": len(shipped), "mismatched": bad}))
    assert len(grp) == len(shipped) and bad == 0, "notices do not rebuild the shipped opportunity table"


if __name__ == "__main__":
    main()
