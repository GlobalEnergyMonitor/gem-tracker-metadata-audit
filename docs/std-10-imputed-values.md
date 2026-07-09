# STD-10: Imputed Values

**Status:** Draft — for discussion with Data Team  
**Scope:** Fields where researchers or automated logic have filled in a derived, estimated, or rule-based value in place of a directly observed one

---

## Current State

"Imputed value" covers several distinct practices that are currently treated inconsistently:

1. **`>0` — bounded assertion**: "this value is nonzero but the exact quantity is unknown"
2. **Rule-based status inference**: "this status was set by a rule, not a researcher"
3. **Projected vs. confirmed years**: "this year is our best estimate, not a historical fact"
4. **Calculated/assumed ownership shares**: "this percentage was calculated, not directly stated"
5. **Assigned capacity factors**: "this value was set by country-level assumption, not measured"
6. **`unknown` as a sentinel in fraction fields**: "this fraction is unresearched"

In each case, the data contains a value (not null) that wasn't directly sourced but was derived through some logic. The problem is that this distinction is largely invisible in the data itself.

---

## Pattern 1: `>0` — Bounded Assertions in Capacity Fields

As noted in STD-05, `>0` appears in numeric capacity and production fields to signal "nonzero but quantity unknown":

| Field | Tracker | `>0` count |
|---|---|---|
| Cement Capacity (Mtpa) | Cement | 324 |
| Clinker Capacity (Mtpa) | Cement | 827 |
| Nominal iron capacity (ttpa) | Iron & Steel | 217 (plant + ownership) |
| Nominal crude steel capacity (ttpa) | Iron & Steel | 97 (plant + ownership) |
| % scrap / % DRI / % HBI etc. | Iron & Steel EAF units | 484, 139, 64... |
| Plant production (annual, by year) | Iron & Steel production | 16–46 per year |
| Current capacity (ttpa) | Iron & Steel unit data | 22–31 |
| Cement / Clinker capacity | Ownership Tracker | 458, 2,392 |

`>0` is the most systematic imputed-value pattern in the dataset. It is used deliberately and consistently within the Iron & Steel and Cement trackers, and carries meaningful content: the researcher knows the asset has capacity in a given category but couldn't obtain the specific figure.

The EAF feedstock percentage fields (`% scrap`, `% DRI`, `% pig iron`, etc.) are particularly interesting: values must sum to approximately 1.0 for a given unit, so a `>0` in several categories and `unknown` in others means the percentage split is partially known. These fields sit at the intersection of Patterns 1 and 6 below.

---

## Pattern 2: Rule-based Status Inference

The research DB automatically sets two status values based on time-elapsed rules rather than researcher confirmation:

- **`shelved - inferred 2 y`** — a project has been shelved (or pre-construction) for 2+ years with no updates; the system infers it is shelved. 3,635 records.
- **`cancelled - inferred 4 y`** — a project has been shelved-inferred for 4+ years; the system infers cancellation. 3,633 records.

These 7,268 records represent a significant fraction of all non-operating projects. They appear in the same `Status` field as researcher-confirmed statuses (`cancelled`, `shelved`), but the `-inferred` suffix distinguishes them. No companion flag exists — the inference is encoded in the status value itself.

In downstream queries, "cancelled" and "cancelled - inferred 4 y" are typically treated identically, but the distinction matters for data quality review: inferred statuses are candidates for researcher review and reversal.

---

## Pattern 3: Projected vs. Confirmed Years

The research DB stores a `startYearPlanned` boolean alongside `startYearLow` (the effective start year field). As of the current snapshot:

- 135,830 records have a non-null start year
- 10,827 of those have `startYearPlanned = True`

In the spreadsheet exports, `startYearPlanned` collapses into a separate `Planned retirement` column (for end years), but the start-year planned flag is not exported as a standalone field. Users of the spreadsheet cannot distinguish a confirmed 2027 start from a projected 2027 start.

Similarly, `endYearPlanned = True` on 12,100 records — these are planned retirement years, not confirmed.

---

## Pattern 4: Calculated Ownership Shares

The Ownership Tracker (Global Energy Ownership Tracker) includes an explicit `Share Imputed?` field with values:

- `known value, not imputed` — 44,557 records in asset ownership, 20,207 in entity ownership
- `imputed value` — 4,834 records in asset ownership, 4,144 in entity ownership

This is the most transparent imputation pattern in any tracker: the imputed status is explicitly flagged in a companion field, and the companion field has documented allowed values. When a company is listed as an owner but their percentage stake is undisclosed, the tracker calculates or assumes a share (often equal division among co-owners) and marks it as imputed.

The `Share Imputed?` field is notable for having a named, documented value set (`known value, not imputed`, `imputed value`) rather than a boolean. This makes the field more readable but means it can't be used in a boolean filter without mapping.

---

## Pattern 5: Country-level Capacity Factor Assignment

The Coal Plant Tracker includes a `Capacity factor` field containing the average national capacity factor for the plant's country, sourced from Ember data. The field's documented behavior:

> "Plants that are retired or cancelled are given a capacity factor of 0, i.e. no generation is assumed."

This means `0.0` in capacity factor is not null (unknown) and not measured (zero generation from a live plant) — it's an assigned imputed value for all non-operating plants. 6,237 records have `Capacity factor = 0.0`, which corresponds to the retired/cancelled inventory.

The national average capacity factor (e.g., `0.54` for 4,329 plants in a high-CF country) is also an imputed value at the plant level: individual plants likely have capacity factors above and below the national average. The field assigns a national estimate to each unit.

This imputation is documented in the field definition but not flagged in a companion field. Users querying the data directly see `0.54` with no indication that it's a national average rather than a measured plant-level figure, unless they read the field definition.

---

## Pattern 6: `unknown` as a Sentinel in Fraction/Percentage Fields

Iron & Steel EAF unit data stores feedstock percentages (share of scrap, DRI, HBI, pig iron, etc.) that must sum to approximately 1.0. When the mix is unresearched, each component field receives `unknown`:

| EAF % field | `unknown` count | `>0` count | numeric count |
|---|---|---|---|
| % scrap | 267 | 484 | 656 |
| % DRI | 775 | 139 | 493 |
| % HBI | 861 | 64 | 482 |
| % basic/merchant pig iron | 794 | 125 | 488 |
| % pig iron (type unknown) | 861 | 18 | 469 |

`unknown` here is a text value in what would otherwise be a numeric field. This is the same conceptual problem as in STD-05 (numeric field purity) but with a specific epistemic meaning: the researcher knows the field is applicable (the furnace uses some of this input) but hasn't determined the share.

A companion `% known total` field contains `1` where all percentages are known and `0` where they are not, providing a summary flag for records where the split is fully researched.

---

## Pattern 7: `fuelConversionUnknown` Boolean

The `snapshot.powerplant_unit` table has a `fuelConversionUnknown` boolean set to `True` for 10 records. This flags units where the fuel type after conversion is not known. It's a DB-level imputation flag with no corresponding exported field — invisible to spreadsheet users.

---

## Decision Points

### Decision 1: Should `>0` be formalized as an allowed qualifier in numeric fields?

`>0` is used deliberately in Iron & Steel and Cement to encode "positive but unknown." The alternatives:

**Option A — Keep `>0` as an in-cell qualifier**  
Formalize `>0` as a permitted non-numeric token in designated numeric fields. Document it in field metadata (`allowed_values: [">0"]` alongside `data_type: numeric`). Downstream tools must handle it explicitly.

**Option B — Replace `>0` with a companion boolean flag**  
Numeric field holds the quantity or null; companion boolean `{field}_positive_unknown` = True when the value is known to be nonzero but unquantified.

- Pro: Clean numeric fields. Machine-readable.
- Con: More columns. Requires schema changes across Iron & Steel and Cement.

**Option C — Replace `>0` with a structured sentinel token**  
Choose a token like `UNK>0` or `nonzero` that is clearly not a real number but encodes the bounded-unknown concept. Slightly more parseable than `>0` but still a text value in a numeric field.

**Option D — Accept loss of the `>0` signal; convert to null**  
Treat `>0` as a special null proxy and convert to NULL at ETL. Documents the lower bound in field metadata as a known-range note.

The tradeoff: `>0` carries meaningful research signal (the capacity exists, just unknown) that NULL erases. For a research organization where the *existence* of capacity in a category matters for classification (e.g., "does this plant have any EAF capacity?"), losing `>0` matters.

### Decision 2: Should inferred statuses be distinguishable at the query layer?

Currently `cancelled - inferred 4 y` and `shelved - inferred 2 y` are explicit in the status field. If the org standardizes on a simpler status vocabulary (see STD-04), these values might collapse into `cancelled` and `shelved` without the inference qualifier.

**Option A — Keep the explicit `-inferred` suffix in the canonical status list**  
Preserves the researcher-confirmation distinction. Makes queries for "all cancelled projects" require listing both `cancelled` and `cancelled - inferred 4 y`.

**Option B — Add a `status_inferred` boolean companion field**  
`Status = cancelled`, `status_inferred = True`. Cleaner canonical status vocabulary; inference distinction lives in a companion field. Consistent with how other imputation patterns work (Share Imputed?).

**Option C — Keep inferred status as an internal DB state; normalize to base status in exports**  
The DB distinguishes inferred from confirmed; the spreadsheet export collapses both to `cancelled`. Documents the distinction in metadata but not in the data.

### Decision 3: Should `startYearPlanned` be exported as a column in spreadsheets?

Currently the planned/confirmed distinction for start years is lost in the spreadsheet export. Users querying "plants starting in 2027" get both confirmed and projected 2027 starts with no way to distinguish them.

**Option A — Export `startYearPlanned` as a companion column**  
Add `Start year (planned)` or `Start year type` to the spreadsheet. Aligns the export with the DB.

**Option B — Encode in year value** (e.g., `~2027` for projected)  
Non-standard; would break numeric parsing.

**Option C — Accept the loss**  
The planned/confirmed distinction is documented in the DB but not in the public data. For public-facing use cases, the distinction may not be necessary.

### Decision 4: Is there a standard pattern for imputation companion flags?

The Ownership Tracker uses `Share Imputed?` as an explicit companion. The Coal Plant uses `0.0` as an assigned value in capacity factor with no companion flag. The DB uses `startYearPlanned`, `fuelConversionUnknown` as booleans. The status field embeds imputation in the value suffix.

These are four different conventions for the same underlying need. A standard would define:

- **When to use a companion boolean**: when the primary field must remain clean (numeric), when users need to filter for imputed-only records
- **When to embed in the value**: when the imputed status is one of several possible values and already requires a controlled vocabulary (status values)
- **Naming**: `{field}_imputed`, `{field}_estimated`, `{field}_planned` — or a fixed vocabulary like `Share Imputed?`

**Proposed rule:** For any field where imputed values appear alongside directly observed values, a companion boolean `{field} imputed` (or boolean property in metadata) is required if the primary field is numeric. For categorical fields, encode as a distinct allowed value (like the inferred status pattern).

### Decision 5: How should national-average assignments (capacity factor) be communicated?

A value like `0.54` in Capacity factor looks like observed data but is a national-average assignment. Options:

**Option A — Field definition only**  
Accept that the definition documents the methodology. No in-data signal needed.

**Option B — Companion field for assignment methodology**  
`Capacity factor source: national average | plant-specific | 0 (retired)` — would make the assignment reason queryable.

**Option C — Separate imputed-assignment fields**  
Fields like `Capacity factor` only contain directly measured values; separately, `Capacity factor (imputed)` holds the assigned national average. The original field is null for plants without measured capacity factors.

This is relevant beyond capacity factor: wherever GEM assigns a country-level or category-level default in lieu of a plant-level measured value, the assignment is invisible without documentation.

---

## Summary Table

| Pattern | Fields affected | Current signal | Companion flag? |
|---|---|---|---|
| `>0` bounded assertion | Iron & Steel, Cement capacity/production | In-cell `>0` | None |
| Inferred status | All trackers | `-inferred` in status value | None |
| Planned year | All power trackers | DB `startYearPlanned` | Not exported |
| Ownership share | Ownership Tracker | `Share Imputed?` field | Yes (explicit) |
| Assigned capacity factor | Coal Plant | `0.0` for retired | None |
| `unknown` in fractions | Iron & Steel EAF % | In-cell `unknown` | `% known total` field |
| Fuel conversion unknown | Gas tracker (DB) | `fuelConversionUnknown` bool | DB only, not exported |

---

## Related Standards

- **STD-01: Null / Missing Value Encoding** — null vs. `>0` vs. assigned value
- **STD-04: Categorical Allowed Values** — inferred status values; `unknown` as a categorical sentinel
- **STD-05: Numeric Field Purity** — `>0` as a non-numeric token
- **STD-06: Date / Year Format** — `startYearPlanned` and projected years
- **STD-09: Cross-field Links** — companion flags and their associated primary fields
