# STD-12: Geographic Hierarchy

**Status:** Draft — for discussion with Data Team  
**Scope:** All geographic fields across tracker spreadsheets and the research database

---

## Current State

Point-location trackers use up to eight geographic levels, but the levels present, their names, and their coverage vary significantly across trackers. The research DB derives higher-level geography (Region, Subregion) from the Country field automatically, but the field names used in exports are inconsistent.

---

## The Standard Geographic Hierarchy (DB-backed power trackers)

The most complete implementation — used by Coal Plant, Nuclear, Solar, Wind, and the GIPT — has eight levels:

| Level | Field name (Coal Plant) | Field name (Nuclear/Solar) | Field name (GIPT) |
|---|---|---|---|
| Country/territory | `Country/Area` | `Country/Area` | `Country/area` |
| Continent | `Region` | `Region` | `Region` |
| Subcontinent | `Subregion` | `Subregion` | `Subregion` |
| Primary admin division | `Subnational unit (province, state)` | `State/Province` | `Subnational unit (state, province)` |
| Secondary admin division | `Major area (prefecture, district)` | `Major Area (prefecture, district)` | `Major area (prefecture, district)` |
| Tertiary admin division | `Local area (taluk, county)` | `Local Area (taluk, county)` | `Local area (taluk, county)` |
| Nearest settlement | `Location` | `City` | `City` |
| Coordinates | `Latitude`, `Longitude` | `Latitude`, `Longitude` | `Latitude`, `Longitude` |

There are 41 tables that contain `Country/Area` — the field is universal across trackers that cover located assets. But even for the standard DB-backed power trackers, the same level has three different names (e.g., `Subnational unit (province, state)` vs `State/Province` vs `Subnational unit (state, province)`).

---

## Country / Territory Name

### Naming inconsistencies

The country field appears under four distinct names:

| Field name | Tables | Trackers |
|---|---|---|
| `Country/Area` | 41 | Coal Plant, Nuclear, Solar, Bioenergy, GGIT LNG, etc. |
| `Country/area` | 10 | Iron & Steel, GIPT |
| `Country / Area` | 3 | Coal Mine, Portal Energetico |
| `Country` | 8 | Coal Mine historical tabs, Gas Finance, Iron Ore stats |

`Country/Area` is the GEM-standard naming: it acknowledges that some entries are not sovereign states (Taiwan, Hong Kong SAR, disputed territories, joint zones). Using plain `Country` is technically incorrect for those entries.

The slash-with-spaces (`Country / Area`) appears in Coal Mine and Portal Energetico — the same semantic concept but slightly different formatting.

### The 251-entry country reference set

The `snapshot.country` table defines GEM's canonical country list: 251 entries with `gemName` (the display name used in exports), `isoCode`, `isoCodeAlpha2`, `isoCodeAlpha3`, and geographic parent fields (`region`, `subRegion`, `weoRegion`).

Notable entries:
- Territories (American Samoa, Guam, etc.) are included as distinct rows with `territory = 'yes'` and `territoryOf` pointing to the parent country
- `Joint Petroleum Development Area` — a joint zone with no ISO code
- Some entries have null `region` or `subRegion` (1-2 entries)

The country reference set is the single strongest cross-tracker canonical vocabulary — covered in STD-04.

---

## Region and Subregion

Both fields are **derived** from the Country field via a lookup, not entered directly by researchers. The values come from the DB's country table and correspond to UN M49 geographic groupings:

| Level | Values (count) |
|---|---|
| Region | Africa (60), Americas (57), Europe (52), Asia (51), Oceania (29) |
| Subregion | Sub-Saharan Africa (53), Latin America and the Caribbean (52), Western Asia (18), Southern Europe (17), Northern Europe (16), South-eastern Asia (11), Eastern Asia (8), … |

The DB also stores a `weoRegion` (IEA/IMF World Economic Outlook regions): Asia Pacific, Africa, Europe, Central & South America, Middle East, Eurasia, North America. This doesn't appear in most spreadsheet exports.

The Ownership Tracker additionally uses UN M49 numeric codes: `Country or Area (M49)`, `M49 Country Code`, `Region Code (M49)`, `Sub-region Code (M49)`, `Intermediate Region Code (M49)`. These appear in the Ownership Tracker's entity data but not in asset-level exports.

---

## Subnational Hierarchy (Levels 4–6)

The three sub-country administrative levels have the most naming inconsistency:

| Concept | Coal Plant | Coal Mine | Nuclear/Solar | Iron & Steel | GOGET | GIPT |
|---|---|---|---|---|---|---|
| Primary (province/state) | `Subnational unit (province, state)` | `State, Province` | `State/Province` | `Subnational unit` | `Subnational unit` | `Subnational unit (state, province)` |
| Secondary (prefecture/district) | `Major area (prefecture, district)` | `Prefecture, District` | `Major Area (prefecture, district)` | — | — | `Major area (prefecture, district)` |
| Tertiary (taluk/county) | `Local area (taluk, county)` | — | `Local Area (taluk, county)` | — | — | `Local area (taluk, county)` |

All three names for the primary subnational level refer to the same concept — the largest administrative subdivision of a country (state in the US, province in China, Bundesland in Germany, etc.). The parenthetical explanations in the Coal Plant and GIPT names (`(province, state)`, `(prefecture, district)`, `(taluk, county)`) help users understand the concept but make machine-matching harder.

**`subnationalChecked` boolean in DB**: 25,546 records in `snapshot.powerplant_unit` have `subnationalChecked = True`, indicating a targeted effort to populate and verify subnational data for a subset of records. This internal flag is not exported but explains why some trackers have more complete subnational coverage than others.

---

## Nearest Settlement / Location Name

Two field names are used for the same concept — the name of the nearest city or town:

| Field name | Trackers |
|---|---|
| `Location` | Coal Plant, Coal Mine (free text, sometimes includes industrial park / administrative zone names) |
| `City` | Nuclear, Solar, Wind, Gas, GIPT, Hydro |

Sample values from Coal Plant `Location`: `Wucaiwan Town`, `Economy Development District`, `Xinfa Industrial Park`, `Hwange`, `Grevenbroich`, `Neyveli`. This mixes settlement names, industrial zones, and administrative areas — it is the closest named place to the plant, not necessarily a city.

Coal Mine adds a `Location (Non-ENG)` field (2,580 non-null records) for the local-language location name. There is no corresponding `City (local language)` in other trackers.

---

## Non-Point-Location Asset Types

### Pipelines (GGIT, GOIT)

Linear infrastructure spans multiple countries. GGIT Gas Pipelines duplicates the geographic hierarchy with `Start` and `End` prefixes:

```
StartLocation, StartPrefecture/District, StartState/Province, 
StartCountryOrArea, StartRegion, StartSubRegion
EndLocation, EndPrefecture/District, EndState/Province,
EndCountryOrArea, EndRegion, EndSubRegion
```

No route-level geography exists at the record level — routing detail is in the map layer, not the tabular data. The `RouteAccuracy` field (see STD-09) rates the quality of the route geometry rather than a specific geographic attribute.

### Multi-country infrastructure (Hydro)

Cross-border hydropower plants (shared rivers) use a `Country/Area 1` / `Country/Area 2` pattern with a duplicated geographic hierarchy for each country and a capacity split:

```
Country/Area 1, Country/Area 1 Capacity (MW)
City 1, Local Area 1, Major Area 1, State/Province 1, Subregion 1, Region 1
Country/Area 2, Country/Area 2 Capacity (MW)
City 2, Local Area 2, Major Area 2, State/Province 2, Subregion 2, Region 2
```

The GIPT handles this identically: `Country/area 1 (hydropower only)`, `Country/area 2 (hydropower only)`.

### Geological areas (GOGET)

GOGET uses `Basin` (geological basin name: Permian, Western Gulf, Neuquina, etc.) instead of the standard administrative hierarchy above the field level. Oil and gas fields are identified by their geological basin, not administrative province. GOGET still includes `Country/Area` and `Subnational unit`, but the mid-level geography is geology-based, not administrative.

### No location (Ownership Tracker, production statistics)

The Ownership Tracker has no geographic fields at the asset level — location comes through the join to the asset's primary tracker. The production/consumption statistics tab is country-level aggregate data; geography is encoded only in the country column.

---

## Decision Points

### Decision 1: Standardize the country field name

Four spellings of the same field (`Country/Area`, `Country/area`, `Country / Area`, `Country`) need to converge. The stakes are high: this is the most common join field across trackers and a candidate for cross-tracker querying.

**Proposed standard:** `Country/Area` (title case, no spaces around slash) — matches the majority of trackers and the DB-backed export convention. Map `Country/area`, `Country / Area`, and `Country` to this standard at ETL.

### Decision 2: Standardize subnational level names

The three subnational levels need unified names. Two options:

**Option A — Keep the parenthetical-explainer convention**  
`Subnational unit (province, state)`, `Major area (prefecture, district)`, `Local area (taluk, county)`. Already used in Coal Plant and GIPT; parentheticals help non-expert users understand the level.

**Option B — Clean level names without parentheticals**  
`State/Province`, `Prefecture/District`, `Local area`. Shorter; parentheticals move to field definitions. Already used by Nuclear and Solar.

The parenthetical convention (Option A) makes the field name self-documenting, which is useful in spreadsheets where users may not consult definitions. The clean names (Option B) are more API-friendly.

### Decision 3: Standardize `Location` vs. `City`

These two fields represent the same level but with different semantic assumptions:

- `City` implies an urban settlement with a defined administrative status
- `Location` allows for industrial zones, towns, and approximate place names

**Options:**
- Rename all `Location` fields to `City` for consistency (but accepts the misfit for industrial zone names)
- Rename all `City` fields to `Location` for accuracy (but loses the human-readable clarity of "city")
- Rename to `Nearest named place` or `Locality` — accurate but verbose

Whatever the name, the concept is the same: a human-readable place name that locates the asset below the level of a formal administrative division.

### Decision 4: How to handle the `weoRegion` — export or not?

The World Economic Outlook region grouping (Asia Pacific, Middle East, Eurasia, etc.) is stored in the country table but not exported in most tracker spreadsheets. It differs from the M49 regional grouping (Asia includes Middle East in M49; WEO splits them).

For cross-tracker energy analysis, WEO regions may be more analytically useful than M49 subregions (which are more granular and less aligned with energy-sector norms). Options:
- Export `weoRegion` as an additional column in all tracker exports
- Keep WEO as a DB-level derived field, available via query but not in spreadsheets
- Make it optional per tracker, based on analytical use case

### Decision 5: How should multi-country assets be handled in a unified schema?

The `Country/Area 1` / `Country/Area 2` pattern works for assets that span exactly two countries (most cross-border dams, some pipelines). For assets spanning more countries (long-distance pipelines, regional grids), this pattern doesn't scale.

**Options:**
- **Current approach**: `Country/Area 1` + `Country/Area 2` — handles binary cross-border cases
- **Multi-value `Country/Area`**: allow semicolon-separated values in `Country/Area` for multi-country assets; treat country as multi-value (see STD-02)
- **Separate junction table**: a `{tracker}_country` table with one row per (asset, country, share) — fully relational, but spreadsheet-incompatible
- **Primary country + multi-country flag**: a single `Country/Area` for the primary jurisdiction, plus a boolean `multi_country` and a `Country/Area (all)` multi-value field for the full list

### Decision 6: Should Basin-style geological geography be part of the standard?

GOGET's `Basin` field represents a different geographic ontology — geological rather than administrative. Other trackers don't have an equivalent because their assets don't have meaningful geological basin assignments.

**Options:**
- Treat `Basin` as a tracker-specific field, not part of the standard geographic hierarchy
- Add an optional `geographic_zone` level between Country and Subnational for any tracker where an ecological or geological area is more meaningful than an administrative one (could also apply to offshore wind farms, where `Sea Area` or `Exclusive Economic Zone` is more relevant than a subnational province)

---

## Summary: Geographic Hierarchy by Tracker

| Tracker | Country | Region/Subregion | Primary subnational | Secondary | Tertiary | Settlement | Coordinates |
|---|---|---|---|---|---|---|---|
| Coal Plant (DB) | Y | Y | Y | Y | Y | Y (Location) | Y |
| Nuclear (DB) | Y | Y | Y | Y | Y | Y (City) | Y |
| Solar / Wind (DB) | Y | Y | Y | Y | Y | Y (City) | Y |
| Gas / GIPT | Y | Y | Y | Y | Y | Y (City) | Y |
| Coal Mine | Y | Y | Y | Y | — | Y (Location) | Y |
| Iron & Steel | Y | Y | Y | — | — | Y (Municipality) | — |
| Cement | Y | — | Y | — | — | Y (Municipality) | — |
| GOGET | Y | — | Y | — | — | — | Y |
| GGIT Pipelines | Y (Start/End) | Y (Start/End) | Y (Start/End) | Y (Start/End) | — | Y (Start/End) | — |
| Hydro | Y (×2) | Y (×2) | Y (×2) | Y (×2) | — | Y (×2) | Y |
| GMET | Y | — | — | — | — | — | Y |
| Ownership | — | — | — | — | — | — | — |

---

## Related Standards

- **STD-04: Categorical Allowed Values** — `Country/Area` is the most important canonical reference set
- **STD-02: Multi-value Separators** — multi-country assets using semicolon-separated country lists
- **STD-08: Field Naming Conventions** — parenthetical explainers in geographic field names
- **STD-09: Cross-field Links** — `Location accuracy` as a qualifier for `Latitude` / `Longitude`


---

**Standardization docs:** [Index](index.md) · [STD-01](std-01-null-encoding.md) · [STD-02](std-02-multi-value-separators.md) · [STD-03](std-03-boolean-encoding.md) · [STD-04](std-04-categorical-allowed-values.md) · [STD-05](std-05-numeric-field-purity.md) · [STD-06](std-06-date-year-format.md) · [STD-07](std-07-required-fields-nullability.md) · [STD-08](std-08-field-naming-conventions.md) · [STD-09](std-09-cross-field-links.md) · [STD-10](std-10-imputed-values.md) · [STD-11](std-11-data-provenance-source-fields.md) · [STD-12](std-12-geographic-hierarchy.md) · [STD-13](std-13-temporal-snapshots.md)
