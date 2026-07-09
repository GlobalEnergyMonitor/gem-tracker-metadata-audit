# STD-05: Numeric Field Purity

**Status:** Draft — for discussion with Data Team  
**Scope:** All tracker spreadsheets and the research database export pipeline

---

## Current State

Numeric fields across trackers contain several distinct types of non-numeric content. These are not randomly distributed — each type represents a specific encoding convention that a different team or tracker adopted to solve a real problem. The question is whether those problems should be solved in the data or elsewhere.

### Type 1 — Dash (`-`) as null proxy

The single dash is used as a missing-value marker in numeric fields across two major trackers:

- **Coal Mine Tracker** — annual production columns (`Coal Output (Annual, Mt) 2017` through `2023`): thousands of `-` values per year column, representing mines with no production data for that year. The proportion of `-` increases for earlier years (2,746 `-` values in 2017 vs. 779 in 2023), which likely reflects both data availability and the tracker's coverage history.
- **Coal Terminals Tracker** — `Capacity (Mt)`, `Start Year`, `Retired Year`: `-` used where data is unknown or not applicable.
- **GMET** — `GEM Coal Mine Methane Emissions Estimate (Mt/yr)`: 300 `-` values alongside numeric estimates.

This is a variant of the null proxy problem raised in STD-01, applied specifically to numeric fields. A dash cannot be stored as a number, so it forces the column to be treated as text at ingest time.

### Type 2 — `N/A` as "doesn't apply" in type-specific capacity fields

Iron & Steel uses `N/A` in technology-specific capacity columns:

| Field | N/A count |
|---|---|
| Nominal BOF steel capacity (ttpa) | 1,220 |
| Nominal BF capacity (ttpa) | 1,078 |
| Nominal EAF steel capacity (ttpa) | 904 |
| Nominal iron capacity (ttpa) | 809 |
| Nominal DRI capacity (ttpa) | 1,553 |
| Other/unspecified steel capacity (ttpa) | 1,794 |

Here `N/A` means "this plant doesn't have a BOF / BF / EAF / DRI unit" — a legitimate "doesn't apply" case. An electric arc furnace plant genuinely has no BOF capacity; the column doesn't apply to it. This is the numeric counterpart of the "doesn't apply" distinction in STD-01.

### Type 3 — `>0` as a qualified assertion

`>0` appears in Iron & Steel capacity fields across three trackers (Iron & Steel plant data, Iron unit data, Ownership Tracker):

| Field | `>0` count |
|---|---|
| Nominal iron capacity (ttpa) | 185 + 32 |
| Nominal crude steel capacity (ttpa) | 97 |
| Current capacity (ttpa) — iron units | 22 |
| Nominal EAF steel capacity (ttpa) | 10 |
| Nominal DRI capacity (ttpa) | 17 |
| Current capacity (ttpa) — steel units | 9 |

`>0` is not a null. It is an assertion: "this plant has positive capacity in this category, but we do not know the exact value." It's a bounded unknown — the researcher knows the lower bound (greater than zero) but not the precise figure. This is semantically closer to an imputed or qualified value than to a missing value, and is closely related to the discussion in STD-10 (Imputed Values).

### Type 4 — `*` as a restricted-data marker

The asterisk appears in production and capacity columns with specific semantic meaning:

- **GMET** — `Production (Mtpa)`: 3,154 `*` values, making it the single most common value in that column. Given the context (Chinese coal mine production data), `*` almost certainly means "production data exists but is not publicly disclosed" — a regulatory or confidentiality restriction rather than a data gap.
- **Coal Terminals** — `Capacity (Mt)`: 69 `*` values. Same probable meaning: capacity not publicly available.
- **Portal Energetico** — various production/capacity fields: smaller counts, same pattern.

`*` conveys something that empty cell does not: the researcher knows data exists somewhere but cannot obtain it. It's a research-quality signal, not just a missing-value placeholder.

### Type 5 — Excel error propagation

`#N/A` appears in a small number of fields:
- `Methane Emissions Factor` (Coal Mine): 2 occurrences
- `Capacity factor` (Coal Finance): 1 occurrence
- `Emission factor (kg of CO2 per TJ)` (Coal Finance): 1 occurrence

These are Excel formula errors that were exported without being resolved. They carry no intentional meaning and should be treated as data errors.

### Type 6 — Structural issues

- **Latitude field (Coal Mine)**: 2 cells contain a coordinate pair (`41.02985051408915, -0.5964618077206504`) — a lat/lon pair stored in what should be a single lat field. This is a data entry error, not a numeric purity convention.
- **`to be determined` (Portal Energetico Capacity)**: 2 occurrences; a planning-stage note.

---

## Decision Points

### Decision 1: What replaces `-` as a null proxy in numeric fields?

Per STD-01, the org standard for missing values should be empty cell. `-` in numeric fields is a PM convention (likely inherited from spreadsheet display habits — an empty cell in a wide table is visually confusing; a dash is clearer to a human reader).

**Options:**
- **Replace with empty cell at ETL** — normalize `-` to NULL during ingest. Document this as a known transformation so downstream users know a null means "no data for this year," not "zero production."
- **Accept `-` in spreadsheets, convert at ETL** — recognize this as a PM workflow accommodation and clean it programmatically. No PM workflow change required.
- **Require empty cell in spreadsheets** — enforce at data entry. Requires PM training and tooling changes.

The tradeoff is between PM ergonomics (dashes are visually cleaner in wide production tables) and data cleanliness. Conversion at ETL is the lowest-friction path.

### Decision 2: How to handle `N/A` in type-specific capacity fields?

The Iron & Steel tracker uses multiple capacity columns, each specific to a production technology. A plant with no BOF unit legitimately has no BOF capacity. Three structural options:

**Option A — Accept `N/A` in numeric fields as a "doesn't apply" marker**  
Treat `N/A` as a special null with a specific meaning. Store as NULL in the DB with a `null_reason` annotation (see STD-01 Decision 1, Option D).

- Pro: Preserves the "doesn't apply" signal without restructuring the schema.
- Con: Makes the field a mixed type (numeric + token). Requires special handling in all downstream tools.

**Option B — Use a separate boolean flag column per technology type**  
Add `has_bof`, `has_eaf`, `has_dri` boolean columns. Capacity column is empty when the flag is false.

- Pro: Clean separation of "does this technology exist" from "what is its capacity."
- Con: More columns. Adds data entry complexity.

**Option C — Restructure as unit-level rows**  
Instead of one row per plant with multiple technology capacity columns, use one row per production unit (BOF unit, EAF unit, etc.). Capacity is always a clean number; the unit type identifies what it measures.

- Pro: Fully normalized. The DB's `steel_unit` tables already use this approach.
- Con: Significant schema change for the spreadsheet format. PMs currently work with a wide, plant-level table.

### Decision 3: How to handle `>0`?

`>0` is a qualified numeric assertion. It sits at the boundary between numeric purity and imputation. Two framings:

**Framing A — Treat as numeric purity issue**  
`>0` is non-numeric and should not appear in a numeric field. Replace with empty cell (NULL) and move the "positive but unknown" signal to a companion field or note.

**Framing B — Treat as a valid imputed/qualified value**  
`>0` conveys meaningful information (the capacity is nonzero) that pure NULL loses. Document it as an allowed qualifier in the field metadata, and handle it in the imputation standard (STD-10) rather than here.

The data shows `>0` is used consistently and deliberately in Iron & Steel capacity fields — it's not a random outlier. That argues for Framing B: treat it as a qualified value with a defined meaning, to be addressed in STD-10.

### Decision 4: What does `*` mean, and how should it be represented going forward?

The asterisk in GMET and Coal Terminals almost certainly means "data exists but is not publicly available." This is a meaningful research-quality annotation that empty cell erases.

**Options:**
- **Retain `*` as a documented allowed token** for numeric fields where data-exists-but-restricted is a known condition. Document its meaning in field metadata.
- **Replace with a companion boolean `_data_restricted` field** — numeric field is empty; companion field flags restricted data.
- **Replace with empty cell** — accept the loss of the restricted-data signal. Simplest, but loses information.

The choice depends on how important the "data restricted" signal is for downstream use cases. For methane emissions data (where China's non-disclosure is a major coverage issue), losing the `*` signal means users can't distinguish "no data available" from "data exists but was withheld."

### Decision 5: Ranges in numeric fields

No ranges (`100-200 MW`) appear in the current data, but they've been discussed as a known issue in other contexts. If ranges ever appear, the options are:
- Store midpoint only (lossy)
- Store as two fields: `{field}_low` and `{field}_high`
- Store as text with a `structured` sub-type and document the format

This is worth including in the standard even if it's not yet a live issue.

---

## Summary of Non-Numeric Tokens by Recommended Treatment

| Token | Current use | Recommended treatment |
|---|---|---|
| `-` | Null proxy in Coal Mine / Coal Terminals | Convert to NULL at ETL (see STD-01) |
| `N/A` | "Doesn't apply" in Iron & Steel capacity | Structural decision needed (Decision 2) |
| `>0` | Qualified assertion in Iron & Steel capacity | Address in STD-10 (Imputed Values) |
| `*` | Data-restricted marker in GMET / Coal Terminals | Formalize meaning or companion field |
| `#N/A` | Excel error | Data error; clean unconditionally |
| Coordinate pairs | Structural data entry error | Data error; fix in source |

---

## Related Standards

- **STD-01: Null / Missing Value Encoding** — `-` and `N/A` as null proxies
- **STD-10: Imputed Values** — `>0` as a qualified / bounded assertion
- **STD-07: Required Fields / Nullability** — which capacity fields must be populated
