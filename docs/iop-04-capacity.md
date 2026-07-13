---
layout: default
title: "IOP-04: Capacity / Size"
---

# IOP-04: Capacity / Size

**Status:** Draft — for discussion with Data Team  
**Scope:** The primary magnitude field across trackers — capacity, throughput, production volume, and physical size

---

## Inventory

"Capacity" means different things across tracker types. The table below groups trackers by the concept their primary magnitude field represents:

### Electrical capacity (MW)

The most consistent group. Nearly all power trackers use `Capacity (MW)` at the unit or phase level, with the unit embedded in the field name.

| Tracker | Field(s) | Notes |
|---|---|---|
| Coal Plant, Solar, Wind, Bioenergy, Hydro, GOGPT | `Capacity (MW)` | Standard form |
| Geothermal | `Unit Capacity (MW)` | Inconsistent field name |
| Nuclear | `Capacity (MW)`, `Design Net Capacity (MW)`, `Reference Net Capacity (MW)`, `Thermal Capacity (MWt)` | Multiple measures; see Gaps |
| Solar | `Capacity (MW)` + `Capacity Rating` | Rating likely captures DC vs. AC distinction |
| Hydro | `Capacity (MW)` + `Country/Area 1 Capacity (MW)`, `Country/Area 2 Capacity (MW)` | Per-country split for cross-border assets |

### Variable-unit capacity (infrastructure)

Pipelines, terminals, and carriers transport different commodities with no single standard unit. The DB stores capacity and unit as separate fields; the spreadsheet export sometimes omits or embeds the unit.

| Tracker | Field(s) | Units in DB |
|---|---|---|
| LNG Terminals / Projects | `Capacity` + `capacityUnit` (DB) | bcf/d, mtpa, bcm/y, MWh/d, TJ/d, MMcf/d |
| Gas Pipelines | `Capacity` | Unit specified in tracker metadata tab |
| Oil/NGL Pipelines | `Capacity` | Unit specified in tracker metadata tab |
| LNG Carrier | `Capacity` + `Capacity units` | Unit stored as separate field in spreadsheet |
| Coal Terminals | `Capacity (Mt)` | Throughput, unit embedded |
| Gas Finance | `Capacity (MW)`, `Capacity (mtpa)` | Separate fields by asset type within tracker |

### Mass-based capacity and production (extraction / heavy industry)

For mines and industrial plants, capacity is a nameplate or design figure; production is the actual output. Both are tracked where possible, though coverage varies.

| Tracker | Capacity field | Production field | Unit |
|---|---|---|---|
| Coal Mine | `Capacity (Mtpa)` | `Production (Mtpa)` + annual time series | Mt / Mst per year |
| Iron Ore | `Design capacity (ttpa)` | `Production 20XX (ttpa)` (3 years) | ttpa |
| Iron & Steel (unit level, DB) | `capacity` | Separate `steel_yearly_production` / `iron_yearly_production` tables | ttpa |
| Iron & Steel (plant level, export) | `Nominal crude steel capacity (ttpa)`, `Nominal iron capacity (ttpa)`, plus 8+ process-specific fields | Annual production tab | ttpa |
| Cement | `Cement Capacity (mmtpa)`, `Clinker Capacity (mmtpa)` | Not tracked at plant level | mmtpa |

Note: The Iron & Steel spreadsheet export denormalizes the DB's clean unit-level `capacity` field into multiple plant-level aggregate columns. The DB's native representation — unit type + unit capacity — is simpler.

### Physical size

A small number of fields capture physical dimensions rather than throughput or output capacity:

| Tracker | Field | Concept |
|---|---|---|
| Coal Mine | `Mine Size (Km2)` | Surface area of the mine site |
| Iron & Steel (blast furnace units) | `Current size (m3)` | Furnace interior volume |
| Coal Mine, Iron & Steel | `Workforce Size` | Headcount |
| Gas Pipelines / GMET | `Length Merged Km` | Linear infrastructure length |

### No capacity field

GOGET has no asset-level capacity or size field. Production and reserve volumes are tracked in a separate time-series `reserves_production` table (one row per project/unit/year) with a `quantity` and `reserveClassification` field. This is by design — extraction volumes change annually and don't have a meaningful "nameplate" equivalent.

---

## Interoperability Gaps

**Unit embedding vs. separate unit field.** Power trackers embed the unit in the field name (`Capacity (MW)`), which is readable but means a unit change requires renaming the field. Infrastructure trackers with variable units (LNG, pipelines) store the unit separately in the DB — but the spreadsheet export is inconsistent: LNG Carrier exposes `Capacity units` as a separate field, while gas and oil pipeline exports omit the unit from the field name entirely and rely on the metadata tab.

**Nuclear has four capacity fields with no documented primary.** `Capacity (MW)`, `Design Net Capacity (MW)`, `Reference Net Capacity (MW)`, and `Thermal Capacity (MWt)` all appear in the export. For cross-tracker comparisons, it is not documented which is the canonical electrical capacity figure. `Capacity (MW)` is most likely, but this should be confirmed and made explicit in the field metadata.

**Iron & Steel: DB model vs. spreadsheet export diverge.** The DB stores a single `capacity` value per unit (paired with unit type). The spreadsheet export adds calculated plant-level aggregates (`Nominal crude steel capacity`, `Nominal iron capacity`, plus 8+ process-specific columns). Cross-tracker queries against the spreadsheet face a different schema than queries against the DB.

**Capacity vs. production is only tracked in some extraction trackers.** Coal Mine and Iron Ore both carry design capacity and actual production. Cement does not track production at the plant level. The ambition to expand production coverage to more trackers (where data is available) is not yet reflected in a consistent field schema.

**`Geothermal` uses `Unit Capacity (MW)` instead of `Capacity (MW)`.** Functionally identical but doesn't match as a string.

---

## Decisions Needed

### Naming and field conventions

**Standardize `Unit Capacity (MW)` → `Capacity (MW)`.** Geothermal is the only power tracker using the longer form; no semantic distinction justifies it.

**Document the canonical capacity field for Nuclear.** Confirm which of the four fields is the primary cross-tracker magnitude, and add that designation to the field metadata. The others should be documented as supplementary.

**Standardize the unit-handling pattern for variable-unit infrastructure trackers.** Two options:
- **Embed unit in field name** — acceptable when the unit is constant across all records in the tracker (Coal Terminals: `Capacity (Mt)` is fine)
- **Separate unit field** — required when the unit varies by record (LNG: the DB's `capacityUnit` field is the correct pattern; LNG Carrier's `Capacity units` in the export follows this correctly)

Gas and oil pipeline exports should either embed a consistent unit in the field name or expose a separate unit field — not rely on the metadata tab alone.

### Schema and architecture

**Align Iron & Steel export with the DB model.** For cross-tracker interoperability, the unit-level `capacity` (ttpa) + unit type is more useful than the plant-level aggregated columns. If the aggregated columns are retained for readability, the unit-level data should be the canonical form.

**Define a capacity vs. production schema for extraction trackers.** As more trackers add production coverage, a consistent two-field pattern should be documented: `Capacity ([unit])` for nameplate/design and `Production ([unit])` for actual annual output, with a `Year of Production` companion (following the Coal Mine pattern — see IOP-06).

### Comparability across asset types

Matching units do not imply comparable quantities. A coal mine's `Capacity (Mtpa)` measures extraction output; a coal terminal's `Capacity (Mt)` measures throughput; a coal plant's `Capacity (MW)` measures electrical generation. All three appear in adjacent rows of a cross-tracker query but represent qualitatively different physical concepts. Summing or visually scaling them together is misleading even when the unit strings happen to match.

This comparability problem is inherent to any cross-sector tracker portfolio and cannot be fully resolved at the schema level. What metadata can do is make the asset type and physical concept explicit enough that a consuming application can make informed decisions:

- **Asset type** is already encoded by tracker identity and the `taxonomy` tag on ID fields — a consuming API can expose this as a first-class filter
- **Field definitions** should clearly state what the capacity figure represents (extraction rate, throughput, nameplate generation) rather than just the unit
- **Display scaling** decisions (e.g. whether to size map bubbles by MW, Mtpa, or some normalized energy-equivalent) belong in application logic, not field metadata

The question of whether and how to normalize across asset types for aggregate displays is an analytical and front-end concern that the metadata standard should inform but not prescribe.

### External interoperability

**GOGET volume data is not accessible from the main spreadsheet.** Users querying GOGET capacity will need to join to the `reserves_production` table. This join path should be documented, and whether any summary capacity or peak production figure should be added to the main GOGET export is an open question for the PM.

---

## Related Topics

- **STD-05: Numeric Field Purity** — `>0`, `*`, and `-` placeholders are common in capacity and production fields
- **STD-06: Date / Year Format** — `Year of Production` companion field for actual output figures
- **STD-09: Cross-field Links** — capacity accuracy fields; production year companions
- **STD-13: Temporal Snapshots** — capacity as a static snapshot vs. production as a time-varying series
- **IOP-05: Location** — cross-border capacity splits in Hydro

---

**Interoperability topics:** [Index](index.md) · [IOP-01: IDs](iop-01-ids.md) · [IOP-02: Names](iop-02-names.md) · [IOP-03: Status](iop-03-status.md) · [IOP-04: Capacity](iop-04-capacity.md) · [IOP-05: Location](iop-05-location.md) · [IOP-06: Temporal](iop-06-temporal.md) · [IOP-07: Entities](iop-07-entities.md)
