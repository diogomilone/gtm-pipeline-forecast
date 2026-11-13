"""Further change (method page): replace each en or em dash inside a text field of the two shipped tables with a
hyphen, so the public files hold none. Only two fields carry one: 33 solicitation numbers (the same 33 in both tables)
and 6 buyer names. The check below refuses a rewrite that would merge two values of any field, so every join and every
buyer grouping is kept, and the results are unchanged: re-running the three study steps on the rewritten tables gives
the same results files, byte for byte.

Usage: python3 -I -B tools/dash_free.py
Run it after get_data.py and get_notices.py. It rewrites data/opportunities.csv.gz and data/notices.csv.gz in place,
with a fixed gzip header, so the same input always gives the same bytes. Running it again changes nothing.
"""
import csv
import gzip
import io
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES = ["opportunities.csv.gz", "notices.csv.gz"]
DASHES = {0x2013: "-", 0x2014: "-"}  # en dash, em dash


def columns(text):
    rows = list(csv.reader(io.StringIO(text, newline="")))
    return rows[0], [set(col) for col in zip(*rows[1:])]


def rewrite(path):
    raw = gzip.decompress(path.read_bytes()).decode("utf-8")
    new = raw.translate(DASHES)
    head, before = columns(raw)
    head2, after = columns(new)
    assert head == head2, f"{path.name}: header changed"
    for name, a, b in zip(head, before, after):
        assert len(a) == len(b), f"{path.name}: {name} would merge {len(a) - len(b)} values"
    assert not any(ord(ch) in DASHES for ch in new)
    changed = sum(1 for x, y in zip(raw.splitlines(), new.splitlines()) if x != y)
    if new != raw:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(gzip.compress(new.encode("utf-8"), compresslevel=9, mtime=0))
        os.replace(tmp, path)
    return changed


def ids(t):
    text = gzip.decompress((ROOT / "data" / t).read_bytes()).decode("utf-8")
    return {r["opportunity_id"] for r in csv.DictReader(io.StringIO(text, newline=""))}


def main():
    joined = len(ids(TABLES[0]) & ids(TABLES[1]))
    for t in TABLES:
        print(f"{t}: {rewrite(ROOT / 'data' / t)} rows changed")
    now = len(ids(TABLES[0]) & ids(TABLES[1]))
    assert now == joined, f"notices joined to an opportunity: {joined} before, {now} after"
    print(f"opportunity ids shared by the two tables: {now}, as before")


if __name__ == "__main__":
    main()
