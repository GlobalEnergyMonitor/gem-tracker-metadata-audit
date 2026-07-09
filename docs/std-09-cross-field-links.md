# STD-09: Cross-field Links

**Status:** Draft — for discussion with Data Team  
**Scope:** Accuracy qualifier fields, year-of fields, source companion fields, and any other fields whose meaning depends on another field

---

## Current State

Several field types only make sense in relation to another field. Two categories dominate:

1. **Accuracy qualifier fields** — a categorical field that rates the quality or method of measurement for another field (`Location accuracy` qualifies `Latitude` and `Longitude`)
2. **"Year of" / temporal qualifier fields** — a year field whose value is the year as of which another field's value was measured or reported (`Year of Production` qualifies the production figure)

A third category — **source provenance companion fields** — overlaps with STD-11 (Data Provenance / Source Fields) and is addressed there. It is noted here where the naming convention creates ambiguity.

---

## Accuracy Qualifier Fields

### How many and which trackers

The audit found 50+ distinct accuracy-related fields across 34 tables that have both a latitude and accuracy field. The pattern is nearly universal for geo-located trackers.

| Accuracy field | Qualifies | Tracker(s) | Values |
|---|---|---|---|
| `Location accuracy` | `Latitude`, `Longitude` | Gas, Coal Plant, Solar, Wind, Hydro, Nuclear, Bioenergy, Geothermal, GOGET, Coal Finance, etc. | `exact` / `approximate` |
| `Location Accuracy` | same | Coal Mine, Coal Terminals | `Exact` / `Approximate` |
| `Coordinate accuracy` | `Latitude`, `Longitude` | Cement, Chemicals, Iron & Steel | `exact` / `approximate` |
| `RouteAccuracy` | Pipeline route geometry | GGIT Gas Pipelines, GOIT Oil Pipelines | `high` / `medium` / `low` / `no route` |
| `Accuracy` | `Latitude`, `Longitude` | GGIT LNG Terminals, GMET LNG, Portal Energetico LNG | `exact` / `approximate` |
| `Output Accuracy` | Annual production columns | Coal Mine historical production | `Reported` / `Estimated` |
| `Depth Accuracy` | `Mine Depth (m)` | Coal Mine | `Exact` / `Estimate` |
| `Workforce Accuracy` | `Workforce Size` | Coal Mine | `Exact` / `Estimate` |
| `Accuracy Rating` | Percentage split fields | Coal Mine | `Reported` / `Estimated` |
| `Feedstock accuracy` | Feedstock type | Chemicals | `exact` / `assumed` / `unknown` |
| `Yard location accuracy` | Shipyard coordinates | LNG Carrier | `exact` / `approximate` |

### The linking problem

The connection between an accuracy field and the field(s) it qualifies is encoded inconsistently across trackers:

**Explicit in metadata** (Coal Mine, Coal Plant only)  
The `api_metadata` for these two trackers includes an `accuracy_for_field` property:
```json
"Location accuracy": {
  "accuracy_for_field": ["Latitude", "Longitude"]
}
"Depth Accuracy": {
  "accuracy_for_field": "mine_depth_m"
}
```
Note the inconsistency even within this: one uses the display name (`Latitude`, `Longitude`), the other uses the `code_friendly_name` (`mine_depth_m`).

**Implicit by naming convention** (most trackers)  
`Location accuracy` clearly modifies location-related fields. But the link isn't machine-readable without parsing the field name — and it's ambiguous for fields like `Accuracy` (GGIT LNG, Portal LNG) with no subject qualifier.

**Implicit by column position** (Coal Mine historical production)  
The most fragile form of linking. The historical production tab repeats the same block of columns per year:

```
Coal Output (Annual, Mt) 2023
Coal Output (Annual, Mst) 2023
Output Accuracy          ← qualifies the two columns above it
Coal Output (Annual, Mt) 2022
Coal Output (Annual, Mst) 2022
Output Accuracy_2        ← renamed _2 by ingest deduplication logic
...
```

The link is entirely positional. The `_2` suffix in the ingested data is an artifact of deduplication, not part of the original field name. In the original spreadsheet, all seven accuracy columns are literally named `Output Accuracy`.

### Accuracy value inconsistency

Three distinct value sets appear for the same `exact / approximate` concept:

| Pattern | Values | Source |
|---|---|---|
| Lowercase | `exact`, `approximate` | DB-backed exports (dominant) |
| Title case | `Exact`, `Approximate` | Coal Mine, Coal Terminals |
| Mixed | `exact`, `Approximate` | Solar (case error in ~71 rows) |
| Descriptive | `Reported`, `Estimated` | Coal Mine output accuracy |
| Tiered | `high`, `medium`, `low`, `no route` | Pipeline route accuracy |
| Domain-specific | `exact`, `assumed`, `unknown` | Chemicals feedstock accuracy |

The `Reported` / `Estimated` distinction in Coal Mine output is semantically different from `exact` / `approximate` for location: it's about data source type, not spatial precision. Yet both live in fields named `*Accuracy`.

---

## "Year of" / Temporal Qualifier Fields

These fields store the year as of which another field's snapshot value applies. They are common in trackers where a measurement can change over time and researchers want to record when the value was obtained.

| Field | Qualifies | Tracker |
|---|---|---|
| `Year of Production` | Annual production figure | Coal Mine |
| `Reported Year of Percentage Split` | `Percentage of Met Coal`, `Percentage of Thermal Coal` | Coal Mine |
| `Year of Total Reserves Recorded` | Total reserves | Coal Mine |
| `Reported Year of Mine Life` | `Reported Life of Mine` | Coal Mine |
| `Year of Reported Coal Mine Methane Emissions` | CH4 emissions fields | Coal Mine |
| `Gas-level Rating Appraisal Year` | `Gas-level Rating` | Coal Mine |

The `associated_field` property in the coal mine's `api_metadata` makes the link explicit:
```json
"Reported Year of Percentage Split": {
  "associated_field": ["Percentage of Met Coal", "Percentage of Thermal Coal"]
}
"Gas-level Rating Appraisal Year": {
  "associated_field": ["Gas-level Rating"]
}
```

As with `accuracy_for_field`, this metadata exists only in the two documented trackers and is not populated elsewhere.

Note: `Year of Total Reserves Recorded` has itself as its own `associated_field` — a self-referential entry that suggests the metadata was placeholder-filled rather than deliberately authored.

---

## Source Companion Fields (cross-reference to STD-11)

Several fields whose names contain "source" are **data fields** (substantive content), not provenance fields:

- `Coal source` — where the plant's coal comes from (a region or country), not who provided the data
- `Iron ore source` / `Met coal source` — same pattern in Iron & Steel
- `FuelSource` — the type of fuel, not a citation

These are distinct from fields that record the citation or evidence for another field's value (`Data Source`, `[ref]`). The naming overlap creates false positives when scanning for companion provenance fields. This is addressed in STD-11.

---

## Decision Points

### Decision 1: How should the accuracy-to-field link be encoded?

Currently the link is either absent (most trackers), implicit by name, or explicit in metadata only for the two documented trackers.

**Option A — Naming convention only (current de facto standard)**  
`{Subject} accuracy` (e.g., `Location accuracy`, `Depth Accuracy`). The subject in the name is sufficient to identify the target field. Works for simple cases; breaks for ambiguous names like `Accuracy` and for compound cases where one accuracy field qualifies multiple fields.

**Option B — Populate `accuracy_for_field` in all field metadata**  
Every accuracy field has an `accuracy_for_field` property listing the field(s) it qualifies. Currently only Coal Mine and Coal Plant have this. The metadata schema already defines the property; it just needs to be populated for every tracker.

**Option C — Structural: companion column adjacent to its parent**  
Require that accuracy fields appear immediately after the field(s) they qualify in the column order. This is already implicit in the historical production tab. Makes the positional link conventional rather than coincidental.

**Option D — Separate metadata table**  
Define cross-field relationships explicitly in a lookup table (or JSON config): `{"Depth Accuracy": {"qualifies": "Mine Depth (m)", "type": "accuracy"}}`. Not stored in the data itself, but in a schema document alongside the data.

Options B and D are not mutually exclusive; Option B embeds the link in per-field metadata, Option D centralizes it in a schema document.

### Decision 2: Should "accuracy" value sets be unified across trackers?

The `exact` / `approximate` split covers location accuracy across most trackers. But different use cases have genuinely different value sets:

- Location accuracy: `exact` / `approximate` — spatial precision
- Output accuracy: `Reported` / `Estimated` — source type
- Route accuracy: `high` / `medium` / `low` / `no route` — geometric precision tier
- Feedstock accuracy: `exact` / `assumed` / `unknown` — epistemic state

**Option A — Single `location_accuracy` canonical set** (`exact`, `approximate`)  
Apply this set only to lat/lon qualifier fields. Other accuracy fields define their own allowed values per tracker and use case.

**Option B — Parameterized accuracy schema**  
Define accuracy fields with an explicit `purpose` property: `location`, `measurement`, `source_type`, `route`. Each purpose has a documented allowed-value set.

**Option C — Unify where concepts are the same; leave domain-specific as-is**  
`Location accuracy` and `Coordinate accuracy` should merge into one canonical set. `Output Accuracy` (`Reported`/`Estimated`) and `RouteAccuracy` are different concepts and don't need to unify.

### Decision 3: Case normalization for accuracy values

All DB-backed trackers use lowercase (`exact`, `approximate`). Coal Mine and Coal Terminals use title case (`Exact`, `Approximate`). The Solar tracker has a mixed-case artifact (71 `Approximate` values in a field that otherwise uses `approximate`).

This is a subset of the broader Decision 2 in STD-04 (Categorical Allowed Values). The recommendation there is lowercase everywhere; applying it here means `Exact` → `exact`, `Estimate` → `estimate`, `Reported` → `reported`.

### Decision 4: How should the Output Accuracy / positional-link problem be addressed?

The historical production tab pattern — seven `Output Accuracy` columns linked to seven annual output blocks by position — is the most fragile linking approach currently in use. It breaks as soon as columns are reordered and produces ambiguous deduplicated names (`Output Accuracy_2`) in ingest.

**Option A — Accept the position-based convention**  
Document that in wide-format annual tabs, accuracy columns immediately follow the data columns they qualify. The positional link is conventional. No schema change required.

**Option B — Rename accuracy columns to embed the year**  
`Output Accuracy 2023`, `Output Accuracy 2022`, etc. Makes the link explicit in the name. Requires spreadsheet column renames.

**Option C — Restructure the tab as long-format**  
One row per mine per year: `{mine_id, year, output_mt, output_mst, accuracy}`. Eliminates the wide-format position problem entirely. Significant schema change for the spreadsheet.

### Decision 5: Should `associated_field` be populated as a standard property?

The Coal Mine metadata demonstrates that temporal qualifier fields (`Year of Production`, `Gas-level Rating Appraisal Year`) can be explicitly linked to their parent fields via `associated_field`. This makes the relationship machine-readable.

**Is this worth doing broadly?**  
Year-of-measurement fields appear in Coal Mine only (the other trackers track lifecycle years, not measurement snapshot years). If other trackers adopt snapshot-year fields in the future, `associated_field` provides the right structure. For now, the question is whether it's worth backfilling for Coal Mine beyond what already exists.

Note: the current self-referential `"Year of Total Reserves Recorded": {"associated_field": ["Year of Total Reserves Recorded"]}` entry is a bug — it should point to the reserves field, not itself.

### Decision 6: Naming standard for accuracy fields

The naming is mostly consistent (`{Subject} accuracy`) but has surface variations:

| Variant | Example |
|---|---|
| `{Subject} accuracy` | `Location accuracy`, `Depth Accuracy` |
| `{Subject}Accuracy` | `RouteAccuracy` |
| `Accuracy` (no subject) | GGIT LNG, Portal LNG |
| `Accuracy Rating` | Coal Mine percentage split |
| `{Subject} accuracy rating` | Could be |

**Proposed standard:**  
`{Subject} accuracy` (title case on Subject, lowercase "accuracy", space-separated) — consistent with the DB-backed tracker convention. `RouteAccuracy` → `Route accuracy`. Plain `Accuracy` → `Location accuracy` (or whatever the actual subject is).

---

## Related Standards

- **STD-04: Categorical Allowed Values** — allowed values for accuracy fields; case normalization
- **STD-06: Date / Year Format** — "Year of" fields use year-only format
- **STD-08: Field Naming Conventions** — `{Subject} accuracy` naming pattern
- **STD-11: Data Provenance / Source Fields** — source companion fields vs. data "source" fields
