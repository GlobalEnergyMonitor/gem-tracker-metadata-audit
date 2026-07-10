# STD-03: Boolean Encoding

**Status:** Draft — for discussion with Data Team  
**Scope:** All tracker spreadsheets and the research database export pipeline

---

## Current State

Boolean fields (yes/no, true/false, present/absent) are encoded three different ways across trackers, plus a systematic "third value" problem that applies to most of them.

### Encoding patterns in use

**Pattern A — `yes` / `no` (lowercase)**  
The most common pattern and the one produced by the research database export pipeline.

| Field | Tracker | Values seen |
|---|---|---|
| CCS | Coal Plant | `yes`, `no`, `not found` |
| CHP | Coal Plant, Gas, GOGPT, GIPT | `yes`, `no`, `not found` |
| CCS attachment? | Gas / GOGPT | `yes`, `no`, `not found` |
| IRP | Gas | `yes`, `no` |
| CCS/CCUS | Cement | `yes`, `no`, `unknown`, `n/a` |
| Alternative Fuel | Cement | `yes`, `no`, `unknown`, `n/a` |
| Green Hydrogen Producing | Geothermal | `yes`, `no`, `not found` |
| Binational | Hydro | `Yes`, `No` *(title case variant)* |

**Pattern B — `True` / `False` (title case)**  
Used in GGIT LNG terminals and Solar/Wind trackers. These likely originate from Python boolean serialization or a different internal system.

| Field | Tracker | Values seen |
|---|---|---|
| Offshore, Floating, LH2, NH3, CCS | GGIT LNG | `True` *(false rows absent — see below)* |
| Hydrogen, Associated Storage | Solar, Wind | `True` *(same pattern)* |
| PubliclyListed | Ownership | `True`, `False` |
| Offshore, Floating | Portal Energetico (LNG tab) | `TRUE` *(all-caps, Excel export artifact)* |

**Pattern C — `Y` / `N` (single letter)**  
Used in Coal Mine Tracker methane metadata fields and Nuclear Tracker.

| Field | Tracker | Values seen |
|---|---|---|
| Has mine boundary data | Coal Mine | `Y`, `N` |
| Has associated plume data | Coal Mine | `Y`, `N` |
| Has associated CMM mitigation data | Coal Mine | `Y`, `N` |
| Planned Retirement | Nuclear | `Y`, `N` |
| For internal use — is Chinese coal mine | GMET | `y`, `n` *(lowercase)* |

### The DB layer

In the normalized `snapshot.*` tables, boolean fields are stored as proper database booleans (`True` / `False` / `None`). The export pipeline converts these to lowercase `yes` / `no` for spreadsheet delivery — which is the source of Pattern A. Patterns B and C come from trackers built outside or before the current DB pipeline.

---

## The "Third Value" Problem

Most boolean fields in the DB pipeline carry a third value alongside `yes` and `no`:

- `not found` — the researcher looked but couldn't determine whether the feature is present
- `unknown` — semantically similar; used in Cement tracker
- `n/a` — used in Cement to mean "doesn't apply to this plant type"

This is the boolean manifestation of the same semantic problem raised in STD-01 (null encoding): the distinction between "we don't know" and "this doesn't apply." For boolean fields it's especially visible because `yes` / `no` / `not found` becomes a three-value categorical rather than a true boolean.

The Cement tracker goes furthest, with four values: `yes`, `no`, `unknown`, `n/a` — explicitly encoding both the "don't know" and "doesn't apply" cases.

### The absent-false pattern

Several GGIT and Solar/Wind fields only store `True` — a `False` value appears to be represented by an empty cell rather than the word `False`. This is a semi-sparse encoding: "if the field is present, the answer is yes; if absent, no." It works in practice but is ambiguous — an empty cell could also mean "we haven't checked this field for this record."

---

## Decision Points

### Decision 1: Which encoding is the standard?

**Option A — `yes` / `no` (lowercase)**  
Already the DB export standard. Human-readable, case-insensitive matching is straightforward.

- Pro: Consistent with current DB pipeline output. Most trackers already use it.
- Con: `Yes` / `No` title case variants exist (Binational, Hydro tracker) — minor inconsistency requiring case normalization.

**Option B — `True` / `False` (title case)**  
Consistent with JSON/Python serialization; directly usable in typed systems without mapping.

- Pro: Unambiguous in typed systems. Easier to coerce to a native boolean in ETL.
- Con: Requires changing the DB export pipeline and all trackers currently using `yes`/`no`. `TRUE` all-caps (Excel artifact) would still need normalization.

**Option C — `1` / `0` (integer)**  
Standard in many database systems; compact.

- Pro: Unambiguous, compact, numeric.
- Con: Not human-readable in spreadsheets. Requires extra documentation for PM workflow.

**Recommendation for discussion:** Standardize on **`yes` / `no` (lowercase)** for spreadsheet-facing fields, since that's what the DB already produces and what most trackers use. ETL to the unified DB converts to native boolean. Case normalization (`Yes` → `yes`) should be handled automatically.

---

### Decision 2: How to handle "we haven't checked" vs. "doesn't apply"

This decision mirrors STD-01 but is specific to boolean fields. Four options, each with a different surface representation:

**Option A — `not found` as a third allowed value**  
Current practice for DB-backed trackers. Formally recognize `not found` as a valid value for boolean fields where the researcher actively checked but couldn't confirm.

- Pro: Already in use. Explicit signal for research completeness tracking.
- Con: Makes the field a 3-value categorical, not a boolean. Tools that expect boolean inputs need special handling.
- Con: Conflates two cases: "not found" could mean "we looked at sources and found no evidence" OR "we haven't searched for this yet."

**Option B — Empty cell for both "don't know" and "doesn't apply"**  
True/false are the only non-null values; absence is absence. Simpler.

- Pro: Clean boolean. Standard tooling works without special cases.
- Con: Loses the research-completeness signal. Can't distinguish checked-and-negative-evidence from not-yet-checked.

**Option C — Separate `_confidence` or `_checked` companion field**  
Boolean field stores only `yes` / `no` / empty; a companion field records whether the field has been actively researched.

- Pro: Data stays clean. Research tracking is explicit and queryable.
- Con: Doubles the field count. Adds data entry burden.

**Option D — `n/a` for "doesn't apply" + `not found` for "researched, unclear"**  
Four-value set: `yes`, `no`, `not found`, `n/a`. Cement already does this.

- Pro: Most expressive. Distinguishes all four states.
- Con: Four values is complex for what users expect to be a yes/no field. Risk of inconsistent use by different researchers.

---

### Decision 3: The absent-false pattern in GGIT and Solar/Wind

Fields like `Offshore`, `Floating`, `Hydrogen`, `Associated Storage` in GGIT and renewable trackers only store `True` — the negative case is an empty cell. This is likely because the population of `True` records is small and sparse encoding saves effort.

**Options:**
- **Require explicit `no` for all boolean fields** — every record must have a value. More work at data entry; cleaner for queries.
- **Allow sparse encoding with documentation** — document that empty means `no` for specific fields, enforced by the field's metadata.
- **Convert at ETL time** — accept sparse encoding in spreadsheets, fill in `no` / `False` during ETL based on field-level metadata that marks the field as sparse-boolean.

---

### Decision 4: Case normalization

Even within `yes`/`no`, the data shows `Yes`/`No` (Hydro Binational), and `TRUE`/`FALSE` (Portal Energetico LNG, from Excel). These are minor but should be resolved:

- All `yes`/`no` variants (`Yes`, `YES`, `y`, `Y`) should normalize to lowercase `yes`/`no` at ETL time regardless of what appears in the spreadsheet.
- This should be documented so PMs know case doesn't matter at data entry.

---

## Fields Requiring Separate Discussion

**Captive (Coal Plant, Gas):** Despite the field name sounding boolean ("is this plant captive-use?"), the data stores the industry type (`aluminum`, `chemicals`, `iron & steel`) rather than `yes`/`no`. This is actually a categorical field masquerading as boolean — it belongs in the categorical allowed values discussion (STD-04) rather than here.

**% HBI / % other iron (Iron & Steel):** Flagged as boolean because `0` and `1` appear, but these are actually percentage fields where 0% and 100% are common values. False positives from the boolean detector.

---

## Related Standards

- **STD-01: Null / Missing Value Encoding** — the "not found" / "doesn't apply" distinction applies here too
- **STD-04: Categorical Allowed Values** — Captive and similar fields that appear boolean but are actually categorical
- **STD-10: Imputed Values** — some boolean fields may have values that were inferred rather than researched


---

**Standardization docs:** [Index](index.md) · [STD-01](std-01-null-encoding.md) · [STD-02](std-02-multi-value-separators.md) · [STD-03](std-03-boolean-encoding.md) · [STD-04](std-04-categorical-allowed-values.md) · [STD-05](std-05-numeric-field-purity.md) · [STD-06](std-06-date-year-format.md) · [STD-07](std-07-required-fields-nullability.md) · [STD-08](std-08-field-naming-conventions.md) · [STD-09](std-09-cross-field-links.md) · [STD-10](std-10-imputed-values.md) · [STD-11](std-11-data-provenance-source-fields.md) · [STD-12](std-12-geographic-hierarchy.md) · [STD-13](std-13-temporal-snapshots.md)
