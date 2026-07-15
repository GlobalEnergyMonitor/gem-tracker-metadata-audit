---
layout: default
title: "IOP-05: Location"
---

# IOP-05: Location

**Status:** Draft — for discussion with Data Team  
**Scope:** How geodata is stored and provided; the types and depth of location information across trackers

---

## Inventory

### Coordinates

Point-location trackers use one of two patterns for storing coordinates:

**Separate fields** (most DB-backed power trackers, Coal Mine, Coal Terminals, GOGET, GMET):
- `Latitude` and `Longitude` as independent numeric fields
- Enables direct numeric queries and mapping without parsing

**Combined field** (Iron & Steel, Cement, Chemicals, Iron Ore):
- A single `Coordinates` field in `lat, lon` format (decimal degrees, comma-separated)
- Example: `47.9822760, 37.8106340`
- Requires string splitting to use in mapping tools or numeric queries

LNG Carrier is a special case: coordinates (`Yard location latitude`, `Yard location longitude`) refer to the shipyard where the vessel was built, not the vessel's current position — carriers are mobile assets unlike all other GEM-tracked infrastructure.

GMET tracks two coordinate pairs per record: asset location (`Latitude`, `Longitude`) and methane plume origin (`Plume Origin Latitude`, `Plume Origin Longitude`).

### Coordinate accuracy

Almost all trackers with coordinates include an accuracy qualifier. This is one of the most consistently implemented cross-tracker fields in the portfolio, though naming and case vary:

| Field name | Trackers | Values |
|---|---|---|
| `Location accuracy` | Coal Plant, Solar, Wind, Bioenergy, GOGPT, GOGET, GIPT | `exact`, `approximate` |
| `Location Accuracy` | Nuclear, Geothermal, Hydro, Bioenergy, Coal Mine, Coal Terminals | `exact`/`Exact`, `approximate`/`Approximate` |
| `Coordinate accuracy` | Iron & Steel, Cement, Chemicals, Iron Ore | `exact`, `approximate` |
| `Accuracy` | LNG Terminals, GMET | `approximate`, `exact` |
| `Yard location accuracy` | LNG Carrier | `exact`, `approximate` |
| `RouteAccuracy` | Gas Pipelines, Oil/NGL Pipelines | `low`, `medium`, `high`, `very high (within meters)`, `no route` |

Pipeline route accuracy uses a different scale entirely — it rates the precision of the route geometry, not a point coordinate.

Case is inconsistent even within the same tracker: Solar has both `approximate` and `Approximate` in the same field.

### GOGET location derivation

GOGET's `Project location type` field distinguishes two derivation methods:
- `project level location` — coordinates were assigned at the project centroid directly
- `location derived from fields` — coordinates were computed from the individual field (sub-project) locations

This is a useful distinction for downstream users who need to know whether a GOGET point location is directly observed or calculated.

### Administrative hierarchy

The standard geographic hierarchy has up to six levels below coordinates. Coverage and field naming vary by tracker. The subnational unit standard has recently been updated — field names, allowed values, and boundary definitions have been standardized — but tracker adoption is in progress.

**Current field names in use for the primary subnational level:**

| Field name | Trackers | Notes |
|---|---|---|
| `State/Province` | Solar, Wind, Nuclear, Geothermal, GOGPT, LNG Terminals, Coal Terminals | New standard |
| `Subnational unit (province, state)` | Coal Plant, GIPT | Old standard, pending migration |
| `Subnational unit (state, province)` | GIPT variant | Parenthetical word order differs |
| `Subnational unit` | Iron & Steel, Cement, Chemicals, Iron Ore, GOGET, GMET | No parenthetical explainer |
| `State, Province` | Coal Mine | Comma separator instead of slash |

**Secondary and tertiary subnational levels:**

| Level | DB-backed power trackers | Coal Mine |
|---|---|---|
| Secondary | `Major area (prefecture, district)` | `Prefecture, District` |
| Tertiary | `Local area (taluk, county)` | — |
| Settlement | `City` or `Location` | `Location` + `Location (Non-ENG)` |

Cement, Chemicals, Iron Ore, and Iron & Steel use only two levels (`Subnational unit` + `Municipality`) — no secondary or tertiary divisions.

**Country field** — see STD-12 for the full name variant inventory (`Country/Area`, `Country/area`, `Country / Area`, `Country`). `Country/Area` is the standard.

**Region and Subregion** are derived from Country via lookup (UN M49), not entered directly. `SubRegion` (capital R) appears in some older exports; the standard is `Subregion`.

### Special geographic structures

**Multi-country assets (Hydro):** Cross-border hydropower plants duplicate the full hierarchy with `1`/`2` suffixes: `City 1`, `City 2`, `State/Province 1`, `State/Province 2`, etc.

**Pipeline geography (GGIT, GOIT):** Multi-country pipelines use `CountriesOrAreas` (a multi-value field) instead of a single `Country/Area`. Route geometry lives in the map layer, not the tabular data.

**Geological geography (GOGET):** Uses `Basin` (geological basin name) as an additional location concept that has no equivalent in administrative hierarchies. GOGET still includes `Country/Area` and `Subnational unit`, but the mid-level geography is geology-based.

**Ownership Tracker:** No asset-level coordinates or administrative hierarchy. Location comes through joins to primary trackers. The Ownership Tracker does include entity-level fields: `Headquarters Country`, `Registration Country`, `Parent Headquarters Country`, `Parent Registration Country`.

**GIPT (Integrated Power):** Includes full UN M49 codes and names (`M49 Country Code`, `Region Code (M49)`, `Sub-region Code (M49)`, etc.) in addition to the standard GEM fields — the most complete geographic metadata of any tracker.

---

## Interoperability Gaps

**Two coordinate storage patterns with no standard.** Separate `Latitude`/`Longitude` fields and a combined `Coordinates` field serve the same purpose. The combined field requires parsing before use in any numeric context. There is no documented rationale for which pattern to use.

**Coordinate accuracy field name and case are inconsistent.** Five different field names for the same `exact`/`approximate` concept, plus case inconsistency within some trackers. A cross-tracker query on location accuracy cannot use a single field name.

**Subnational standard adoption is incomplete.** The new standard (field name, allowed values, boundary definitions) has been defined and implemented for new work, but a number of trackers still use the old field name (`Subnational unit (province, state)`) or non-standard variants (`State, Province`). Until migration is complete, a cross-tracker join on subnational unit will not reliably match records in the same administrative area.

**`City` vs. `Location` for the settlement level.** DB-backed power trackers split on which word to use: Coal Plant and Coal Mine use `Location` (which admits industrial parks, administrative zones, and approximate place names); most newer trackers use `City`. These mean the same structural level but different things semantically — `City` implies an urban settlement.

**Pipeline and point accuracy are on incompatible scales.** `RouteAccuracy` (`low/medium/high/very high`) cannot be compared to point accuracy (`exact/approximate`). A unified query across all trackers on "how precise is the location" would need to handle these separately.

**An internal GMET field is exposed in the export.** The field `for internal use - gem subnational unit` appears in the GMET spreadsheet. Internal workflow fields should not appear in public exports.

---

## Decisions Needed

### Naming and field conventions

**Standardize coordinate storage pattern.** Separate `Latitude` and `Longitude` fields is the better choice for numeric usability — no parsing required, directly queryable. Trackers using `Coordinates` (Iron & Steel, Cement, Chemicals, Iron Ore) should migrate; the combined format could be offered as a derived convenience column.

**Standardize coordinate accuracy field name and case.** Proposed standard: `Location accuracy` (lowercase, matching the majority of DB-backed power trackers), with values `exact` and `approximate` (lowercase). `Coordinate accuracy` (used by the `Coordinates`-pattern trackers) should align once those trackers adopt separate lat/lon fields.

**Standardize settlement level field name.** A decision is needed on `City` vs. `Location`. See STD-12 Decision 3 for the tradeoff; whichever is chosen should apply consistently.

### Schema and architecture

**Complete subnational standard adoption.** The new subnational standard defines field names, allowed values, and boundary agreements. Trackers still using old field names should be migrated on a defined schedule. Until then, field-level metadata should document the mapping from old to new names for consuming applications.

**Document the GOGET `Project location type` pattern.** The distinction between directly-assigned and derived coordinates is useful for data quality assessment and should be considered for other trackers where coordinates may be approximate centroids rather than observed points (e.g. mine areas, pipeline project locations).

**Formalize the multi-country asset pattern.** Hydro's `1`/`2` suffix approach handles binary cross-border cases. See STD-12 Decision 5 for options when assets span more than two countries.

### Governance and process

**Remove the internal GMET field from exports.** `for internal use - gem subnational unit` should not be in the public spreadsheet.

---

## Related Topics

- **STD-12: Geographic Hierarchy** — full inventory of country/area naming variants and subnational level decisions
- **STD-09: Cross-field Links** — `Location accuracy` as a qualifier for `Latitude`/`Longitude`
- **IOP-04: Capacity / Size** — cross-border capacity splits in Hydro mirror the geographic duplication
- **IOP-01: IDs** — `GEM location ID` is the join key for location-level cross-tracker queries

---

**Interoperability topics:** [Index](index.md) · [IOP-01: IDs](iop-01-ids.md) · [IOP-02: Names](iop-02-names.md) · [IOP-03: Status](iop-03-status.md) · [IOP-04: Capacity](iop-04-capacity.md) · [IOP-05: Location](iop-05-location.md) · [IOP-06: Temporal](iop-06-temporal.md)
