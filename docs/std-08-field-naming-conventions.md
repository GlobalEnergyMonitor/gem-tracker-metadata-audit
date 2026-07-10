# STD-08: Field Naming Conventions

**Status:** Draft — for discussion with Data Team  
**Scope:** Spreadsheet column headers, DB column names, and `code_friendly_name` (API field names)

---

## Current State

Field names exist at two levels: the human-readable spreadsheet column header (e.g., `Capacity (MW)`) and the machine-readable API/DB name (`code_friendly_name`, e.g., `capacity_mw`). There is no documented standard for either level, and conventions vary significantly between trackers and between tracker generations.

---

### Human-readable names (spreadsheet column headers)

**Convention A — Title Case with parenthetical unit or qualifier (DB-backed trackers)**

The dominant pattern across DB-backed exports. Units and disambiguators are appended in parentheses:

```
Capacity (MW)
Plant name (English)
Plant name (other language)
Local area (taluk, county)
Major area (prefecture, district)
Subnational unit (province, state)
Conversion to (fuel)
Conversion to (GEM unit ID)
Thermal Capacity (MWt)
Ferronickel capacity (ttpa)
Plant age (years)
```

The parenthetical carries several distinct meanings depending on the field:
- **Unit**: `(MW)`, `(ttpa)`, `(Mtpa)`, `(MWt)`, `(years)`, `(US$ Million)`
- **Language variant**: `(English)`, `(other language)`, `(local lang/script)`, `(ENG)`, `(Non-ENG)`
- **Geographic level explainer**: `(taluk, county)`, `(prefecture, district)`, `(province, state)`
- **Type disambiguation**: `(fuel)`, `(GEM unit ID)`, `(location)`, `(unit/phase)`
- **Optionality/plurality hint**: `(s)` — `Name(s)`, `Other Name(s)`, `Alternate Project Name(s)`

These are structurally different purposes being served by the same `(...)` syntax. A machine parser cannot reliably distinguish a unit suffix from a geographic explainer.

**Convention B — camelCase, no spaces (GGIT trackers)**

GGIT Gas Pipelines, GGIT LNG Terminals, and GOIT Oil Pipelines use camelCase with no spaces — a convention consistent with JSON/API naming but unusual for spreadsheet column headers:

```
PipelineName, SegmentName, ProjectID, LastUpdated
CapacityBcm/y, CapacityBOEd, FIDStatus
ProposalYear, ConstructionYear, ShelvedYear, CancelledYear
ImportExportOnly, Offshore, Floating
```

Notable: units are embedded directly in the field name (`CapacityBcm/y`) rather than appended in parentheses, and slashes appear within camelCase names (`CapacityBcm/y`).

**Convention C — `[ref]` suffix for source fields (GIPT, GOIT, LNG Carrier)**

Some trackers append `[ref]` to mark companion source fields:

```
Diameter [ref]
FuelSource [ref]
IMO number [ref]
Name [ref]
```

This is the most systematic approach to source provenance — every data field has a named companion. It's discussed further in STD-11 (Data Provenance / Source Fields).

**Convention D — `{Field} Data Source` suffix (Gas tracker DB export)**

The gas tracker DB export uses a different companion naming pattern:

```
Fuel Data Source
Capacity Data Source
Status Data Source
Turbine/Engine Technology Data Source
Cancellation year Data Source
```

Same concept as `[ref]`, different syntax. Both conventions exist simultaneously across different trackers.

**Convention E — Question mark suffix for boolean fields**

18 fields end with `?` to signal a yes/no question:

```
Repaid?
Share Imputed?
CCS attachment?
Conversion/Replacement?
H2 ready turbine (%)?
```

Informal; overlaps with STD-03 (Boolean Encoding) and STD-09 (Cross-field Links).

---

### Year / date field naming

The same concept — "when did X happen" — is expressed four different ways:

| Pattern | Example | Source |
|---|---|---|
| `{Event} year` (lowercase, space) | `Start year`, `Retired year` | Coal Plant DB export |
| `{Event} Year` (title case, space) | `Start Year`, `Retired Year` | Gas, Nuclear DB export |
| `{Event}Year` (camelCase) | `StartYear`, `ConstructionYear`, `ShelvedYear` | GGIT trackers |
| `{Event} date` | `Start date`, `Construction date`, `Announced date` | Iron & Steel |

Beyond the format inconsistency, "year" vs. "date" carries meaning: "year" implies annual granularity, "date" implies day-level precision. In practice the distinction isn't applied consistently (see STD-06).

---

### Unit representation in field names

Units appear three different ways:

1. **Parenthetical suffix**: `Capacity (MW)`, `Production (Mtpa)` — most common, human-readable, not machine-parseable without convention documentation
2. **Embedded in camelCase**: `CapacityBcm/y`, `CapacityBOEd`, `CapacityMtpa` — machine-unfriendly (slash in name), hard to tokenize
3. **Spelled out**: `Cement Capacity (millions metric tonnes per annum)` — unambiguous but verbose; Cement tracker only

The unit itself has inconsistency: `(Mtpa)` vs. `(millions metric tonnes per annum)` for the same unit; `(MW)` vs. `(MWt)` for thermal vs. electrical capacity (a meaningful distinction that gets lost when both are abbreviated similarly).

---

### Language variant naming

Fields with language variants use five different patterns:

```
Plant name (English) / Plant name (other language)   ← DB-backed trackers
Plant name (ENG) / Plant name (Non-ENG)              ← variant
GEM Wiki Page (ENG) / GEM Wiki Page (Non-ENG)        ← GIPT
Owner (other language)                               ← Steel
Owner Name in Local Language / Script                ← Portal Energetico
nameLocal                                            ← snapshot DB column
```

No consistent rule for how to name the local-language variant of a field.

---

### `code_friendly_name` (API/DB names)

The `code_friendly_name_guess` values produced by `analyze.py` are auto-generated by lowercasing and snake_casing the raw field name. They are not a documented standard. The current approach strips parenthetical units, which means `Capacity (MW)` and `Capacity (ttpa)` both become `capacity` — losing the unit information that was in the original name.

In the DB itself, Django model column names use camelCase: `startYear`, `capacityRating`, `startYearPlanned`. The DB and the spreadsheet naming conventions are therefore different at both levels.

---

## Decision Points

### Decision 1: Should units be in the field name, field metadata, or both?

The parenthetical `(MW)` convention serves two purposes: it helps PMs and users understand what a field contains, and it disambiguates same-concept fields with different units (`Capacity (MW)` vs. `Capacity (ttpa)`). But it embeds metadata into the name rather than in a structured `unit_name` property.

**Option A — Unit in name only (current practice)**  
Keep `Capacity (MW)` as the field name. Simple for humans; hard for machines to parse without a convention.

**Option B — Unit in metadata only**  
Strip units from field names: `Capacity` with `unit_name_short: MW` in the field schema. Cleaner names; requires metadata to be populated for every field.

**Option C — Unit in both name and metadata**  
Keep `Capacity (MW)` as the display name; require `unit_name_short` and `unit_name_long` in metadata. Best of both — human-readable and machine-parseable. More documentation work.

The existing field schema already has `unit_name_short` and `unit_name_long` properties defined, which suggests Option C was the intent. The question is whether to enforce it.

### Decision 2: Standardize the parenthetical convention

If units (and other qualifiers) stay in field names, the parenthetical needs a documented grammar so parsers can extract them reliably. Current uses:

| Purpose | Proposed syntax | Example |
|---|---|---|
| Unit | `(unit)` | `Capacity (MW)` |
| Language variant | `(lang)` | `Plant name (English)` |
| Geographic explainer | omit from name; put in definition | — |
| Plurality hint | omit; use `multiple_values_separator` in metadata | — |
| Type disambiguation | `(type)` | `Conversion to (fuel)` |

The geographic explainers (`(taluk, county)`, `(prefecture, district)`) are particularly problematic — they contain commas, making them look like multi-value annotations. Moving that information to the field definition rather than the name would clean this up.

### Decision 3: camelCase vs. Title Case for spreadsheet headers

GGIT trackers use camelCase; all DB-backed exports use Title Case with spaces. These need to converge for a unified schema.

**Option A — Title Case with spaces** (current DB standard)  
`Start Year`, `Plant Name`, `Country/Area`. Human-readable; consistent with existing exports.

**Option B — camelCase** (GGIT convention)  
`startYear`, `plantName`, `countryArea`. More API-like; harder for PMs to read.

The GGIT trackers were built to a different convention; migration to Title Case would require renaming columns. But they'll need to converge with the other trackers eventually.

### Decision 4: Companion field naming — `[ref]` vs. `{Field} Data Source`

Two incompatible patterns exist for source/provenance companion fields. This is addressed fully in STD-11 (Data Provenance / Source Fields), but the naming decision belongs here: what is the standard suffix for a companion source field?

**Option A — `{Field} Data Source`** — current Gas tracker pattern; human-readable; long
**Option B — `{Field} [ref]`** — current GIPT/GOIT pattern; compact; bracket syntax unusual in column names  
**Option C — `{Field} Source`** — shorter than A; ambiguous (Coal Source is not a provenance field)
**Option D — `{field}_source` in API names** — machine-friendly; invisible to spreadsheet users

### Decision 5: API/DB `code_friendly_name` convention

For the unified DB and API, a `code_friendly_name` convention needs to be defined. Candidates:

**snake_case** (most common in Python/REST APIs): `capacity_mw`, `start_year`, `plant_name`  
**camelCase** (JavaScript/JSON convention, current Django models): `capacityMw`, `startYear`, `plantName`

If the DB uses Django/PostgreSQL, camelCase is already the model convention. If the API layer uses a REST framework that serializes to JSON, it may translate to camelCase automatically regardless.

The key question is whether units should be in the `code_friendly_name`:
- `capacity_mw` vs. `capacity` (unit in metadata only)
- `capacity_mw` and `capacity_ttpa` as separate fields vs. `capacity` with unit metadata

For fields that exist in multiple unit variants across trackers, embedding the unit in the CFN is the only way to disambiguate. For fields where the unit is fixed by tracker type, it's noise.

### Decision 6: Language variant naming

Standardize on one pattern for primary vs. local-language field variants:

| Option | Primary | Local language |
|---|---|---|
| Current DB | `Plant name` | `Plant name (other language)` or `nameLocal` |
| Proposed A | `{Field}` | `{Field} (local language)` |
| Proposed B | `{Field} (English)` | `{Field} (local language)` |
| Proposed C | `{Field}` | `{Field}_local` (in API names) |

Option B makes the primary field's language explicit, which is useful when the data is multilingual. Option C keeps the display name clean while making the distinction visible at the API level.

---

## Related Standards

- **STD-02: Multi-value Separators** — `(s)` suffix as an informal multi-value marker
- **STD-06: Date / Year Format** — year vs. date in field names
- **STD-09: Cross-field Links** — accuracy and companion field naming
- **STD-11: Data Provenance / Source Fields** — `[ref]` and `Data Source` companion naming


---

**Standardization docs:** [Index](index.md) · [STD-01](std-01-null-encoding.md) · [STD-02](std-02-multi-value-separators.md) · [STD-03](std-03-boolean-encoding.md) · [STD-04](std-04-categorical-allowed-values.md) · [STD-05](std-05-numeric-field-purity.md) · [STD-06](std-06-date-year-format.md) · [STD-07](std-07-required-fields-nullability.md) · [STD-08](std-08-field-naming-conventions.md) · [STD-09](std-09-cross-field-links.md) · [STD-10](std-10-imputed-values.md) · [STD-11](std-11-data-provenance-source-fields.md) · [STD-12](std-12-geographic-hierarchy.md) · [STD-13](std-13-temporal-snapshots.md)
