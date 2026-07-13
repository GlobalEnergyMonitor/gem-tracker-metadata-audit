---
layout: default
title: "IOP-02: Names"
---

# IOP-02: Names

**Status:** Draft — for discussion with Data Team  
**Scope:** Primary asset names, local-language variants, and alternate/alias names across trackers

---

## Inventory

Each tracker has a primary name field for the asset and (for multi-level trackers) a separate name field for the unit or phase. The naming of these fields varies by tracker type:

| Tracker | Primary name field | Unit/phase name field |
|---|---|---|
| Nuclear, Hydro, Geothermal, Bioenergy | `Project Name` | `Unit Name` |
| Solar, Wind | `Project Name` | `Phase Name` |
| Gas / GIPT | `Plant name` | `Unit name` |
| Coal Plant | `Plant name` | `Unit name` |
| Iron & Steel | `Plant name (English)` | `Unit name` |
| Chemicals | `Plant name (English)` | — |
| Cement | `GEM Asset name (English)` | — |
| Coal Mine | `Mine Name` | — |
| Coal Terminals | `Coal Terminal Name` | — |
| GOGET | `Project Name` | `Unit Name` |
| Gas Finance | `Project Name` | `Train/Unit Name` |
| LNG Carrier | `Name` | — |
| GMET | `Name` | — |

**"Project" vs. "Plant"** is an intentional distinction: "Project" is the general term used for any type of infrastructure asset (plant, terminal, pipeline, extraction operation); "Plant" is used where the asset is specifically a generation or processing facility.

### Local-language name fields

All trackers that include a local-language name use it for the same purpose — the asset's name in its native script or language, for display in local contexts. The field name varies:

| Field name | Trackers |
|---|---|
| `Project Name in Local Language / Script` | Nuclear, Solar, Wind, Bioenergy, Geothermal, Hydro |
| `Plant Name in Local Language / Script` | GOGPT |
| `Plant name (local)` | Coal Plant |
| `Plant name (other language)` | Iron & Steel, Chemicals |
| `Asset name (other language)` | Cement, Iron Ore |
| `Mine Name (Non-ENG)` | Coal Mine |

Owner and operator local-language names follow similar variation: `Owner Name in Local Language / Script` vs. `Owner name (other language)` vs. `Owner Name (local lang/script)`.

### Alternate / alias name fields

All trackers that include alternate names use them for the same purpose — known aliases, former names, or variant spellings that aid search and deduplication. Field name varies:

| Field name | Trackers |
|---|---|
| `Other Name(s)` | Nuclear, Solar, Wind, Bioenergy, Geothermal, Hydro, GOGPT |
| `Mine Name AKAs` | Coal Mine |
| `Alternate Project Name(s)` | Gas Finance |
| `Plant name (other)` | Coal Plant |
| `Alternative asset name(s)` | Cement |
| `Coal Terminal Name (detail or other)` | Coal Terminals |

These fields are typically multi-value (comma- or semicolon-separated); see STD-02 for separator conventions.

### Mine complex names

Coal Mine includes a `Complex Name` field — the name of the larger mine complex that a given mine area belongs to. This is free text and only populated for mines that are part of a complex. No other tracker has an equivalent field, and mine complexes have no GEM ID (see IOP-01).

---

## Interoperability Gaps

**Primary name field naming is inconsistent at both levels.**  
The concept "the canonical display name for this asset" is expressed as `Project Name`, `Plant name`, `Plant name (English)`, `GEM Asset name (English)`, `Mine Name`, `Coal Terminal Name`, or `Name` depending on the tracker. Similarly at the unit level: `Unit Name`, `Unit name`, `Phase Name`, `Unit / Phase name`, `Train/Unit Name`. These all refer to the same structural role in their respective trackers.

**Local-language and alias fields have no consistent naming.**  
Three distinct naming patterns exist for local-language names alone (see table above). A tool doing cross-tracker name lookup cannot assume a consistent field name.

**No defined canonical name source.**  
Each asset also has a wiki page with a title. It is not documented whether the wiki title is authoritative over the spreadsheet field or vice versa, or what the process is when they diverge.

**Deduplication process is undocumented.**  
When two proposed project records are later found to refer to the same asset, it is unclear whether the merge decision is made by name matching, coordinate proximity, ID matching, or researcher judgment. This affects data quality but also the design of any automated deduplication tooling.

---

## Decisions Needed

### Naming and field conventions

**Standardize the primary name field name.** The "Project" vs. "Plant" distinction is meaningful and should be preserved. The question is whether the field name should be consistent within each group:
- All general-purpose trackers: `Project Name`
- All plant-specific trackers: `Plant Name` (dropping the `(English)` qualifier — if the canonical name is always in English, that should be documented rather than embedded in the field name)
- Type-specific trackers: `Mine Name`, `Terminal Name` — acceptable as-is

**Standardize local-language name fields.** All variants mean the same thing. Proposed standard: `[Asset type] Name (local language / script)` — e.g. `Project Name (local language / script)`, `Plant Name (local language / script)`, `Mine Name (local language / script)`. More explicit than `(Non-ENG)` and more consistent than `(other language)`.

**Standardize alternate name fields.** Proposed standard: `Other Name(s)` — already used by most DB-backed trackers, clearly conveys "alias or alternate" without being tracker-specific.

### Schema and architecture

**Canonical name source.** A decision is needed on whether the wiki page title or the tracker spreadsheet field is the source of truth for an asset's display name, and what the update process is when they diverge.

**Mine complex names.** `Complex Name` is currently free text with no ID backing. If cross-mine queries by complex are a use case, complex names need IDs (see IOP-01).

### Governance and process

**Deduplication.** The merge process for duplicate project records should be documented — specifically: what triggers a merge investigation, what evidence is required, which record's ID and name survive, and who approves the merge.

---

## Related Topics

- **IOP-01: IDs** — ID assignment and merge decisions when duplicate name records are found; mine complex IDs
- **STD-02: Multi-value Separators** — `Other Name(s)` and AKA fields contain multiple values
- **STD-08: Field Naming Conventions** — `(English)` qualifier in asset name fields; `(local)` vs. `(local language / script)`
- **IOP-07: Entities** — owner and operator name fields follow the same local-language pattern

---

**Interoperability topics:** [Index](index.md) · [IOP-01: IDs](iop-01-ids.md) · [IOP-02: Names](iop-02-names.md) · [IOP-03: Status](iop-03-status.md) · [IOP-04: Capacity](iop-04-capacity.md) · [IOP-05: Location](iop-05-location.md) · [IOP-06: Temporal](iop-06-temporal.md) · [IOP-07: Entities](iop-07-entities.md)
