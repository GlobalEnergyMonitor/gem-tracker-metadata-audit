"""
analyze.py

For each data table in tracker_data.db, computes per-field statistics and
generates type/subtype guesses (mirroring the Observable metadata notebook logic).

Compliance flags (errors — always wrong):
  - numeric_outliers: numeric field (>95%) has real non-numeric, non-null-proxy values
  - non_standard_null_proxies: numeric/boolean field contains null-proxy shorthands
  - wrong_multi_value_separator: multi-value field uses ',' (conflicts with CSV export)
  - out_of_set_categorical: values outside org reference set or README allowed_values
  - duplicate_rows: table has duplicate rows (table-level stat)

Compliance flags (warnings — org convention):
  - multi_value_separator_check: reports which separator(s) are in use
  - boolean_encoding: reports which boolean encoding is in use
  - year_out_of_range: year field has values outside 1900–2100
  - required_field_has_nulls: is_required field has null values

Legacy heuristic flags (suppressed when reference set exists):
  - mostly_numeric_with_outliers / numeric_null_proxies
  - categorical_rare_values: only fires when no reference set available
  - potential_multi_value: only fires when & is not in the allowed-value vocabulary

Outputs JSON to analysis/{table_name}.json.
Also writes analysis/_summary.json.

Run: python3 analyze.py
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "tracker_data.db"
OUTPUT_DIR = Path("analysis")
REFERENCES_PATH = Path("reference_sets.json")
OVERRIDES_PATH = Path("overrides.json")

RESEARCH_DB_TRACKER_PREFIXES = {
    "global_coal_plant_tracker",
    "global_wind_power_tracker",
    "global_solar_power_tracker",
    "global_nuclear_power_tracker",
    "geothermal_power_tracker",
    "global_hydropower_tracker",
    "global_bioenergy_power_tracker",
    "global_oil_and_gas_extraction_tracker",
    "global_oil_and_gas_plant_tracker_gogpt",
    "global_integrated_power",
    "gem_ggit_lng",
    "steel_unit_data_global_iron_and_steel",
    "iron_unit_data_global_iron_and_steel",
    "plant_level_data_global_iron_and_steel",
}

# Field name patterns that trigger reference-set validation (case-insensitive substring match)
COUNTRY_FIELD_HINTS = ("country", "country_area")
STATUS_FIELD_HINTS = ("status",)
FUEL_FIELD_HINTS = ("fuel",)

# URL-like fields where & in values is query-string noise, not a separator
URL_FIELD_HINTS = ("url", "source", "link", "ref", "wiki", "http")

NULL_PROXIES = {None, "", "*", "-", "N/A", "UA", "n/a", "None", "none", "NA", "na"}

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

YEAR_NAME_HINTS = ("year", "start", "end", "opening", "closing", "commissioned", "retired", "date")
CATEGORICAL_THRESHOLD = 25
MULTI_VALUE_SEPS = ("&", ";")


def in_research_db(tracker_slug):
    return any(tracker_slug.startswith(p) for p in RESEARCH_DB_TRACKER_PREFIXES)


def load_reference_sets():
    if not REFERENCES_PATH.exists():
        return {}
    with open(REFERENCES_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    # Normalize to lowercase sets for case-insensitive matching
    return {k: {v.lower() for v in vals} for k, vals in raw.items()}


def load_overrides():
    if not OVERRIDES_PATH.exists():
        return {}
    with open(OVERRIDES_PATH, encoding="utf-8") as f:
        return json.load(f)


def looks_like_null_proxy(val):
    if val in NULL_PROXIES or val is None:
        return True
    return bool(_EXTENDED_NULL_RE.match(str(val).strip()))


def slugify(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", "_", text)
    return text.strip("_")


def is_numeric(val):
    if val in NULL_PROXIES:
        return None
    try:
        float(str(val).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False


def guess_type(field_name, n_unique, portion_numeric, portion_null, top_values):
    name_lower = field_name.lower()
    if any(h in name_lower for h in YEAR_NAME_HINTS):
        return "datetime", "year"
    if portion_numeric is not None and portion_numeric > 0.95:
        subtype = "measurement" if "(" in field_name else None
        return "numeric", subtype
    if n_unique < CATEGORICAL_THRESHOLD:
        if "accuracy" in name_lower:
            return "text", "accuracy"
        return "text", "categorical"
    if "id" in name_lower or "url" in name_lower or "wiki" in name_lower or "regex" in name_lower:
        return "text", "structured"
    return "text", "unstructured"


def _get_reference_set_for_field(cfn, ref_sets):
    """Return (ref_set, source_name) for a field by its code_friendly_name, or (None, None)."""
    cfn_lower = cfn.lower()
    if any(h in cfn_lower for h in COUNTRY_FIELD_HINTS):
        return ref_sets.get("country"), "country"
    if any(h in cfn_lower for h in STATUS_FIELD_HINTS):
        return ref_sets.get("status"), "status"
    if any(h in cfn_lower for h in FUEL_FIELD_HINTS):
        return ref_sets.get("fuel_category"), "fuel_category"
    return None, None


def _compute_out_of_set(top_values, effective_ref):
    """Return list of values (original case) not present in effective_ref (lowercase set)."""
    if not effective_ref or not top_values:
        return []
    return [
        v for v, _ in top_values
        if v and not looks_like_null_proxy(v) and str(v).strip().lower() not in effective_ref
    ]


def _is_url_field(field_name):
    fl = field_name.lower()
    return any(h in fl for h in URL_FIELD_HINTS)


def detect_flags(
    field_name, cfn, n_total, n_null, n_unique, portion_numeric,
    top_values, data_type=None, data_sub_type=None,
    allowed_values=None, ref_set=None
):
    """
    Returns list of flag strings.
    allowed_values: set of lowercase strings from README/API metadata (optional)
    ref_set: set of lowercase strings from reference_sets.json (optional)
    """
    flags = []
    null_rate = n_null / n_total if n_total else 0
    effective_ref = ref_set or allowed_values  # prefer org ref set, fall back to README

    # ── Numeric compliance ────────────────────────────────────────────
    if portion_numeric is not None and data_type != "datetime":
        if portion_numeric > 0.95:
            # Cleanly numeric — check for non-numeric non-null values (outliers)
            non_numeric_real = [
                (v, c) for v, c in top_values
                if is_numeric(v) is False and not looks_like_null_proxy(v)
            ]
            if non_numeric_real:
                flags.append(f"numeric_outliers:{len(non_numeric_real)}_non_numeric_values")
        elif 0.80 < portion_numeric < 0.95:
            non_numeric_top = [(v, c) for v, c in top_values if is_numeric(v) is False]
            if non_numeric_top and all(looks_like_null_proxy(v) for v, _ in non_numeric_top):
                flags.append("non_standard_null_proxies")
            else:
                flags.append("mostly_numeric_with_outliers")

    # ── Year format ───────────────────────────────────────────────────
    if data_type == "datetime" and data_sub_type == "year":
        out_of_range = []
        for v, _ in top_values:
            if looks_like_null_proxy(v):
                continue
            try:
                yr = int(str(v).strip().split(".")[0])  # handle "2023.0"
                if not (1900 <= yr <= 2100):
                    out_of_range.append(v)
            except (ValueError, TypeError):
                out_of_range.append(v)
        if out_of_range:
            flags.append(f"year_out_of_range:{len(out_of_range)}_invalid_values")

    # ── Categorical compliance ────────────────────────────────────────
    if data_type == "text" and data_sub_type in ("categorical", "ordinal", "accuracy"):

        # Out-of-set check (when reference is available)
        if effective_ref and top_values:
            out_of_set = [
                v for v, _ in top_values
                if v and not looks_like_null_proxy(v) and str(v).strip().lower() not in effective_ref
            ]
            if out_of_set:
                flags.append(f"out_of_set_categorical:{len(out_of_set)}_values_not_in_reference")
        else:
            # Fallback: rarity heuristic (only when no reference set)
            if 0 < n_unique < CATEGORICAL_THRESHOLD and top_values:
                total_non_null = n_total - n_null
                if total_non_null > 0:
                    rare = [v for v, c in top_values if c / total_non_null < 0.01]
                    if rare:
                        flags.append(f"categorical_rare_values:{len(rare)}_values_below_1pct")

        # Multi-value separator detection (reference-aware)
        if top_values and not _is_url_field(field_name):
            # Values in the allowed-value vocabulary that contain & (not separators)
            amp_in_vocab = effective_ref and any("&" in v for v in effective_ref)
            # Also check top_values themselves: if & appears in every value it's vocab, not sep
            if not amp_in_vocab and allowed_values:
                amp_in_vocab = any("&" in str(v) for v in allowed_values)

            has_amp = any("&" in str(v) for v, _ in top_values if v)
            has_semi = any(";" in str(v) for v, _ in top_values if v)
            has_comma_sep = any(
                "," in str(v) and not looks_like_null_proxy(v)
                for v, _ in top_values if v
            )

            if has_comma_sep and (has_amp or has_semi):
                flags.append("wrong_multi_value_separator:comma_used_alongside_amp_or_semi")
            elif has_comma_sep and n_unique > 1:
                # Comma as sole separator — only flag if values look like lists
                comma_vals = [v for v, _ in top_values if v and "," in str(v)]
                if comma_vals:
                    flags.append("wrong_multi_value_separator:comma_only")

            if (has_amp and not amp_in_vocab) or has_semi:
                sep = []
                if has_amp and not amp_in_vocab:
                    sep.append("&")
                if has_semi:
                    sep.append(";")
                flags.append(f"multi_value_separator_check:uses_{'_and_'.join(sep)}")

    # ── Boolean encoding ──────────────────────────────────────────────
    if data_type == "text" and data_sub_type == "categorical" and n_unique <= 4:
        vals_lower = {str(v).strip().lower() for v, _ in top_values if v and not looks_like_null_proxy(v)}
        bool_encodings = [
            ("yes_no_lower", {"yes", "no"}),
            ("yes_no_title", {"Yes", "No"}),
            ("true_false", {"true", "false"}),
            ("true_false_title", {"True", "False"}),
            ("one_zero", {"1", "0"}),
            ("y_n", {"y", "n"}),
        ]
        for enc_name, enc_set in bool_encodings:
            if vals_lower <= {v.lower() for v in enc_set}:
                flags.append(f"boolean_encoding:{enc_name}")
                break

    return flags


def code_friendly_name(field_name):
    name = field_name.lower()
    name = re.sub(r"\s*\(", "_", name)
    name = re.sub(r"\)", "", name)
    name = re.sub(r"[^\w]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def count_duplicate_rows(conn, table_name, col_names):
    """Return count of duplicate rows (all-column match)."""
    cols = ", ".join(f'"{c}"' for c in col_names)
    try:
        result = conn.execute(
            f'SELECT COUNT(*) FROM (SELECT {cols}, COUNT(*) as _n FROM "{table_name}" '
            f'GROUP BY {cols} HAVING _n > 1)'
        ).fetchone()[0]
        return result
    except Exception:
        return 0


def analyze_table(conn, table_name, ref_sets, overrides):
    try:
        n_rows = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    except Exception as e:
        return None, None, f"Error: {e}"

    if n_rows == 0:
        return [], 0, None

    cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 0')
    col_names = [d[0] for d in cursor.description]

    n_duplicate_rows = count_duplicate_rows(conn, table_name, col_names)
    table_overrides = overrides.get(table_name, {})

    fields = []
    for col in col_names:
        n_null = conn.execute(
            f'SELECT COUNT(*) FROM "{table_name}" WHERE "{col}" IS NULL OR "{col}" = \'\''
        ).fetchone()[0]
        n_total = n_rows
        n_non_null = n_total - n_null
        null_rate = n_null / n_total if n_total else 0

        limit = CATEGORICAL_THRESHOLD * 4
        rows = conn.execute(
            f'SELECT "{col}", COUNT(*) as cnt FROM "{table_name}" '
            f'WHERE "{col}" IS NOT NULL AND "{col}" != \'\' '
            f'GROUP BY "{col}" ORDER BY cnt DESC LIMIT {limit}'
        ).fetchall()

        top_values = [(r[0], r[1]) for r in rows]
        n_unique_seen = len(top_values)

        if n_unique_seen == limit:
            n_unique = conn.execute(
                f'SELECT COUNT(DISTINCT "{col}") FROM "{table_name}" '
                f'WHERE "{col}" IS NOT NULL AND "{col}" != \'\''
            ).fetchone()[0]
        else:
            n_unique = n_unique_seen

        sample = conn.execute(
            f'SELECT "{col}" FROM "{table_name}" '
            f'WHERE "{col}" IS NOT NULL AND "{col}" != \'\' LIMIT 500'
        ).fetchall()

        numeric_results = [is_numeric(r[0]) for r in sample]
        real_results = [r for r in numeric_results if r is not None]
        portion_numeric = sum(real_results) / len(real_results) if real_results else None

        cfn = code_friendly_name(col)
        data_type, data_sub_type = guess_type(col, n_unique, portion_numeric, null_rate, top_values)
        is_required_guess = null_rate == 0.0

        ref_set, ref_set_source = _get_reference_set_for_field(cfn, ref_sets)

        flags = detect_flags(
            col, cfn, n_total, n_null, n_unique, portion_numeric,
            top_values, data_type, data_sub_type,
            allowed_values=None,  # enriched after API metadata is loaded
            ref_set=ref_set,
        )

        out_of_set_values = _compute_out_of_set(top_values, ref_set)

        # Apply overrides: mark suppressed flags
        field_overrides = table_overrides.get(col, [])
        suppressed_flag_names = {o["flag"] for o in field_overrides if isinstance(o, dict)}
        active_flags = [f for f in flags if f.split(":")[0] not in suppressed_flag_names]
        suppressed_flags = [
            {"flag": o["flag"], "reason": o.get("reason", "")}
            for o in field_overrides if isinstance(o, dict)
            and any(f.split(":")[0] == o["flag"] for f in flags)
        ]

        fields.append({
            "field_name": col,
            "code_friendly_name_guess": cfn,
            "n_total": n_total,
            "n_null": n_null,
            "n_non_null": n_non_null,
            "null_rate": round(null_rate, 4),
            "n_unique": n_unique,
            "top_values": top_values[:20],
            "portion_numeric": round(portion_numeric, 4) if portion_numeric is not None else None,
            "type_guess": data_type,
            "subtype_guess": data_sub_type,
            "is_required_guess": is_required_guess,
            "flags": active_flags,
            "suppressed_flags": suppressed_flags,
            "ref_set_source": ref_set_source,
            "out_of_set_values": out_of_set_values if out_of_set_values else None,
        })

    return fields, n_duplicate_rows, None


def load_field_metadata(conn, tracker_slug, tab_slug):
    rows = conn.execute(
        """
        SELECT field_name, definition, notes
        FROM _tracker_fields
        WHERE tracker_slug = ? AND (tab_slug = ? OR tab_slug = 'unknown') AND entry_type = 'field'
        """,
        (tracker_slug, tab_slug),
    ).fetchall()
    field_defs = {r[0]: {"definition": r[1], "notes": r[2]} for r in rows}

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
    path = Path("metadata") / f"{tracker_slug}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("header_info", {})


def load_api_metadata(tracker_slug):
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


def _rerun_flags_with_allowed_values(field, ref_sets):
    """Re-run flag detection after allowed_values from API metadata are available."""
    api_meta = field.get("api_metadata", {})
    allowed_raw = api_meta.get("allowed_values", [])
    if not allowed_raw:
        return

    allowed_set = {str(v).strip().lower() for v in allowed_raw}
    cfn = field["code_friendly_name_guess"]
    ref_set, ref_set_source = _get_reference_set_for_field(cfn, ref_sets)
    col = field["field_name"]

    new_flags = detect_flags(
        col, cfn,
        field["n_total"], field["n_null"], field["n_unique"],
        field["portion_numeric"],
        field["top_values"],
        field["type_guess"], field["subtype_guess"],
        allowed_values=allowed_set,
        ref_set=ref_set,
    )
    # Preserve suppressed flags; update active flags
    suppressed_names = {s["flag"] for s in field.get("suppressed_flags", [])}
    field["flags"] = [f for f in new_flags if f.split(":")[0] not in suppressed_names]
    field["allowed_values_from_api"] = sorted(allowed_raw)

    # Update reference set provenance and out-of-set values
    effective_ref = ref_set or allowed_set
    field["ref_set_source"] = ref_set_source or "api_allowed_values"
    oos = _compute_out_of_set(field["top_values"], effective_ref)
    field["out_of_set_values"] = oos if oos else None


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    ref_sets = load_reference_sets()
    overrides = load_overrides()
    conn = sqlite3.connect(DB_PATH)

    if ref_sets:
        print(f"Reference sets loaded: {', '.join(f'{k}({len(v)})' for k, v in ref_sets.items())}")
    if overrides:
        print(f"Overrides loaded for {len(overrides)} tables")

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '\\_%' ESCAPE '\\' ORDER BY name"
    ).fetchall()

    summary = []

    for (table_name,) in tables:
        parts = table_name.split("__", 1)
        tracker_slug = parts[0]
        tab_slug = parts[1] if len(parts) > 1 else "data"

        print(f"Analyzing: {table_name}")

        fields, n_duplicate_rows, error = analyze_table(conn, table_name, ref_sets, overrides)
        if error:
            print(f"  Error: {error}")
            continue

        field_defs, value_defs = load_field_metadata(conn, tracker_slug, tab_slug)
        api_meta = load_api_metadata(tracker_slug)

        n_with_definition = 0
        for f in fields:
            name = f["field_name"]
            if name in field_defs:
                f["definition_from_readme"] = field_defs[name].get("definition")
                f["notes_from_readme"] = field_defs[name].get("notes")
                if field_defs[name].get("definition"):
                    n_with_definition += 1
            if name in value_defs:
                f["value_definitions"] = value_defs[name]
            if name in api_meta:
                f["api_metadata"] = {
                    k: v for k, v in api_meta[name].items()
                    if k not in ("url", "aggregate_urls", "is_filterable", "filter_operators")
                }
                # Re-run flags now that we have allowed_values from API
                _rerun_flags_with_allowed_values(f, ref_sets)
                if f["api_metadata"].get("definition") and name not in field_defs:
                    n_with_definition += 1

        tracker_info = load_tracker_info(tracker_slug)
        n_flagged = sum(1 for f in fields if f["flags"])
        n_suppressed = sum(1 for f in fields if f.get("suppressed_flags"))
        print(f"  {len(fields)} fields | {n_flagged} flagged | {n_suppressed} suppressed | {n_duplicate_rows} dup rows")

        out = {
            "table_name": table_name,
            "tracker_slug": tracker_slug,
            "tab_slug": tab_slug,
            "n_rows": fields[0]["n_total"] if fields else 0,
            "n_duplicate_rows": n_duplicate_rows,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "tracker_info": tracker_info,
            "fields": fields,
        }
        out_path = OUTPUT_DIR / f"{table_name}.json"
        with open(out_path, "w", encoding="utf-8") as f_out:
            json.dump(out, f_out, indent=2, ensure_ascii=False)

        summary.append({
            "table_name": table_name,
            "tracker_slug": tracker_slug,
            "tab_slug": tab_slug,
            "n_rows": out["n_rows"],
            "n_duplicate_rows": n_duplicate_rows,
            "n_fields": len(fields),
            "n_flagged": n_flagged,
            "n_suppressed": n_suppressed,
            "n_with_definition": n_with_definition,
            "flags_by_type": _count_flag_types(fields),
            "in_research_db": in_research_db(tracker_slug),
        })

    with open(OUTPUT_DIR / "summary.json", "w", encoding="utf-8") as f:
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
