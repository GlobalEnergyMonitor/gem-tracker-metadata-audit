"""
analyze.py

For each data table in tracker_data.db, computes per-field statistics and
generates type/subtype guesses (mirroring the Observable metadata notebook logic).

Flags data quality issues:
  - mostly_numeric_with_outliers: field is 50–95% numeric — expected numeric but has non-numeric values
  - categorical_rare_values: categorical (<15 unique values) with some values <1% of rows
  - high_null_rate: >50% null
  - potential_multi_value: categorical values containing '&', ';', or ','

Outputs JSON to analysis/{table_name}.json.
Also writes a cross-table summary to analysis/_summary.json.

Run: python3 analyze.py
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "tracker_data.db"
OUTPUT_DIR = Path("analysis")

# Tracker slug prefixes for trackers managed in the GEM research database.
# Spreadsheet-only trackers (Coal Finance, Chemicals, Coal Mines, etc.) are not listed.
RESEARCH_DB_TRACKER_PREFIXES = {
    "global_coal_plant_tracker",
    "global_wind_power_tracker",
    "global_solar_power_tracker",
    "global_nuclear_power_tracker",
    "geothermal_power_tracker",
    "global_hydropower_tracker",
    "global_bioenergy_power_tracker",
    "global_oil_and_gas_extraction_tracker",   # GOGET
    "global_oil_and_gas_plant_tracker_gogpt",  # GOGPT
    "global_integrated_power",                 # GIP
    "gem_ggit_lng",                            # LNG terminals
    "steel_unit_data_global_iron_and_steel",
    "iron_unit_data_global_iron_and_steel",
    "plant_level_data_global_iron_and_steel",
}


def in_research_db(tracker_slug):
    return any(tracker_slug.startswith(p) for p in RESEARCH_DB_TRACKER_PREFIXES)

# Values treated as null/missing for GEM data
NULL_PROXIES = {None, "", "*", "-", "N/A", "UA", "n/a", "None", "none", "NA", "na"}

# Extended null-proxy patterns not in NULL_PROXIES (e.g. "--", "**", "TBD")
_EXTENDED_NULL_RE = re.compile(
    r'^('
    r'[\*#?]{2,}'
    r'|[-]{2,}'
    r'|[=~]{2,}'
    r'|tbd|t\.b\.d\.'
    r'|nd|nr|ns|nk'
    r'|unk(?:nown)?'
    r'|unspecified|unclear|unavailable'
    r'|not\s+(?:available|found|applicable|reported|known)'
    r')$',
    re.IGNORECASE,
)


def looks_like_null_proxy(val):
    """True if val is a known or pattern-matched null/missing representation."""
    if val in NULL_PROXIES or val is None:
        return True
    return bool(_EXTENDED_NULL_RE.match(str(val).strip()))

# Fields whose names hint at datetime/year
YEAR_NAME_HINTS = ("year", "start", "end", "opening", "closing", "commissioned", "retired", "date")

# Threshold: if fewer than this many unique values, treat as categorical
CATEGORICAL_THRESHOLD = 25

# Separators that suggest a field allows multiple values
MULTI_VALUE_SEPS = ("&", ";")


def slugify(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", "_", text)
    return text.strip("_")


def is_numeric(val):
    """True if val can be parsed as a float (after stripping common numeric suffixes)."""
    if val in NULL_PROXIES:
        return None  # treated as missing, not as non-numeric
    try:
        float(str(val).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False


def guess_type(field_name, n_unique, portion_numeric, portion_null, top_values):
    """
    Mirror the Observable notebook guesses function.
    Returns (data_type, data_sub_type).
    """
    name_lower = field_name.lower()

    # Year / date hint check
    if any(h in name_lower for h in YEAR_NAME_HINTS):
        return "datetime", "year"

    # Mostly numeric
    if portion_numeric is not None and portion_numeric > 0.95:
        subtype = "measurement" if "(" in field_name else None
        return "numeric", subtype

    # Few unique values → categorical
    if n_unique < CATEGORICAL_THRESHOLD:
        if "accuracy" in name_lower:
            return "text", "accuracy"
        return "text", "categorical"

    # Many unique values → text
    if "id" in name_lower or "url" in name_lower or "wiki" in name_lower or "regex" in name_lower:
        return "text", "structured"
    return "text", "unstructured"


def detect_flags(field_name, n_total, n_null, n_unique, portion_numeric, top_values, data_type=None, data_sub_type=None):
    flags = []

    null_rate = n_null / n_total if n_total else 0

    # Mostly numeric but not cleanly so (skip for fields already guessed as datetime)
    if portion_numeric is not None and 0.80 < portion_numeric < 0.95 and data_type != "datetime":
        # Check whether the non-numeric values in top_values are null-proxy-like
        non_numeric_top = [(v, c) for v, c in top_values if is_numeric(v) is False]
        if non_numeric_top and all(looks_like_null_proxy(v) for v, _ in non_numeric_top):
            # Soft flag: non-numeric values are just non-standard null shorthands
            flags.append("numeric_null_proxies")
        else:
            flags.append("mostly_numeric_with_outliers")

    # Categorical with rare values — only applies to text/categorical guesses
    if data_type == "text" and data_sub_type in ("categorical", "ordinal", "accuracy"):
        if 0 < n_unique < CATEGORICAL_THRESHOLD and top_values:
            total_non_null = n_total - n_null
            if total_non_null > 0:
                rare = [v for v, c in top_values if c / total_non_null < 0.01]
                if rare:
                    flags.append(f"categorical_rare_values:{len(rare)}_values_below_1pct")

            multi = [v for v, _ in top_values if v and any(s in str(v) for s in MULTI_VALUE_SEPS)]
            if multi:
                flags.append("potential_multi_value")

    return flags


def code_friendly_name(field_name):
    """Generate a snake_case API-friendly name (mirrors Observable notebook logic)."""
    name = field_name.lower()
    name = re.sub(r"\s*\(", "_", name)
    name = re.sub(r"\)", "", name)
    name = re.sub(r"[^\w]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def analyze_table(conn, table_name):
    """Analyze all columns in a table. Returns a list of field-level dicts."""
    try:
        n_rows = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    except Exception as e:
        return None, f"Error: {e}"

    if n_rows == 0:
        return [], None

    # Get column names
    cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 0')
    col_names = [d[0] for d in cursor.description]

    fields = []
    for col in col_names:
        # Total and null count
        n_null = conn.execute(
            f'SELECT COUNT(*) FROM "{table_name}" WHERE "{col}" IS NULL OR "{col}" = \'\''
        ).fetchone()[0]
        n_total = n_rows
        n_non_null = n_total - n_null
        null_rate = n_null / n_total if n_total else 0

        # Unique value counts (cap at CATEGORICAL_THRESHOLD * 4 for performance)
        limit = CATEGORICAL_THRESHOLD * 4
        rows = conn.execute(
            f'SELECT "{col}", COUNT(*) as cnt FROM "{table_name}" '
            f'WHERE "{col}" IS NOT NULL AND "{col}" != \'\' '
            f'GROUP BY "{col}" ORDER BY cnt DESC LIMIT {limit}'
        ).fetchall()

        top_values = [(r[0], r[1]) for r in rows]
        n_unique_seen = len(top_values)

        # If we hit the cap, get the real total unique count with a separate query
        if n_unique_seen == limit:
            n_unique = conn.execute(
                f'SELECT COUNT(DISTINCT "{col}") FROM "{table_name}" '
                f'WHERE "{col}" IS NOT NULL AND "{col}" != \'\''
            ).fetchone()[0]
        else:
            n_unique = n_unique_seen

        # Numeric detection: sample non-null values
        sample = conn.execute(
            f'SELECT "{col}" FROM "{table_name}" '
            f'WHERE "{col}" IS NOT NULL AND "{col}" != \'\' LIMIT 500'
        ).fetchall()

        numeric_results = [is_numeric(r[0]) for r in sample]
        # Exclude None (null-proxies) from the numerics check
        real_results = [r for r in numeric_results if r is not None]
        portion_numeric = sum(real_results) / len(real_results) if real_results else None

        data_type, data_sub_type = guess_type(col, n_unique, portion_numeric, null_rate, top_values)
        is_required_guess = null_rate == 0.0
        flags = detect_flags(col, n_total, n_null, n_unique, portion_numeric, top_values, data_type, data_sub_type)

        fields.append(
            {
                "field_name": col,
                "code_friendly_name_guess": code_friendly_name(col),
                "n_total": n_total,
                "n_null": n_null,
                "n_non_null": n_non_null,
                "null_rate": round(null_rate, 4),
                "n_unique": n_unique,
                "top_values": top_values[:20],  # cap for output size
                "portion_numeric": round(portion_numeric, 4) if portion_numeric is not None else None,
                "type_guess": data_type,
                "subtype_guess": data_sub_type,
                "is_required_guess": is_required_guess,
                "flags": flags,
            }
        )

    return fields, None


def load_field_metadata(conn, tracker_slug, tab_slug):
    """
    Load field definitions and value definitions from _tracker_fields.
    Returns (field_defs, value_defs) where:
      field_defs:  {field_name: {definition, notes}}
      value_defs:  {parent_field_name: [{name, definition}]}
    """
    # Field-level definitions: match tab_slug or 'unknown' (global defs with no specific tab)
    rows = conn.execute(
        """
        SELECT field_name, definition, notes
        FROM _tracker_fields
        WHERE tracker_slug = ? AND (tab_slug = ? OR tab_slug = 'unknown') AND entry_type = 'field'
        """,
        (tracker_slug, tab_slug),
    ).fetchall()
    field_defs = {r[0]: {"definition": r[1], "notes": r[2]} for r in rows}

    # Value-level definitions (categorical values): tracker-wide, matched by parent_field
    val_rows = conn.execute(
        """
        SELECT parent_field, field_name, definition
        FROM _tracker_fields
        WHERE tracker_slug = ? AND entry_type = 'definition' AND parent_field IS NOT NULL
        """,
        (tracker_slug,),
    ).fetchall()
    value_defs = {}
    for parent, name, defn in val_rows:
        value_defs.setdefault(parent, []).append({"name": name, "definition": defn or ""})

    return field_defs, value_defs


def load_tracker_info(tracker_slug):
    """Load tracker-level header info (title, citation, contact, license) from metadata JSON."""
    path = Path("metadata") / f"{tracker_slug}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("header_info", {})


def load_api_metadata(tracker_slug):
    """Load the saved API gold-standard metadata if available."""
    # Map tracker slugs to API metadata files
    mapping = {
        "global_coal_mine_tracker_may_2026": "metadata/api_coal_mines.json",
        "global_coal_plant_tracker_january_2026": "metadata/api_coal_plants.json",
    }
    path = mapping.get(tracker_slug)
    if not path or not Path(path).exists():
        return {}

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return {f["name"]: f for f in data.get("fieldsDetail", [])}


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # Get all data tables (not metadata tables)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '\\_%' ESCAPE '\\' ORDER BY name"
    ).fetchall()

    summary = []

    for (table_name,) in tables:
        # Parse tracker_slug and tab_slug from table name
        parts = table_name.split("__", 1)
        tracker_slug = parts[0]
        tab_slug = parts[1] if len(parts) > 1 else "data"

        print(f"Analyzing: {table_name}")

        fields, error = analyze_table(conn, table_name)
        if error:
            print(f"  Error: {error}")
            continue

        # Enrich with existing metadata
        field_defs, value_defs = load_field_metadata(conn, tracker_slug, tab_slug)
        api_meta = load_api_metadata(tracker_slug)

        for f in fields:
            name = f["field_name"]
            if name in field_defs:
                f["definition_from_readme"] = field_defs[name].get("definition")
                f["notes_from_readme"] = field_defs[name].get("notes")
            # Attach value definitions for this field (e.g. Status allowed values + defs)
            if name in value_defs:
                f["value_definitions"] = value_defs[name]
            if name in api_meta:
                f["api_metadata"] = {
                    k: v for k, v in api_meta[name].items()
                    if k not in ("url", "aggregate_urls", "is_filterable", "filter_operators")
                }

        tracker_info = load_tracker_info(tracker_slug)
        n_flagged = sum(1 for f in fields if f["flags"])
        print(f"  {len(fields)} fields | {n_flagged} flagged")

        # Write per-table output
        out = {
            "table_name": table_name,
            "tracker_slug": tracker_slug,
            "tab_slug": tab_slug,
            "n_rows": fields[0]["n_total"] if fields else 0,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "tracker_info": tracker_info,
            "fields": fields,
        }
        out_path = OUTPUT_DIR / f"{table_name}.json"
        with open(out_path, "w", encoding="utf-8") as f_out:
            json.dump(out, f_out, indent=2, ensure_ascii=False)

        summary.append(
            {
                "table_name": table_name,
                "tracker_slug": tracker_slug,
                "tab_slug": tab_slug,
                "n_rows": out["n_rows"],
                "n_fields": len(fields),
                "n_flagged": n_flagged,
                "flags_by_type": _count_flag_types(fields),
                "in_research_db": in_research_db(tracker_slug),
            }
        )

    # Write summary
    with open(OUTPUT_DIR / "_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    conn.close()
    total_flagged = sum(s["n_flagged"] for s in summary)
    print(f"\nDone. {len(summary)} tables analyzed, {total_flagged} total flagged fields.")
    print(f"Outputs: {OUTPUT_DIR}/")


def _count_flag_types(fields):
    counts = {}
    for f in fields:
        for flag in f["flags"]:
            key = flag.split(":")[0]
            counts[key] = counts.get(key, 0) + 1
    return counts


if __name__ == "__main__":
    main()
