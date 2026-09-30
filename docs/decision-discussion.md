---
layout: default
title: "Decision Discussion & Notes"
---

# Decision Discussion & Notes

Backup detail behind each [decision-log](decision-log.md) entry: the reasoning, the discussion excerpts it came from, and — for STD-10 — the pattern-by-pattern breakdown the final decision was distilled from.

**Source notes (all items draw on these four group discussions):**

- Metadata discussion — 2026-08-14 (Notes by Gemini)
- Metadata pt 2 — 2026-08-20 (Notes by Gemini)
- Metadata audit continues — 2026-09-17 (Notes by Gemini)
- Metadata review — 2026-09-25 (Notes by Gemini)

---

<a id="std-01"></a>
## STD-01: Null / Missing Value Encoding

**Decision:** Keep the numeric column pure; have a companion reason column where needed. Allow `not found`, `not applicable`, `null`, `not available`.

**Discussion:** Two situations were being conflated under one empty/proxy representation — a field that doesn't apply to a record, versus one the team tried and failed to research. The group settled on `not found` rather than `unknown` specifically because it signals research was attempted and came up empty, rather than implying the field hasn't been looked at.

> "Maisie Bird and Taylor Higgins proposed that they standardize on 'not found' and 'not applicable' rather than 'unknown,' emphasizing that 'not found' implies research was completed without success, rather than implying the data has not yet been researched." — Aug 14 meeting

**Resolved against STD-05, 2026-09-24:** no placeholder token survives in a numeric column — companion column only, enforced by the QC script.

[Background page →](std-01-null-encoding.md)

---

<a id="std-02"></a>
## STD-02: Multi-value Separators

**Decision:** Use semicolon (`;`) for the separator; allow `&` in categorical options (not as a separator).

**Discussion:** Commas conflicted with CSV export and `&` already appeared legitimately inside vocabulary/value names (e.g. "Thermal & Met"), so the rule distinguishes "separator" from "character that can appear in a value."

> "Before concluding, they confirmed quick decisions regarding data formatting, agreeing to use a semicolon as a separator." — Aug 20 meeting

[Background page →](std-02-multi-value-separators.md)

---

<a id="std-03"></a>
## STD-03: Boolean Encoding

**Decision:** No true booleans — standardize on a categorical field with a standardized value set, e.g. `true`, `false`, `unknown`, `not found` (the set can grow as needed). `not found` entries are excluded from public/published exports (internal bookkeeping only).

**Discussion:** Trackers used three incompatible patterns (`yes/no`, `True/False`, `Y/N`), and most boolean-shaped fields actually carry three or four real states, which a plain boolean can't hold without ambiguity.

> "The group ultimately reached a consensus that boolean fields should be converted into standardized categorical drop-down interfaces to prevent invalid combinations like 'yes' and 'not found.'" — Sep 25 meeting
> "Maisie Bird also suggested evaluating whether 'not found' entries should be withheld from public releases as internal bookkeeping." — Sep 25 meeting

**Open:** Maisie to audit how current report-generation code handles `not found` entries before this rolls out.

[Background page →](std-03-boolean-encoding.md)

---

<a id="std-04"></a>
## STD-04: Categorical Allowed Values

**Decision:** Create an allowed list of values for each categorical field, for each tracker; enforce it with dropdowns (DB-backed trackers) and QC scripts (spreadsheets outside the database).

**Discussion:** 98 categorical fields were out-of-set against canon and 143 more had no defined reference set at all, with no consistent way to tell a legitimate new value from a data-entry error. A PM-form approval-request system that would fast-track a new value into the DB canon was discussed as a further extension but isn't committed — it's tracked as the open item below.

> "Database metadata should maintain a strict list of allowed values, enforced through regular quality control code running on Google Sheets, alongside interface-level enforcement... to add new categorical fields or values, users submit a proposal for data team sign-off." — Sep 25 meeting

**Open:** create an interface mechanism for a PM to request a new allowed value option.

[Background page →](std-04-categorical-allowed-values.md)

---

<a id="std-05"></a>
## STD-05: Numeric Field Purity

**Decision:** Clean up data to remove `#N/A` and coordinate pairs. Decide on a standardized placeholder for blanks outside the database, transformed to blank in ETL for reports. No ranges — pick a single value. Asterisk token moves to a companion boolean flag; numeric column stays pure/blank.

**Discussion:** Numeric columns carried dashes, "N/A", ">0" assertions, asterisks for restricted data, and Excel formula errors — all of which break aggregation and force columns into text type.

> "The group agrees that these markers must be removed from numeric columns to prevent interference with mathematical operations and to ensure consistent data ingestion... such signals should be moved to companion boolean fields rather than polluting the numeric columns." — Aug 14 meeting

**Resolved against STD-01, 2026-09-24:** no placeholder token survives in a numeric column — companion column only, enforced by the QC script.

[Background page →](std-05-numeric-field-purity.md)

---

<a id="std-06"></a>
## STD-06: Date / Year Format

**Decision:** Three separate columns in ISO format `YYYY-MM-DD`. Fiscal year (e.g. GCMT): a single start-year `YYYY` column, plus an associated companion column indicating fiscal-year status for that country, e.g. `Start Year | Fiscal_{ISO country code}` if fiscal year for start year.

**Discussion:** 316 date/year fields used nine different formats, mixing full timestamps, natural-language dates, Excel serial artifacts, and fiscal-year notation like `2024-25`.

> "The team decided to store dates in three separate columns (year, month, and day)... they agreed to include a categorical column where researchers can specify the fiscal system or country." — Aug 20 meeting

[Background page →](std-06-date-year-format.md)

---

<a id="std-07"></a>
## STD-07: Required Fields / Nullability

**Decision:** Universal minimum publish bar: ID, name, country, status, geometry must be populated before a record is published — will help with de-duplication and QC efforts. Individual tracker teams may layer stricter rules on top.

**Discussion:** "Required-ness" existed only implicitly in the database (Django's `blank=True`), undocumented and inconsistent across trackers.

> "Maisie Bird emphasized establishing a consistent minimum information bar... Stephen Osserman highlighted user feedback from Sylvia's audience interviews indicating that geography fields are universally loved, leading the group to officially add geometry to the list of universal required fields." — Sep 25 meeting

**Open:** talk further with teams about their own publication rules.

[Background page →](std-07-required-fields-nullability.md)

---

<a id="std-08"></a>
## STD-08: Field Naming Conventions

**Decision:** Keep units in the header name (parentheses) — no separate unit-of-measurement metadata column. Move geographic explainer text, plurality hints, and conversion-field wording out of headers into documentation/metadata; parentheses reserved primarily for units. Lowercase for data values (except proper nouns); Title Case for headers. No question marks in column headers. Companion fields use the pattern `{Field} | {Companion Information}` — applied to all companion fields, not just source references — for example: `Start Year | Ref`, `Route | Accuracy`. Code-friendly names: standardize on `snake_case` over `camelCase` — open to revisiting if others have a strong case for camelCase.

**Discussion:** Five incompatible naming conventions coexisted across trackers (Title Case with parentheses, camelCase, `[ref]` suffixes, "Data Source" suffixes, question-mark booleans).

> "Discussing database and API compatibility, Stephen Osserman and Maisie Bird favored snake case to avoid SQL uppercase quoting issues." — Sep 25 meeting
> "Maisie Bird and Taylor Higgins agreed to strip these non-essential examples from column headers and move detailed explanations into the metadata." — Sep 25 meeting
> "Taylor Higgins and Stephen Osserman agreed to apply this piping pattern to other companion fields such as field|reason and field|accuracy." — Sep 25 meeting

**Open:** language-variant field naming — e.g. `Plant name (English)` / `Plant name (other language)`. We don't want parentheses there, but haven't settled on the best header name to use instead.

[Background page →](std-08-field-naming-conventions.md)

---

<a id="std-09"></a>
## STD-09: Cross-field Links

**Decision:** Companion fields (accuracy, year, ref, etc.) all use the pipe pattern: `{Field} | Accuracy`, `{Field} | Year`, `{Field} | Ref`. Coordinates publish as `Lat_Lon`, with a companion `Lat_Lon | Accuracy`. Column headings: Title Case. Data values: lowercase unless a proper noun. Standardize approximation/accuracy words where the underlying concept is the same across trackers (e.g. location accuracy); leave domain-specific accuracy scales as-is. Wide-format historical columns (e.g. `Output 2023 | Accuracy`) are the current pattern; new standard direction is long-format in a separate tab — migrate over time.

**Discussion:** 50+ distinct accuracy-related fields exist across 34 tables with inconsistent linking and inconsistent value sets between trackers.

> "Maisie Bird proposed combining latitude and longitude into a single published column named lat|long with a corresponding lat|long|accuracy field." — Sep 25 meeting
> "Location accuracy must be uniform everywhere, whereas domain-specific fields like feedstock accuracy do not need to mirror location standards." — Sep 25 meeting

[Background page →](std-09-cross-field-links.md)

---

<a id="std-10"></a>
## STD-10: Imputed Values

**Decision:** Use the companion column pattern to hold standardized descriptive information, as established in other items: `{Field} | {Reason}`. Keep numeric fields pure. Use the new status timeline where implemented to capture planned statuses, and export it consistently regardless. Use the companion field pattern for national average assignments — for example `Capacity Factor | Source` with options "national average" and "plant-specific", and `Capacity Factor | Year`. Make sure unknown is blank in the numeric field, and use a companion field to describe why it's unknown.

**Discussion:** Seven distinct patterns of derived, estimated, or rule-based values were found across heavy-industry trackers. The pattern-by-pattern breakdown below is what this decision was distilled from.

> "Taylor Higgins noted previous agreements to keep numeric columns strictly numeric while introducing a secondary column to capture confidence, reasons, or details." — Sep 17 meeting
> "Country-level capacity factor assignments should not be stored at the individual plant or unit level... stored centrally in a separate table and applied during report generation." — Sep 17 meeting
> "Stephen Osserman proposed standardizing companion fields across trackers by using a categorical field named field_reason rather than multiple boolean flags." — Sep 17 meeting

**Open:**
- Move inferred statuses to the interoperability item.
- Establish when to use blank or 0 for numeric columns.
- Decide how to capture historic production that's not known but definitely more than zero.
- Sort out with GIST how to handle feedstock percentages when one part isn't researched.
- See if other tracker teams beyond Heavy Industry use "not researched."

### STD-10 — patterns (backup detail)

| # | Pattern | Decision | Detail / rationale | Status |
|---|---|---|---|---|
| 1 | `>0` — Bounded Assertions in Capacity Fields | Use the `not found` companion column established in STD-01 instead of `>0`, and keep the numeric column blank. Note `not applicable` in the companion column. | Open: when to use blank vs. `0` in the numeric column, and what description to use for historic production that isn't known. | Open |
| 2 | Rule-based Status Inference | Address in interoperability; skip here. | | Deferred |
| 3 | Projected vs. Confirmed Years | `startYearLow` is not used. Add a checkbox for planned retirement and planned start year. | Handle how this is communicated to users in the interoperability statuses topic, so that delays, plans, and actual milestones are consistent across GEM. | Proposed |
| 4 | Calculated Ownership Shares | No change — handled well. | | Closed |
| 5 | Country-level Capacity Factor Assignment | Treat capacity factor like production data: pair it with a year, alongside generation data and capacity for that same year. | A single capacity factor value is never true — it is only true for a given year, and it has to come from somewhere, so it needs a source and a date. Bring the pieces together at publication, the same way a currency conversion factor is handled.<br><br>Structure: numeric column plus adjacent explainer columns (`Capacity Factor \| Source`, with options "national average" / "plant-specific", and `Capacity Factor \| Year`). Potentially dozens of sources. | Proposed |
| 6 | `unknown` as a Sentinel in Fraction/Percentage Fields | Unknown → blank in the numeric column; the descriptive adjacent column carries the reason. | Open: whether `not researched` is the correct term, and whether it should be supported if other programs aren't using it — check with GIST and other Heavy Industry-adjacent teams. Note that if any values aren't researched, a percentage can't be calculated. | Open |
| 7 | `fuelConversionUnknown` Boolean | No action — unlikely to be an issue at only 10 cases. | | Closed |

### STD-10 — decision points

| # | Question | Decision | Detail / rationale |
|---|---|---|---|
| 1 | Should `>0` be formalized as an allowed qualifier in numeric fields? | Option B, modified. | Not a companion boolean flag — an adjacent column description, as in STD-05. |
| 2 | Should inferred statuses be distinguishable at the query layer? | Handle with status interoperability. | |
| 3 | Should `startYearPlanned` be exported as a column in spreadsheets? | Handled by status timeline. | |
| 4 | Is there a standard pattern for imputation companion flags? | Standard is a second categorical field named `{field}_reason`, with a small set of options. | Keeping it a separate categorical field lets the option set vary by field, rather than splitting the rule between numeric booleans and categorical allowed values. |
| 5 | How should national-average assignments be communicated? | Option B. | One column for the number, then a companion field for descriptions and sources — not categorical. |

[Background page →](std-10-imputed-values.md)

---

<a id="std-11"></a>
## STD-11: Data Provenance / Source Fields

**Decision:** Record-level: never publish researcher name in public views (internal only). Standardize how `Last Updated` and `Research Status` appear in spreadsheets to match the database, so public reports align regardless of tracker. Field-level: adopt the pipe companion pattern — `{Field} | Ref` — and align production/reserves-tab column names to it. Support both record-level and field-level provenance. Source content: plain URL; when it points to a general resource rather than the specific document, add a **Short name** to indicate where to find the specific document. Apply the already-standardized database pattern, including the database's Record of full update values, to spreadsheet-only trackers too.

**Discussion:** Provenance tracking splits unevenly between record-level (mostly a Wiki URL) and field-level (three incompatible companion patterns), with most trackers carrying no field-level attribution at all. The "Wiki URL" note in the original audit doc was a misread and is disregarded.

> "Agreeing to adopt pattern C (last updated, researcher date, researcher notes) while deciding never to publish researcher names publicly, though keeping them for internal reports." — Sep 25 meeting

[Background page →](std-11-data-provenance-source-fields.md)

---

<a id="std-12"></a>
## STD-12: Geographic Hierarchy

**Decision:** Replace `Location` with `Address`. Replace `City` with `Nearest City`. Remove parentheses from `Subnational Unit` and put the explainer into metadata; standardize the `Subnational Unit` header name. Leave parentheses for now in Secondary and Tertiary location fields (`Major area`, `Local area`). Use `Country/Area` for the highest national-level location field. Countries, regions, and subregions are established in the database, but we also offer IEA regions. Standardize Start/End location headers for pipelines to align with the other point-based location header names: `Region`, `Subregion`, `Country/Area`, `Subnational Unit`, `Major area (prefecture, district)`, `Local area (taluk, county)`, `Nearest City`, `Lat_Lon`, `Address`. Multi-country assets keep the existing Country 1 / Country 2 pattern, just aligned naming. Basin-style geological hierarchies: out of scope for this standard.

**Discussion:** Geographic hierarchies vary in both structure and naming across trackers — up to eight admin levels, but even identical concepts carry three or more different field names. **Resolved:** WEO regions are the IEA's definitions — not IMF. The full region/subregion/WEO mapping is maintained in [this sheet](https://docs.google.com/spreadsheets/d/1mtlwSJfWy1gbIwXVgpP3d6CcUEWo2OM0IvPD6yztGXI/edit?gid=0#gid=0).

> "'Location' is too vague and should be replaced with 'address,' and 'city' should explicitly refer to the nearest city rather than being used interchangeably with address." — Sep 25 meeting

**Open:**
- Have an LLM look into what secondary and tertiary location data exists, to see how to standardize it.
- Make sure `Location` data actually holds addresses before renaming.

[Background page →](std-12-geographic-hierarchy.md)

---

<a id="std-13"></a>
## STD-13: Temporal Snapshots / "As Of" Dating

**Decision:** Put the tracker's release date in metadata (not a per-row column). For all annual series and date columns, make sure they align with the companion field pattern. `Last Updated` should be the researcher's access date, not the reference/document date — the reference date can be held in the source document itself when available.

**Discussion:** Five different temporal patterns coexist with no unified standard, making it impossible to reliably distinguish a recently verified value from a stale one, or to answer historical questions across releases.

> "Release snapshot dates are redundant across every row for now and that granular last-update fields or companion fields should handle time-varying changes." — Sep 25 meeting
> "The date recorded should be the access date or review date when the information was actually found and verified by the researcher." — Sep 25 meeting

[Background page →](std-13-temporal-snapshots.md)
