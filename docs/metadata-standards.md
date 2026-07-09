# Metadata Standards Reference

This document records the standards considered for GEM's tracker metadata and data delivery, with rationale for current choices and notes on future compatibility.

---

## Current Stack

### Table Schema (Frictionless Data) — field-level metadata
**Status: adopted**

Governs field-level metadata: name, type, description, constraints, categorical allowed values. Chosen because it directly maps onto the three core needs: internal data validation, front-end field display, and download attribution. The existing GEM metadata structure (built around `data_type`, `data_sub_type`, `allowed_values`, `definition`, etc.) required mostly renaming rather than rebuilding to conform to Table Schema.

Spec: https://specs.frictionlessdata.io/table-schema/

### DCAT (Data Catalog Vocabulary, W3C) — dataset-level metadata
**Status: adopted**

Governs dataset-level metadata: title, publisher, license, temporal coverage, contact. Used for discoverability and attribution on data slices made available for download. Maps closely onto the `header_info` fields already extracted from tracker README/About tabs.

Spec: https://www.w3.org/TR/vocab-dcat/

---

## Standards Under Consideration

### Data Package (Frictionless Data)
**Status: worth adopting when formalizing downloads**

The dataset-level wrapper that pairs naturally with Table Schema. A `datapackage.json` per tracker would point to data files and embed the Table Schema for each resource, making the tracker directly consumable by Frictionless tooling and any data catalog that understands the format.

This is essentially what `metadata/{tracker_slug}.json` already does informally. Formalizing it to the Data Package spec would cost little and make the output machine-readable by a wider ecosystem.

Spec: https://specs.frictionlessdata.io/data-package/

**When to act**: When GEM formalizes CSV/XLSX download packaging. A `datapackage.json` next to each download would be low-effort and high-value.

### schema.org/Dataset
**Status: worth adding to download pages**

Google Dataset Search and other data portals index `schema.org/Dataset` JSON-LD markup. The property set overlaps heavily with DCAT (title, description, creator, license, temporalCoverage, spatialCoverage, distribution). A well-documented DCAT→schema.org crosswalk exists, so this is mostly a serialization step once DCAT metadata is clean.

Adding a `<script type="application/ld+json">` block to each tracker's download page would get GEM data into dataset search engines with minimal ongoing maintenance.

**When to act**: When GEM tracker data appears on public-facing download pages. Low effort; high discoverability payoff.

Spec: https://schema.org/Dataset  
Crosswalk: https://www.w3.org/TR/vocab-dcat/#dcat-sdo

### CSVW (CSV on the Web, W3C)
**Status: monitor; relevant to multi-value separator problem**

W3C standard for annotating CSV files with a companion JSON-LD metadata file (`{filename}-metadata.json`). Notably, CSVW has a field-level `separator` property that specifies the delimiter used within multi-value cells — the only major standard that explicitly models this.

Relevant because GEM trackers have inconsistent multi-value separators across fields and trackers (`&`, `;`, `,`). A CSVW descriptor would encode the intended separator per field, making it machine-parseable downstream.

**When to act**: If GEM formalizes CSV delivery and wants machine-readable multi-value handling. Tooling for CSVW is thinner than Frictionless; evaluate at that point.

Spec: https://www.w3.org/TR/tabular-data-primer/

### DataCite Metadata Schema
**Status: relevant for versioned DOI releases**

Handles versioning, citations, and contributors for research datasets. Maps cleanly onto DCAT. GEM already produces versioned releases (e.g. "Coal Plant Tracker — January 2026"); DataCite would provide a standard way to express version relationships, contributor roles, and persistent identifiers (DOIs).

**When to act**: If GEM begins minting DOIs for tracker releases (e.g. via Zenodo). The metadata is essentially a subset of what DCAT already captures.

Spec: https://schema.datacite.org/

### SDMX (Statistical Data and Metadata eXchange)
**Status: deferred; useful for inter-agency interoperability**

Used by Eurostat, IEA, World Bank, and other statistical agencies for time-series data exchange. SDMX "code lists" are directly analogous to GEM's `allowed_values` — a maintained registry of valid categorical values with labels and definitions.

Not worth adopting internally (significant overhead; tooling is complex), but worth knowing for potential data-exchange agreements with IEA or national statistical offices. If GEM data needs to feed into an SDMX-consuming system, the `allowed_values` structure in Table Schema crosswalks reasonably well.

Spec: https://sdmx.org/

### ISO 19115 / ISO 19139 (Geographic Metadata)
**Status: deferred; crosswalkable later**

The ISO standard for geographic dataset metadata, used by national mapping agencies and GIS platforms (ArcGIS, QGIS metadata tools). Relevant because every GEM tracker has latitude/longitude and country/region fields.

The standard is XML-heavy and the tooling is burdensome unless you're integrating with GIS infrastructure specifically. Not worth adopting now, but Table Schema + DCAT is straightforward to crosswalk to ISO 19115 if a specific GIS platform integration requires it.

Spec: https://www.iso.org/standard/53798.html

### DDI (Data Documentation Initiative)
**Status: deferred indefinitely**

Designed for survey and social-science data. Carries overhead (universes, question text, interviewer instructions) that doesn't apply to GEM's infrastructure tracking data. Table Schema + DCAT is crosswalkable to DDI if a specific stakeholder (e.g. ICPSR or a research archive) requires it.

Spec: https://ddialliance.org/

---

## Compatibility Matrix

Which GEM metadata properties map to which standards:

| GEM field-level property | Table Schema | DCAT | schema.org | CSVW | DataCite |
|---|---|---|---|---|---|
| `name` (display name) | `title` | — | — | `titles` | — |
| `code_friendly_name` | `name` | — | — | `name` | — |
| `definition` | `description` | — | — | `dc:description` | — |
| `data_type` / `data_sub_type` | `type` / `format` | — | — | `datatype` | — |
| `allowed_values` | `constraints.enum` | — | — | — | — |
| `is_required` | `constraints.required` | — | — | `required` | — |
| `multiple_values_separator` | — | — | — | `separator` | — |
| `required_format_regex` | `constraints.pattern` | — | — | — | — |
| `unit_name_short` | `--` (no native unit field) | — | — | — | — |

| GEM dataset-level property | DCAT | schema.org/Dataset | DataCite | Dublin Core |
|---|---|---|---|---|
| Tracker title | `dct:title` | `name` | `titles` | `dc:title` |
| Citation / publisher | `dct:publisher` | `publisher` | `publisher` | `dc:publisher` |
| License | `dct:license` | `license` | `rightsList` | `dc:rights` |
| Contact | `dcat:contactPoint` | `contactPoint` | `contributors` | — |
| Temporal coverage | `dct:temporal` | `temporalCoverage` | `dates` | `dc:coverage` |
| Tracker version / release date | `dct:issued` / `owl:versionInfo` | `version` | `version` | `dc:date` |
| Geographic coverage | `dct:spatial` | `spatialCoverage` | `geoLocations` | — |

---

## Notes on Table Schema Gaps

Two GEM-specific properties have no direct Table Schema equivalent and are handled as extensions:

- **`unit_name_short` / `unit_name_long`**: Table Schema doesn't have a unit field. These are currently stored as custom properties. When/if GEM adopts Data Package, these can be expressed in the `dialect` or as custom `x-` prefixed properties.
- **`taxonomy`**: Cross-tracker semantic tags (`unit`, `location`, `status`, etc.). No equivalent in any of the above standards; this is GEM-specific and should be maintained as a custom property regardless of which standard is adopted.
