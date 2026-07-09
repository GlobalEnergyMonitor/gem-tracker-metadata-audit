# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

This project evaluates and standardizes metadata across 20+ tracker spreadsheets (Global Energy Monitor), with the long-term goal of migrating from spreadsheet-based data delivery to a centralized database. Each tracker spreadsheet has a metadata tab and one or more data tabs.

## Existing Work Context

- **2 trackers** (Global Coal Mine Tracker, Global Coal Plant Tracker) have robust field-level metadata that serves as the gold standard for this project
- Their full metadata JSON is available from the internal API and is saved locally at `metadata/api_coal_mines.json` and `metadata/api_coal_plants.json`
- **9 trackers** (including those 2) are already in a pilot DB with an internal API at `https://gem-api.thirdbear.net/` — useful as a reference but **not** the target architecture; that pilot was proof-of-concept and the goal now is to define a proper gold standard
- The remaining trackers have less developed metadata and are the primary targets for standardization work
- An Observable notebook (`8b80b4aa636d6e38@1341.js`) documents the original semi-automated metadata compilation workflow, including guessing logic and field schema design — this is the direct predecessor to `analyze.py`

## Research Database (`researchDBfiles/`)

GEM has a Django/PostgreSQL **research database** (separate from the proof-of-concept pilot API) that is the primary data entry system for many trackers. Files:

- `researchDBfiles/models.py` — Django ORM model definitions (3881 lines); source of truth for the DB schema
- `researchDBfiles/report_snapshot.duckdb` — DuckDB snapshot with three schemas:
  - `snapshot.*` — normalized relational tables (Entity, Plant, PowerUnit, SteelProject, SteelUnit, LNGProject, GOGETProject, etc.)
  - `reports.*` — denormalized output tables used to generate tracker spreadsheet exports (native types)
  - `reports_text.*` — same as `reports` but all values as text

**Trackers covered by the research DB** (based on `PROJECT_TYPES` enum and report tables):
combustion/gas, solar, wind, nuclear, geothermal, steel, hydro, LNG, GOGET (oil/gas extraction), coal (combustion units), bioenergy

**Trackers NOT in the research DB** (spreadsheet-only):
Coal Finance, Chemicals, Iron Ore Mines, Cement, Coal Terminals, Coal Mines (separate system), Portal Energetico

**Important caveat for interoperability work:** Project Managers download `reports.*` output and may modify the spreadsheets before public release. The `gem-data/` spreadsheets therefore may diverge from the DB snapshot. When comparing DB fields to spreadsheet fields, treat the DB as the canonical pre-PM-edit version. Use `duckdb` Python package to query the snapshot (it's already installed).

## Metadata Standards

**Primary standard: [Table Schema](https://specs.frictionlessdata.io/table-schema/) (Frictionless Data)** — governs field-level metadata (name, type, description, constraints, categorical values). Directly serves the three core needs: internal validation, front-end display, and download attribution.

**Dataset-level: [DCAT](https://www.w3.org/TR/vocab-dcat/)** — governs dataset-level metadata (title, publisher, license, temporal coverage). Used for discoverability and attribution on data slices made available for download.

**DDI: skip for now.** DDI is designed for survey data and carries conceptual overhead (universes, question text, etc.) that doesn't apply here. A well-structured Table Schema + DCAT setup is straightforward to crosswalk to DDI later if a specific stakeholder requires it.

The existing tracker metadata was built around internal validation, front-end friendliness, and download attribution — these map closely onto Table Schema + DCAT, so standardization is mostly renaming/reorganizing rather than rebuilding.

## Workflow Phases

1. **Map** — Compare existing metadata from the 2 robust trackers against Table Schema + DCAT properties to establish the target field structure
2. **Extract** — Parse each spreadsheet's metadata tab and field definitions into Table Schema-compatible JSON
3. **Ingest** — Load data tabs into a local SQLite database
4. **Analyze** — Run queries to extract per-field, per-tracker statistics (type distributions, unique values, nullability, etc.)
5. **Audit UI** — Simple web frontend to surface data quality issues (e.g. numeric fields with non-numeric outliers, categorical fields with likely typos)
6. **Interoperability** — Cross-tracker analysis to identify schema conflicts and tradeoffs for a unified schema; measure distance from the established field standardization used by the 9 pilot trackers

## Field-Level Metadata Schema

Each field in a tracker's metadata JSON has the following properties. The gold-standard examples are in `metadata/api_coal_mines.json` and `metadata/api_coal_plants.json`.

**Always present:**
- `name` — display name (matches spreadsheet column header)
- `definition` — human-readable description
- `code_friendly_name` — snake_case API field name
- `data_type` — `text` | `numeric` | `datetime` | `boolean`
- `data_sub_type` — see type system below
- `category` — grouping for UI display (see categories below)
- `is_required` — boolean
- `present_in_tabs` — array of tab names where this field appears

**Conditional (by data_type/sub_type):**
- `allowed_values` — array, for categorical/ordinal/accuracy
- `values_definitions` — object `{value: definition}`, for categorical/ordinal
- `order_of_values` — array, for ordinal fields
- `multiple_values_separator` — string (`&`, `;`, `,`), when a cell may contain multiple values
- `required_format_regex` — string, for structured text (IDs, URLs)
- `datetime_format` — string (e.g. `YYYY`), for datetime fields
- `unit_name_short` / `unit_name_long` — strings, for measurement fields
- `accuracy_for_field` — field name(s) this accuracy field qualifies
- `associated_field` — related field name(s) (e.g. a year-of-X field linked to its X)
- `yes_value` / `no_value` — strings, for boolean fields
- `taxonomy` — cross-tracker semantic tag (`unit`, `location`, `country_area`, `status`, `latitude`, `longitude`, `state_province`, `owner_name`, `owner_entity_id`, `parent_name`, `parent_entity_id`)

**Optional enrichment:**
- `null_is_what` — what a null value means in context
- `flags` — notes on known data quality issues
- `other_notes` / `other_rules` — additional validation rules
- `histogram_weight` — hint for numeric display weighting

**Type system (`data_type` / `data_sub_type`):**

| data_type | data_sub_type | Key extra fields |
|-----------|--------------|-----------------|
| text | categorical | allowed_values, values_definitions, multiple_values_separator |
| text | ordinal | allowed_values, values_definitions, order_of_values |
| text | accuracy | allowed_values, accuracy_for_field, order_of_values |
| text | structured | required_format_regex |
| text | unstructured | — |
| datetime | year | datetime_format |
| numeric | measurement | unit_name_short, unit_name_long |
| numeric | percent | — |
| numeric | null | — |
| boolean | null | yes_value, no_value |

**Standard field categories** (ordered for UI display):
`IDs`, `Names`, `Geography`, `Main`, `Size`, `Age`, `Details`, `Reference`, `Ownership`, `End Users`, `Methane`, `CO2 estimates`

## Data Layout

- Spreadsheets live in `gem-data/` directory
- Each spreadsheet: one metadata tab (README, About, etc.) + one or more data tabs
- SQLite database: `tracker_data.db` (created by ingest scripts)
- Gold-standard metadata JSON: `metadata/api_coal_mines.json`, `metadata/api_coal_plants.json`
- Extracted README/About metadata: `metadata/{tracker_slug}.json`
- Field-level analysis outputs: `analysis/{tracker_slug}__{tab_slug}.json`
- Cross-table summary: `analysis/_summary.json`

## Architecture

### Scripts (Python)
- `extract_metadata.py` — reads metadata tabs (README, About) from all spreadsheets; outputs `metadata/{tracker_slug}.json`. Detects "Dictionary" and "Field Descriptions" sections; cross-references entries against data tab column headers to classify as `field` vs `definition` (category value).
- `ingest.py` — loads data tabs into SQLite (all TEXT, chunked); skips known non-data tabs; deduplicates column names. Also populates `_tracker_fields` and `_trackers` tables from metadata JSON if available.
- `analyze.py` — per-field statistics (null rate, unique count, numeric portion, top values) + type/subtype guesses mirroring the Observable notebook's `guesses()` logic. Flags: `high_null_rate`, `mostly_numeric_with_outliers`, `categorical_rare_values`, `potential_multi_value`. Outputs `analysis/{table_name}.json` and `analysis/_summary.json`. Enriches output with README-extracted definitions and API gold-standard metadata where available.

### Web UI (to be built)
- Plain JS, served locally (no framework needed)
- Reads `analysis/*.json` as static files — no server-side logic required
- Key views: per-tracker field browser, flagged field audit, categorical value distributions, cross-tracker field name matching

### SQLite Conventions
- Table naming: `{tracker_slug}__{tab_slug}` (double underscore separator)
- All values ingested as TEXT; type inference happens at analysis time, not ingest time
- `_tracker_fields` — parsed README/About metadata (field_name, definition, notes, entry_type, parent_field, tracker_slug, tab_slug)
- `_trackers` — dataset-level metadata (title, citation, contact, license) per tracker

### Known Tab Classification Issues
Some trackers have non-standard tab structures that aren't auto-detected:
- `METADATA_TAB_NAMES` in both `extract_metadata.py` and `ingest.py` must be kept in sync
- Portal Energetico has `about_*` tabs per data tab — these are currently ingested as data tables
- GMET has a "Data Dictionary" tab treated as a data table (not in the skip list)
- About tabs for most trackers (non-Coal) use formats that don't match the section-header detection keywords — they'll have 0 extracted fields until their format is handled

## Key Dependencies

```
openpyxl       # reading .xlsx files
sqlite3        # stdlib, no install needed
```

Install: `pip3 install openpyxl`  (pandas not currently used)

## Running Things

```bash
# 1. Extract metadata tabs → metadata/*.json
python3 extract_metadata.py

# 2. Ingest all data tabs → tracker_data.db
python3 ingest.py

# 3. Analyze fields → analysis/*.json
python3 analyze.py

# 4. Audit web UI (to be built)
# open index.html in browser, or: python3 -m http.server 8080
```

Run all three steps in sequence after adding new spreadsheets to `gem-data/`.

## Design Principles

- Ingest raw, analyze later — never coerce types during ingest; keep original values intact
- One script per phase — keep extract/ingest/analyze as separate, re-runnable steps
- Idempotent ingest — dropping and recreating tables on each run is fine at this scale
- Analysis outputs are files (`analysis/*.json`) so the UI can be static if needed
