---
layout: default
title: "Decision Log"
---

# Decision Log

Standardization decisions, ordered STD-01 → STD-13. All 13 items reviewed and finalized as of 2026-09-30. Item names link to the original background page for that item (unchanged); each decision links out to [Decision Discussion & Notes](decision-discussion.md) for the reasoning, source meeting excerpts, and — for STD-10 — the pattern-by-pattern breakdown.

## Standardization decisions

| ID | Item | Decision | Status |
|---|---|---|---|
| STD-01 | [Null / Missing Value Encoding](std-01-null-encoding.md) | Keep the numeric column pure; have a companion reason column where needed. Allow `not found`, `not applicable`, `null`, `not available`. [Discussion →](decision-discussion.md#std-01) | Final |
| STD-02 | [Multi-value Separators](std-02-multi-value-separators.md) | Use semicolon (`;`) for the separator; allow `&` in categorical options (not as a separator). [Discussion →](decision-discussion.md#std-02) | Final |
| STD-03 | [Boolean Encoding](std-03-boolean-encoding.md) | No true booleans — standardize on a categorical field with a standardized value set, e.g. `true`, `false`, `unknown`, `not found` (the set can grow as needed). `not found` entries are excluded from public/published exports (internal bookkeeping only). [Discussion →](decision-discussion.md#std-03) | Final — 1 open item |
| STD-04 | [Categorical Allowed Values](std-04-categorical-allowed-values.md) | Create an allowed list of values for each categorical field, for each tracker; enforce it with dropdowns (DB-backed trackers) and QC scripts (spreadsheets outside the database). [Discussion →](decision-discussion.md#std-04) | Final — 1 open item |
| STD-05 | [Numeric Field Purity](std-05-numeric-field-purity.md) | Clean up data to remove `#N/A` and coordinate pairs. Decide on a standardized placeholder for blanks outside the database, transformed to blank in ETL for reports. No ranges — pick a single value. Asterisk token moves to a companion boolean flag; numeric column stays pure/blank. [Discussion →](decision-discussion.md#std-05) | Final |
| STD-06 | [Date / Year Format](std-06-date-year-format.md) | Three separate columns in ISO format `YYYY-MM-DD`. Fiscal year (e.g. GCMT): a single start-year `YYYY` column, plus an associated companion column indicating fiscal-year status for that country, e.g. `Start Year | Fiscal_{ISO country code}` if fiscal year for start year. [Discussion →](decision-discussion.md#std-06) | Final |
| STD-07 | [Required Fields / Nullability](std-07-required-fields-nullability.md) | Universal minimum publish bar: ID, name, country, status, geometry must be populated before a record is published — will help with de-duplication and QC efforts. Individual tracker teams may layer stricter rules on top. [Discussion →](decision-discussion.md#std-07) | Final — 1 open item |
| STD-08 | [Field Naming Conventions](std-08-field-naming-conventions.md) | Keep units in the header name (parentheses). Move geographic explainer text, plurality hints, and conversion-field wording out of headers into documentation/metadata. Lowercase data values (except proper nouns); Title Case headers; no question marks in headers. Companion fields: `{Field} \| {Companion Information}`, e.g. `Start Year \| Ref`, `Route \| Accuracy`. Code-friendly names: `snake_case` over `camelCase` (open to revisiting). [Discussion →](decision-discussion.md#std-08) | Final — 1 open item |
| STD-09 | [Cross-field Links](std-09-cross-field-links.md) | Companion fields all use the pipe pattern: `{Field} \| Accuracy`, `{Field} \| Year`, `{Field} \| Ref`. Coordinates publish as `Lat_Lon`, companion `Lat_Lon \| Accuracy`. Standardize approximation/accuracy words where the concept is the same across trackers; leave domain-specific scales as-is. New standard direction for historical series: long-format in a separate tab. [Discussion →](decision-discussion.md#std-09) | Final |
| STD-10 | [Imputed Values](std-10-imputed-values.md) | Use the companion column pattern (`{Field} \| {Reason}`) for standardized descriptive info; keep numeric fields pure. Use the status timeline for planned statuses. Use companion fields for national-average assignments. Unknown → blank in the numeric field, reason in the companion field. [Discussion & pattern detail →](decision-discussion.md#std-10) | Final — several open items |
| STD-11 | [Data Provenance / Source Fields](std-11-data-provenance-source-fields.md) | Never publish researcher name publicly; standardize `Last Updated` / `Research Status` to match the database. Field-level provenance via `{Field} \| Ref`. Support both record- and field-level provenance. Source content is a plain URL, with a **Short name** label when it points to a general resource. Apply the database pattern, including its Record of full update values, to spreadsheet-only trackers too. [Discussion →](decision-discussion.md#std-11) | Final |
| STD-12 | [Geographic Hierarchy](std-12-geographic-hierarchy.md) | Replace `Location` with `Address`; `City` with `Nearest City`. Remove parentheses from `Subnational Unit` (move to metadata); keep them for now on Secondary/Tertiary fields. `Country/Area` for the top level. Regions/subregions are DB-established; IEA regions also offered. Standardize pipeline Start/End headers to the standard location-field list. [Discussion →](decision-discussion.md#std-12) | Final — 2 open items |
| STD-13 | ["As Of" Dating](std-13-temporal-snapshots.md) | Put the tracker's release date in metadata, not a per-row column. All annual series and date columns align with the companion field pattern. `Last Updated` is the researcher's access date, not the reference/document date. [Discussion →](decision-discussion.md#std-13) | Final |

## Open items

- STD-03 — Maisie to audit how current report-generation code handles `not found` entries before they're excluded from exports. (Maisie)
- STD-04 — build an interface mechanism for a PM to request a new allowed value option. (unassigned, but should involve engineer & programs)
- STD-07 — talk further with teams about their own publication rules on top of the universal floor. (unassigned, but should involve programs)
- STD-08 — settle the header naming pattern for language-variant fields (e.g. `Plant name (English)` / `Plant name (other language)`) without parentheses. (unassigned, but should involve programs)
- STD-10 — move inferred statuses and planned statuses discussion to interoperability; decide blank vs. `0` for numeric columns; decide wording for historic production that's known-nonzero but unquantified; sort out with GIST how to handle feedstock percentages when one part isn't researched; check whether `not researched` is used by teams beyond Heavy Industry. (unassigned, but should involve programs)
- STD-12 — LLM-assisted audit of secondary/tertiary administrative division data; confirm `Location` data actually holds addresses before the `Address` rename goes live. (unassigned)

### Deferred to Interoperability

All of these are STD-10 items that were explicitly pulled out of this standard and pushed to the [IOP-03: Status](iop-03-status.md) interoperability topic — not decided here.

- **STD-10 / Pattern 2 — Rule-based status inference** (e.g. auto-marking a unit "shelved" after 2 years with no update). Struck from imputation entirely; belongs to the statuses topic.
- **STD-10 / Pattern 3 — Planned vs. actual retirement/start-year milestones.** How delays, plans, and confirmed milestones get communicated to users needs to stay consistent across GEM — handled by the status timeline, not this standard.
- **STD-10 / Decision point 2 — Inferred statuses at the query layer.** Whether an inferred status should be distinguishable from a researcher-confirmed one in queries — status interoperability topic.
- **STD-10 / Decision point 3 — `startYearPlanned` as an export column.** Whether to export it to spreadsheets — handled by the status timeline (statuses topic), not exported as its own field here.
