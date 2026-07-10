# STD-02: Multi-value Separators

**Status:** Draft — for discussion with Data Team  
**Scope:** All tracker spreadsheets and the research database export pipeline

---

## Current State

Several fields across trackers encode multiple values in a single cell. Three different separator characters are in use:

### `;` — semicolon (DB-backed trackers, Owner/Operator fields)

The research database export pipeline uses `;` as the multi-value separator for fields that can have multiple entries. This is clearest in Owner and Operator fields:

```
NTPC Ltd [49%]; Rajasthan Rajya Vidyut Utpadan Nigam Ltd [51%]
China Gezhouba Group Co Ltd [15%]; Government of Malawi [85%]
Gadani Power Park Management Co Ltd; ANC Holdings LLC
```

Also used in Other Name(s), Parent Company, and vessel/operator fields across Nuclear, Portal Energetico, and GGIT trackers.

### `,` — comma (widespread, often wrong)

Comma is the most commonly flagged separator across tracker spreadsheets, appearing in fields that clearly contain multiple distinct values:

| Field | Tracker | Example value |
|---|---|---|
| Alternate Fuel | Coal Plant, Coal Finance, GOGPT | `fossil liquids, fossil gas` |
| Fuel | Gas / GOGPT / Portal Energetico | `fossil gas: natural gas, fossil liquids: fuel oil` |
| Terminal Type | Coal Terminals | `Exports, Imports` |
| Coal Grade | Coal Mine | `Thermal, Met` *(but see below — this field uses `&`)* |
| Category steel product | Iron & Steel | `semi-finished, finished rolled` |
| Countries | Portal Energetico | `Colombia, Brazil, Argentina` |

Comma is also problematic because it conflicts with CSV export format — a cell containing `fossil gas, fossil liquids` breaks naive CSV parsers.

### `&` — ampersand (vocabulary, not a separator)

`&` appears widely but almost exclusively as part of a value's name rather than as a delimiter between values:

- `iron & steel`, `oil & refining`, `other metals & mining`, `cement & building` — industry type vocabulary
- `Thermal & Met`, `Underground & Surface` — coal grade and mine type vocabulary  
- `Florida Power & Light Co`, `Babcock & Wilcox`, `Pulp & Paper` — company names
- `Central & South America`, `Middle East & North Africa` — region names

The audit tool's reference-aware check correctly identifies these as vocabulary. **`&` is not used as a multi-value separator in any DB-backed export.**

### The compound fuel notation

The Fuel field in Gas, GOGPT, and Portal Energetico uses a compound structure:

```
fossil gas: natural gas, fossil liquids: fuel oil
fossil gas: natural gas, fossil liquids: diesel
fossil gas: natural gas, fossil gas: unknown
```

Here `,` separates fuel entries, and `:` separates the fuel category from the fuel detail within each entry. This is a two-level structure that a simple separator standard doesn't fully address.

---

## False Positives

Several `wrong_multi_value_separator` flags in the audit are genuine false positives:

- **Share Imputed?** (Ownership Tracker): values like `known value, not imputed` are single multi-word labels, not two values separated by a comma.
- **Region** (Iron & Steel, Iron Ore): `Central & South America` is a single region name.
- **Portal Energetico about/metadata tabs**: flagged because the tab contains free-text descriptions with commas, not data cells.
- **WKT geometry fields**: polygon coordinate strings contain commas as part of the geometry format.

---

## Decision Points

### Decision 1: What is the standard separator?

**Option A — Semicolon (`;`) as the org standard**  
Consistent with the DB export pipeline, which already uses `;` for Owner/Operator and other multi-value fields. Would require migrating comma-separated fields (Alternate Fuel, Fuel, Terminal Type, etc.) to `;`.

- Pro: Aligns with what the DB already produces. Doesn't conflict with CSV export.
- Pro: `;` is the separator standard used by Table Schema (via CSVW's `separator` property) and most structured data tooling.
- Con: Requires changes to spreadsheet data and data entry conventions for fields currently using `,`.

**Option B — Retain comma (`,`) for fields outside the DB pipeline**  
Accept `,` as the separator for spreadsheets not generated from the research DB, and clean to `;` only at ETL time when loading into the unified DB.

- Pro: No PM workflow changes required now.
- Con: Perpetuates inconsistency. Complicates ETL (need to distinguish `,` as separator vs. `,` in a value name). Breaks CSV export.
- Con: Fields like `fossil gas: natural gas, fossil liquids: fuel oil` are genuinely ambiguous when comma-delimited — is the comma separating fuels or could it be part of a longer value?

**Option C — Define allowed separators per field in metadata**  
Rather than a single org-wide standard, specify the separator in each field's metadata (`multiple_values_separator` property already exists in the schema). Allow `;` and `,` but require it to be documented.

- Pro: Flexible. Preserves current conventions for fields where `,` is well-established.
- Con: Makes cross-tracker comparisons harder. No single rule for tooling to apply. Still doesn't solve the CSV conflict.

---

### Decision 2: Should `&` be formally prohibited as a separator?

`&` doesn't currently function as a separator in any DB-backed export. However, it appears in value names frequently enough that it could never reliably serve as a separator without reference-aware parsing.

**Recommendation:** Explicitly document that `&` is reserved for vocabulary (value names, company names, region names) and must not be used as a multi-value separator. This makes the audit check unambiguous.

---

### Decision 3: How to handle the compound fuel notation

The `fossil gas: natural gas, fossil liquids: fuel oil` pattern represents a structured sub-vocabulary (fuel_category: fuel_detail) that predates any separator standard. If the org moves to `;` as the separator, this becomes:

```
fossil gas: natural gas; fossil liquids: fuel oil
```

which is unambiguous. But the `:` internal delimiter then needs its own documentation and the fuel field becomes a structured type, not just categorical.

**Options:**
- **Keep the colon notation, switch outer separator to `;`** — minimal change, retains the human-readable compound format.
- **Normalize to separate fields** — `Fuel Category` + `Fuel Detail` as distinct columns. Cleaner for DB storage but a significant schema change for fuel fields across many trackers.
- **Document the compound structure as a known exception** — formally specify the `fuel_category: detail` format as a structured sub-type with `;` as the outer separator.

---

### Decision 4: Which fields are actually multi-value?

The current audit flags any field where a separator character appears, but not all such fields are intended to hold multiple values. Formally identifying which fields are multi-value (and which separator they use) in the field-level metadata is a prerequisite for enforcement.

Fields where multi-value is clearly intentional (current data shows it):
- Owner, Operator, Parent Company — `;` in DB; may be `,` elsewhere
- Alternate Fuel — `,` currently; should be `;`
- Fuel (compound) — `,` currently; should be `;` with `:` internal delimiter
- Other Name(s), Mine Name AKAs — `;` in most trackers
- Coal Grade — `&` in vocabulary only; `Thermal & Met` is a single value, not two

Fields where multi-value may be unintentional or should be restructured:
- Countries (Portal Energetico pipeline) — currently comma-separated; may warrant one row per country
- Other IDs (location) — currently comma-separated list of `System: ID` pairs; compound structured field

---

## Recommended Starting Point for Discussion

The DB pipeline already enforces `;` for Owner/Operator fields. The most tractable near-term step is:

1. **Adopt `;` as the org standard** for all multi-value fields.
2. **Update the `multiple_values_separator` metadata property** for fields that are explicitly multi-value; fields without this property should be single-value and flagged if a separator is detected.
3. **Migrate Alternate Fuel and Terminal Type** — the clearest cases of wrong-separator usage with simple fixes.
4. **Defer the compound fuel notation** to a separate discussion, as it involves field structure, not just separator choice.

---

## Related Standards

- **STD-04: Categorical Allowed Values** — reference sets that enable reference-aware separator detection
- **STD-08: Field Naming Conventions** — how compound fields (fuel category + fuel detail) should be named if split
- **STD-11: Data Provenance / Source Fields** — source fields that use `;` to separate multiple citations


---

**Standardization docs:** [Index](index.md) · [STD-01](std-01-null-encoding.md) · [STD-02](std-02-multi-value-separators.md) · [STD-03](std-03-boolean-encoding.md) · [STD-04](std-04-categorical-allowed-values.md) · [STD-05](std-05-numeric-field-purity.md) · [STD-06](std-06-date-year-format.md) · [STD-07](std-07-required-fields-nullability.md) · [STD-08](std-08-field-naming-conventions.md) · [STD-09](std-09-cross-field-links.md) · [STD-10](std-10-imputed-values.md) · [STD-11](std-11-data-provenance-source-fields.md) · [STD-12](std-12-geographic-hierarchy.md) · [STD-13](std-13-temporal-snapshots.md)
