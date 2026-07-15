---
layout: default
title: "IOP-01: Identifier Systems"
---

# IOP-01: Identifier Systems

**Status:** Draft — for discussion with Data Team  
**Scope:** GEM-assigned identifiers, external reference IDs, and cross-tracker linking

---

## Inventory

Most trackers have one or two levels of GEM-assigned IDs. The table below maps each tracker to its levels and field names as they appear in spreadsheet exports.

| Tracker | Level 1 (location / plant / asset) | Level 2 (unit / phase) | Notes |
|---|---|---|---|
| Coal Plant | `GEM location ID` | `GEM unit/phase ID` | |
| Gas / GIPT | `GEM location ID` | `GEM unit/phase ID` | |
| Nuclear | `GEM location ID` | `GEM unit ID` | |
| Hydro | `GEM location ID` | `GEM unit ID` | |
| Geothermal | `GEM location ID` | `GEM unit ID` | |
| Solar | `GEM location ID` | `GEM phase ID` | "Phase" reflects staged buildout |
| Wind | `GEM location ID` | `GEM phase ID` | |
| Bioenergy | `GEM location ID` | `GEM phase ID` | |
| Iron & Steel | `GEM plant ID` | `GEM unit ID` | |
| Coal Terminals | `GEM Terminal ID` | `GEM Unit/Phase ID` | |
| Cement | `GEM Plant ID` | — | |
| Chemicals | `GEM plant ID` | — | Capitalization inconsistent with Cement |
| Coal Mine | `GEM Mine ID` | — | Multiple rows per Mine ID (see Gaps) |
| Iron Ore | `GEM Asset ID` | — | |
| GOGET | `Project ID` | `Unit ID` | Not GEM-prefixed in export |
| Gas Finance | `GEM Project ID`, `GEM Terminal ID`, `GEM Combo ID` | `GEM Unit ID` | Multiple level-1 types within one tracker |
| GMET | `GEM Mine ID`, `GEM GOGET ID`, `GEM Project ID`, `GEM Methane Plume ID` | — | References IDs from other trackers |
| Ownership | All of the above (as foreign keys) | | Derivative tracker |
| Portal Energetico | All of the above (as foreign keys) | | Derivative tracker |

**Cross-tracker linking patterns:**
- **Derivative trackers** (Ownership, Portal Energetico) carry primary tracker IDs as foreign keys rather than assigning new ones
- **Shared location IDs across fuels** — a site with units of different fuel types has distinct unit IDs per tracker but a shared `GEM location ID`
- **Related-asset references** — some trackers reference IDs from other trackers to express a dependency (e.g. a steel plant's captive coal plant)
- **Conversion references** — `Conversion to (GEM unit ID)` / `Conversion from/replacement of (GEM unit ID)` link records within a tracker when a plant converts fuel type

---

## Interoperability Gaps

**No consistent primary key definition**  
Several trackers lack a formally defined primary key for their data tab. Coal Mine is the clearest case: mine areas with different statuses (active, expansion, closed) share the same `GEM Mine ID`, so no single field uniquely identifies a row. The working key is `Mine ID + Status`, but this is not enforced. Other trackers may have similar issues that haven't been audited.

**Missing IDs for grouping concepts**  
Some concepts that appear in the data have no GEM ID assigned: mine complexes (groups of operationally related mines), pipeline segments (individual segments of a larger pipeline). Without IDs, these can only be referenced by name, which is fragile for cross-tracker joins.

**GOGET IDs are not GEM-prefixed**  
`Project ID` and `Unit ID` in GOGET look like external or government IDs in the spreadsheet export. This is inconsistent with every other tracker and makes it harder to recognize them as GEM-assigned keys.

**Capitalization is inconsistent**  
`GEM plant ID` (Iron & Steel, Chemicals) vs. `GEM Plant ID` (Cement, Ownership); `GEM location ID` vs. `GEM Location ID` — these refer to the same concepts but don't match as strings.

---

## Decisions Needed

### Naming and field conventions

The type-specific nouns in ID field names (`Mine ID`, `Terminal ID`, `Plant ID`) are intentional and should be kept — `GEM Unit ID` for a pipeline segment or mine area would be confusing. The issues are format, not semantics.

**Proposed standard:** `GEM [Type] ID` — always GEM-prefixed, title case for the type noun.  
Fixes needed: `GEM plant ID` → `GEM Plant ID`; `Project ID` / `Unit ID` in GOGET → `GEM Project ID` / `GEM Unit ID`.

### Schema and architecture

**Define granularity levels per tracker.** No document currently maps each tracker to its ID levels and defines the primary key for each data tab. This inventory (and the decisions that follow from it) is the prerequisite for any other ID work.

For API and cross-tracker use, the internal representation should normalize to two canonical levels — `location_id` and `unit_id` — as the Ownership API already does. Each tracker's type-specific field names map to one of these two levels.

**Define composite keys where single-field keys don't exist.** For Coal Mine and any other tracker where a single ID field isn't a primary key, a composite key needs to be defined, documented, and validated.

**Assign IDs to currently unidentified concepts.** Mine complexes and pipeline segments need GEM IDs if they are to be joinable. This requires deciding what level of concept warrants an ID and who is responsible for assignment.

### Governance and process

**ID assignment.** GEM IDs are internally generated and uniqueness is consistently enforced, but there is no documented process for: (a) how new IDs are allocated, (b) how duplicate project records are merged and which ID survives, (c) how IDs are assigned retroactively to concepts that currently lack them.

### External interoperability

Inclusion of third-party IDs (`MSHA ID`, `SFI ID`, `LeadIT Project ID`, etc.) is currently ad hoc — each tracker manager decides independently whether to include them and what to name the field.

**Options:**
- **Document and leave as-is** — inventory what exists; no new standard
- **Define inclusion criteria** — include an external ID when it comes from an authoritative source and enables joins that GEM users would want (e.g. regulatory filings, widely-used reference datasets); exclude internal supplier IDs with no public reference
- **Standardize field naming** — whatever is included, name it `[Source] ID` consistently (e.g. `MSHA ID`, `WRI ID`) rather than generic names like `Source ID`

---

## Related Topics

- **IOP-02: Names** — display names alongside IDs; deduplication by name vs. ID
- **IOP-03: Status** — status as part of composite keys (Coal Mine)

---

**Interoperability topics:** [Index](index.md) · [IOP-01: IDs](iop-01-ids.md) · [IOP-02: Names](iop-02-names.md) · [IOP-03: Status](iop-03-status.md) · [IOP-04: Capacity](iop-04-capacity.md) · [IOP-05: Location](iop-05-location.md) · [IOP-06: Temporal](iop-06-temporal.md)
