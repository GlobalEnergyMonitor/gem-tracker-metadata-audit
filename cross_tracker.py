#!/usr/bin/env python3
"""
cross_tracker.py

Groups fields that appear across multiple trackers to surface standardization
opportunities and naming conflicts.

Pass 1 — Exact: fields sharing the same normalized name (code_friendly_name_guess)
          across ≥2 trackers.
Pass 2 — Fuzzy: pairs of distinct names with token-level Jaccard similarity ≥0.5
          that together span ≥2 trackers.

For categorical groups/pairs, value-set overlap is computed to show whether fields
with the same name actually encode the same values.

Output: analysis/_cross_tracker.json
Run:    python3 cross_tracker.py
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ANALYSIS_DIR = Path("analysis")
CATEGORIES_PATH = Path("categories.json")

SKIP_TRACKER_SLUGS = {"sqlite_sequence"}
SKIP_TAB_SLUGS = {
    "introduction_terminology", "column_dictionary",
    "regions_area_and_countries", "about_ggit_lng",
}
SKIP_TAB_PREFIX = "about_"
FUZZY_THRESHOLD = 0.5
MIN_TRACKERS = 2

METHODOLOGY = (
    "Fields are grouped in two passes. "
    "Pass 1 (exact): fields whose normalized snake_case names match exactly across "
    "two or more trackers are collected as a group; the more trackers share a name, "
    "the stronger the standardization signal. "
    "Pass 2 (fuzzy): pairs of distinct normalized names whose token-set Jaccard "
    "similarity is ≥0.5 are flagged as potential synonyms or variants — for example, "
    "'status' and 'plant_status' share one token out of two (Jaccard = 0.50). "
    "For categorical fields in any group or pair, the top-value sets are compared: "
    "the Jaccard score reflects overlap across all value sets; 'shared' values appear "
    "in every field; 'partial' values appear in at least half. Value divergence among "
    "same-name fields flags tracker-specific extensions or encoding differences that "
    "need resolving before schema unification."
)


# ── Category mapping ──────────────────────────────────────────────────────────

def load_categories():
    """Load categories.json → {category_name: {description, patterns: [str]}}"""
    if not CATEGORIES_PATH.exists():
        return {}
    with open(CATEGORIES_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def assign_category(code_friendly_name, categories):
    """Return the first matching category name for a cfn, or None."""
    cfn = code_friendly_name.lower()
    for cat_name, cat in categories.items():
        for pattern in cat.get("patterns", []):
            if cfn == pattern or cfn.startswith(pattern + "_") or cfn.endswith("_" + pattern) or pattern in cfn:
                return cat_name
    return None


# ── Data loading ──────────────────────────────────────────────────────────────

def load_fields():
    summary_path = ANALYSIS_DIR / "_summary.json"
    db_map = {}
    if summary_path.exists():
        with open(summary_path, encoding="utf-8") as f:
            for entry in json.load(f):
                db_map[entry["table_name"]] = entry.get("in_research_db", False)

    records = []
    for path in sorted(ANALYSIS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        tracker = data["tracker_slug"]
        tab = data["tab_slug"]
        if tracker in SKIP_TRACKER_SLUGS:
            continue
        if tab in SKIP_TAB_SLUGS or tab.startswith(SKIP_TAB_PREFIX):
            continue
        in_db = db_map.get(data["table_name"], False)
        for field in data.get("fields", []):
            records.append({
                "tracker_slug": tracker,
                "tab_slug": tab,
                "table_name": data["table_name"],
                "in_research_db": in_db,
                "field_name": field["field_name"],
                "code_friendly_name": field["code_friendly_name_guess"],
                "type_guess": field.get("type_guess"),
                "subtype_guess": field.get("subtype_guess"),
                "top_values": field.get("top_values", [])[:15],
                "null_rate": field.get("null_rate", 0),
                "n_total": field.get("n_total", 0),
                "definition_from_readme": field.get("definition_from_readme"),
            })
    return records


# ── Algorithms ────────────────────────────────────────────────────────────────

def token_jaccard(a, b):
    ta = set(a.split("_")) - {""}
    tb = set(b.split("_")) - {""}
    if not (ta or tb):
        return 0.0
    return len(ta & tb) / len(ta | tb)


def compute_value_overlap(field_list):
    cat_fields = [
        f for f in field_list
        if f.get("subtype_guess") in ("categorical", "ordinal", "accuracy")
        and f.get("top_values")
    ]
    if len(cat_fields) < 2:
        return None

    # One value set per table (deduplicate if same tracker/tab appears multiple times)
    keyed = {}
    for f in cat_fields:
        key = f["table_name"]
        keyed[key] = {
            "tracker_slug": f["tracker_slug"],
            # Normalize case for comparison; keep original for display via canonical map
            "values": {str(v).strip().lower() for v, _ in f["top_values"]},
            "values_display": {str(v).strip().lower(): str(v).strip() for v, _ in f["top_values"]},
        }
    if len(keyed) < 2:
        return None

    value_sets = [v["values"] for v in keyed.values()]
    union = set().union(*value_sets)
    if not union:
        return None
    intersection = set.intersection(*value_sets)
    jaccard = round(len(intersection) / len(union), 3)

    # Canonical display form: prefer title-case; take the most title-case-like occurrence
    all_display = {}
    for info in keyed.values():
        for low, disp in info["values_display"].items():
            if low not in all_display or disp[0].isupper():
                all_display[low] = disp

    n = len(value_sets)
    partial = {
        v for v in union
        if max(2, n / 2) <= sum(1 for s in value_sets if v in s) < n
    }

    tracker_specific = {
        info["tracker_slug"]: sorted(
            all_display.get(v, v) for v in info["values"] - intersection - partial
        )
        for info in keyed.values()
        if info["values"] - intersection - partial
    }

    return {
        "n_fields": len(keyed),
        "jaccard": jaccard,
        "shared_values": sorted(all_display.get(v, v) for v in intersection),
        "partial_values": sorted(all_display.get(v, v) for v in partial),
        "tracker_specific": tracker_specific,
    }


def field_summary(f):
    return {
        "tracker_slug": f["tracker_slug"],
        "tab_slug": f["tab_slug"],
        "in_research_db": f["in_research_db"],
        "field_name": f["field_name"],
        "code_friendly_name": f["code_friendly_name"],
        "type_guess": f["type_guess"],
        "subtype_guess": f["subtype_guess"],
        "null_rate": f["null_rate"],
        "top_values": f["top_values"][:10],
        "definition_from_readme": f["definition_from_readme"],
    }


def most_common_label(fields):
    if not fields:
        return ""
    return Counter(f["field_name"] for f in fields).most_common(1)[0][0]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    records = load_fields()
    print(f"Loaded {len(records)} field records.")

    categories = load_categories()
    print(f"Loaded {len(categories)} interoperability categories.")

    by_name = defaultdict(list)
    for r in records:
        by_name[r["code_friendly_name"]].append(r)

    # ── Pass 1: Exact groups ──────────────────────────────────────
    exact_groups = []
    for name, fields in sorted(by_name.items()):
        trackers = sorted({f["tracker_slug"] for f in fields})
        if len(trackers) < MIN_TRACKERS:
            continue
        vo = compute_value_overlap(fields)
        exact_groups.append({
            "group_key": name,
            "label": most_common_label(fields),
            "category": assign_category(name, categories),
            "n_trackers": len(trackers),
            "trackers": trackers,
            "subtypes": sorted({f["subtype_guess"] for f in fields if f["subtype_guess"]}),
            "fields": [field_summary(f) for f in sorted(fields, key=lambda f: f["tracker_slug"])],
            "value_overlap": vo,
        })

    exact_groups.sort(key=lambda g: (-g["n_trackers"], g["group_key"]))
    print(f"Exact groups (≥{MIN_TRACKERS} trackers): {len(exact_groups)}")

    # ── Pass 2: Fuzzy pairs ───────────────────────────────────────
    name_trackers = {
        name: {f["tracker_slug"] for f in fields}
        for name, fields in by_name.items()
    }
    unique_names = sorted(name_trackers.keys())

    fuzzy_pairs = []
    for i, name_a in enumerate(unique_names):
        for name_b in unique_names[i + 1:]:
            sim = token_jaccard(name_a, name_b)
            if sim < FUZZY_THRESHOLD:
                continue
            combined = name_trackers[name_a] | name_trackers[name_b]
            if len(combined) < MIN_TRACKERS:
                continue
            all_fields = by_name[name_a] + by_name[name_b]
            fuzzy_pairs.append({
                "name_a": name_a,
                "name_b": name_b,
                "label_a": most_common_label(by_name[name_a]),
                "label_b": most_common_label(by_name[name_b]),
                "similarity": round(sim, 3),
                "n_trackers_a": len(name_trackers[name_a]),
                "n_trackers_b": len(name_trackers[name_b]),
                "trackers_a": sorted(name_trackers[name_a]),
                "trackers_b": sorted(name_trackers[name_b]),
                "fields_a": [field_summary(f) for f in sorted(by_name[name_a], key=lambda f: f["tracker_slug"])],
                "fields_b": [field_summary(f) for f in sorted(by_name[name_b], key=lambda f: f["tracker_slug"])],
                "value_overlap": compute_value_overlap(all_fields),
            })

    fuzzy_pairs.sort(key=lambda p: (-p["similarity"], -(p["n_trackers_a"] + p["n_trackers_b"])))
    print(f"Fuzzy pairs (Jaccard ≥{FUZZY_THRESHOLD}): {len(fuzzy_pairs)}")

    # ── Category summary ──────────────────────────────────────────
    # For each category, collect all trackers that have at least one matching field
    # and the exact groups assigned to that category.
    all_trackers = sorted({r["tracker_slug"] for r in records})
    category_summary = {}
    for cat_name, cat_info in categories.items():
        cat_groups = [g for g in exact_groups if g["category"] == cat_name]
        # Per-tracker: which field name(s) they use for this category
        tracker_fields = defaultdict(list)
        for group in cat_groups:
            for f in group["fields"]:
                tracker_fields[f["tracker_slug"]].append({
                    "field_name": f["field_name"],
                    "group_key": group["group_key"],
                    "in_research_db": f["in_research_db"],
                })
        # Also check single-tracker fields (not in exact_groups) for coverage
        for r in records:
            cfn = r["code_friendly_name"]
            if assign_category(cfn, categories) == cat_name:
                slug = r["tracker_slug"]
                already = any(e["group_key"] == cfn for e in tracker_fields[slug])
                if not already:
                    tracker_fields[slug].append({
                        "field_name": r["field_name"],
                        "group_key": cfn,
                        "in_research_db": r["in_research_db"],
                    })

        trackers_with_category = sorted(tracker_fields.keys())
        category_summary[cat_name] = {
            "description": cat_info.get("description", ""),
            "n_trackers_with_field": len(trackers_with_category),
            "trackers_with_field": trackers_with_category,
            "trackers_missing_field": [t for t in all_trackers if t not in tracker_fields],
            "n_exact_groups": len(cat_groups),
            "exact_group_keys": [g["group_key"] for g in cat_groups],
            "tracker_fields": dict(tracker_fields),
            # Value consistency: aggregate Jaccard across categorical groups in this category
            "value_jaccard": _mean_jaccard(cat_groups),
        }

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": METHODOLOGY,
        "stats": {
            "n_field_records": len(records),
            "n_unique_names": len(by_name),
            "n_exact_groups": len(exact_groups),
            "n_fuzzy_pairs": len(fuzzy_pairs),
            "n_trackers": len(all_trackers),
        },
        "categories": category_summary,
        "exact_groups": exact_groups,
        "fuzzy_pairs": fuzzy_pairs,
    }

    out_path = ANALYSIS_DIR / "_cross_tracker.json"
    with open(out_path, "w", encoding="utf-8") as f_out:
        json.dump(out, f_out, indent=2, ensure_ascii=False)
    print(f"Output: {out_path}")


def _mean_jaccard(groups):
    """Average value Jaccard across groups that have value_overlap data."""
    scores = [
        g["value_overlap"]["jaccard"]
        for g in groups
        if g.get("value_overlap") and g["value_overlap"].get("jaccard") is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 3)


if __name__ == "__main__":
    main()
