# STD-07: Required Fields / Nullability

**Status:** Draft — for discussion with Data Team  
**Scope:** All tracker spreadsheets and the research database export pipeline

---

## Current State

Required-ness exists in the DB but is implicit, inconsistent across models, and not surfaced in field metadata.

The field-level metadata schema defines an `is_required` boolean property, but it is a placeholder — it has never been populated for any tracker. To understand what is actually required, you have to read the Django models directly.

### How Django encodes required-ness

In Django, `blank=True` on a field means "optional at form level." The default (no `blank=` specified) is `blank=False`, meaning required. This is distinct from `null=False` (which controls the DB column constraint) — most fields are stored as nullable at the DB level even if they're required at the form level.

**Plant and PowerUnit models** — the core power-plant models — use Django defaults: `name`, `capacity`, `wikiUrl`, `city`, `coalSource`, etc. have no `blank=` specified, making them de facto required at form-entry time. Required-ness here is implicit in the absence of `blank=True`.

**SteelProject, LNGProject, GOGETProject** — newer models — take the opposite approach: they use `blank=True` explicitly on most fields, treating the majority of content as optional. This reflects a deliberate shift in how the DB team approached data completeness requirements for these asset types.

The only fields with explicit `null=False` DB constraints are: internal FK relationships (`project`, `company`, `owner`), audit timestamps (`created`, `modified`, `deleted`), and a handful of internal flags (`projectType`, `subnationalChecked`, `order`). No content fields — name, status, capacity, country — carry DB-level NOT NULL constraints.

De facto required fields are still visible in the export data: GEM Unit ID, GEM Location ID, Plant name, Country/Area, Status, and Capacity (MW) are **0% null** across mature DB-backed tracker exports (Coal Plant, Gas, Nuclear, Hydro). But this reflects application-level enforcement at data entry, not a documented standard.

### Null rate distribution (excluding Portal Energetico)

Across all fields in non-Portal trackers with ≥10 records:

| Null rate | Field count | Share |
|---|---|---|
| 0% | 795 | 42% |
| <1% | 68 | 4% |
| 1–5% | 75 | 4% |
| 5–25% | 156 | 8% |
| 25–75% | 347 | 18% |
| >75% | 422 | 22% |

The bimodal distribution — 42% fully populated, 22% mostly empty — reflects two distinct field populations: core identity/status fields that are always present, and optional/specialized fields that apply only to subsets of records.

### Fields that are de facto required (0% null in DB exports)

Across mature trackers (Coal Plant, Gas, Nuclear, Hydro, Steel):

- **GEM Unit ID / GEM Location ID / GEM Plant ID** — the join key; always present
- **Plant name** — always present
- **Country/Area** — always present
- **Status** — always present
- **Capacity (MW)** — always present in power plant trackers (not a universal requirement — hydro and nuclear have it; steel uses different capacity fields)

### Fields that are explicitly not required (significant null rates in DB exports)

- **Start year** — 26% null in Coal Plant, 15% null in Gas. Many plants in the DB lack confirmed start dates; this is by design.
- **Retired year** — null for all operating plants; structural null, not a data gap.
- **Operator** — 70% null at the unit level in `snapshot.powerplant_unit`. Ownership data is often incomplete.
- **Latitude / Longitude** — 71% null in `snapshot.powerplant_unit`; location precision varies widely by tracker.

### Special cases

**Portal Energetico** shows 82–98% null rates on GEM IDs, names, status, and country across most of its tabs. This is because Portal Energetico is a multi-tracker aggregation and many records are either partially matched or sourced from other trackers' tabs included for reference. It is not a data quality failure; it reflects the nature of the tracker.

**Gas Finance Tracker** — GEM Unit ID is 61% null. Finance deals are often recorded at the plant or project level, and not all deals can be attributed to a specific GEM unit. Required-ness at the unit level is not appropriate here; required-ness at the project/plant level may be.

---

## Decision Points

### Decision 1: Should `is_required` be formally documented in field metadata?

Currently no field has `is_required` set, making the compliance check for required-field nulls inoperable. Before the check can be meaningful, the field needs to be populated for at least the core fields.

**Options:**
- **Populate for de facto required fields only** — mark the handful of fields that are genuinely always required (GEM ID, name, country, status) as `is_required = true` based on current practice. Document the rest as not required. This is a starting point that doesn't require resolving every edge case.
- **Define per-tracker required sets** — required fields vary by tracker type. A coal mine doesn't have a Capacity (MW) field; an LNG terminal doesn't have a Start year in the same sense as a power plant. Required-ness is most meaningful as a per-tracker-per-field property.
- **Defer until unified schema is defined** — required-ness in the current spreadsheet world is less important than required-ness in the target DB. Formally defining it now may create work that needs to be redone once the schema is unified.

### Decision 2: Where is required-ness enforced?

Three possible enforcement layers, from most to least strict:

**DB constraint (NOT NULL)** — enforced at write time; no null can be inserted. Guarantees data integrity but requires the DB to know required-ness at schema definition time.

**Application validation (Django form)** — enforced at data entry; the UI prevents saving a record without the required field. Currently how the DB handles it, though not documented in the schema.

**Audit/export check** — required-ness is checked at report generation time; records with missing required fields are flagged or excluded. Most flexible; allows partial records in the DB for in-progress research.

The current system implicitly uses application validation. The audit tool adds export-time checking. For the unified DB, a combination of application validation (for user-facing entry) and audit flagging (for imported/legacy data) is likely the right approach.

### Decision 3: How to handle legitimately partial records?

Some records are intentionally incomplete — a newly announced plant may have a name, country, and status but no capacity yet; a historical plant may have a capacity and status but no precise start year. Two framings:

**Framing A — Required = must be non-null before export**  
A field is required if it must be populated before a record appears in a public release. In-progress records can have nulls; they're excluded from export until populated. This is closest to current practice.

**Framing B — Required = must be non-null at all times**  
A stronger constraint that forces researchers to provide at least a placeholder value (e.g., `unknown`) for required fields at data entry. Easier to query but at the cost of polluting required fields with sentinel values (see STD-01).

### Decision 4: Capacity as a required field — by tracker type?

Capacity (MW) is 0% null in Coal Plant, Gas, Nuclear, and Hydro exports — but it isn't meaningful for all tracker types. Steel has technology-specific capacity fields (BOF, EAF, DRI) rather than a single MW figure. Coal Mines have production capacity in Mtpa rather than MW. Coal Terminals have throughput capacity in Mt.

Required-ness for capacity is therefore tracker-specific: the field name and units differ, but the concept ("what is the scale of this asset") should be required for all trackers. A unified schema would need to define which capacity field is required per asset type.

### Decision 5: GEM IDs as conditionally required

GEM Unit ID is 0% null in mature trackers but 61% null in Gas Finance and high-null in early Portal Energetico tabs. The ID requirement depends on what level the tracker operates at:

- **Unit-level trackers** (Coal Plant, Gas, Nuclear): GEM Unit ID required
- **Project/plant-level trackers** (Steel, Hydro): GEM Plant ID or GEM Location ID required; GEM Unit ID may be optional or absent
- **Finance trackers** (Coal Finance, Gas Finance): GEM IDs are reference fields — required if the deal can be attributed to a known asset, but legitimately null for portfolio-level deals

A unified required-field standard needs to account for this hierarchy.

---

## Proposed Minimum Required Set

As a starting point for discussion, these fields should be `is_required = true` for any record included in a public release, across all tracker types:

| Field concept | Canonical name(s) | Notes |
|---|---|---|
| Primary GEM ID | `GEM unit/phase ID`, `GEM plant ID`, `GEM project ID` | Type-appropriate ID must be present |
| Name | `Unit name`, `Plant name`, `Project name` | Human-readable identity |
| Country / Area | `Country/Area` | Geographic anchor |
| Status | `Status` | Lifecycle state |
| Scale / Capacity | varies by tracker | The primary magnitude field for the asset type |

Fields that appear in nearly every tracker but are **not** proposed as universally required:

- **Start year** — significant legitimate null rate; many announced/pre-construction assets have no confirmed date
- **Latitude / Longitude** — coverage is deliberately partial; location accuracy tiers exist precisely because location data varies
- **Owner / Operator** — ownership data is systematically incomplete; treating it as required would either block export of many valid records or force `unknown` into the field

---

## Related Standards

- **STD-01: Null / Missing Value Encoding** — what null means vs. unknown vs. doesn't apply
- **STD-04: Categorical Allowed Values** — `unknown` as a value for required categorical fields
- **STD-09: Cross-field Links** — required fields that travel in pairs (e.g., capacity + datasource)
