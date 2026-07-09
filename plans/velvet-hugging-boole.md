# Plan: Per-tracker compliance + cross-tracker compatibility views

## Context

The existing audit UI surfaces a lot of per-field detail that's hard to act on. Two distinct goals have now been identified:

1. **Per-tracker compliance** — does each tracker meet internal org standards for field encoding (nulls, separators, numeric purity, allowed values)? Some checks are "always wrong" (numeric outliers); others are "standard compliance" (separator choice, boolean encoding).
2. **Cross-tracker interoperability** — across the 7 key field categories that matter for schema unification, how consistently are trackers implementing them?

These are separate views but both live in the audit UI.

---

## Part A: Per-tracker compliance checks

### The 9 compliance checks

Split into two bins based on severity:

**Always wrong (flag as error):**
1. `numeric_outliers` — a field guessed as numeric (>95% numbers) has real non-numeric, non-null-proxy values
2. `non_standard_null_proxies` — a numeric or boolean field contains null-proxy shorthands (`*`, `-`, `UA`, `--`, etc.) instead of actual SQL NULL / empty string; suggests ETL gap
3. `wrong_multi_value_separator` — a multi-value field uses `,` as separator (conflicts with CSV export); org standard is `&` or `;`. **Important caveat**: `&` frequently appears *within* single categorical values (e.g. "iron & steel", "oil & refining", "pulp & paper" in Captive Industry Type), so `&` cannot be naively treated as a separator signal. Detection must be reference-aware: if `&` appears within any value in the field's allowed-value set, it is part of the vocabulary, not a separator. For fields with a known allowed-value set, test candidate separators by splitting and checking whether resulting tokens are all in the set. For fields without a reference, flag `&` as a low-confidence heuristic only.
4. `out_of_set_categorical` — a categorical field has values outside its reference set. Reference priority: (a) org-level reference sets (country, status, fuel category — extracted from DuckDB); (b) README-defined `allowed_values`. When a reference set exists, this replaces `categorical_rare_values` entirely — rarity is not meaningful for country fields (Botswana may appear once) or any other field with a known allowed-value list.
5. `duplicate_rows` — duplicate row detection per table (all-column match)

**Standard compliance (flag as warning, org convention may vary):**
6. `multi_value_separator_check` — flag which separator is in use (`&`, `;`, or `,`) so org can audit consistency
7. `boolean_encoding` — boolean fields: detect and report which encoding is used (`yes/no`, `Yes/No`, `TRUE/FALSE`, `1/0`, etc.) — cross-tracker consistency is the goal
8. `year_format` — fields guessed as datetime/year: verify values are 4-digit integers (1900–2100); flag out-of-range values
9. `required_field_null_rate` — fields defined as `is_required` in README metadata but having nulls

### Where compliance data lives

- Checks 1, 2, 3, 6, 7, 8 can be computed in `analyze.py` at analysis time — add to per-field `flags` and/or a new `compliance` dict
- Check 4 requires a reference set. Org-level references (country names, status values, fuel categories) are extracted from `researchDBfiles/report_snapshot.duckdb` into `reference_sets.json` (one-time extraction step, can be re-run). README-defined `allowed_values` are already available via `field_defs` / `api_meta`. When a reference set is present, `categorical_rare_values` is suppressed for that field.
- Check 5 (duplicate rows) is a table-level stat, not per-field — add to the table-level output JSON
- Check 9 requires `is_required` from metadata — already available via `api_meta` / `field_defs`

### Reference set extraction

New script `extract_references.py` (or a function in `analyze.py`):
- Reads `researchDBfiles/report_snapshot.duckdb`
- Exports `reference_sets.json` with keys: `country` (from `snapshot.country.gemName`), `status` (from `snapshot.status.name`), `fuel_category` (from `snapshot.fuel_category.name`)
- `analyze.py` detects country fields by `code_friendly_name` containing `country` or `country_area`; status fields by name containing `status`
- Reference matching is case-insensitive

### Human feedback on compliance findings

The UI maintains suppression state in `localStorage` (survives page refresh, no server needed). The flow:

1. **In the compliance tab**, each flagged field row has a **Suppress** toggle. Clicking it marks the flag as suppressed and opens an optional free-text reason field.
2. All suppression state is stored in `localStorage` under a key like `gem_overrides_v1`.
3. A **"Download overrides.json"** button in the compliance tab header exports the current state as a properly-formatted JSON file. This file can be committed to the repo and served as a static file.
4. On page load, the UI merges two sources: the static `overrides.json` (committed, loaded via fetch) overlaid with any newer `localStorage` state — so committed suppressions are always the baseline.
5. **Unsaved changes warning**: `window.beforeunload` fires if `localStorage` has suppressions that haven't been downloaded since the last change, with a message like "You have unsuppressed flags not yet saved to overrides.json."

`overrides.json` format (hand-editable too):
```json
{
  "global_coal_plant_tracker_january_2026__units": {
    "Capacity (MW)": [
      {"flag": "numeric_null_proxies", "reason": "intentional — field uses UA for missing values, not a data error"}
    ]
  }
}
```

The UI renders suppressed flags in grey with the reason shown on hover. Active flags remain colored (error/warning).

---

## Part B: Cross-tracker compatibility categories

### The 7 interoperability categories

Extended from the Ownership API's original 6 to add **Entities** (Owner/Operator), drawing on what the Ownership Tracker already standardized:

| Category | Key `code_friendly_name` patterns | Why it matters |
|---|---|---|
| **IDs** | `gem_unit_id`, `gem_location_id`, `gem_project_id`, `gem_plant_id`, `gem_mine_id`, `gem_terminal_id`, `gem_combo_id`, `gem_asset_id`, `gem_phase_id` | Join key across trackers; plant vs. unit level must be distinguishable |
| **Names** | `unit_name`, `plant_name`, `project_name`, `name` | Human-readable identity for display and deduplication |
| **Status** | `status`, `operational_status`, `project_status`, `plant_status` | Present in nearly every tracker; biggest known value-encoding divergence |
| **Capacity / Size** | `capacity_mw`, `capacity`, `total_capacity`, `installed_capacity`, `production_capacity` | Primary magnitude field; units vary by sector |
| **Location / Geodata** | `latitude`, `longitude`, `country_area`, `country`, `location_accuracy`, `state_province`, `subnational_unit`, `region`, `local_area_taluk_county` | Geographic queries; accuracy encoding varies |
| **Temporal** | `start_year`, `retired_year`, `year`, `commissioning_year`, `announced_year`, `construction_year`, `shelved_year`, `cancelled_year` | Time-sliced queries ("operating in year X"); field names diverge significantly |
| **Entities (Owner / Operator)** | `owner`, `operator`, `parent_company`, `owner_name`, `operator_name` | Standardized by the Ownership Tracker already; key for company-level queries |

Category mapping lives in a `categories.json` config file (easy to edit without touching JS).

### What we learn from GIPT and Ownership Tracker

These two trackers have already implemented cross-tracker normalization — treat them as implementation references, not a new category:

- **GIPT pattern**: every field has a `[ref]` companion + `Tracker` + `Data Source` fields → Data Provenance is a solved problem *within GIPT*; for other trackers it's aspirational and doesn't need its own audit category yet
- **Ownership Tracker pattern**: entity-level rollup keyed by GEM ID with status-based capacity aggregation → the GEM ID field and the owner/operator fields are already the target shape for Entities; the compatibility view should show which trackers are "ready" (have `owner_name` + a GEM entity ID)

---

## What to build (UI views)

### 1. Per-tracker compliance tab (new tab within each tracker view)

Add a **Compliance** tab alongside the existing field list tab on each tracker's detail page.

- Summary bar: count of errors / warnings / suppressed flags
- Table: one row per flagged field, columns = field name | check | severity | suppressed?
- "Suppression" button per row that adds the flag to `overrides.json` (in-page, writes via a local file picker or shows copy-paste JSON)

The suppression UI can be simple for now: clicking "suppress" shows the JSON fragment to paste into `overrides.json`. Full in-page editing is a follow-on.

### 2. Cross-tracker compatibility page (Categories tab, default)

Add a **Categories** tab to the existing cross-tracker page as the default view (before Exact/Fuzzy).

Per-panel layout (one panel per category):
- Header: category name + one-line description of what compatibility means here
- Tracker × field table:
  - Rows: each tracker (with DB badge)
  - Column A: field name used (or "—" if absent)
  - Column B: value Jaccard (for Status/categorical) or unit annotation (for Capacity)
  - Column C: presence indicator (green check / red dash)
- Below table: plain-text "compatibility blockers" callout (e.g. "Status: 22 of 24 trackers have tracker-specific values not shared by others")

### 3. Updated welcome page

Replace the generic welcome with a **two-panel overview**:

- **Left**: 7-row category compatibility summary table (category | trackers covered | name consistency | value consistency | key blocker)
- **Right**: compact tracker list with DB/CSV badge + colored dots for which categories each tracker covers

### 4. `n_with_definition` in summary JSON (small analyze.py addition)

Add one field to `analyze.py`'s per-table summary output: count of fields that have a `definition_from_readme`. Useful context in the tracker detail view.

---

## Files to change

| File | Change |
|---|---|
| `extract_references.py` | New one-time script: reads DuckDB, writes `reference_sets.json` with canonical country/status/fuel lists |
| `reference_sets.json` | Generated file: `{"country": [...], "status": [...], "fuel_category": [...]}` (case-insensitive matching at analysis time) |
| `analyze.py` | Add compliance checks to `detect_flags()`: null proxy check for numeric/boolean fields, wrong separator detection, year value validation, out-of-set categorical check (using `reference_sets.json` + README values; suppress `categorical_rare_values` when reference set exists). Add `duplicate_rows` count at table level. Add `n_with_definition` to summary entries. Load `overrides.json` and mark suppressed flags. |
| `cross_tracker.py` | Load `categories.json` and annotate each exact group with its category. Add `categories` section to output JSON with per-category tracker coverage stats. |
| `categories.json` | New config file: maps category names to lists of `code_friendly_name` patterns (supports prefix/suffix matching). |
| `overrides.json` | New hand-edited file: maps `{table_name: {field_name: [flag, ...]}}` for suppression. Start as `{}`. |
| `app.js` | (1) Compliance tab in tracker detail view; (2) Categories tab in cross-tracker page; (3) Updated welcome page with category summary + tracker dot matrix; (4) Load/apply `overrides.json` for flag display. |
| `style.css` | Styles for compliance tab, suppressed-flag state, category panels, tracker coverage dots, compatibility blocker callouts. |

---

## Open questions (need Stephen's input before/during implementation)

1. **Category mapping review**: the `categories.json` field-name lists above should be reviewed — some names are ambiguous (e.g. `name` by itself could be a project name or a value label). Will confirm at implementation time by checking what trackers actually have fields matching those patterns.

2. **Suppression UX**: The plan shows a copy-paste approach for `overrides.json`. Is that acceptable for now, or should we wire up an actual file-write (would require a local server instead of static file serving)?

3. **Boolean encoding standard**: What is the org's canonical encoding? (`yes`/`no` lowercase? Title case?) Knowing this lets the compliance check be specific rather than just "flag any boolean field."

---

## First steps before any code changes

1. Copy this plan file into `plans/velvet-hugging-boole.md` in the repo and commit it, so plan history is versioned alongside the code.

2. Write `docs/metadata-standards.md` — a reference document covering:
   - **Current stack**: Table Schema (field-level) + DCAT (dataset-level) — why these were chosen
   - **schema.org/Dataset**: near-zero-cost discoverability layer; crosswalk to DCAT is well-documented; useful when GEM data appears on download pages or data portals
   - **Data Package** (Frictionless): the dataset-level wrapper that pairs with Table Schema; a `datapackage.json` per tracker would formalize what `metadata/*.json` already does and make trackers directly consumable by Frictionless tooling
   - **CSVW** (CSV on the Web, W3C): the only standard with a field-level `separator` property — directly relevant to the multi-value separator problem; worth revisiting if GEM formalizes CSV delivery
   - **DataCite**: versioned DOI/citation metadata; maps onto DCAT; relevant if GEM publishes versioned releases with persistent identifiers
   - **SDMX**: used by Eurostat/IEA/World Bank for statistical time series; code lists are analogous to `allowed_values`; overhead too high for current needs but worth knowing for future interoperability with those orgs
   - **ISO 19115**: geographic metadata standard; relevant given every tracker has lat/lon; XML-heavy, not worth adopting now but crosswalkable later for GIS platform integration
   - **DDI**: designed for survey data; deferred indefinitely — Table Schema + DCAT is crosswalkable to DDI if a specific stakeholder requires it
   - **Compatibility matrix**: a table showing which properties in GEM's current schema map to which standard(s)
   
   Commit alongside the plan file.

---

## Verification

1. `python3 extract_references.py` — confirm `reference_sets.json` created with country/status/fuel lists
2. `python3 analyze.py` — check that compliance flags appear in per-table JSON; check `n_with_definition` in `_summary.json`; verify a country field does NOT get `categorical_rare_values` (should get `out_of_set_categorical` instead if values are valid countries)
3. `python3 cross_tracker.py` — confirm `categories` section in `_cross_tracker.json`; verify category assignments on known fields (e.g. `status` → Status, `latitude` → Location)
4. `python3 -m http.server 8080` → open localhost:8080:
   - Welcome page: 7-row category table + tracker dot matrix
   - Pick a tracker → Compliance tab shows flagged fields; country fields show out-of-set check rather than rare-value check
   - Cross-tracker page → Categories tab as default; Status panel shows divergence; Latitude panel shows consistency
