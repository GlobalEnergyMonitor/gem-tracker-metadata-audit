# STD-06: Date / Year Format

**Status:** Draft — for discussion with Data Team  
**Scope:** All tracker spreadsheets and the research database export pipeline

---

## Current State

Date and year fields span a wide range of granularities and formats. The audit identified 316 fields matching date/year patterns across all trackers, with 163 flagged for out-of-range values or format issues. The DB export pipeline is broadly consistent; the issues concentrate in a few specific fields and in trackers outside the DB pipeline.

### Formats in use

| Format | Example | Occurrences | Source |
|---|---|---|---|
| `YYYY` (integer year) | `2025` | 50,593 | DB exports (start year, retired year, etc.) — dominant |
| `YYYY/MM/DD` | `2025/08/05` | ~100,000+ | GIPT, GGIT Last Updated fields |
| `YYYY-MM-DD HH:MM:SS` | `2019-09-01 00:00:00` | 4,692 | Gas Finance FID Date — Excel datetime export |
| `YYYY-MM-DD` | `2022-08-26` | 1,631 | GGIT Last Updated, Nuclear dates |
| `MM/DD/YYYY` | `03/07/2023` | 889 | GMET Satellite Imagery Dates |
| `D Month YYYY` | `June 26, 2015` | hundreds | Coal Plant Permit Date |
| `YYYY.decimal` | `2005.0` | ~162 | Excel float export of year-only cells |
| Excel serial | `17579.92465` | 162 | GMET (date cells exported as numeric) |
| `YYYY-YY` | `2024-25` | ~62 | Coal Mine methane reporting year (fiscal year) |

### The DB export standard

For fields that track lifecycle years (Start year, Retired year, Planned retirement), the research database exports a clean 4-digit integer: `2006`, `2025`, `2030`. No format ambiguity.

For fields with day-level precision (Last Updated, First Criticality Date, Construction Start Date in Nuclear), the DB exports `YYYY-MM-DD`.

This two-tier convention — `YYYY` for year-only fields, `YYYY-MM-DD` for full dates — is coherent and already in use across the majority of trackers.

### Problem areas

**Mixed formats in the same column (39 fields)**  
The most significant issue is fields that contain both `YYYY` and `YYYY-MM-DD` values in the same column:

- **Gas Finance FID Date / Close Year**: mix of `2022` (year-only) and `2019-09-01 00:00:00` (full datetime with timestamp) — reflecting different levels of precision available for different records
- **Nuclear Construction Start Date / Commercial Operation Date**: mix of `2024` (year known, day unknown) and `1979-10-01` (precise date known)
- **Iron & Steel relining dates, announced dates, construction dates**: same pattern — some records have full dates, others only years

**Coal Plant Permit Date**  
Three formats co-exist in a single column: `2005.0` (Excel float), `2015-06-26 00:00:00` (full datetime), and `June 26, 2015` (natural language). This is likely because the field was partially populated from different source systems over time.

**`0.0` as empty date**  
14,645 occurrences of `0.0` appear in date-flagged fields. This is Excel's representation of an empty date cell exported as numeric: an empty date field becomes `0`, which Excel interprets as the serial date for 1900-01-00. These are not real dates and should be treated as NULL.

**`YYYY/MM/DD` in Last Updated fields**  
GIPT and several GGIT trackers use `YYYY/MM/DD` (slash-separated) rather than `YYYY-MM-DD` (hyphen-separated) for their Last Updated fields. This is a minor format inconsistency — same information, different delimiter.

**`MM/DD/YYYY` in GMET**  
GMET's Satellite Imagery Dates field uses American-style `MM/DD/YYYY` — different from all other date fields.

**Fiscal/reporting year notation**  
Coal Mine uses `2024-25` for the Year of Reported Coal Mine Methane Emissions — a fiscal year spanning two calendar years. This is a legitimate need (many methane reporting periods follow fiscal rather than calendar years) but doesn't fit either the `YYYY` or `YYYY-MM-DD` convention.

**`YYYY-MM-DD HH:MM:SS` timestamp format**  
Gas Finance FID Date exports full timestamps (`2019-09-01 00:00:00`) when only the year or month is known. The time component is always `00:00:00`, indicating it's a date-only value mistakenly exported with a time suffix — an Excel/Pandas artifact.

---

## Decision Points

### Decision 1: Year-only vs. full date — when is each appropriate?

The DB already makes an implicit decision here: lifecycle years (start, retired, planned retirement) are stored as integers; administrative/event dates (last updated, first criticality) are stored as full dates. This distinction is worth formalizing.

**Proposed rule:**
- **Year-only fields** (`YYYY`): fields tracking when something happened at annual granularity — start year, retired year, announced year, construction year, shelved year, cancelled year, planned retirement year. The year is the meaningful unit; the precise date is either unknown or not relevant.
- **Full date fields** (`YYYY-MM-DD`): fields where day-level precision matters — last updated, permit date, criticality date, commissioning date, specific event dates. 

**Open question:** Some fields (Nuclear Construction Start Date, Iron & Steel relining dates) have day-level precision for some records and year-only for others. How should mixed-precision data be handled in a single column? Options:
- Store as full date; populate day/month as `01` where only year is known (loss of precision information)
- Store as year-only integer; accept loss of day-level data for full-date records
- Use two columns: `{field}_year` (always populated) and `{field}_date` (populated when full date known)
- Store as text with a precision flag in metadata

### Decision 2: Which separator for full dates — `/` or `-`?

`YYYY/MM/DD` and `YYYY-MM-DD` are both in use. ISO 8601 standard is hyphen (`YYYY-MM-DD`). No functional difference, but consistency matters for parsing.

**Recommendation:** Standardize on `YYYY-MM-DD` (ISO 8601). Convert `YYYY/MM/DD` at ETL. This is already what the DB exports for full-date fields.

### Decision 3: Timestamps — strip or preserve?

`YYYY-MM-DD HH:MM:SS` with always-zero time (`00:00:00`) is an export artifact. Stripping to `YYYY-MM-DD` is a safe normalization.

For fields that might legitimately have intra-day timestamps (e.g., satellite observation times in GMET), the timestamp should be preserved. But for event dates (FID Date, Close Date), the time component carries no information.

**Recommendation:** Strip the `00:00:00` timestamp suffix at ETL for fields that are semantically date-only. Document which fields might have meaningful intra-day times if any are identified.

### Decision 4: Fiscal / reporting year notation

`2024-25` for a fiscal year is a meaningful format that doesn't fit either convention. Two options:

**Option A — Store as text, document in metadata**  
The field is of type `text/structured` with a documented format `YYYY-YY`. Downstream tools must parse it explicitly.

**Option B — Store start year only**  
`2024-25` becomes `2024`. Simple; loses the fiscal-year framing.

**Option C — Store as two fields: `{field}_year_start` and `{field}_year_end`**  
`2024-25` becomes `year_start=2024`, `year_end=2025`. Clean; adds fields.

This is a narrow case (currently only one field uses this format) but the underlying issue — that some reporting periods span calendar years — may become more common as methane and emissions tracking expands.

### Decision 5: Natural-language date strings

`June 26, 2015` in the Permit Date field is likely a direct transcription from a document. Three options:

- **Parse and convert at ETL** to `YYYY-MM-DD` — automated, but fragile for ambiguous formats
- **Require structured format at data entry** — PM training change
- **Accept as-is and parse at query time** — most flexible but pushes complexity downstream

The Permit Date field specifically is a known messy field (see also STD-05 for its `2005.0` Excel float problem). It may warrant special handling regardless of the general standard.

---

## False Positives in the Audit

The 163 `year_out_of_range` flags include a significant number of false positives:

- **`YYYY/MM/DD` dates** — flagged as non-year because the slash-format isn't recognized as a year; these are valid dates, wrong format
- **`0.0`** — Excel empty-date artifact; not a real out-of-range value, should be NULL
- **Region and country names** (Asia, Americas, Eastern Asia, etc.) — appearing in fields whose names contain "date" or "year" but are not actually date fields (false positives from the field classifier)
- **`35.0`, `5.0`** — small numeric values correctly flagged as out of year range; may be data errors or wrong-field entries

---

## Summary Table

| Format | Status | Action |
|---|---|---|
| `YYYY` integer | Standard for year-only fields | Keep |
| `YYYY-MM-DD` | Standard for full-date fields | Keep |
| `YYYY/MM/DD` | Minor variant | Convert to `YYYY-MM-DD` at ETL |
| `YYYY-MM-DD HH:MM:SS` with zero time | Export artifact | Strip time suffix at ETL |
| `MM/DD/YYYY` | Non-standard | Convert at ETL |
| `YYYY.decimal` | Excel export artifact | Round to integer |
| Excel serial number | Export artifact | Convert using Excel date origin |
| `D Month YYYY` / `Month D, YYYY` | Non-standard | Parse and convert at ETL |
| `YYYY-YY` fiscal year | Legitimate but non-standard | Decision needed (Decision 4) |
| `0.0` | Excel empty date | Treat as NULL |

---

## Date Estimates, Ranges, and Sub-year Precision

Beyond format consistency, several fields encode epistemic uncertainty about dates — the year is known only approximately, is projected rather than confirmed, or falls within a range. This is a distinct problem from format normalization.

### How the DB currently handles this

The `snapshot.powerplant_unit` table has three year-uncertainty fields:

- `startYearLow` — populated for 135,830 of 218,354 records; used in practice as the single best-estimate year, not as a true lower bound (`startYearHigh` has only 1 non-null value across the entire table)
- `startYearPlanned` — a boolean (10,827 True) flagging whether the start year is projected rather than historical fact
- `endYearLow` / `endYearPlanned` — same pattern for retirement/end year

In the spreadsheet exports, this collapses to two columns: `Start year` (the Low value) and `Planned retirement` (a separate future-projection column). The High/Low distinction disappears in the export because in practice only Low is ever populated.

The intent — distinguishing "this is our best estimate of when it started" from "this is the confirmed commissioning year" — is meaningful, but the mechanism has drifted from its design: `startYearLow` functions as the year field, full stop.

### Planned vs. actual

The `startYearPlanned` boolean is the DB's way of encoding "we don't know the actual year yet; this is a projection." The spreadsheet equivalent is having `Planned retirement` as a separate column from `Retired year`. Both approaches capture the same distinction — projected vs. historical — but through different structures.

This distinction matters for time-sliced queries: "plants operating in 2030" must decide whether to include plants whose start year is planned-2029 as well as plants that actually started in 2029.

### Quarter and half-year precision

GGIT LNG Terminals and Portal Energetico record construction and start months at sub-annual but sub-monthly precision:

```
ConstructionMonth: Q4, Q3, Q1, H2, H1
ActualStartMonth: H2
```

These values sit between a year (`2025`) and a full date (`2025-10-01`) — more precise than a year but less precise than a month. No current field type in the schema handles this.

**Options:**
- **Store as text with documented format** — `Q4 2025`, `H2 2026` as structured text values; downstream tools parse them
- **Store year only; accept loss of quarter/half precision** — simpler, but loses information that's available
- **Use Low/High year pair** — Q4 2025 becomes `year_low=2025`, `year_high=2026`; H2 2025 stays `year_low=2025`, `year_high=2025`. Not intuitive but queryable

### Year ranges

Explicit year ranges appear sparsely: `2017-2019` (Coal Mine year of production), `2027-2028` (Gas Finance expected start year), `2019/2020` (Coal Mine closing year). These represent genuine uncertainty — the event happened or is projected somewhere within the range.

The DB's High/Low pair is the right structure for this, but as noted above, only Low is ever used in practice. If year ranges are to be supported properly, the High field needs to actually be populated.

### Partial dates and the Permit Parsed field

Coal Plant's `Permit Parsed` field takes an interesting approach to variable-precision dates, storing them as structured text: `Year: 2015, Month: 6, Day: 26` or `Year: 2005` (when only the year is known). This makes the available precision explicit rather than forcing all values to a common granularity.

This pattern — storing what is known at the precision that is known — is worth considering as a model for other fields with variable precision.

### Decision 6: How to represent date estimates and projections

**Option A — Single year field + planned boolean (current DB approach)**  
One `{field}_year` column holds the best estimate; a boolean `{field}_planned` flags whether it's projected. Simple; loses the High/Low range.

**Option B — Low/High year pair**  
`{field}_year_low` and `{field}_year_high` for every year field that might have range uncertainty. When the year is known precisely, Low = High. When a range is known, Low and High differ. When only a lower bound is known, High is null.

- Pro: Captures ranges and single estimates in the same structure. Machine-readable.
- Con: Doubles year-related columns. Most fields will have Low = High = the same value, which is verbose.

**Option C — Year + precision flag**  
Single year field + a `{field}_precision` categorical: `exact`, `estimated`, `planned`, `range`. When precision is `range`, a companion `{field}_year_end` column holds the upper bound.

- Pro: Keeps the common case (single known year) simple. Makes precision queryable.
- Con: Adds a column per year field. Requires agreement on what the precision categories mean.

**Option D — Store as structured text for uncertain values**  
Follow the Permit Parsed approach: store what is known at the granularity known. `2025`, `Q4 2025`, `2025-2027`, `planned 2028` are all valid values in a `text/structured` field with a documented format.

- Pro: Flexible. No schema change required.
- Con: Harder to query. Requires parsing logic. Not compatible with clean integer year fields.

---

## Related Standards

- **STD-01: Null / Missing Value Encoding** — `0.0`, `Not available` in date fields
- **STD-08: Field Naming Conventions** — `{field}_year` vs. `{field}_date` naming pattern
- **STD-09: Cross-field Links** — year fields paired with datasource fields
