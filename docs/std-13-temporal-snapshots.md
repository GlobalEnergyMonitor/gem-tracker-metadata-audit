# STD-13: Temporal Snapshots / "As Of" Dating

**Status:** Draft — for discussion with Data Team  
**Scope:** All mechanisms by which trackers record *when* a value applies — at the tracker level, the record level, and the field level

---

## Current State

GEM tracker data changes over time: plants change status, capacities are revised, ownership transfers, new projects are announced. The mechanisms for capturing when a value applies — and distinguishing "historical as of date X" from "current state as of release" — are inconsistent and largely implicit across trackers.

Five distinct temporal patterns are in use simultaneously.

---

## Pattern 1: Release-date Snapshot (Implicit)

**Used by:** All trackers (as the default)

The most common approach: the entire tracker is a current-state snapshot as of the release date. The release date appears in the filename (`global_coal_plant_tracker_january_2026.xlsx`, `global_gas_tracker_march_2026.xlsx`) but not in any field within the data itself.

Implications:
- Every field in a record is implicitly "as of January 2026" (or whatever the release date is)
- No field distinguishes "this value was last confirmed in 2024" from "this value was confirmed in 2026"
- Comparing two releases to find what changed requires a diff process external to the tracker
- A plant added in the 2022 release with no changes since has the same timestamp as a plant updated in 2026 — no way to distinguish them from the data alone

The gas tracker partially addresses this with `Last Updated` (see Pattern 4).

---

## Pattern 2: Wide-format Annual Time Series

**Used by:** Coal Mine (historical production), Iron Ore Mines

The Coal Mine tracker maintains a separate historical production tab with one column per year:

```
Coal Output (Annual, Mt) 2018
Coal Output (Annual, Mt) 2019
Coal Output (Annual, Mt) 2020
Coal Output (Annual, Mt) 2021
Coal Output (Annual, Mt) 2022
Coal Output (Annual, Mt) 2023
Coal Output (Annual, Mt) 2024
Coal Output (Annual, Mt) 2025
```

Each column is a distinct temporal snapshot for that year's production. The mine record joins both the current-state tab (status, capacity, location) and the historical production tab via GEM ID.

Iron Ore Mines uses the same approach for 3 years: `Production 2022 (ttpa)`, `Production 2023 (ttpa)`, `Production 2024 (ttpa)`.

**Tradeoffs:**
- Adding a new year requires adding a new column — schema changes with each update
- The wide format is intuitive for PMs reading the spreadsheet but awkward for querying ("show me all mines that produced >10 Mtpa in any year")
- Companion `Output Accuracy` columns travel with the production columns, creating a positional-link problem (see STD-09)
- The `*` restricted-data marker and `-` null proxy are widely used in these columns (see STD-05)

---

## Pattern 3: Long-format Annual Time Series

**Used by:** Iron & Steel yearly production, GOGET reserves/production (in separate tabs / DB tables), GMET reserves

The DB-backed approach: a separate table with one row per (asset, year):

```
iron_yearly_production:
  Project ID | Project Name | Year | Total Iron Production | BF Iron Production | ...

goget_reserves_production:
  Project ID | Project Name | Type | Fuel | Year | Quantity | Data Source | Notes

steel_yearly_production:
  Project ID | Project Name | Year | Total Steel Production | BOF | EAF | IF | ...
```

The `Year` field is the temporal key. This is the correct relational design for time-varying quantities: the schema doesn't change when a new year is added, and year-based queries are straightforward.

The GOGET reserves/production long-format structure is the most complete example: it includes `Year`, `Data Source`, and `Reserve Classification` per row — full field-level provenance for each temporal entry. GMET `oil_and_gas_reserves` uses a `Data year` field for the same purpose.

**Gap**: the Iron & Steel yearly production data is separate from the main plant-level spreadsheet and linked only through GEM Project ID. There is no single spreadsheet that shows both current status and historical production in the same tab.

---

## Pattern 4: "As Of Year" Companion Field

**Used by:** GOGET (`Status year`), Coal Mine (`Year of Production`, `Year of Total Reserves Recorded`, `Reported Year of Mine Life`, `Gas-level Rating Appraisal Year`), GMET (`Status year`, `Climate TRACE Field Estimate Year`), Portal Energetico (`Data Year`, `Status year`)

Some trackers pair a current-state field with an explicit "as of year" companion — the year as of which that specific field's value was last confirmed or measured:

| Current-state field | "As of" companion |
|---|---|
| `Status` (GOGET) | `Status year` (values: 2022–2025) |
| `Production (Mtpa)` (Coal Mine) | `Year of Production` (values: 2020–2025) |
| `Total Reserves` (GOGET/GMET) | `Data Year` / `Year of Total Reserves Recorded` |
| `Reported Life of Mine` | `Reported Year of Mine Life` |
| `Percentage of Met Coal` | `Reported Year of Percentage Split` |
| `Gas-level Rating` | `Gas-level Rating Appraisal Year` |
| `Climate TRACE Field Emissions` | `Climate TRACE Field Estimate Year` |

This pattern is explicit and correct: it acknowledges that a current-state record contains values that were measured or confirmed at different times. A mine's production figure might be from 2024 while its reserves figure comes from a 2022 study.

**Coverage**: this pattern exists in GOGET, Coal Mine, GMET, and Portal Energetico. It does not exist in the power plant trackers (Coal Plant, Gas, Nuclear, Solar, Wind) — even though the same problem applies (a plant's capacity might have last been verified in 2022 while its status was confirmed in 2026).

**The `Coal Mine Year of Production` definition** explicitly documents the behavior:
> "The year during which the cited coal production occurred. (If coal output for the current year is unavailable, data for the most recently available year is given.)"

This clarifies that the production value is not necessarily from the release year — it's whatever the most recent available data year was.

---

## Pattern 5: Record-level Research Freshness

**Used by:** Gas tracker, Coal Plant, LNG Carrier (`Last Updated`); most DB-backed power trackers (`Research Status`)

`Last Updated` records when a researcher last reviewed the record:

- Gas tracker: `Last Updated` as `YYYY-MM-DD`, plus `Researcher` (who reviewed it)
- Coal Plant: `Last Updated` as a date field
- LNG Carrier: `Last updated` as `YYYY-MM-DD HH:MM:SS` (timestamp artifact)

`Research Status` (Solar, Wind, Nuclear, Hydro, Geothermal, Coal Plant, Gas) tracks the record's workflow state in the most recent release cycle: `added`, `updated`, `no changes`, `in progress`. See STD-11.

**What these fields tell you**: they tell you *when the record was last touched*, not necessarily *when the data values were last confirmed by a primary source*. A record touched in 2026 to fix a typo will show `Last Updated: 2026` even if the underlying status, capacity, and location data hasn't been re-verified since 2022.

---

## The Fundamental Design Tension

The root issue: GEM trackers are primarily designed as **current-state inventories**, not **time-series databases**. A record represents the current state of an asset; lifecycle years (`Start year`, `Retired year`) capture when state transitions happened, but point-in-time historical states are not preserved.

This means:
- A query like "how many coal plants were under construction in 2020?" cannot be answered from the current spreadsheet alone — it requires comparing the 2020 release to the current one
- Capacity changes (expansions, decommissioning of units) are invisible unless the PM records them explicitly
- Ownership changes require a separate Ownership Tracker query, which itself is a point-in-time snapshot

The long-format production tables (Iron & Steel, GOGET) and the `Year of Production` pattern in Coal Mine are the main exceptions — deliberate designs for fields that are inherently time-varying.

---

## Decision Points

### Decision 1: Should the release date be an explicit field in the data?

Currently the release date lives only in the filename. If the file is renamed, saved under a new name, or its data is loaded into a database without the filename metadata, the release date is lost.

**Option A — Add a `Data release` or `As of date` column**  
A static column (same value for every row in a given release): `Data release: 2026-01` or `As of date: 2026-01-01`. Simple to add; increases file size marginally.

**Option B — Include in dataset-level DCAT metadata**  
The DCAT `dct:issued` and `dct:modified` properties capture release dates at the dataset level, not the row level. Correct for dataset provenance but invisible in the spreadsheet itself.

**Option C — Keep in filename only**  
Accept the current practice. Document the filename convention so users know where to find the date.

### Decision 2: Should the "as of year" pattern be extended to power plant trackers?

The `Status year` in GOGET and `Year of Production` in Coal Mine are valuable — they tell users precisely which year a specific value applies to. Power plant trackers don't have equivalent fields.

**Arguments for extension:**
- Capacity figures may be from different years for different plants (recent buildouts vs. decades-old data)
- Status for operating plants may not have been re-verified since the plant was added
- A `Capacity confirmed year` would help users judge data freshness

**Arguments against:**
- The DB stores `lastUpdated` per record, which gives similar information at a finer granularity — extending `Status year` to power plants may duplicate this
- Adding per-field year companions doubles the column count for key fields
- Power plant status and capacity change less frequently than oil field production and reserves; the staleness problem is less acute

### Decision 3: How should time-varying capacity changes be handled?

Currently, if a plant expands from 100 MW to 200 MW, the spreadsheet shows 200 MW with no record of the prior value. The only temporal signal is the `Start year` of new units (in unit-level trackers).

**Option A — Current-state only (status quo)**  
Track only the current capacity. Historical capacity is implicit in the difference between releases.

**Option B — Capacity history tab**  
Add a separate `Capacity history` tab (like the Coal Mine `Historical Production` tab) that records capacity at each annual data point. Requires a significant data collection effort.

**Option C — Unit-level expansion tracking**  
For trackers that already have unit-level data (Coal Plant, Gas), each capacity expansion is a new unit with its own `Start year`. The plant-level capacity is the sum of active units — historical plant capacity is reconstructable from the unit data.

Option C is already implicitly implemented for power plants. The question is whether the reconstruction is easy enough to be practically usable.

### Decision 4: Wide format vs. long format for annual series

The Coal Mine historical production tab uses wide format (one column per year); Iron & Steel yearly production uses long format (one row per year). Both exist because the Coal Mine tab is PM-managed (wide is more readable) while Iron & Steel production is DB-generated (long is more queryable).

**For a unified schema:**

**Wide format**
- Pro: intuitive for PM editing; column-per-year easy to read
- Con: schema changes every year; year-based queries require unpivoting; works badly for long time series

**Long format**
- Pro: schema stable across years; time-range queries are direct; the DB's native representation
- Con: PM editing is harder; a single plant becomes 7+ rows; wide pivot needed for display

**Proposed rule:** Long format for DB-backed trackers (Iron & Steel, GOGET, Steel); wide format acceptable for PM-managed spreadsheets (Coal Mine) as long as the data is converted to long format at ETL for DB ingestion.

### Decision 5: What should `Last Updated` represent — research date or data observation date?

`Last Updated` currently records when a researcher last touched the record. This conflates:
1. The date a value was last verified against a primary source
2. The date the record was last edited (even for minor corrections)

**Option A — Keep as research/edit date (current practice)**  
Simplest; already populated in some trackers. Tells users when a record was last reviewed.

**Option B — Separate `Last Updated` from `Data observation date`**  
`Last Updated: 2026-03` (last edit) vs. `Data observation year: 2024` (when the underlying data was collected). More precise; more data entry burden.

**Option C — Field-level as-of dates for key fields only**  
Rather than a single record-level date, add `Status year` and `Capacity year` (following the GOGET model) for the most time-sensitive fields. Capacity and status are the fields most likely to be stale.

---

## Summary: Temporal Mechanisms by Tracker

| Tracker | Release-date snapshot | Wide annual | Long annual | As-of year field | Last Updated |
|---|---|---|---|---|---|
| Coal Plant (DB) | Y (implicit) | — | — | — | Y |
| Gas (DB) | Y (implicit) | — | — | — | Y (+ Researcher) |
| Solar / Wind / Nuclear / Hydro | Y (implicit) | — | — | — | — |
| Coal Mine | Y (implicit) | Y (production) | — | Y (Year of Production, etc.) | — |
| Iron & Steel | Y (implicit) | Y (plant production tab) | Y (DB: yearly_production) | — | — |
| GOGET | Y (implicit) | — | Y (DB: reserves_production) | Y (Status year, Data Year) | — |
| GMET | Y (implicit) | — | Y (reserves) | Y (Status year, Data year) | — |
| LNG Carrier | Y (implicit) | — | — | — | Y (timestamp) |
| GGIT (Gas Pipelines, LNG) | Y (implicit) | — | — | — | Y (LastUpdated) |
| Ownership | Y (implicit) | — | — | — | — |
| Cement / Chemicals / Iron Ore | Y (implicit) | Y (3 years) | — | — | — |

---

## Related Standards

- **STD-06: Date / Year Format** — year-only vs. full-date format for temporal fields; estimate vs. confirmed years
- **STD-09: Cross-field Links** — `Year of X` companion fields and their links to parent fields
- **STD-10: Imputed Values** — `startYearPlanned` as a temporal uncertainty flag
- **STD-11: Data Provenance / Source Fields** — `Last Updated`, `Research Status` as temporal provenance
