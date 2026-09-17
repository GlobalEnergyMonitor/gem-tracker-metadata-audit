---
layout: default
title: "Decision Log"
---

# Decision Log

Standardization decisions, ordered STD-01 → STD-13. Item titles and pattern/decision-point wording are pulled from the [GEM Tracker Metadata Audit](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/). Items with no recorded proposal are left blank.

## Standardization decisions

| ID | Item | Decision | Detail / rationale | Status |
|---|---|---|---|---|
| STD-01 | [Null / Missing Value Encoding](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-01-null-encoding.html) | Categorical: `not found`. Numeric: keep the numeric column pure and add a companion column for confidence, reason, or detail. | Companion vocabulary should cover null, not found, not applicable, and not available. | Proposed |
| STD-02 | [Multi-value Separators](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-02-multi-value-separators.html) | Use `;`. | | Proposed |
| STD-03 | [Boolean Encoding](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-03-boolean-encoding.html) | Use `True` / `False`. | | Proposed |
| STD-04 | [Categorical Allowed Values](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-04-categorical-allowed-values.html) | Stand up a QC script for all trackers outside the database that runs on categorical columns of the working data and flags new values against the last release. | Runs during research or prior to release, so it doubles as the tracker's own QC and makes clear whether a new value is expected. Preserves tracker autonomy.<br><br>Possible extension: an approval-request system that folds into database trackers — a new value (today a database request) is added to the canon via a PM form fill on the database, which fast-tracks adding that field to the DB trackers and becomes the up-to-date set the QC script checks against. | Open — extension not settled |
| STD-05 | [Numeric Field Purity](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-05-numeric-field-purity.html) | Clean up the data to remove `#N/A` and coordinate pairs. Allow a standardized placeholder for blanks outside the database, transformed to blank in ETL for reports. No ranges — pick a single value. | | Proposed |
| STD-06 | [Date / Year Format](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-06-date-year-format.html) | Three separate columns in ISO format `YYYY-MM-DD`. | Fiscal year (GCMT): use a start-year `YYYY` column only, with an associated column indicating that it is a fiscal year for a given country. | Proposed |
| STD-07 | [Required Fields / Nullability](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-07-required-fields-nullability.html) | | | |
| STD-08 | [Field Naming Conventions](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-08-field-naming-conventions.html) | Lowercase unless a proper noun or a header column, which take title case. No question marks in column headers. | **Option B accepted for geographic fields:** move explainer parentheses text out of geographic fields and into the documentation, which shortens many header columns.<br><br>**Units of measurement:** two separate columns, for easier formula conversion and analysis.<br><br>Still to resolve — how parentheses are used for: language variant for names; geographic explainer; plurality hints. | Proposed — parenthetical uses open |
| STD-09 | [Cross-field Links](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-09-cross-field-links.html) | | | |
| STD-10 | [Imputed Values](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-10-imputed-values.html) | See the pattern and decision-point tables below. | | Mixed |
| STD-11 | [Data Provenance / Source Fields](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-11-data-provenance-source-fields.html) | | |  |
| STD-12 | [Geographic Hierarchy](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-12-geographic-hierarchy.html) | | No decision recorded in notes. | Not yet reviewed |
| STD-13 | [Temporal Snapshots / "As Of" Dating](https://globalenergymonitor.github.io/gem-tracker-metadata-audit/docs/std-13-temporal-snapshots.html) | | No decision recorded in notes. | Not yet reviewed |

## STD-10 — patterns

| # | Pattern | Decision | Detail / rationale | Status |
|---|---|---|---|---|
| 1 | `>0` — Bounded Assertions in Capacity Fields | Use the `not found` companion column established in STD-01 instead of `>0`, and keep the numeric column blank. Note `not applicable` in the companion column. | Open: when to use blank vs. `0` in the numeric column, and what description to use for historic production that isn't known. | Open |
| 2 | Rule-based Status Inference | Address in interoperability; skip here. | | Deferred |
| 3 | Projected vs. Confirmed Years | `startYearLow` is not used. Add a checkbox for planned retirement and planned start year. | Handle how this is communicated to users in the interoperability statuses topic, so that delays, plans, and actual milestones are consistent across GEM. | Proposed |
| 4 | Calculated Ownership Shares | No change — handled well. | | Closed |
| 5 | Country-level Capacity Factor Assignment | Treat capacity factor like production data: pair it with a year, alongside generation data and capacity for that same year. | A single capacity factor value is never true — it is only true for a given year, and it has to come from somewhere, so it needs a source and a date. Bring the pieces together at publication, the same way a currency conversion factor is handled.<br><br>Structure: numeric column plus adjacent explainer columns (data source with country values, year). Potentially dozens of sources. | Proposed |
| 6 | `unknown` as a Sentinel in Fraction/Percentage Fields | Unknown → blank in the numeric column; the descriptive adjacent column carries the reason. | Open: whether `not researched` is the correct term, and whether it should be supported if other programs aren't using it. Note that if any values aren't researched, a percentage can't be calculated. | Open |
| 7 | `fuelConversionUnknown` Boolean | No action — unlikely to be an issue at only 10 cases. | | Closed |

## STD-10 — decision points

| # | Question | Decision | Detail / rationale |
|---|---|---|---|
| 1 | Should `>0` be formalized as an allowed qualifier in numeric fields? | Option B, modified. | Not a companion boolean flag — an adjacent column description, as in STD-05. |
| 2 | Should inferred statuses be distinguishable at the query layer? | Handle with status interoperability. | |
| 3 | Should `startYearPlanned` be exported as a column in spreadsheets? | Handled by status timeline. | |
| 4 | Is there a standard pattern for imputation companion flags? | Standard is a second categorical field named `{field}_reason`, with a small set of options. | Keeping it a separate categorical field lets the option set vary by field, rather than splitting the rule between numeric booleans and categorical allowed values. |
| 5 | How should national-average assignments be communicated? | Option B. | One column for the number, then a companion field for descriptions and sources — not categorical. |

## Open items

- **STD-04** — whether to build the PM-form approval-request system that feeds the canon and the QC script.
- **STD-07, STD-09** — flagged quick / lower priority; no proposal recorded yet.
- **STD-08** — how parentheses should be used for language variants, geographic explainers, and plurality hints.
- **STD-10 / Pattern 1** — blank vs. `0` in numeric columns where one might be useful over another even when it isn't known exactly'; wording for unknown historic production.
- **STD-10 / Pattern 6** — whether `not researched` is the right term, and whether to support it if other programs don't.
- **STD-12, STD-13** — not yet reviewed.

