---
layout: default
title: Standardization Documentation
---

# GEM Tracker Metadata — Standardization Docs

The [audit tool](/) shows per-tracker field statistics, compliance flags, and cross-tracker field comparisons.

---

## Interoperability Topics

These documents examine how the 7 key field categories work across trackers — where schemas align well enough to join, and where they diverge in ways that would block a unified query.

| # | Topic | Scope |
|---|---|---|
| [IOP-01](iop-01-ids.md) | **Identifier Systems** | GEM-assigned IDs, external reference IDs, cross-tracker linking |
| [IOP-02](iop-02-names.md) | **Names** | Display names, aliases, deduplication |
| [IOP-03](iop-03-status.md) | **Status** | Status vocabulary, value sets, lifecycle encoding |
| [IOP-04](iop-04-capacity.md) | **Capacity / Size** | Capacity, throughput, production volume, and physical size fields |
| [IOP-05](iop-05-location.md) | **Location** | Geographic fields — coordinate systems, accuracy, hierarchy |
| [IOP-06](iop-06-temporal.md) | **Temporal** | Start/end years, date precision, time-varying field patterns |

---

## Standardization Topics

These documents cover field-level encoding conventions — how individual values should be represented within a tracker.

| # | Topic | Key questions |

| # | Topic | Key questions |
|---|---|---|
| [STD-01](std-01-null-encoding.md) | **Null / Missing Value Encoding** | `--` vs. `N/A` vs. empty cell; "doesn't apply" vs. "don't know" |
| [STD-02](std-02-multi-value-separators.md) | **Multi-value Separators** | `;` vs. `,` vs. `&`; which fields are multi-value |
| [STD-03](std-03-boolean-encoding.md) | **Boolean Encoding** | `yes/no` vs. `True/False` vs. `Y/N`; "not found" as third value |
| [STD-04](std-04-categorical-allowed-values.md) | **Categorical Allowed Values** | Status vocab across trackers; case normalization; governance |
| [STD-05](std-05-numeric-field-purity.md) | **Numeric Field Purity** | `-`, `N/A`, `>0`, `*` in numeric fields |
| [STD-06](std-06-date-year-format.md) | **Date / Year Format** | `YYYY` vs. `YYYY-MM-DD`; mixed precision; fiscal years; estimates |
| [STD-07](std-07-required-fields-nullability.md) | **Required Fields / Nullability** | What's actually required; where enforcement lives |
| [STD-08](std-08-field-naming-conventions.md) | **Field Naming Conventions** | Units in names; camelCase vs. Title Case; `[ref]` vs. `Data Source` |
| [STD-09](std-09-cross-field-links.md) | **Cross-field Links** | Accuracy qualifier fields; year-of companions; linking mechanisms |
| [STD-10](std-10-imputed-values.md) | **Imputed Values** | `>0`; inferred status; planned years; ownership share imputation |
| [STD-11](std-11-data-provenance-source-fields.md) | **Data Provenance / Source Fields** | Wiki URL; `{Field} Data Source`; `[ref]`; Research Status |
| [STD-12](std-12-geographic-hierarchy.md) | **Geographic Hierarchy** | Country/Area naming; subnational levels; multi-country assets |
| [STD-13](std-13-temporal-snapshots.md) | **Temporal Snapshots / "As Of" Dating** | Release-date snapshots; annual series; `Status year` pattern |

---

## Background

- **Target metadata standards:** [Table Schema](https://specs.frictionlessdata.io/table-schema/) (field-level) + [DCAT](https://www.w3.org/TR/vocab-dcat/) (dataset-level)
- **Gold-standard metadata:** Coal Plant and Coal Mine trackers (documented for front-end tooling)
- **Research DB:** Django/PostgreSQL with DuckDB snapshot; covers combustion, gas, solar, wind, nuclear, geothermal, steel, hydro, LNG, GOGET, coal, bioenergy
- **Trackers not in research DB:** Coal Finance, Chemicals, Iron Ore Mines, Cement, Coal Terminals, Coal Mines (separate system), Portal Energetico
