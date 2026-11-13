"""Download the two CanadaBuys files, hash them, and reduce them to one CRM-shaped opportunity table.

Usage: python3 -I -B tools/get_data.py <download dir> [--no-download]
Writes data/opportunities.csv.gz and data/sources.json. Needs DuckDB (pip install duckdb).
Contact, supplier and address fields are never selected, so they never leave the raw files.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
PROTO = json.loads((ROOT / "protocol-r1.json").read_text(encoding="utf-8"))
FILES = PROTO["data"]["files"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    dl = Path(sys.argv[1]).resolve()
    dl.mkdir(parents=True, exist_ok=True)
    paths = {k: dl / Path(u).name for k, u in FILES.items()}
    if "--no-download" not in sys.argv:
        for k, u in FILES.items():
            subprocess.run(["curl", "-fsSL", "-o", str(paths[k]), u], check=True)
    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='1GB'")
    opts = "header=true, all_varchar=true, strict_mode=false, ignore_errors=true, max_line_size=20000000"
    con.execute(f"""CREATE TABLE t AS SELECT
        "referenceNumber-numeroReference" ref, "solicitationNumber-numeroSollicitation" sol,
        try_cast("publicationDate-datePublication" AS DATE) pub,
        try_cast(try_cast("tenderClosingDate-appelOffresDateCloture" AS TIMESTAMP) AS DATE) clo,
        try_cast("amendmentDate-dateModification" AS DATE) amdd,
        try_cast("expectedContractStartDate-dateDebutContratPrevue" AS DATE) exs,
        "tenderStatus-appelOffresStatut-eng" st, "noticeType-avisType-eng" nt,
        "procurementCategory-categorieApprovisionnement" cat,
        "contractingEntityName-nomEntitContractante-eng" ent
        FROM read_csv('{paths["tenders"]}', {opts})""")
    con.execute(f"""CREATE TABLE a AS SELECT
        "solicitationNumber-numeroSollicitation" sol,
        try_cast("publicationDate-datePublication" AS DATE) pub,
        try_cast("contractAwardDate-dateAttributionContrat" AS DATE) awd,
        try_cast("contractStartDate-contratDateDebut" AS DATE) cs,
        try_cast("contractAmount-montantContrat" AS DOUBLE) amt,
        "contractCurrency-contratMonnaie" cur,
        "amendmentType-typeModification-eng" amt_type
        FROM read_csv('{paths["awards"]}', {opts})""")
    n_t, n_a = con.execute("select count(*) from t").fetchone()[0], con.execute("select count(*) from a").fetchone()[0]
    cutoff = con.execute("select max(pub) from t").fetchone()[0]
    excl = PROTO["opportunity"]["excluded_notice_types"]
    groups = PROTO["opportunity"]["channel_groups"]
    case = " ".join(f"WHEN nt IN ({', '.join(repr(v) for v in vals)}) THEN {g!r}"
                    for g, vals in groups.items() if isinstance(vals, list))
    con.execute(f"""CREATE TABLE o0 AS SELECT coalesce(nullif(trim(sol), ''), ref) oid, * FROM t
        WHERE nt IS NULL OR nt NOT IN ({', '.join(repr(v) for v in excl)})""")
    # one row per opportunity: first publication, latest closing, fields of the latest-published notice
    con.execute(f"""CREATE TABLE o AS SELECT oid,
        min(pub) created_at, max(clo) bid_close_at,
        arg_max(exs, pub) expected_start, arg_max(st, pub) status, arg_max(amdd, pub) last_amendment,
        arg_max(CASE {case} ELSE 'Other' END, pub) channel,
        arg_max(replace(replace(cat, '*', ''), chr(10), '+'), pub) category,
        arg_max(ent, pub) account_raw, count(*) notices
        FROM o0 GROUP BY oid""")
    con.execute("""CREATE TABLE w AS SELECT o.oid, min(a.awd) won_at, min(a.pub) won_known_at, min(a.cs) go_live_at,
        sum(CASE WHEN a.amt > 1 AND a.cur = 'CAD' THEN a.amt END) amount_cad, count(*) award_rows
        FROM o JOIN a ON a.sol = o.oid
        WHERE (a.amt_type IS NULL OR a.amt_type = 'Original') AND a.awd IS NOT NULL AND a.awd >= o.created_at
        GROUP BY o.oid""")
    con.execute("""CREATE TABLE out AS SELECT o.oid opportunity_id, o.created_at, o.bid_close_at, o.expected_start,
        CASE WHEN o.status = 'Cancelled' THEN coalesce(o.last_amendment, o.bid_close_at) END cancelled_at,
        o.status, w.won_at, w.won_known_at, w.go_live_at, round(w.amount_cad, 2) amount_cad, o.channel, o.category,
        o.account_raw, o.notices
        FROM o LEFT JOIN w USING (oid) ORDER BY o.created_at, o.oid""")
    stats = dict(zip(["opportunities", "won", "cancelled", "open"], con.execute(
        "select count(*), count(won_at), count(cancelled_at), sum(case when status='Open' then 1 else 0 end) from out").fetchone()))
    out = ROOT / "data" / "opportunities.csv.gz"
    con.execute(f"COPY out TO '{out}' (HEADER, DELIMITER ',', COMPRESSION gzip)")
    src = {"files": {k: {"url": FILES[k], "sha256": sha256(paths[k]), "bytes": paths[k].stat().st_size} for k in FILES},
           "rows": {"tender_notices": n_t, "award_rows": n_a}, "cutoff_latest_tender_publication": str(cutoff),
           "opportunities": {k: int(v) for k, v in stats.items()}, "licence": PROTO["data"]["licence"],
           "attribution": "Contains information licensed under the Open Government Licence - Canada."}
    (ROOT / "data" / "sources.json").write_text(json.dumps(src, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(src["opportunities"]), "cutoff", cutoff)


if __name__ == "__main__":
    main()
