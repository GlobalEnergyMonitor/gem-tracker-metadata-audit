# STD-11: Data Provenance / Source Fields

**Status:** Draft — for discussion with Data Team  
**Scope:** All fields that document where data came from, when it was last reviewed, and who reviewed it

---

## Current State

GEM's provenance infrastructure operates at two levels: **record-level** (where did this record's data originate?) and **field-level** (where did *this specific field's value* come from?). The two levels have very different coverage and naming conventions across trackers.

---

## Record-Level Provenance

### Pattern A — Wiki URL (dominant approach, 20+ trackers)

The most common provenance mechanism: a `Wiki URL` (or `GEM wiki page`, `GEM.Wiki URL`) field containing a link to the asset's GEM Wiki page.

| Field name variant | Trackers |
|---|---|
| `Wiki URL` | Coal Plant, Coal Mine, Solar, Wind, Nuclear, Geothermal, Hydro, Bioenergy, GGIT, GOGET, GMET, Coal Terminals, Gas Finance, Iron Ore Mines, Chemicals |
| `GEM wiki page` | Cement |
| `GEM.Wiki URL` | GIPT |
| `Wiki URL (project)` / `Wiki URL (field)` | GOGET (two separate links for project and field level) |

The wiki page itself documents the sources for a record in unstructured prose or a sources section. The `Wiki URL` field in the tracker is not a citation — it's a pointer to a page that *contains* the citations.

**Coverage gap**: Iron & Steel, Ownership Tracker, and LNG Carrier have no `Wiki URL` field. Whether wiki pages exist for these assets and are simply not linked in the tracker spreadsheet, or whether these trackers lack wiki coverage, varies by tracker.

**Volatility risk**: Wiki pages are editable and can change after the spreadsheet is published. A `Wiki URL` link at time of release may point to a page with different content at time of user access. The link preserves access to a research artifact, not a fixed citation.

### Pattern B — Research Status (DB-backed trackers)

Several DB-backed tracker exports include a `Research Status` field tracking the record's state during the most recent data release cycle:

| Value | Meaning |
|---|---|
| `added` | New record this release cycle |
| `updated` | Existing record with changes this cycle |
| `no changes` | Existing record with no changes this cycle |
| `in progress` | Under active research, incomplete |
| `''` (blank) | Unset |

This field is an internal workflow audit trail, not a data provenance citation. It tells users how recently a record was reviewed and whether it changed — useful for detecting stale data — but not what source the values came from.

Coverage: Coal Plant, Gas, Solar, Wind, Nuclear, Hydro, Geothermal.  
Not exported: Iron & Steel, Steel, LNG, Bioenergy, Cement, GOGET.

### Pattern C — Last Updated / Researcher (DB internal, partially exported)

The research DB stores `Last Updated`, `Researcher`, `Date Last Researched`, and `ResearcherNotes` for each record at the DB level. Of these:

- **`Last Updated`** — exported in Coal Plant, Gas tracker exports
- **`Researcher`** — exported in Gas tracker export only
- **`Date Last Researched`** / **`ResearcherNotes`** — not exported to any public spreadsheet

The gas tracker is the only one that exposes the researcher attribution publicly. This is the most traceable internal provenance but is inconsistently applied.

---

## Field-Level Provenance

### Pattern D — `{Field} Data Source` companion columns (Gas, Steel, GOGET, Combustion)

The most granular approach: each key data field has a named companion column containing the URL or citation for that specific field's value. The gas_all DB export has 24 such columns:

```
Fuel Data Source
Capacity Data Source
Status Data Source
Start Year Data Source
Retired Year Data Source
CCS Data Source
CHP Data Source
Operators Data Source
Owners Data Source
Location Data Source
Turbine/Engine Technology Data Source
... (14 more)
```

The research DB stores the corresponding `{field}Datasource` columns natively (e.g., `capacityDatasource`, `statusDatasource`, `locationDatasource`). These are Django model fields that record the URL or citation at data entry time.

Steel tracker: 17 `{Field} Data Source` columns (Capacity, Carbon Capture, Hydrogen Reductant, Decarbonization Technology, etc.)  
GOGET: 12 `{Field} Data Source` columns (Basin, Concession block, Location, Discovery Year, etc.)  
Combustion (gas/oil): 17 columns shared with Gas

Most values in these fields are URLs (EIA, ENTSOE, Bundesnetzagentur, etc.). The top value in `Capacity Data Source` for gas is `https://www.eia.gov/electricity/data/eia860m/...` with 1,920 records — reflecting systematic import from a single source.

### Pattern E — `[ref]` suffix (LNG Carrier, GOIT Oil Pipelines)

Some trackers append `[ref]` to each field name to create a paired source companion:

| Data field | Source companion |
|---|---|
| `IMO number` | `IMO number [ref]` |
| `Name` | `Name [ref]` |
| `Status` | `Status [ref]` |
| `Shipowner` | `Shipowner [ref]` |
| `Capacity` | `Capacity [ref]` |
| `Diameter` (GOIT) | `Diameter [ref]` |

Values are URLs. For LNG Carrier, most `[ref]` fields point to the IGU World LNG Report as the bulk source. For GOIT, sources are more varied (OPEC publications, government documents, satellite imagery).

This pattern is structurally equivalent to `{Field} Data Source` but uses a different naming convention and brackets rather than a suffix phrase.

### Pattern F — `Data source type` (GOGET production/reserves)

GOGET's production and reserves tabs include a `Data source type` field that is categorical rather than a URL:

| Value | Count |
|---|---|
| `project level production` | 270 |
| `production summed from fields` | 61 |
| `project level reserves` | 375 |
| `reserves summed from fields` | 56 |

This describes the aggregation level of the data (was it reported at project level, or summed up from field-level data?) rather than the citation. It's a methodological provenance note, not a source citation.

---

## What's Not Captured

Most trackers (Coal Mine, Solar, Wind, Nuclear, Bioenergy, Cement, Chemicals, Iron & Steel, Ownership, Coal Finance) have only the `Wiki URL` for record-level provenance and nothing for field-level provenance. No indication of:

- Which source was used for status vs. capacity vs. ownership
- When specific fields were last updated (as distinct from when the whole record was reviewed)
- Whether a field value came from a primary source (company report, regulator filing) or a secondary one (news article, Wikipedia)

---

## Decision Points

### Decision 1: What level of provenance granularity is the target?

Three possible targets:

**Option A — Record-level only (current majority practice)**  
`Wiki URL` or similar points to a page with sources. No field-level attribution. Simple; the wiki is the authoritative source document.

**Option B — Field-level for key fields only**  
Add source tracking for a defined set of high-value fields: Capacity, Status, Owner, Start Year, Location. Mirrors what Gas and Steel currently do for their most important fields.

**Option C — Field-level for all fields**  
Full `{Field} Data Source` or `[ref]` for every data field. Maximum traceability; significant data entry overhead.

The Gas and Steel trackers implement Option C for their key fields, but this was a deliberate choice enabled by the DB's datasource column infrastructure. For trackers that are spreadsheet-only and lack that infrastructure, Options B or A are more realistic.

### Decision 2: Naming standard for field-level source companions — `{Field} Data Source` vs. `{Field} [ref]`

Two incompatible conventions currently exist:
- `{Field} Data Source` — Gas, Steel, GOGET (22+ trackers' DB outputs)
- `{Field} [ref]` — LNG Carrier, GOIT Oil Pipelines

The `{Field} Data Source` convention aligns with the DB model naming (`capacityDatasource`) and is more widely used. The `[ref]` convention is more compact and keeps the companion field visually distinct.

**Proposed standard:** `{Field} Data Source` — consistent with the DB convention and the majority of existing practice. The `[ref]` convention should be treated as a legacy pattern; new trackers should use `{Field} Data Source`.

### Decision 3: What should a source field value contain?

Currently, source fields contain:
- A URL to a specific document or database (`https://www.eia.gov/...`)
- A URL to a general resource (`https://transparency.entsoe.eu/`)
- A Google Maps URL (LNG Carrier `Yard location lat/lon [ref]` — 270 entries)
- Free text (occasional)

There's no standard for:
- How to cite a printed publication vs. a web page
- How to attribute a calculated value (see STD-10)
- How to attribute a value imported from another GEM tracker
- How to handle values from multiple sources

**Options:**
- **URL only** — simple, machine-readable, but doesn't cover print sources or internal attributions
- **Structured citation** — `{author, title, year, url}` — thorough but complex at data entry
- **GEM citation key** — a short identifier pointing to a GEM-maintained bibliography (analogous to BibTeX keys)

### Decision 4: Should `Research Status` values be standardized across trackers?

Current values (`added`, `updated`, `no changes`, `in progress`) are consistent across the trackers that use it. The inconsistency is in which trackers include it, and in the blank (`''`) records.

**Options:**
- **Extend to all trackers** — add `Research Status` to Iron & Steel, Bioenergy, Cement, Chemicals, Ownership Tracker exports
- **Keep as-is** — accept that Research Status is only in DB-backed power trackers
- **Formalize the value set** — add `Research Status` to the field schema with documented `allowed_values`; eliminate blank values

The field is useful for users who want to filter to recently verified records or find records under active review. Extending it universally would make the tracker portfolio more consistent.

### Decision 5: Should `Last Updated` be universal?

`Last Updated` tells users how fresh a record's data is. Currently it appears in Coal Plant and Gas tracker exports only.

**Options:**
- **Export to all trackers** from the DB's `lastUpdated` column
- **Add for spreadsheet-only trackers** — requires a tracking mechanism that doesn't currently exist
- **Defer** — accept that record freshness is tracked at the wiki level, not in the data

For spreadsheet-only trackers (Coal Mine, Coal Terminals, etc.), there is no DB to pull `lastUpdated` from. PMs would need to update a column manually, which is unlikely to be maintained.

### Decision 6: How should the wiki be used as a provenance mechanism long-term?

The `Wiki URL` approach delegates source documentation to the wiki. This has tradeoffs:

**Advantages:**
- Sources can be updated without re-releasing the data file
- Narrative context is possible (not just a URL)
- No field-per-source overhead in the data schema

**Disadvantages:**
- A wiki page can be edited after the data is released, making it impossible to reconstruct what sources supported a specific data release version
- Users querying the data directly cannot determine source without leaving the dataset
- Wiki pages may not exist for all records (LNG Carrier, Iron & Steel, Ownership)
- The wiki is a separate system; its availability and persistence are independent of the data

For versioned data releases, the wiki is insufficient as the sole provenance record. A snapshot of the wiki page at release time would be needed — something not currently done.

---

## Summary: Current State by Tracker

| Tracker | Wiki URL | Research Status | Last Updated | Field Data Source |
|---|---|---|---|---|
| Coal Plant | Y | Y | Y | — |
| Gas | Y | Y (Research status) | Y (+ Researcher) | Y (24 fields) |
| Solar / Wind | Y | Y | — | — |
| Nuclear / Hydro / Geothermal / Bioenergy | Y | Y | — | — |
| Coal Mine | Y | — | — | — |
| Steel | — | — | — | Y (17 fields) |
| GOGET | Y (2 fields) | — | — | Y (12 fields) + type |
| GGIT (Gas Pipelines, LNG) | Y | — | — | — |
| LNG Carrier | — | — | — | Y (`[ref]`, 14 fields) |
| GOIT Oil Pipelines | — | — | — | Y (`[ref]`, 2 fields) |
| Cement / Chemicals / Iron Ore | Y | — | — | — |
| Ownership / Coal Finance | — | — | — | — |
| GIPT | Y | — | — | — |
| GMET | Y | — | — | — |

---

## Related Standards

- **STD-08: Field Naming Conventions** — `{Field} Data Source` vs. `{Field} [ref]` naming
- **STD-09: Cross-field Links** — companion field pairing and linking mechanisms
- **STD-13: Temporal Snapshots / "as of" dating** — `Last Updated` as a temporal provenance field


---

**Standardization docs:** [Index](index.md) · [STD-01](std-01-null-encoding.md) · [STD-02](std-02-multi-value-separators.md) · [STD-03](std-03-boolean-encoding.md) · [STD-04](std-04-categorical-allowed-values.md) · [STD-05](std-05-numeric-field-purity.md) · [STD-06](std-06-date-year-format.md) · [STD-07](std-07-required-fields-nullability.md) · [STD-08](std-08-field-naming-conventions.md) · [STD-09](std-09-cross-field-links.md) · [STD-10](std-10-imputed-values.md) · [STD-11](std-11-data-provenance-source-fields.md) · [STD-12](std-12-geographic-hierarchy.md) · [STD-13](std-13-temporal-snapshots.md)
