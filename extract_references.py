#!/usr/bin/env python3
"""
extract_references.py

Extracts canonical reference sets from the GEM research DB snapshot
(researchDBfiles/report_snapshot.duckdb) and writes them to reference_sets.json.

These reference sets are used by analyze.py to validate categorical field values
against org-canonical lists, replacing the rarity heuristic for known fields.

Current sets extracted:
  - country:      snapshot.country.gemName   (251 entries)
  - status:       snapshot.status.name       (12 canonical status values)
  - fuel_category: snapshot.fuel_category.name

Run: python3 extract_references.py
Output: reference_sets.json
"""

import json
from pathlib import Path

DB_PATH = Path("researchDBfiles/report_snapshot.duckdb")
OUT_PATH = Path("reference_sets.json")


def extract(conn):
    sets = {}

    # Country names (GEM canonical form)
    rows = conn.execute(
        "SELECT DISTINCT gemName FROM snapshot.country WHERE gemName IS NOT NULL ORDER BY gemName"
    ).fetchall()
    sets["country"] = [r[0] for r in rows]

    # Canonical status values
    rows = conn.execute(
        "SELECT name FROM snapshot.status WHERE name IS NOT NULL ORDER BY \"order\""
    ).fetchall()
    sets["status"] = [r[0] for r in rows]

    # Fuel categories
    rows = conn.execute(
        "SELECT name FROM snapshot.fuel_category WHERE name IS NOT NULL ORDER BY name"
    ).fetchall()
    sets["fuel_category"] = [r[0] for r in rows]

    return sets


def main():
    try:
        import duckdb
    except ImportError:
        print("ERROR: duckdb package not installed. Run: pip3 install duckdb")
        return

    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found")
        return

    conn = duckdb.connect(str(DB_PATH), read_only=True)
    sets = extract(conn)
    conn.close()

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sets, f, indent=2, ensure_ascii=False)

    for key, vals in sets.items():
        print(f"  {key}: {len(vals)} entries")
    print(f"Written: {OUT_PATH}")


if __name__ == "__main__":
    main()
