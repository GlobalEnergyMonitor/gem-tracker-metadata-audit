# STD-04: Categorical Allowed Values

**Status:** Draft — for discussion with Data Team  
**Scope:** All tracker spreadsheets and the research database export pipeline

---

## Current State

Categorical fields — those with a defined set of permitted values — are the most common field type across trackers and the one with the most significant cross-tracker divergence. The audit found 98 out-of-set categorical fields and 143 additional fields with rare-value patterns and no defined reference set.

Three tiers of allowed-value definitions currently exist:

**Tier 1 — Org-canonical reference sets (in the DB)**  
Defined in `snapshot.*` lookup tables and extracted into `reference_sets.json`. Currently covers:
- `status` — 12 canonical values (see below)
- `fuel_category` — 11 values (bioenergy, coal, fossil gas, fossil liquids, geothermal, hydro, nuclear, other, solar, storage, wind)
- `country` — 251 GEM country/area names

**Tier 2 — README/About tab definitions**  
Some trackers define allowed values in their metadata tab ("Field Descriptions" or "Dictionary" sections). These are tracker-specific and are extracted by `extract_metadata.py` into `metadata/{tracker_slug}.json`. Coverage is uneven — mature trackers have detailed definitions; others have none.

**Tier 3 — Implied by data**  
Most categorical fields have no formal allowed-value definition anywhere. The audit infers the value set from what actually appears in the data, which makes it impossible to distinguish "legitimate value not yet seen" from "data entry error."

---

## Status: The Most Important Categorical Field

Status is present in nearly every tracker and has the most significant divergence. Three distinct patterns emerge:

### Pattern A — DB canonical (12 values, lowercase)
Used by trackers driven by the research database: Gas, Nuclear, Hydro, Solar, Wind, Bioenergy, Geothermal, Steel.

```
operating, announced, pre-construction, construction, shelved,
shelved - inferred 2 y, cancelled, cancelled - inferred 4 y,
mothballed, retired, operating pre-retirement, mothballed pre-retirement
```

### Pattern B — Extended or modified canonical (tracker-specific additions)
- **Coal Plant**: adds `permitted` and `pre-permit` — representing regulatory stages not in the canonical set
- **GGIT Gas Pipelines**: uses `proposed` instead of `announced`; omits `pre-construction`
- **GGIT LNG Terminals**: similar to pipelines; adds `ShelvedCancelledStatusType` field to distinguish inferred vs. confirmed (a structural solution the DB handles via separate status values)
- **Coal Terminals**: title case (`Operating`, `Proposed`, `Retired`); uses `Proposed` not `announced`
- **Coal Mine**: title case; uses `Proposed`, `Closed` (not `announced`, `retired`); no `pre-construction`

### Pattern C — Domain-specific vocabulary (different lifecycle model)
Some trackers track assets with genuinely different life stages:

- **GOGET (Oil/Gas Extraction)**: `operating`, `discovered`, `in-development`, `mothballed`, `abandoned` — an oil/gas field has an exploration and discovery phase that a power plant doesn't
- **LNG Carrier**: `active`, `on order`, `proposed` — a vessel lifecycle, not a project lifecycle
- **Iron Ore Mines**: `operating`, `proposed`, `mothballed`, `retired`, `unknown` — closer to canonical but with different terminology

### Case inconsistency
Several trackers use title case (`Operating`, `Proposed`) while the DB canonical set is lowercase. In the data these appear as out-of-set flags even when the underlying concept is correct.

---

## Fuel: A Compound Vocabulary

The fuel reference set in the DB has 11 top-level categories, but actual usage across trackers varies widely:

- **DB-backed trackers** (gas, power): use a compound notation `fuel_category: fuel_detail` — e.g., `fossil gas: natural gas`, `fossil gas: LNG`, `fossil liquids: heavy fuel oil`. This is not the reference set itself but a structured encoding built on top of it.
- **GGIT Gas Pipelines**: just `Gas` (single word, title case)
- **GOIT Oil Pipelines**: `Oil`, `NGL`, `LPG`, `Oil, NGL` — different vocabulary, comma-separated multi-value
- **Geothermal, Nuclear, Hydro**: no Fuel field (implicitly single-fuel by tracker type)

The compound notation is a significant extension beyond the 11-category reference set and has no formal documentation of what `fuel_detail` values are allowed.

---

## Other Fields with Significant Divergence

Beyond Status and Fuel, several tracker-specific categorical fields have no org-level reference and varied definitions:

| Field | Tracker(s) | Notable values / issues |
|---|---|---|
| Mining Method | Coal Mine | Open Pit, Longwall, Mixed, Bord and Pillar, Strip — one value flagged as out-of-set |
| Coal Grade | Coal Mine | Thermal, Met, Chemical, `Thermal & Met` — last value is multi-value-in-cell (see STD-02) |
| Relining status | Iron & Steel | complete, planned, in progress, cancelled, unknown |
| Hydrogen reductant status | Iron & Steel | N/A, unknown, capable, in-use, incapable |
| SOE status | Iron & Steel | N/A, Partial, Full |
| Finance Status / FID Status | Coal Finance, GGIT | Tracker-specific financial lifecycle values |
| Mine Site Status | Coal Mine | Rehabilitation, Abandoned, Demolished — a separate status field for closed sites |
| Status Detail | Coal Mine, GOGET | Free-text extensions of the main status field; high cardinality |

---

## Decision Points

### Decision 1: How should the canonical status list be extended for tracker-specific stages?

The 12-value canonical list covers the power-plant lifecycle well. Other asset types need extensions or replacements. Three options:

**Option A — Single extended list covering all asset types**  
Add tracker-specific stages (`discovered`, `in-development`, `permitted`, `proposed`, `abandoned`, etc.) to the canonical list, marked with which tracker types they apply to.

- Pro: One list to maintain. Cross-tracker status queries can use a single field.
- Con: List grows large. Many values only apply to one asset type. Conflates stages that mean different things across sectors.

**Option B — Canonical core + tracker-specific extensions**  
Maintain the 12-value core (which applies to all power-plant trackers) and allow each tracker to define additional values in its own metadata. Extensions must be documented and approved.

- Pro: Core stays clean. Tracker PMs can define what they need.
- Con: Cross-tracker status queries must map extensions to core values. Governance of extensions needs a process.

**Option C — Per-tracker status vocabularies**  
Treat status as fundamentally tracker-specific. Define allowed values per tracker in that tracker's metadata; use a semantic `taxonomy` tag to identify which values are semantically equivalent across trackers.

- Pro: Most accurate to how trackers actually work.
- Con: Makes cross-tracker status queries hard without explicit mapping tables.

---

### Decision 2: Title case vs. lowercase — pick one and enforce it

Multiple trackers use `Operating` vs. `operating`, `Proposed` vs. `announced` for the same concept. This creates unnecessary out-of-set flags and makes cross-tracker queries case-sensitive.

**Recommendation:** Standardize on lowercase for all canonical status values (consistent with the DB), and treat title case as a data quality flag correctable at ETL. Document this as a normalization rule rather than a manual fix.

---

### Decision 3: How should the compound fuel notation be formalized?

The `fossil gas: natural gas` pattern is used widely across DB-backed trackers but is undocumented as a standard. Three options:

**Option A — Formalize the compound notation as a structured type**  
Define the `fuel_category: fuel_detail` structure explicitly in field metadata (as a `structured` data sub-type). Document the allowed fuel_detail values per category.

- Pro: Already in use. Preserves human-readability.
- Con: Requires documenting all valid fuel_detail values. Parsing is slightly harder than a simple categorical.

**Option B — Split into two fields: Fuel Category + Fuel Detail**  
Two separate columns, each with its own allowed-value list.

- Pro: Cleaner for querying. Each field is simple categorical.
- Con: Significant schema change across many trackers. Doubles the fuel-related columns.

**Option C — Use only the 11 top-level categories in spreadsheets**  
Simplify to the reference set categories; move fuel detail to a separate notes/detail column if needed.

- Pro: Simple, consistent.
- Con: Loses useful granularity (natural gas vs. LNG vs. biogas are meaningfully different).

---

### Decision 4: Governance — who can add values to a reference set?

Currently there's no formal process. Values get added to spreadsheets when PMs need them, and the canonical DB list drifts away from what trackers actually contain. This is the root cause of most out-of-set flags.

**Options:**
- **PM self-service with audit** — PMs can use any value; the audit tool flags non-canonical values for periodic review.
- **Approval workflow** — new values require sign-off before use; the DB lookup table is the gating mechanism.
- **Versioned reference sets** — allowed values are frozen per data release; changes go through a changelog process.

The approval workflow is most consistent with a DB-driven architecture. The PM self-service approach is closest to current practice.

---

### Decision 5: How to handle "unknown" within categorical fields

Several categorical fields include `unknown` as a permitted value: Coal type, Combustion technology, Mining Method, Plant type (Cement), etc. This is the same problem raised in STD-01 (null encoding) — `unknown` means "we researched but couldn't determine" — but here it appears in the allowed-value list of fields that are otherwise categorical.

**Options:**
- **Allow `unknown` as an explicit allowed value** for any categorical field where the answer may be undeterminable. Document it in the field's metadata.
- **Use empty cell for `unknown`** and reserve the allowed-value list for known valid values only.
- **Require a specific null token** (e.g., `not determined`) distinct from `unknown` to avoid conflation with the STD-01 decision.

This decision should be made consistently with whatever is decided in STD-01.

---

## False Positives in the Audit

Several out-of-set flags are artifacts rather than real data issues:

- **`proposed` vs `announced`** in GGIT/pipeline trackers — these may be intentionally different lifecycle stages for pipeline vs. power-plant projects, not errors
- **`Financing ` (with trailing space)** in Coal Finance — a data entry issue, not a vocabulary issue; normalizable with trimming
- **`True`/`False` in boolean-adjacent categorical fields** — overlap with STD-03 (Boolean Encoding)
- **`N/A`** appearing as a value in categorical fields — overlap with STD-01 (Null Encoding)
- **`#N/A`** in Conversion to (fuel) — Excel error propagation, not a data entry issue

---

## Related Standards

- **STD-01: Null / Missing Value Encoding** — `unknown`, `N/A` as values in categorical fields
- **STD-02: Multi-value Separators** — `Thermal & Met`, compound fuel notation
- **STD-03: Boolean Encoding** — Captive, boolean-adjacent categoricals
- **STD-06: Date / Year Format** — Status Detail field contains free-text with dates


---

**Standardization docs:** [Index](index.md) · [STD-01](std-01-null-encoding.md) · [STD-02](std-02-multi-value-separators.md) · [STD-03](std-03-boolean-encoding.md) · [STD-04](std-04-categorical-allowed-values.md) · [STD-05](std-05-numeric-field-purity.md) · [STD-06](std-06-date-year-format.md) · [STD-07](std-07-required-fields-nullability.md) · [STD-08](std-08-field-naming-conventions.md) · [STD-09](std-09-cross-field-links.md) · [STD-10](std-10-imputed-values.md) · [STD-11](std-11-data-provenance-source-fields.md) · [STD-12](std-12-geographic-hierarchy.md) · [STD-13](std-13-temporal-snapshots.md)
