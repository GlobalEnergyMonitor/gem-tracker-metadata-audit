# STD-01: Null / Missing Value Encoding

**Status:** Draft — for discussion with Data Team  
**Scope:** All tracker spreadsheets and the research database export pipeline

---

## Current State

Missing values are represented inconsistently across trackers and across layers of the data stack.

### In the research database (normalized layer)

The `snapshot.*` tables use SQL NULL cleanly for missing numeric and foreign-key fields: capacity, latitude, longitude, status, and most optional fields are NULL where data is absent. This is the right behavior at the storage layer.

### In the database export (reports layer)

The `reports.*` tables — which generate the spreadsheet exports — introduce a mixed picture:

| Token | Fields where it appears | Apparent meaning |
|---|---|---|
| `unknown` | Combustion technology (2,400 rows), Coal type (6,886 rows), Parent, Captive | "We researched this but couldn't determine the answer" |
| empty string | Retired year, Planned retirement, most optional text fields | "This field doesn't apply to this record" |
| `--` | Unit name (630 rows), pipeline capacity fields | Unclear — appears to enter through import workflows rather than intentional DB encoding |
| SQL NULL | Location, Local area, a handful of others | Inconsistently present in the reports layer |

### In spreadsheets (outside the DB pipeline)

Trackers not driven by the research DB (Coal Finance, Chemicals, Iron Ore, Cement, Coal Terminals, Portal Energetico) have no shared convention:

| Token | Trackers | Count |
|---|---|---|
| `--` | GGIT Gas Pipelines, GOIT Oil Pipelines, Nuclear, Ownership | 118,000+ cells |
| `N/A` | Coal Finance, Iron & Steel | 9,400+ cells |
| `Unknown` / `unknown` | Cement, Ownership, Iron & Steel, others | scattered |
| `Not available` | Gas Finance | isolated |
| `not found` | Ownership (external IDs) | isolated |

### Field-specific workarounds

The research DB has at least one ad-hoc solution to the "unknown vs N/A" problem: a `fuelConversionUnknown` boolean column that explicitly flags when a fuel conversion value is unknown rather than absent. This is a sign that the distinction matters to researchers but hasn't been solved at the system level.

---

## The Core Distinction

Two semantically different situations currently map to the same empty-or-proxy representation:

1. **Doesn't apply** — the field is irrelevant for this record. A retired plant has no planned retirement year. A pipeline with no capacity data collected doesn't have a capacity value.

2. **Don't know** — the field applies but the value couldn't be found. A plant almost certainly has a construction technology; the researcher simply didn't find documentation for it.

These are meaningfully different for data users:
- A "doesn't apply" null is correct and final; it should not trigger a data quality flag.
- A "don't know" null signals a research gap that could in principle be filled; it's worth tracking for completeness metrics.

The current informal convention in the DB export layer — empty string for "doesn't apply," `unknown` for "don't know" — captures this distinction, but it's undocumented, unenforced, and not applied consistently across all trackers.

---

## Decision Points

### Decision 1: Should "doesn't apply" and "don't know" be formally distinguished?

**Option A — Single convention (empty = missing, reason unspecified)**  
All missing values are represented as empty cells (SQL NULL in the DB, empty string in exports). The distinction between "doesn't apply" and "don't know" is left implicit or documented in field-level metadata.

- Pro: Simple. No new columns or tokens. Works with standard tools (NULL-aware queries, CSV parsers).
- Con: Loses the research-gap signal. Completeness metrics become meaningless (a field that "doesn't apply" to 80% of records looks 80% empty even if researchers have found everything they can find).

**Option B — Encode the distinction in-band (current informal practice, formalized)**  
Continue using empty string / NULL for "doesn't apply" and `unknown` (lowercase, controlled) as a categorical value for "we researched but couldn't determine."

- Pro: Already partially in use. Preserves research-gap signal. PMs already understand it for fields like Combustion technology and Coal type.
- Con: `unknown` pollutes categorical distributions and allowed-value lists. Users running `GROUP BY technology` get `unknown` as a category, which must be filtered out. Requires documenting which fields allow `unknown` as a valid value vs. which should be empty.
- Con: Doesn't generalize well to numeric fields (you can't put `unknown` in a capacity column).

**Option C — Encode the distinction out-of-band (companion field)**  
Add a `{field}_unknown` boolean or a `{field}_confidence` field for fields where the distinction matters. The DB already does this with `fuelConversionUnknown`.

- Pro: Keeps numeric fields clean. Doesn't pollute categorical distributions. Machine-readable.
- Con: Doubles the number of fields for any field where it matters. Adds data entry burden. Unclear which fields warrant a companion.

**Option D — Null reason as metadata, not data**  
Track null reasons in a separate audit/provenance table rather than in the data itself. Each null cell can have an associated reason code (not_applicable, researched_unknown, not_yet_researched, etc.).

- Pro: Data stays clean. Reason tracking is flexible and extensible.
- Con: Significant infrastructure. Not usable by PM spreadsheet workflow without tooling changes. Overkill for many fields.

---

### Decision 2: What tokens are allowed in exported spreadsheets?

Whatever convention is chosen for the DB, a separate question is what appears in the spreadsheet exports that PMs and public users see.

**Current problem:** `--` appears in 118,000+ cells in GGIT and other trackers. Its origin is unclear — it appears to enter through the export pipeline or PM editing, not through intentional DB encoding. `N/A`, `Not available`, and `not found` appear in various trackers with no shared meaning.

**Options:**
- **Empty cell only** — SQL NULL / empty string throughout. Simplest for downstream use; loses any in-band signal.
- **Controlled token list** — define a small set of allowed null tokens (e.g., `unknown` for researched-missing, empty for N/A), document them in the README/About tab, and treat any other proxy as a data quality flag.
- **Status quo** — accept token diversity in spreadsheets, clean to a standard at ETL time when loading into the DB.

---

### Decision 3: How should numeric fields handle "unknown" values?

Numeric fields (Capacity MW, production volumes, etc.) can't take `unknown` as a value. Currently they get:
- Empty string / NULL (most common)
- `--` (GGIT pipeline convention)
- Qualifiers like `>0` or ranges like `100-200` (Cement, Steel — see also STD-05: Numeric Field Purity and STD-10: Imputed Values)

The `>0` case in particular sits at the boundary between a null proxy and an imputed/qualified value — it asserts something positive about the field while withholding the exact number. Whether that belongs in the null encoding standard or the imputation standard is itself a decision.

---

## Recommended Starting Point for Discussion

The most concrete near-term question is **Decision 2** — what tokens are allowed in spreadsheet exports — because that's what affects public data users right now. Decisions 1 and 3 have larger infrastructure implications and can follow once the team agrees on the conceptual model.

A minimal viable standard for Discussion 2:
1. Empty cell = "no value" (either doesn't apply or not yet researched — distinction not encoded)
2. `unknown` = "researched, couldn't determine" — only in categorical fields that explicitly allow it; listed in that field's `allowed_values`
3. All other tokens (`--`, `N/A`, `Not available`, `not found`, etc.) are disallowed and flagged by the audit tool

This doesn't resolve the deeper distinction question (Decision 1) but stops the proliferation of ad-hoc tokens and gives the audit tool something specific to flag.

---

## Related Standards

- **STD-05: Numeric Field Purity** — what to do with qualifiers (`>0`, ranges) in numeric fields
- **STD-10: Imputed Values** — how to represent and flag values that were estimated rather than researched
- **STD-07: Required Fields / Nullability** — which fields must be non-null, and how that's enforced
