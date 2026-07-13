---
layout: default
title: "IOP-03: Status"
---

# IOP-03: Status

**Status:** Draft — for discussion with Data Team  
**Scope:** Status vocabulary, value sets, and lifecycle encoding across trackers

---

## Inventory

### The 4-group framework

The Ownership API established a canonical four-group status hierarchy that already applies across most trackers. All raw status values are treated as sub-statuses that roll up to one of these groups:

| Group | Sub-statuses |
|---|---|
| **Operating** | operating, operating pre-retirement, mixed status |
| **Planned** | announced, pre-permit, permitted, pre-construction, construction, proposed, unknown |
| **Cancelled** | shelved, shelved (inferred), cancelled, cancelled (inferred) |
| **Retired** | mothballed, mothballed pre-retirement, retired, idle, abandoned, demolished, historic landmark, reclamation, rehabilitation, renewable energy site, repurpose |

### Sub-status vocabulary by tracker

Most DB-backed power trackers share the same sub-status set:

**Standard set** (Coal Plant, Nuclear, Solar, Wind, Hydro, Geothermal, Bioenergy, GOGPT):
`operating` · `announced` · `pre-permit` · `permitted` · `pre-construction` · `construction` · `shelved` · `shelved - inferred 2 y` · `cancelled` · `cancelled - inferred 4 y` · `mothballed` · `retired`

**Divergences:**

| Tracker | Status field | Notable differences |
|---|---|---|
| Gas Pipelines (GGIT) | `Status` | `proposed` instead of multi-stage pre-construction; `idle` instead of `mothballed`; `mixed status` for segments with varying statuses |
| LNG Terminals (GGIT) | `Status` | `proposed`, `idled` (note spelling variant) |
| Oil/NGL Pipelines (GOIT) | `Status` | `proposed`, `idle` |
| Coal Mine | `Status` + `Status Detail` + `Mine Site Status` | Three separate fields (see below) |
| Coal Terminals | `Status` | Title Case values; `Proposed` instead of multi-stage |
| GOGET | `Status` + `Status detail` | `operating`, `in-development`, `discovered`, `mothballed`; detail field has production-phase values (`ramp up`, `actual`, `decline`) |
| Iron & Steel | `Status` (plant) + `Unit status` | `operating pre-retirement`, `mothballed pre-retirement` as explicit transitional states |
| Cement | `Operating status` | Different field name; includes `operating pre-retirement`, `unknown` |
| Iron Ore | `Operating status` | Different field name; includes `unknown` |
| LNG Carrier | `Status` | Vessel lifecycle: `active`, `on order`, `proposed` |
| GMET | `Status` | Title Case; subset of standard values |
| Finance trackers | `Financing Status`, `FID Status` | Separate fields for deal lifecycle, not asset lifecycle |

### Coal Mine's three-field structure

Coal Mine splits status across three fields rather than using sub-statuses:

- **`Status`** — broad current state: `Operating`, `Mothballed`, `Closed`
- **`Status Detail`** — lifecycle stage for non-operating mines: `Announced`, `Pre-Permit`, `Permitted`, `Construction`, `Care and Maintenance`, `Test Operation`, `Exploration`
- **`Mine Site Status`** — post-closure land use: `Abandoned`, `Rehabilitation`, `Reclamation`, `Renewable energy site`, `Demolished`, `Historic Landmark/Museum`, `Repurpose`, `Other`

This reflects the same logical hierarchy as the 4-group framework (broad group → sub-status), but the split is implemented as separate fields rather than group + sub-status fields. `Mine Site Status` maps to the Retired group; it captures post-closure land use that other trackers don't track.

---

## Interoperability Gaps

**Case inconsistency.** DB-backed power trackers use lowercase (`operating`, `cancelled`). Coal Mine, Coal Terminals, and GMET use Title Case (`Operating`, `Cancelled`). These don't match as strings even when the concept is identical.

**`proposed` compresses the pre-construction sequence.** Pipeline and terminal trackers use a single `proposed` status where power trackers distinguish up to four stages (`announced` → `pre-permit` → `permitted` → `pre-construction`). This is intentional — pipelines don't follow the same permitting sequence — but means `proposed` can't be mapped to a single power-tracker sub-status. It maps correctly to the Planned group.

**`idle` vs. `mothballed`.** GGIT and GOIT use `idle`; all other trackers use `mothballed` for the same concept. Both map to the Retired group. The spelling variant `idled` also appears in LNG Terminals.

**GOGET's vocabulary is partially unmapped.** `discovered` and `in-development` don't appear in any other tracker or the Ownership API taxonomy. Both would likely map to the Planned group, but the extraction project lifecycle is different enough from infrastructure construction that the mapping needs PM input. The `Status detail` field (production phase: `ramp up`, `actual`, `decline`) has no equivalent in any other tracker.

**Coal Mine's structure doesn't port to other tracker types.** The three-field approach captures useful distinctions (especially post-closure land use) but the field boundaries don't align with other trackers. `Status Detail` stages like `Exploration` and `Care and Maintenance` have no equivalents elsewhere.

**`unknown` appears in some trackers but not others.** `unknown` / `Unknown` appears in Cement, Iron Ore, and the Ownership Tracker. It maps to the Planned group in the API taxonomy, which is counterintuitive — an unknown status could mean anything. This mapping reflects a pragmatic grouping choice rather than a semantic one.

---

## Decisions Needed

### Naming and field conventions

**Standardize the status field name.** `Status` is used by most trackers; `Operating status` is used by Cement and Iron Ore. These refer to the same concept. `Status` is the standard.

**Standardize case.** All sub-status values should be lowercase. Coal Mine, Coal Terminals, and GMET need to update their exports.

**Standardize `idle` → `mothballed`.** These are the same concept. GGIT and GOIT should use `mothballed` for consistency; `idle` should be deprecated.

### Schema and architecture

**Adopt the 4-group + sub-status pattern as the standard.** The Ownership API's two-level structure (group + raw sub-status) is the right model: it enables cross-tracker rollup queries while preserving tracker-specific granularity. All trackers should expose both levels — a `status_group` (Operating / Planned / Cancelled / Retired) and the raw `status` value.

**Resolve Coal Mine's three-field structure.** The options:
- **Adapt it as a model** — formalize `Status` as the group field and `Status Detail` as the sub-status field, mapping their values to the standard vocabulary where possible; treat `Mine Site Status` as a tracker-specific extension
- **Flatten to the standard two levels** — merge `Status` and `Status Detail` into a single sub-status field following the standard vocabulary; add `Mine Site Status` as a separate `post_closure_land_use` field
- **Leave as-is and map at query time** — document the mapping from Coal Mine's three fields to the 4-group framework; accept that Coal Mine won't natively expose a standard status field

**Define the GOGET mapping.** `discovered` and `in-development` need explicit placement in the sub-status vocabulary (likely Planned), confirmed with the GOGET PM. The `Status detail` production-phase field is probably outside the scope of the lifecycle status standard and should be documented separately.

### Governance and process

**Inferred status rules.** The `shelved - inferred 2 y` and `cancelled - inferred 4 y` values are automatically assigned based on time since last activity. The rules (2 years → shelved, 4 years → cancelled) are applied consistently across DB-backed trackers but are not documented in tracker metadata. These rules should be formally documented as part of the status standard.

**`unknown` placement.** The Planned group placement of `unknown` in the API taxonomy is a pragmatic decision. The team should confirm this is intentional and document why, so future trackers with unknown status values apply it consistently.

---

## Related Topics

- **STD-04: Categorical Allowed Values** — status is the most important categorical field; allowed value governance applies directly
- **STD-10: Imputed Values** — `shelved - inferred` and `cancelled - inferred` are computed, not researched values
- **IOP-06: Temporal** — `Status year` in GOGET and GMET; lifecycle year fields (`Start year`, `Retired year`) that mark status transitions
- **IOP-01: IDs** — Coal Mine composite key uses Status as part of the row identifier

---

**Interoperability topics:** [Index](index.md) · [IOP-01: IDs](iop-01-ids.md) · [IOP-02: Names](iop-02-names.md) · [IOP-03: Status](iop-03-status.md) · [IOP-04: Capacity](iop-04-capacity.md) · [IOP-05: Location](iop-05-location.md) · [IOP-06: Temporal](iop-06-temporal.md) · [IOP-07: Entities](iop-07-entities.md)
