---
layout: default
title: "IOP-06: Temporal"
---

# IOP-06: Temporal

**Status:** Draft — for discussion with Data Team  
**Scope:** Lifecycle event fields, date format standards, research freshness, and "as of year" companion fields across trackers

*Note: STD-13 covers temporal snapshot patterns (release-date snapshots, wide vs. long annual series, "as of year" companions). This document focuses on cross-tracker naming consistency and date format standardization.*

---

## Inventory

### Lifecycle event fields

Most trackers capture the same core lifecycle events — when an asset entered each major phase — but field names and whether a full date or year-only value is used vary by tracker:

| Concept | Field names in use | Format |
|---|---|---|
| Construction start | `Start year`, `Start Year`, `Construction Start Date`, `Construction date` | Year or full date |
| Commercial operation / start | `Start year`, `Start Year`, `Start date`, `Opening Year`, `Production start year` | Year or full date |
| Retirement / closure | `Retired year`, `Retired Year`, `Retirement Year`, `Retired date`, `Retirement Date`, `Closing Year` | Year or full date |
| Planned retirement | `Planned retirement`, `Planned retire` | Year |
| Cancellation | `Cancellation Year` | Year |
| Announcement | `Announced date` | Year or full date |
| Permit | `Permit Date`, `Permits` | Mixed (see below) |

Domain-specific lifecycle fields that don't map to a cross-tracker equivalent:
- **Nuclear**: `First Criticality Date`, `Commercial Operation Date` — finer-grained than other power trackers
- **Iron & Steel**: `Idled date`, `Pre-retirement announcement date`, `Furnace relining start/stop date`, `Hydrogen reductant conversion date`
- **Coal Mine**: `Opening Year`, `Closing Year`, `Gas-level Rating Appraisal Year`
- **GOGET**: `Discovery year`, `FID Year`, `Production start year` — extraction project lifecycle
- **Gas/Coal Finance**: `FID Date`/`FID Year`, `Close Date`/`Close Year` — deal closure dates, not asset lifecycle
- **Coal Plant**: `Coal phaseout year`, `Net zero year` — policy commitment dates

### Date format in use

Lifecycle year fields are predominantly year-only (`YYYY` integer). Full dates (`YYYY-MM-DD`) appear where precision genuinely matters or where data is available:

- **Year-only** (most trackers): `Start year`, `Retired year`, `Opening Year`, etc.
- **Full date** (Nuclear, Iron & Steel): `Construction Start Date`, `First Criticality Date`, `Retired date`, `Pre-retirement announcement date`
- **Mixed within same field**: Iron & Steel lifecycle date fields contain both `2022` (year-only) and `2022-08-01 00:00:00` (timestamp) in the same column — the timestamp is an Excel formatting artifact when a date cell is exported, not intentional full-date precision
- **Free text mixed in**: Coal Plant `Permits` field contains `"March 31, 2011 – Environmental Clearance; Environmental Clearance Amendment: 2014-05-20"` — full-text entries, not structured dates

### Research freshness

Most DB-backed trackers include a field recording when a record was last reviewed. This is one of the most consistently present cross-tracker fields, but name and format both vary:

| Field name | Trackers | Format examples |
|---|---|---|
| `Date Last Researched` | Nuclear, Geothermal, Bioenergy, Hydro | `2024-05-29`, `2025-01-08 00:00:00` |
| `Date last researched` | Bioenergy (inconsistent case) | `2025-08-18 00:00:00` |
| `Date Last Researched` | Solar, Wind | `2025/08/05`, `2026-01-19 00:00:00` |
| `Last updated` | LNG Carrier | `2024-12-31 00:00:00` |
| `last_updated` | Coal Plant (DB field, not in export) | `YYYY-MM-DD` |

The format varies even within a single tracker: Solar has both `2025/08/05` and `2026-01-19 00:00:00` depending on the data source of the record. Portal Energetico, which aggregates all trackers, surfaces at least five distinct formats for this field.

### "As of year" companion fields

Some trackers pair a current-state field with a year indicating when that value was last confirmed. This pattern is documented in STD-13; the fields in use are:

| Companion field | Qualifies | Tracker |
|---|---|---|
| `Year of Production` | `Production (Mtpa)` | Coal Mine |
| `Year of Total Reserves Recorded` | `Total Reserves` | Coal Mine |
| `Reported Year of Mine Life` | `Reported Life of Mine` | Coal Mine |
| `Gas-level Rating Appraisal Year` | `Gas-level Rating` | Coal Mine |
| `Year of Reported Coal Mine Methane Emissions` | methane estimate | Coal Mine |
| `Data Year` / `Status year` | status and production | GOGET, GMET |
| `Climate TRACE Field Estimate Year` | emissions estimate | GMET |
| `Data year` | reserves data | GMET |

---

## Interoperability Gaps

**`Start year` and `Retired year` have too many name variants to join on.**  
Six names for start-of-operation and five for retirement make cross-tracker temporal queries require per-tracker field mapping. Domain-specific names (`Opening Year`, `Production start year`) are justified where the concept differs, but `Start year` vs `Start Year` (capitalization only) and `Retired year` vs `Retired Year` are unnecessary divergences.

**`Date Last Researched` has five distinct date formats.**  
Even within a single tracker (Solar), the same field contains both `YYYY/MM/DD` and `YYYY-MM-DD HH:MM:SS`. In Portal Energetico, which aggregates all trackers, the field is effectively unqueryable as a date without per-source parsing. The underlying cause is inconsistent Excel date cell formatting at export time.

**Year-only vs. full-date is inconsistent within Iron & Steel.**  
The mix of bare `2022` and `2022-08-01 00:00:00` in the same lifecycle date columns is an export artifact, not intentional. It makes these columns non-numeric and requires parsing before use.

**Planning and policy dates are not comparable across trackers.**  
`Planned retirement`, `Coal phaseout year`, and `Net zero year` look like the same kind of field but are not: some represent operational plans, some regulatory commitments, some aspirational policy targets. Aggregating them as if they are equivalent would be misleading. These fields should be documented with enough context that consuming applications can treat them appropriately.

**`Permits` field is unstructured.**  
Coal Plant's `Permits` field contains free-text entries mixing permit type, date, and amendments in a single string. It is not queryable as a date field. A parsed `Permit Date` field exists alongside it but has inconsistent format (`2005.0` mixed with `2015-06-26 00:00:00`).

---

## Decisions Needed

### Naming and field conventions

**Standardize case for shared lifecycle field names.** Fields that represent the same concept should use consistent casing. Proposed standard: `Start year`, `Retired year`, `Planned retirement` (title case for first word only, matching the majority of DB-backed trackers). Domain-specific variants (`Opening Year`, `Production start year`, `Discovery year`) are acceptable where the concept genuinely differs from a generic start/end event.

**Standardize `Date Last Researched`.** This is the same concept across all trackers that have it. Proposed standard field name: `Date last researched`. Determine whether Coal Plant's DB-level `last_updated` should be exposed in the export under this name.

### Schema and architecture

**Define the year-only / full-date convention.**  
Year-only (`YYYY`) is the default for lifecycle events where only the year is known or where month/day precision is not meaningful. Full date (`YYYY-MM-DD`, ISO 8601) should be used only where sub-year precision is consistently available and meaningful for the tracker's use case (Nuclear is the clearest example). Mixed fields — where some records have a year and others a full date — should be avoided; the field should be defined as one type or the other, with the less precise values stored as year-only.

For fields where source data may have full dates but year-only is also common, a two-field pattern is an option: `Start year` (integer, always populated) + `Start date` (ISO date, populated where available). This avoids mixed-type columns while preserving precision where it exists.

**Fix Iron & Steel date export.**  
The `HH:MM:SS` timestamp artifact should be stripped at export time so date columns contain only `YYYY-MM-DD` or `YYYY`. This is an ETL fix, not a schema change.

**Document planning and policy date fields explicitly.**  
`Planned retirement`, `Coal phaseout year`, and `Net zero year` should each carry metadata that clarifies the source and nature of the date (operational plan, regulatory commitment, government policy, company announcement) so that consuming applications do not aggregate them inappropriately.

---

## Related Topics

- **STD-06: Date / Year Format** — YYYY vs. YYYY-MM-DD; estimate vs. confirmed years; fiscal years
- **STD-13: Temporal Snapshots** — release-date snapshots; wide vs. long annual series; `Year of X` companion pattern
- **STD-01: Null / Missing Value Encoding** — `unknown`, `not found`, `-`, `TBD` as null proxies in date fields
- **IOP-03: Status** — lifecycle event years map directly to status transitions; `Status year` in GOGET/GMET

---

**Interoperability topics:** [Index](index.md) · [IOP-01: IDs](iop-01-ids.md) · [IOP-02: Names](iop-02-names.md) · [IOP-03: Status](iop-03-status.md) · [IOP-04: Capacity](iop-04-capacity.md) · [IOP-05: Location](iop-05-location.md) · [IOP-06: Temporal](iop-06-temporal.md)
