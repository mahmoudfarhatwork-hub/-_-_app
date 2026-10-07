"""Build the SQLite content database (with FTS5 search) from content/.

Usage:
  python -m tools.build_db                    # published items only
  python -m tools.build_db --include-draft    # dev database, all items
  python -m tools.build_db --out build/x.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from tools.common import ROOT, normalize_arabic, validate

SCHEMA_SQL = """
CREATE TABLE hadith (
  id TEXT PRIMARY KEY,
  text_ar TEXT NOT NULL,
  text_search TEXT NOT NULL,
  narrator TEXT NOT NULL,
  graded_by TEXT NOT NULL,        -- JSON array
  grade TEXT NOT NULL,
  agreed_upon INTEGER NOT NULL DEFAULT 0,
  category TEXT NOT NULL,
  topics TEXT NOT NULL,           -- JSON array
  review_status TEXT NOT NULL
);
CREATE TABLE hadith_source (
  hadith_id TEXT NOT NULL REFERENCES hadith(id),
  book TEXT NOT NULL,
  number TEXT NOT NULL
);
CREATE TABLE dhikr (
  id TEXT PRIMARY KEY,
  text_ar TEXT NOT NULL,
  text_search TEXT NOT NULL,
  category TEXT NOT NULL,
  repeat INTEGER NOT NULL,
  virtue_ar TEXT,
  review_status TEXT NOT NULL
);
CREATE TABLE dhikr_source (
  dhikr_id TEXT NOT NULL REFERENCES dhikr(id),
  type TEXT NOT NULL,
  ref TEXT NOT NULL,
  grade TEXT
);
CREATE VIRTUAL TABLE search_fts USING fts5(
  kind UNINDEXED,
  id UNINDEXED,
  text_search,
  tokenize = 'trigram'   -- substring match, so "النيات" finds "بالنيات"; queries need 3+ chars
);
"""


def build(root: Path, out: Path, include_draft: bool = False) -> dict[str, int]:
    items, errors = validate(root)
    if errors:
        raise ValueError("content has validation errors:\n" + "\n".join(f"  - {e}" for e in errors))

    def wanted(item: dict) -> bool:
        return include_draft or item["review_status"] == "published"

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    counts = {"hadith": 0, "dhikr": 0}
    con = sqlite3.connect(out)
    try:
        con.executescript(SCHEMA_SQL)

        for _, h in items["hadith"]:
            if not wanted(h):
                continue
            search = normalize_arabic(h["text_ar"])
            con.execute(
                "INSERT INTO hadith VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    h["id"],
                    h["text_ar"],
                    search,
                    h["narrator"],
                    json.dumps(h["graded_by"], ensure_ascii=False),
                    h["grade"],
                    1 if h.get("agreed_upon") else 0,
                    h["category"],
                    json.dumps(h.get("topics", []), ensure_ascii=False),
                    h["review_status"],
                ),
            )
            con.executemany(
                "INSERT INTO hadith_source VALUES (?,?,?)",
                [(h["id"], s["book"], s["number"]) for s in h["sources"]],
            )
            con.execute("INSERT INTO search_fts VALUES (?,?,?)", ("hadith", h["id"], search))
            counts["hadith"] += 1

        for _, d in items["adhkar"]:
            if not wanted(d):
                continue
            search = normalize_arabic(d["text_ar"])
            con.execute(
                "INSERT INTO dhikr VALUES (?,?,?,?,?,?,?)",
                (
                    d["id"],
                    d["text_ar"],
                    search,
                    d["category"],
                    d["repeat"],
                    d.get("virtue_ar"),
                    d["review_status"],
                ),
            )
            con.executemany(
                "INSERT INTO dhikr_source VALUES (?,?,?,?)",
                [(d["id"], s["type"], s["ref"], s.get("grade")) for s in d["sources"]],
            )
            con.execute("INSERT INTO search_fts VALUES (?,?,?)", ("dhikr", d["id"], search))
            counts["dhikr"] += 1

        con.commit()
    finally:
        con.close()

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--include-draft", action="store_true")
    args = parser.parse_args(argv)

    out = args.out or (args.root / "build" / "content.db")
    try:
        counts = build(args.root, out, args.include_draft)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    mode = "all statuses" if args.include_draft else "published only"
    print(f"wrote {out} ({mode}): hadith={counts['hadith']}, dhikr={counts['dhikr']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
