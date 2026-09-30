"""
qc_check.py

Runs standardization QC checks against a live Google Sheet and reports every
failing cell, grouped by the check that caught it, so a PM can go fix the cell.

Which checks run is NOT hardcoded. It is read at runtime from
docs/decision-log.md: an STD item whose Status says it was *proposed* (by the
group or by Taylor) is active; anything "not yet reviewed" is scaffolded but
skipped. Every STD-01..STD-13 has a function with the same signature, so
turning one on later means filling in a stub, not rewiring the gate.

Outputs:
  qc/issues.csv   one row per flagged cell, with an A1 reference
  qc/report.html  the same findings grouped by check, for reading/sharing
  qc/baselines/{tracker}.json   STD-04 categorical value history per tracker

Run:
  pip3 install gspread google-auth google-auth-oauthlib
  python3 qc_check.py --sheet <google-sheets-url-or-id>
  python3 qc_check.py --sheet <url> --record-release 2026-09-23

Related: analyze.py runs similar heuristics over the whole SQLite corpus.
This script is the single-sheet, pre-release, fix-the-cell counterpart.
"""

import argparse
import csv
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DECISION_LOG_PATH = Path("docs/decision-log.md")
REFERENCES_PATH = Path("reference_sets.json")
OUTPUT_DIR = Path("qc")
BASELINE_DIR = OUTPUT_DIR / "baselines"
DEFAULT_CREDENTIALS = Path("authorized_user.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Kept in sync with ingest.py / extract_metadata.py
METADATA_TAB_NAMES = {
    "readme", "about", "metadata", "notes", "dictionary", "instructions",
    "data dictionary", "acronyms", "copyright", "introduction terminology",
    "column key",
}

# --- Standard values, per the decision log -------------------------------

# STD-01: the four tokens allowed to stand for a missing value.
STD_01_ALLOWED_MISSING = {"not found", "not applicable", "null", "not available"}
STD_01_DEFAULT_MISSING = "not found"
STD_02_SEPARATOR = ";"
# STD-03: no true booleans any more — a categorical set that may grow.
STD_03_ALLOWED = {"true", "false", "unknown", "not found"}
STD_06_DATE_FORMAT = "YYYY-MM-DD"
# STD-08 / STD-09: every companion field is `{Field} | {Companion Information}`.
COMPANION_SEP = " | "
# STD-07: the universal minimum publish bar.
STD_07_REQUIRED = ("id", "name", "country", "status", "geometry")
# STD-12: the standard location headers, in hierarchy order.
STD_12_LOCATION_HEADERS = (
    "Region", "Subregion", "Country/Area", "Subnational Unit",
    "Major area (prefecture, district)", "Local area (taluk, county)",
    "Nearest City", "Lat_Lon", "Address",
)
STD_12_RENAMES = {
    "location": "Address",
    "city": "Nearest City",
    "country": "Country/Area",
    "country/area ": "Country/Area",
}

# Tokens that stand in for "no value". Anything here in a categorical column
# should be `not found`; anything here in a numeric column should be blank.
NULL_PROXY_TOKENS = {
    "-", "--", "---", "n/a", "na", "n.a.", "#n/a", "none", "null", "nil",
    "not found",
    "unknown", "unspecified", "not available", "not applicable", "not reported",
    "no data", "nodata", "tbd", "to be determined", "*", "?", "??", "x",
    "not researched", "undetermined", "blank", "empty",
}

EXCEL_ERRORS = {"#n/a", "#ref!", "#value!", "#div/0!", "#name?", "#null!", "#num!"}

# Headers that must never reach a public export (STD-11).
RESEARCHER_HEADER_HINTS = (
    "researcher", "analyst", "contributor", "created by", "updated by",
    "author", "editor", "reviewer", "assigned to", "entered by",
)
# Per-row release dating that STD-13 moves into metadata.
RELEASE_DATE_HINTS = (
    "release date", "snapshot date", "as of date", "as-of date", "data as of",
    "version date", "export date", "release version", "download date",
)
# Legacy companion suffixes that STD-09 replaces with the pipe pattern.
LEGACY_COMPANION_PATTERNS = (
    (re.compile(r"^(.*?)\s*\[ref\]$", re.I), "Ref"),
    (re.compile(r"^(.*?)\s+data\s*source$", re.I), "Ref"),
    (re.compile(r"^(.*?)[\s_]+ref$", re.I), "Ref"),
    (re.compile(r"^(.*?)[\s_]+reason$", re.I), "Reason"),
    (re.compile(r"^(.*?)[\s_]+accuracy$", re.I), "Accuracy"),
    (re.compile(r"^(.*?)[\s_]+year$", re.I), "Year"),
    (re.compile(r"^(.*?)[\s_]+source$", re.I), "Ref"),
)
PLURALITY_HINT_RE = re.compile(r"\(s\)\s*$|\(s\)")
CONVERSION_PAREN_RE = re.compile(r"\((fuel|gem unit id|unit/phase|location|type)\)", re.I)
CAMEL_CASE_RE = re.compile(r"^[A-Za-z]+(?:[A-Z][a-z0-9]+)+$")

BOOLEAN_TOKEN_MAP = {
    "true": "true", "t": "true", "yes": "true", "y": "true", "1": "true",
    "false": "false", "f": "false", "no": "false", "n": "false", "0": "false",
}

CATEGORICAL_MAX_DISTINCT = 60
CATEGORICAL_MAX_LEN = 80
NUMERIC_COLUMN_THRESHOLD = 0.70
DATE_COLUMN_THRESHOLD = 0.60

UNIT_PARENTHETICAL_RE = re.compile(
    r"\((?:mw|mwt|mwh|gw|gwh|kw|kwh|mt|mtpa|ttpa|mtoe|bcm|bcm/y|boed|km|m|m3|"
    r"tonnes?|t/yr|mt/yr|us\$\s*million|usd|million|billion|years?|%|ktpa|kt)\)",
    re.I,
)
GEO_EXPLAINER_RE = re.compile(
    r"\([^)]*\b(taluk|county|prefecture|district|province|state|municipality|"
    r"oblast|departamento|commune|canton|parish)\b[^)]*\)",
    re.I,
)

YEAR_HEADER_HINTS = (
    "year", "start", "retired", "retirement", "announced", "proposal",
    "construction", "cancelled", "canceled", "shelved", "commissioned",
    "mothballed", "opening", "closing", "operating since",
)
DATE_HEADER_HINTS = ("date", "last updated", "updated", "as of", "asof")
PERCENT_HEADER_HINTS = ("%", "percent", "share", "fraction", "ratio", "pct")
FREETEXT_HEADER_HINTS = (
    "note", "notes", "comment", "comments", "description", "definition",
    "methodology", "summary", "detail", "details", "remark", "address",
    "citation", "quote",
)
URL_HEADER_HINTS = ("url", "link", "wiki", "http", "source", "ref", "website")
GEOMETRY_HEADER_HINTS = ("wkt", "geometry", "geojson", "polygon", "coordinates")

NUMERIC_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
COORD_PAIR_RE = re.compile(r"^[+-]?\d+\.\d+\s*,\s*[+-]?\d+\.\d+$")
RANGE_RE = re.compile(r"^\s*[+-]?[\d,.]+\s*(?:-|–|—|to)\s*[+-]?[\d,.]+\s*$", re.I)
QUALIFIED_RE = re.compile(r"^\s*(?:[<>]=?|~|≈|ca\.?|approx\.?|about)\s*[\d,.]+\s*$", re.I)
THOUSANDS_RE = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")
CURRENCY_RE = re.compile(r"^\s*[$€£¥]\s*[\d,.]+\s*$")
TRAILING_UNIT_RE = re.compile(r"^\s*([+-]?[\d,.]+)\s*([a-zA-Z%/$]+[\w/%]*)\s*$")

BARE_YEAR_RE = re.compile(r"^(1[5-9]\d{2}|20\d{2}|21\d{2})$")
FLOAT_YEAR_RE = re.compile(r"^(1[5-9]\d{2}|20\d{2}|21\d{2})\.0+$")
FISCAL_YEAR_RE = re.compile(r"^(1[5-9]\d{2}|20\d{2})\s*[-/]\s*(\d{2}|\d{4})$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T]\d{2}:\d{2}(:\d{2})?(\.\d+)?$")
SLASH_YMD_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
SLASH_MDY_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
DOT_DMY_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
LONGHAND_DATE_RE = re.compile(
    r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}$"
    r"|^\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+\d{4}$",
    re.I,
)
EXCEL_SERIAL_RE = re.compile(r"^\d{5}(\.\d+)?$")

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


# =========================================================================
# Small helpers
# =========================================================================

def slugify(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", "_", text)
    return text.strip("_")


def normalize_col(name):
    """Strip newlines and collapse whitespace in a column name."""
    if name is None:
        return ""
    return re.sub(r"\s+", " ", str(name).strip())


def col_letter(idx):
    """0-based column index -> spreadsheet letter (0 -> A, 26 -> AA)."""
    letters = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def is_blank(val):
    return val is None or str(val).strip() == ""


def is_numeric(val):
    if is_blank(val):
        return False
    s = str(val).strip()
    return bool(NUMERIC_RE.match(s)) or bool(THOUSANDS_RE.match(s))


def to_float(val):
    s = str(val).strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def header_has(header, hints):
    low = header.lower()
    return any(h in low for h in hints)


def strip_parentheticals(header):
    return re.sub(r"\s*\([^)]*\)", "", header).strip()


# =========================================================================
# Findings
# =========================================================================

class Finding:
    """One thing a person needs to go fix (or at least look at)."""

    __slots__ = (
        "check_id", "check_title", "severity", "scope", "sheet", "cell",
        "row", "column", "column_letter", "value", "problem", "suggested_fix",
        "decision", "rename_to",
    )

    def __init__(self, check_id, severity, sheet, column, problem,
                 suggested_fix="", value="", row=None, column_letter="",
                 scope="cell", rename_to=""):
        self.check_id = check_id
        self.check_title = ""       # filled in from the decision log
        self.decision = ""          # filled in from the decision log
        self.severity = severity
        self.scope = scope
        self.sheet = sheet
        self.column = column
        self.column_letter = column_letter
        self.row = row
        self.cell = f"{column_letter}{row}" if column_letter and row else ""
        self.value = "" if value is None else str(value)
        self.problem = problem
        self.suggested_fix = suggested_fix
        # Set only when the fix is literally "call this column something else",
        # which is what --rename-plan collects. Advice like "drop this column"
        # or "merge these two" is not a rename and leaves this empty.
        self.rename_to = rename_to

    def as_row(self):
        return {
            "check_id": self.check_id,
            "check_title": self.check_title,
            "severity": self.severity,
            "scope": self.scope,
            "sheet": self.sheet,
            "cell": self.cell,
            "row": self.row if self.row else "",
            "column": self.column,
            "column_letter": self.column_letter,
            "value": self.value,
            "problem": self.problem,
            "suggested_fix": self.suggested_fix,
            "decision": self.decision,
        }


def cell_finding(check_id, severity, prof, row, value, problem, fix=""):
    return Finding(
        check_id, severity, prof.sheet, prof.header, problem,
        suggested_fix=fix, value=value, row=row,
        column_letter=prof.letter, scope="cell",
    )


def column_finding(check_id, severity, prof, problem, fix="", rename_to=""):
    return Finding(
        check_id, severity, prof.sheet, prof.header, problem,
        suggested_fix=fix, column_letter=prof.letter, scope="column",
        rename_to=rename_to,
    )


# =========================================================================
# Decision log — this is what decides which checks run
# =========================================================================

ROW_ID_RE = re.compile(r"^\|\s*(STD-\d{2})\s*\|")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
# A cell break is an unescaped pipe. `\|` inside a cell is literal content —
# the companion-field syntax (`Start Year \| Ref`) is full of them.
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
HEADER_CELL_ALIASES = {
    "id": "id", "item": "item", "decision": "decision", "status": "status",
    "detail": "detail", "detail / rationale": "detail", "rationale": "detail",
    "pattern": "item", "question": "item", "#": "id",
}


def split_md_row(line):
    """Split a markdown table row into cells, honouring escaped pipes."""
    cells = CELL_SPLIT_RE.split(line.strip().strip("|"))
    return [c.strip().replace("\\|", "|") for c in cells]


def strip_md(text):
    text = LINK_RE.sub(r"\1", text)
    text = text.replace("<br>", " ").replace("**", "")
    return re.sub(r"\s+", " ", text).strip()


def status_is_active(status):
    """A check is active once a decision has actually been recorded for it.

    The log's vocabulary has changed once already (the Sep 2026 rewrite moved
    everything from 'Proposed by group' to 'Final'), so both are accepted.
    'Not yet reviewed' always wins, and an empty status is never active.
    """
    low = status.lower()
    if not low or "not yet reviewed" in low:
        return False
    if "not reviewed" in low or "no decision" in low:
        return False
    return "final" in low or "proposed" in low or "accepted" in low or "agreed" in low


def parse_header_row(line):
    """-> {column_name: index} if this row is a table header, else None."""
    cells = [c.lower() for c in split_md_row(line)]
    mapped = {HEADER_CELL_ALIASES[c]: i for i, c in enumerate(cells)
              if c in HEADER_CELL_ALIASES}
    if "id" in mapped and "status" in mapped:
        return mapped
    return None


def parse_decision_log(path):
    """Read docs/decision-log.md -> {std_id: {...}} including the active flag.

    Columns are located by the table's own header row rather than by position,
    because the table has already been restructured once (it dropped its
    Detail column in the Sep 2026 rewrite) and will likely change again.
    """
    if not path.exists():
        sys.exit(f"Decision log not found at {path} — pass --decision-log.")

    items, cols = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        header = parse_header_row(line) if line.lstrip().startswith("|") else None
        if header:
            cols = header
            continue

        m = ROW_ID_RE.match(line)
        if not m:
            continue
        std_id = m.group(1)
        if std_id in items:        # first table wins; later tables are sub-tables
            continue

        cells = split_md_row(line)
        idx = cols or {"id": 0, "item": 1, "decision": 2, "status": len(cells) - 1}

        # A row with more cells than the header has columns contains an
        # unescaped `|` inside a cell — the companion syntax written as
        # `Start Year | Ref` instead of `Start Year \| Ref`. That row renders
        # wrong on the site too, but the gate should still read it: fold the
        # overflow back into the prose column it almost certainly came from.
        n_extra = len(cells) - (max(idx.values()) + 1)
        if n_extra > 0 and "decision" in idx:
            d = idx["decision"]
            cells = (cells[:d] + ["|".join(cells[d:d + n_extra + 1])]
                     + cells[d + n_extra + 1:])
        if max(idx.values()) >= len(cells):
            continue

        def cell(key, default=""):
            return strip_md(cells[idx[key]]) if key in idx else default

        status = cell("status")
        items[std_id] = {
            "id": std_id,
            "title": cell("item"),
            "decision": cell("decision"),
            "detail": cell("detail"),
            "status": status,
            "active": status_is_active(status),
        }
    if not items:
        sys.exit(f"No STD-NN rows found in {path} — has the table format changed?")
    return items


# =========================================================================
# Google Sheets input
# =========================================================================

SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def extract_sheet_id(ref):
    """Accept a full share URL or a bare spreadsheet ID."""
    m = SHEET_ID_RE.search(ref)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", ref.strip()):
        return ref.strip()
    sys.exit(f"Could not read a spreadsheet ID out of: {ref}")


def open_spreadsheet(sheet_ref, credentials_path):
    """Authorize against the Sheets API and open the spreadsheet.

    Tries, in order: a service-account key, a stored authorized-user file,
    then gspread's interactive OAuth flow.
    """
    try:
        import gspread
    except ImportError:
        sys.exit(
            "gspread is not installed. Run:\n"
            "  pip3 install gspread google-auth google-auth-oauthlib"
        )

    client = None
    path = Path(credentials_path)
    if path.exists():
        try:
            kind = json.loads(path.read_text(encoding="utf-8")).get("type")
        except (ValueError, OSError):
            kind = None
        if kind == "service_account":
            from google.oauth2.service_account import Credentials
            client = gspread.authorize(
                Credentials.from_service_account_file(str(path), scopes=SCOPES))
        else:
            from google.oauth2.credentials import Credentials
            client = gspread.authorize(
                Credentials.from_authorized_user_file(str(path), SCOPES))
    else:
        client = gspread.oauth(scopes=SCOPES)

    return client.open_by_key(extract_sheet_id(sheet_ref))


def read_tabs(spreadsheet, header_row, include, exclude):
    """-> [(tab_name, header_list, rows)] for the data tabs worth checking."""
    tabs = []
    for ws in spreadsheet.worksheets():
        name = ws.title
        low = name.strip().lower()
        if include and low not in {i.lower() for i in include}:
            continue
        if not include:
            if low in METADATA_TAB_NAMES or low.startswith("about"):
                print(f"  skipping metadata tab: {name}")
                continue
        if exclude and low in {e.lower() for e in exclude}:
            print(f"  skipping (excluded): {name}")
            continue

        values = ws.get_all_values()
        if len(values) <= header_row:
            print(f"  skipping (no data rows): {name}")
            continue

        header = [normalize_col(h) for h in values[header_row - 1]]
        rows = values[header_row:]
        tabs.append((name, header, rows))
        print(f"  read tab '{name}': {len(rows):,} rows x {len(header)} columns")
    return tabs


# =========================================================================
# Column profiling — decides which checks even apply to a column
# =========================================================================

class ColumnProfile:
    """Everything the checks need to know about one column of one tab.

    `cells` is [(spreadsheet_row_number, raw_value)] for non-blank cells only,
    so every finding can carry a real A1 reference back to the sheet.
    """

    __slots__ = (
        "sheet", "header", "index", "letter", "cells", "n_rows", "n_blank",
        "values", "lower_values", "distinct", "n_numeric", "n_null_proxy",
        "role", "is_percent", "is_companion", "sibling_headers",
    )

    def __init__(self, sheet, header, index, column_values, first_row,
                 sibling_headers):
        self.sheet = sheet
        self.header = header
        self.index = index
        self.letter = col_letter(index)
        self.sibling_headers = sibling_headers
        self.n_rows = len(column_values)

        self.cells = [
            (first_row + i, str(v).strip())
            for i, v in enumerate(column_values)
            if not is_blank(v)
        ]
        self.n_blank = self.n_rows - len(self.cells)
        self.values = [v for _, v in self.cells]
        self.lower_values = [v.lower() for v in self.values]
        self.distinct = sorted(set(self.values))
        self.n_null_proxy = sum(1 for v in self.lower_values if v in NULL_PROXY_TOKENS)
        self.n_numeric = sum(1 for v in self.values if is_numeric(v))

        self.is_percent = header_has(header, PERCENT_HEADER_HINTS)
        low_h = header.lower()
        self.is_companion = (
            "|" in header                      # the STD-08/09 pipe pattern
            or low_h.endswith(" reason") or low_h.endswith("_reason")
            or low_h.endswith("data source") or low_h.endswith("[ref]")
        )
        self.role = self._infer_role()

    @property
    def real_values(self):
        """Cells that hold an actual value — null proxies excluded."""
        return [(r, v) for r, v in self.cells if v.lower() not in NULL_PROXY_TOKENS]

    def _infer_role(self):
        """One of: boolean, year, date, numeric, categorical, text, empty.

        Order matters. Boolean before categorical (a yes/no column is also a
        2-value categorical). Date/year before numeric (a year is a number).
        """
        real = self.real_values
        if not real:
            return "empty"
        vals = [v for _, v in real]
        lows = {v.lower() for v in vals}
        n = len(vals)

        unit_named = bool(UNIT_PARENTHETICAL_RE.search(self.header))

        # Boolean if every real value maps onto True/False. The raw tokens may
        # be mixed (yes/Y/TRUE) — what matters is where they land. The 0/1
        # guard keeps percentage columns out, per the STD-03 draft.
        if lows and lows <= set(BOOLEAN_TOKEN_MAP):
            if not (lows <= {"0", "1"} and (self.is_percent or unit_named)):
                return "boolean"

        if header_has(self.header, GEOMETRY_HEADER_HINTS):
            return "text"
        if header_has(self.header, URL_HEADER_HINTS) and not self.is_percent:
            if sum(1 for v in vals if "http" in v.lower()) > n * 0.3:
                return "text"

        n_date = sum(1 for v in vals if looks_like_date(v))
        n_year = sum(1 for v in vals if BARE_YEAR_RE.match(v) or FLOAT_YEAR_RE.match(v))
        # A header naming a year or a date is the strongest signal there is: a
        # badly broken year column is still a year column, and still needs
        # checking as one. A unit parenthetical means it is a measurement
        # ("Plant age (years)"), not a date.
        year_named = header_has(self.header, YEAR_HEADER_HINTS) and not unit_named
        date_named = header_has(self.header, DATE_HEADER_HINTS) and not unit_named

        if date_named and (n_date or n_year):
            return "date" if n_date >= n_year else "year"
        if year_named and (n_year or n_date):
            return "year" if n_year >= n_date else "date"
        if not year_named and not date_named and n_date > n * DATE_COLUMN_THRESHOLD:
            return "date"

        if self.n_numeric > n * NUMERIC_COLUMN_THRESHOLD:
            return "numeric"
        if header_has(self.header, FREETEXT_HEADER_HINTS):
            return "text"

        if (len(lows) <= CATEGORICAL_MAX_DISTINCT
                and max(len(v) for v in vals) <= CATEGORICAL_MAX_LEN
                and len(lows) < n):
            return "categorical"
        return "text"


def looks_like_date(val):
    return bool(
        ISO_DATE_RE.match(val) or ISO_DATETIME_RE.match(val)
        or SLASH_YMD_RE.match(val) or SLASH_MDY_RE.match(val)
        or DOT_DMY_RE.match(val) or LONGHAND_DATE_RE.match(val)
    )


def profile_tab(sheet_name, header, rows, header_row):
    """-> [ColumnProfile], one per named column."""
    profiles = []
    for idx, name in enumerate(header):
        if not name:
            continue
        column_values = [r[idx] if idx < len(r) else "" for r in rows]
        profiles.append(
            ColumnProfile(sheet_name, name, idx, column_values,
                          header_row + 1, header)
        )
    return profiles


# =========================================================================
# Reference sets (used by STD-02 and as the STD-04 fallback)
# =========================================================================

def load_reference_sets(path=REFERENCES_PATH):
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: {str(v).strip().lower() for v in vals} for k, vals in raw.items()}


def reference_set_for(header, ref_sets):
    """-> (set_of_lowercase_values, set_name) or (None, None). Mirrors analyze.py."""
    low = header.lower()
    if "country" in low or "country_area" in low:
        return ref_sets.get("country"), "country"
    if "status" in low:
        return ref_sets.get("status"), "status"
    if "fuel" in low:
        return ref_sets.get("fuel_category"), "fuel_category"
    return None, None


def all_reference_values(ref_sets):
    out = set()
    for vals in ref_sets.values():
        out |= vals
    return out


# =========================================================================
# CHECKS
#
# Every check has the same signature:
#     check_std_NN(profiles, ctx) -> list[Finding]
#
# `profiles` is every ColumnProfile for one tab; `ctx` carries the reference
# sets, the STD-04 baseline, and the parsed decision-log entry. Checks are
# registered in CHECKS below and only run if the decision log says the item
# has been proposed — see parse_decision_log / status_is_active.
# =========================================================================

def companion_name(header, kind="Reason"):
    """STD-08/09: every companion field is `{Field} | {Companion Information}`."""
    return f"{header.rstrip('?').strip()}{COMPANION_SEP}{kind}"


def is_companion_header(header):
    return COMPANION_SEP.strip() in header


def companion_kind(header):
    """-> the bit after the pipe, e.g. 'Ref' for `Start Year | Ref`."""
    return header.split("|", 1)[1].strip() if is_companion_header(header) else ""


def legacy_companion(header, headers_low):
    """-> (base_header, kind) if `header` is an old-style companion field.

    A suffix alone is not enough — `Start Year` ends in "Year" but is a field
    in its own right. It only counts as a companion when stripping the suffix
    leaves the name of another column in the same tab.
    """
    if is_companion_header(header):
        return None
    for rx, kind in LEGACY_COMPANION_PATTERNS:
        m = rx.match(header)
        if not m:
            continue
        base = m.group(1).strip()
        if not base:
            continue
        for cand in (base, base + "s", base.rstrip("s")):
            if cand.lower() in headers_low:
                return cand, kind
    return None


MINOR_WORDS = {"of", "the", "in", "for", "and", "to", "a", "an", "at", "by", "or"}


def to_title_case(header):
    """Title Case a header, leaving acronyms, mixed case and parentheticals alone.

    Parentheticals are held back because STD-08 reserves them for units and the
    language-variant wording inside them is still an open item — retitling
    `(other language)` would be inventing an answer to that.
    """
    held = []

    def hold(m):
        held.append(m.group(0))
        return f"\x00{len(held) - 1}\x00"

    masked = re.sub(r"\([^)]*\)", hold, header)
    if " " not in masked:
        masked = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", masked)

    out, first = [], True
    for tok in re.split(r"([ /_]+)", masked):
        if not tok or re.fullmatch(r"[ /_]+", tok):
            out.append(tok)
            continue
        if tok.isupper() or re.search(r"[a-z][A-Z]", tok) or not tok[:1].isalpha():
            out.append(tok)
        elif not first and tok.lower() in MINOR_WORDS:
            out.append(tok.lower())
        else:
            out.append(tok[:1].upper() + tok[1:])
        first = False

    result = "".join(out)
    for i, original in enumerate(held):
        result = result.replace(f"\x00{i}\x00", original)
    return result


def check_std_01(profiles, ctx):
    """STD-01 Null / Missing Value Encoding.

    Decision (Final): keep the numeric column pure and put the reason in a
    companion column where one is needed. Allow `not found`, `not applicable`,
    `null`, `not available`.

    Owns missing-value tokens in non-numeric columns and the vocabulary inside
    `| Reason` companions. Numeric cells belong to STD-05; boolean-shaped
    columns belong to STD-03; a missing companion belongs to STD-10.
    """
    findings = []
    for p in profiles:
        if p.role in ("boolean", "numeric", "year", "date", "empty"):
            continue
        if UNIT_PARENTHETICAL_RE.search(p.header) or p.is_percent:
            continue        # numeric by intent — STD-05 and STD-10 own these

        legacy = legacy_companion(
            p.header, {h.lower() for h in p.sibling_headers if h})
        if legacy and legacy[1] in ("Accuracy", "Ref"):
            continue        # accuracy scales are domain-specific (STD-09)

        if companion_kind(p.header).lower() == "reason":
            for row, val in p.cells:
                if val.lower() not in STD_01_ALLOWED_MISSING:
                    findings.append(cell_finding(
                        "STD-01", "warning", p, row, val,
                        "Companion value is outside the STD-01 vocabulary",
                        "one of: " + ", ".join(sorted(STD_01_ALLOWED_MISSING)),
                    ))
            continue

        for row, val in p.cells:
            low = val.lower()
            if low in NULL_PROXY_TOKENS and low not in STD_01_ALLOWED_MISSING:
                findings.append(cell_finding(
                    "STD-01", "error", p, row, val,
                    f"Non-standard missing-value token in a {p.role} column",
                    STD_01_DEFAULT_MISSING,
                ))
    return findings


def check_std_02(profiles, ctx):
    """STD-02 Multi-value Separators.

    Decision (Final): use `;` as the separator; `&` is allowed inside
    categorical options but never as a separator.

    Reference-aware, because `&` is vocabulary (`iron & steel`, `Central &
    South America`) far more often than it is a delimiter. A comma is only
    called a separator when the parts it produces are themselves values —
    members of a reference set, or values that appear standalone elsewhere in
    the same column.
    """
    findings = []
    ref_all = ctx["ref_all"]

    for p in profiles:
        if p.role not in ("categorical", "text"):
            continue
        if is_companion_header(p.header):
            continue
        if header_has(p.header, GEOMETRY_HEADER_HINTS + URL_HEADER_HINTS + FREETEXT_HEADER_HINTS):
            continue

        atomic = {
            v.lower() for _, v in p.real_values
            if "," not in v and ";" not in v and "&" not in v
        }
        known = atomic | ref_all
        multi_named = header_has(p.header, (
            "(s)", "names", "name(s)", "types", "countries", "fuel", "owner",
            "operator", "parent", "alternate", "other", "products",
        ))

        for row, val in p.real_values:
            if ";" in val:
                continue                      # already the standard separator
            low = val.lower()
            if low in ref_all or low in atomic:
                continue                      # the whole string is one known value

            for sep, label in ((",", "comma"), ("&", "ampersand")):
                if sep not in val:
                    continue
                parts = [x.strip() for x in val.split(sep)]
                if len(parts) < 2 or not all(parts):
                    continue
                if any(len(x) > 60 for x in parts):
                    continue
                if COORD_PAIR_RE.match(val) or THOUSANDS_RE.match(val):
                    continue

                parts_known = all(x.lower() in known for x in parts)
                if sep == "&" and not parts_known:
                    continue                  # `&` is vocabulary unless proven otherwise
                if not parts_known and not multi_named:
                    continue

                findings.append(cell_finding(
                    "STD-02", "error", p, row, val,
                    f"Multiple values separated by {label}; the standard separator is `{STD_02_SEPARATOR}`",
                    f"{STD_02_SEPARATOR} ".join(parts),
                ))
                break
    return findings


def check_std_03(profiles, ctx):
    """STD-03 Boolean Encoding.

    Decision (Final): no true booleans. A boolean-shaped field becomes a
    categorical with a standardized lowercase value set — `true`, `false`,
    `unknown`, `not found` — which may grow as needed. `not found` is internal
    bookkeeping and is excluded from public exports.

    This reverses the earlier `True`/`False` decision, so title-case values are
    now flagged, and `unknown` / `not found` are valid rather than errors.
    """
    findings = []
    tolerated = STD_03_ALLOWED | STD_01_ALLOWED_MISSING

    for p in profiles:
        if p.role != "boolean":
            continue

        for row, val in p.cells:
            low = val.lower()
            if val in STD_03_ALLOWED:
                continue                      # already lowercase and in the set
            if low in BOOLEAN_TOKEN_MAP:
                findings.append(cell_finding(
                    "STD-03", "error", p, row, val,
                    "Boolean-style value; STD-03 uses a lowercase categorical set",
                    BOOLEAN_TOKEN_MAP[low],
                ))
            elif low in tolerated:
                findings.append(cell_finding(
                    "STD-03", "error", p, row, val,
                    "Correct value, wrong case — STD-03 values are lowercase",
                    low,
                ))
            else:
                findings.append(cell_finding(
                    "STD-03", "error", p, row, val,
                    "Value outside the STD-03 set (true / false / unknown / not found)",
                    "unknown",
                ))

        real = {v.lower() for _, v in p.real_values}
        if real and real <= {"true", "yes", "y", "1"} and p.n_blank:
            findings.append(column_finding(
                "STD-03", "info", p,
                f"Sparse boolean: only true values are recorded and "
                f"{p.n_blank:,} cells are empty, so `false` and `not checked` "
                f"are indistinguishable",
                "write `false` explicitly where the answer is no",
            ))

        n_nf = sum(1 for _, v in p.cells if v.lower() == "not found")
        if n_nf:
            findings.append(column_finding(
                "STD-03", "info", p,
                f"{n_nf:,} `not found` cells — STD-03 treats these as internal "
                f"bookkeeping, excluded from public/published exports",
                "strip before publication (Maisie's report-code audit is still open)",
            ))
    return findings


def check_std_04(profiles, ctx):
    """STD-04 Categorical Allowed Values.

    Decision (Final): an allowed list per categorical field per tracker,
    enforced by dropdowns in DB-backed trackers and by QC scripts for the
    spreadsheet-only ones. This check is that QC script.

    The baseline is a per-tracker history in qc/baselines/{tracker}.json. A run
    compares against the most recent recorded release; `--record-release`
    appends a new one. A tracker with no releases yet gets seeded rather than
    having every value reported as new.
    """
    findings = []
    baseline = ctx["baseline"]
    releases = baseline.get("releases", [])
    latest = releases[-1] if releases else None
    ref_sets = ctx["ref_sets"]

    if latest is None and not ctx["seen"].get("std04_no_baseline"):
        ctx["seen"]["std04_no_baseline"] = True
        findings.append(Finding(
            "STD-04", "info", profiles[0].sheet if profiles else "",
            "(whole tracker)",
            f"No release baseline recorded yet for tracker `{ctx['tracker']}`, "
            f"so new values cannot be detected. Falling back to reference sets "
            f"where one applies.",
            f"seed it with: python3 qc_check.py --sheet <url> --record-release <label>",
            scope="sheet",
        ))

    for p in profiles:
        if p.role != "categorical" or is_companion_header(p.header):
            continue

        prior = None
        if latest:
            prior = latest.get("sheets", {}).get(p.sheet, {}).get(p.header)
            if prior is None:
                findings.append(column_finding(
                    "STD-04", "info", p,
                    f"Column is not in the last release ({latest['label']}) — "
                    f"new column, so its values cannot be compared",
                    "confirm the column is intended, then --record-release",
                ))
                continue

        # Two canons, and a value can fail either. The release baseline is the
        # tracker's own history; the reference set is org-wide vocabulary. Both
        # are checked, because seeding a release from dirty data would
        # otherwise bake a typo in permanently.
        canons = []
        if prior is not None:
            canons.append((
                {v.lower() for v in prior.get("values", [])},
                f"the last release ({latest['label']})", "error",
            ))
        ref, name = reference_set_for(p.header, ref_sets)
        if ref:
            canons.append((ref, f"the `{name}` reference set", "warning"))
        if not canons:
            continue

        for row, val in p.real_values:
            parts = [x.strip() for x in re.split(r"[;,]", val) if x.strip()] or [val]
            failed = [
                (label, sev, [x for x in parts if x.lower() not in known])
                for known, label, sev in canons
            ]
            failed = [f for f in failed if f[2]]
            if not failed:
                continue

            severity = "error" if any(sev == "error" for _, sev, _ in failed) else "warning"
            unknown = sorted({x for _, _, xs in failed for x in xs})
            where = " or ".join(label for label, _, _ in failed)
            subject = "Value does" if len(parts) == 1 else \
                ", ".join(f"`{x}`" for x in unknown) + " do"
            findings.append(cell_finding(
                "STD-04", severity, p, row, val,
                f"{subject} not appear in {where}",
                "confirm it is intended, then approve it into the canon",
            ))
    return findings


def check_std_05(profiles, ctx):
    """STD-05 Numeric Field Purity.

    Decision (Final): remove `#N/A` and coordinate pairs; no ranges, pick a
    single value; the asterisk token moves to a companion boolean flag and the
    numeric column stays pure/blank.

    STD-05 also mentions a standardized placeholder for blanks outside the
    database. Taylor resolved that against STD-01 on 2026-09-24, recorded under
    STD-05 in decision-discussion.md: no placeholder token survives in a numeric
    column, so a missing-value token here is an error.
    """
    findings = []
    for p in profiles:
        if p.is_companion:
            continue        # a companion inherits its base field's unit parens
        numeric_by_header = bool(UNIT_PARENTHETICAL_RE.search(p.header))
        if p.role != "numeric" and not (numeric_by_header and p.role in ("text", "categorical")):
            continue

        for row, val in p.cells:
            if is_numeric(val) and not THOUSANDS_RE.match(val):
                continue
            if p.is_percent and val.lower() in NULL_PROXY_TOKENS:
                continue        # STD-10 pattern 6 owns sentinels in % fields
            severity, problem, fix = classify_numeric_impurity(val, p)
            if problem:
                findings.append(cell_finding("STD-05", severity, p, row, val, problem, fix))
    return findings


def classify_numeric_impurity(val, prof):
    """-> (severity, problem, suggested_fix) for one bad cell in a numeric column."""
    low = val.lower()
    header = prof.header

    if low in EXCEL_ERRORS:
        return ("error", "Excel error value carried into the export", "(blank)")
    if val.strip() == "*":
        return ("error",
                "Asterisk in a numeric column; STD-05 moves this to a companion "
                "boolean flag and leaves the number blank",
                f"(blank) + flag it in `{companion_name(header, 'Restricted')}`")
    if COORD_PAIR_RE.match(val):
        return ("error",
                "A coordinate pair is stored in a single numeric column",
                "keep this column's own coordinate; STD-09 publishes the pair as `Lat_Lon`")
    if RANGE_RE.match(val):
        return ("error", "A range, not a value — STD-05 says pick a single value",
                "a single number")
    if QUALIFIED_RE.match(val):
        return ("error",
                "Qualified assertion in a numeric column (see also STD-10 pattern 1)",
                f"(blank) + record the qualifier in `{companion_name(header)}`")
    if CURRENCY_RE.match(val):
        return ("error", "Currency symbol in a numeric column",
                re.sub(r"[^\d.]", "", val))
    if THOUSANDS_RE.match(val):
        return ("warning", "Thousands separator makes the cell text, not a number",
                val.replace(",", ""))
    if low in NULL_PROXY_TOKENS:
        return ("error",
                "Missing-value token in a numeric column; STD-01 governs, so "
                "the number stays blank and the reason moves to a companion",
                f"(blank) + record the reason in `{companion_name(header)}`")
    m = TRAILING_UNIT_RE.match(val)
    if m:
        return ("error", f"Unit `{m.group(2)}` stored alongside the number "
                         f"(STD-08 keeps units in the header instead)",
                m.group(1).replace(",", ""))
    return ("error", "Non-numeric value in a numeric column", "a single number")


def check_std_06(profiles, ctx):
    """STD-06 Date / Year Format.

    Decision (Final): three separate columns in ISO format `YYYY-MM-DD`.
    Fiscal year (e.g. GCMT): a single start-year `YYYY` column plus a companion
    marking fiscal-year status for that country, e.g.
    `Start Year | Fiscal_{ISO country code}`.

    The three-column split is what lets a partly-known date be recorded without
    inventing a month and day.
    """
    findings = []
    headers_low = {h.lower() for h in (profiles[0].sibling_headers if profiles else [])}

    for p in profiles:
        if p.role not in ("year", "date"):
            continue
        if header_has(p.header, RELEASE_DATE_HINTS):
            continue        # STD-13 removes the column rather than splitting it
        fiscal = "fiscal" in p.header.lower()

        n_bad = 0
        for row, val in p.cells:
            severity, problem, fix = classify_date_value(val, p.role, fiscal, p)
            if problem:
                n_bad += 1
                findings.append(cell_finding("STD-06", severity, p, row, val, problem, fix))

        if p.role == "date":
            base = re.sub(r"\s*\b(date|dates)\b\s*$", "", p.header, flags=re.I).strip() or p.header
            wanted = [f"{base} {part}".lower() for part in ("Year", "Month", "Day")]
            if not all(w in headers_low for w in wanted):
                findings.append(column_finding(
                    "STD-06", "warning" if n_bad else "info", p,
                    "Date field is a single column; STD-06 splits a date across "
                    "three columns so partly-known dates can still be recorded",
                    f"split into `{base} Year`, `{base} Month`, `{base} Day`",
                ))
    return findings


def classify_date_value(val, role, fiscal, prof):
    """-> (severity, problem, suggested_fix) for one date/year cell."""
    low = val.strip().lower()
    header = prof.header

    if low in NULL_PROXY_TOKENS:
        if low in STD_01_ALLOWED_MISSING:
            return (None, None, None)
        return ("error", "Non-standard missing-value token in a date/year column",
                f"(blank) + record the reason in `{companion_name(header)}`")
    if low in ("0", "0.0", "0.00"):
        return ("error", "`0` is Excel's empty-date artifact, not a date", "(blank)")

    m = FISCAL_YEAR_RE.match(val)
    if m:
        if fiscal:
            return ("warning",
                    "Fiscal year spans two years in one cell; STD-06 keeps the "
                    "start year only, with a companion marking fiscal status",
                    f"{m.group(1)} + `{companion_name(header, 'Fiscal_{ISO country code}')}`")
        return ("error", "Two years in one cell", f"{m.group(1)}")

    if FLOAT_YEAR_RE.match(val):
        return ("error", "Year exported as a float by Excel", val.split(".")[0])

    if role == "year":
        if BARE_YEAR_RE.match(val):
            return (None, None, None)
        if EXCEL_SERIAL_RE.match(val):
            iso = excel_serial_to_iso(val)
            return ("error", "Excel serial number in a year column",
                    iso[:4] if iso else "the 4-digit year")
        for rx, grp in ((ISO_DATETIME_RE, 1), (ISO_DATE_RE, 0), (SLASH_YMD_RE, 1), (SLASH_MDY_RE, 3)):
            m = rx.match(val)
            if m:
                year = m.group(grp)[:4] if grp else val[:4]
                return ("warning", "Full date in a year-only column", year)
        if is_numeric(val):
            return ("error", "Number outside the plausible year range 1500-2199",
                    "a 4-digit year")
        return ("error", "Not a 4-digit year", "YYYY")

    # role == "date": the target is ISO YYYY-MM-DD
    if ISO_DATE_RE.match(val):
        return (None, None, None)
    m = ISO_DATETIME_RE.match(val)
    if m:
        return ("error", "Date carries a time component", m.group(1))
    m = SLASH_YMD_RE.match(val)
    if m:
        return ("error", "Slash-separated date",
                f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
    m = SLASH_MDY_RE.match(val)
    if m:
        return ("error", "US-style MM/DD/YYYY date",
                f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}")
    m = DOT_DMY_RE.match(val)
    if m:
        return ("error", "Dot-separated DD.MM.YYYY date",
                f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}")
    if LONGHAND_DATE_RE.match(val):
        return ("error", "Date written out in words", longhand_to_iso(val) or STD_06_DATE_FORMAT)
    if BARE_YEAR_RE.match(val):
        return ("warning",
                "Only the year is known in a full-date column; STD-06's three "
                "columns let you record the year without inventing a month/day",
                f"put {val} in the Year column and leave Month/Day blank")
    if EXCEL_SERIAL_RE.match(val):
        return ("error", "Excel serial number instead of a date",
                excel_serial_to_iso(val) or STD_06_DATE_FORMAT)
    return ("error", f"Unrecognized date format; STD-06 is `{STD_06_DATE_FORMAT}`", STD_06_DATE_FORMAT)


def excel_serial_to_iso(val):
    """Excel's 1900 serial -> ISO date. Excel's 1900 leap-year bug included."""
    num = to_float(val)
    if num is None or not (1 < num < 100000):
        return None
    from datetime import date, timedelta
    return (date(1899, 12, 30) + timedelta(days=int(num))).isoformat()


def longhand_to_iso(val):
    m = re.match(r"^([a-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})$", val.strip(), re.I)
    if m and m.group(1).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{1,2})\s+([a-z]{3})[a-z]*\.?,?\s+(\d{4})$", val.strip(), re.I)
    if m and m.group(2).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


# --- STD-07 column identification ---------------------------------------

ASSET_WORDS = (
    "unit", "project", "plant", "mine", "terminal", "facility", "pipeline",
    "asset", "entity", "site", "station", "field", "complex",
)
ID_HEADER_RE = re.compile(
    r"^(gem\s*)?(" + "|".join(ASSET_WORDS) + r")?\s*id$", re.I)
NAME_HEADER_RE = re.compile(
    r"^(" + "|".join(ASSET_WORDS) + r")?\s*name$", re.I)


def find_required_columns(profiles):
    """-> {concept: [ColumnProfile]} for the STD-07 minimum publish bar."""
    found = {k: [] for k in STD_07_REQUIRED}
    lats, lons = [], []
    for p in profiles:
        h = p.header.strip()
        low = h.lower()
        if is_companion_header(h):
            continue
        # Language and unit variants sit in parentheses, so match without them:
        # `Plant name (English)` is still the name field.
        bare = strip_parentheticals(h)
        if ID_HEADER_RE.match(h) or ID_HEADER_RE.match(bare):
            found["id"].append(p)
        if (NAME_HEADER_RE.match(h) or NAME_HEADER_RE.match(bare)) \
                and not low.startswith("other"):
            found["name"].append(p)
        if low in ("country", "country/area", "countries", "country / area"):
            found["country"].append(p)
        if low == "status":
            found["status"].append(p)
        if low in ("lat_lon", "lat/lon", "geometry", "wkt", "coordinates"):
            found["geometry"].append(p)
        if low in ("latitude", "lat"):
            lats.append(p)
        if low in ("longitude", "lon", "long", "lng"):
            lons.append(p)
    if not found["geometry"] and lats and lons:
        found["geometry"] = lats + lons
    return found


def check_std_07(profiles, ctx):
    """STD-07 Required Fields / Nullability.

    Decision (Final): a universal minimum publish bar — ID, name, country,
    status and geometry must be populated before a record is published. This
    helps de-duplication and QC. Teams may layer stricter rules on top.

    Geometry was added to the bar after audience interviews showed geography
    fields are the most used. A missing-value token counts as unpopulated: a
    record whose country reads `not found` has not met the bar.
    """
    findings = []
    if not profiles:
        return findings
    required = find_required_columns(profiles)

    for concept, cols in required.items():
        if not cols:
            findings.append(Finding(
                "STD-07", "warning", profiles[0].sheet, f"({concept})",
                f"No `{concept}` column found in this tab, so the STD-07 publish "
                f"bar cannot be verified for it",
                "confirm the tab is not a record tab, or add the column",
                scope="sheet",
            ))
            continue

        for p in cols:
            for row, val in [(r, v) for r, v in p.cells if v.lower() in NULL_PROXY_TOKENS]:
                findings.append(cell_finding(
                    "STD-07", "error", p, row, val,
                    f"`{concept}` is on the minimum publish bar, and a "
                    f"missing-value token does not meet it",
                    "populate before publishing",
                ))
            if p.n_blank:
                findings.append(column_finding(
                    "STD-07", "error", p,
                    f"{p.n_blank:,} blank cells in `{concept}`, which is on the "
                    f"minimum publish bar",
                    "populate every row before publishing",
                ))
    return findings


def check_std_08(profiles, ctx):
    """STD-08 Field Naming Conventions.

    Decision (Final): keep units in the header parentheses — no separate unit
    column. Move geographic explainer text, plurality hints and conversion-field
    wording out of headers into metadata; parentheses are reserved primarily for
    units. Lowercase data values (except proper nouns); Title Case headers; no
    question marks. Companion fields use `{Field} | {Companion Information}`.

    Two parts of this reversed the earlier decision: units now stay in the
    header, and headers are Title Case rather than lowercase. Companion naming
    is checked by STD-09, which owns the pipe pattern. The open item —
    language-variant headers such as `Plant name (English)` — is deliberately
    not checked, and neither are the Major/Local area parentheses that STD-12
    explicitly keeps for now.
    """
    findings = []
    for p in profiles:
        h = p.header

        if "?" in h:
            findings.append(column_finding(
                "STD-08", "error", p,
                "Question mark in a column header",
                to_title_case(h.replace("?", "").strip()),
                rename_to=to_title_case(h.replace("?", "").strip()),
            ))

        if not is_companion_header(h):
            titled = to_title_case(h)
            if CAMEL_CASE_RE.match(h.replace(" ", "")) and " " not in h:
                findings.append(column_finding(
                    "STD-08", "warning", p,
                    "camelCase header; STD-08 uses Title Case with spaces "
                    "(snake_case is for code-friendly names, not headers)",
                    titled, rename_to=titled,
                ))
            elif titled != h:
                findings.append(column_finding(
                    "STD-08", "info", p,
                    "Header is not Title Case; STD-08 headers are Title Case "
                    "(it is the data *values* that are lowercase)",
                    titled, rename_to=titled,
                ))

        if PLURALITY_HINT_RE.search(h):
            findings.append(column_finding(
                "STD-08", "warning", p,
                "Plurality hint `(s)` in the header; STD-08 moves these into "
                "the documentation and keeps parentheses for units",
                re.sub(r"\s*\(s\)", "s", h).strip(),
                rename_to=re.sub(r"\s*\(s\)", "s", h).strip(),
            ))

        if CONVERSION_PAREN_RE.search(h):
            findings.append(column_finding(
                "STD-08", "warning", p,
                "Conversion-field wording in the header parentheses; STD-08 "
                "moves this into the documentation",
                strip_parentheticals(h), rename_to=strip_parentheticals(h),
            ))

        # Data values: lowercase unless a proper noun. Case-variant duplicates
        # are the unambiguous failure — the same value written two ways.
        if p.role == "categorical":
            groups = {}
            for _, v in p.real_values:
                groups.setdefault(v.lower(), set()).add(v)
            for low, variants in groups.items():
                if len(variants) > 1:
                    for row, val in p.real_values:
                        if val.lower() == low and val != low:
                            findings.append(cell_finding(
                                "STD-08", "warning", p, row, val,
                                f"Same value recorded as {sorted(variants)}; "
                                f"STD-08 lowercases data values",
                                low,
                            ))
    return findings


def check_std_09(profiles, ctx):
    """STD-09 Cross-field Links.

    Decision (Final): companion fields — accuracy, year, ref and the rest — all
    use the pipe pattern `{Field} | Accuracy`, `{Field} | Year`, `{Field} | Ref`.
    Coordinates publish as `Lat_Lon` with a companion `Lat_Lon | Accuracy`.
    Wide-format historical columns are the current pattern; long-format in a
    separate tab is the new direction, to migrate over time.

    Owns companion-field naming across every standard that uses one. A suffix
    alone never makes a companion — `Start Year` ends in "Year" but is a field
    in its own right, so the base must name another column in the same tab.
    """
    findings = []
    if not profiles:
        return findings
    headers_low = {h.lower() for h in profiles[0].sibling_headers if h}

    for p in profiles:
        legacy = legacy_companion(p.header, headers_low)
        if legacy:
            base, kind = legacy
            if base.strip().lower() in ("coordinates", "coordinate", "coords"):
                base = "Lat_Lon"        # the base field is renamed too
            findings.append(column_finding(
                "STD-09", "error", p,
                f"Companion field using the old `{p.header}` form; STD-09 uses "
                f"the pipe pattern for every companion",
                f"{base}{COMPANION_SEP}{kind}",
                rename_to=f"{base}{COMPANION_SEP}{kind}",
            ))

    for p in profiles:
        if is_companion_header(p.header) or p.header.strip() == "Lat_Lon":
            continue
        pairs = sum(1 for _, v in p.real_values if COORD_PAIR_RE.match(v))
        named = p.header.strip().lower() in (
            "coordinates", "coordinate", "coords", "lat/lon", "latlon",
            "lat/long", "lat_long", "latitude/longitude",
        )
        if named or (pairs and pairs >= len(p.real_values) * 0.8):
            findings.append(column_finding(
                "STD-09", "error", p,
                "Coordinate pair in a single column; STD-09 publishes it as "
                "`Lat_Lon` with a companion `Lat_Lon | Accuracy`",
                "Lat_Lon", rename_to="Lat_Lon",
            ))

    lat = next((p for p in profiles if p.header.strip().lower() in ("latitude", "lat")), None)
    lon = next((p for p in profiles if p.header.strip().lower() in ("longitude", "lon", "long", "lng")), None)
    if lat and lon:
        findings.append(column_finding(
            "STD-09", "warning", lat,
            f"Latitude and longitude are separate columns (`{lat.header}`, "
            f"`{lon.header}`); STD-09 publishes the pair as `Lat_Lon`",
            f"combine into `Lat_Lon`, companion `Lat_Lon{COMPANION_SEP}Accuracy`",
        ))
    return findings


def check_std_10(profiles, ctx):
    """STD-10 Imputed Values.

    Decision (Final): use the companion column pattern `{Field} | {Reason}` for
    standardized descriptive info and keep numeric fields pure. Use the status
    timeline for planned statuses. Use companion fields for national-average
    assignments. Unknown -> blank in the numeric field, reason in the companion.

    From the pattern table: pattern 1 (`>0` bounded assertions) uses the STD-01
    companion and a blank number; pattern 5 pairs a capacity factor with
    `| Source` and `| Year`; pattern 6 blanks `unknown` in fraction fields.
    Patterns 2 (deferred), 4 and 7 (closed) are intentionally not checked.

    Note: the backup detail table in decision-discussion.md still names the old
    `{field}_reason` form for decision point 4. The Sep 30 decision and STD-08
    both supersede it with the pipe pattern, which is what this enforces.
    """
    findings = []
    if not profiles:
        return findings
    headers_low = {h.lower() for h in profiles[0].sibling_headers if h}

    for p in profiles:
        if p.is_companion:
            continue        # a companion is the destination, not the source
        has_companion = any(
            h.startswith(p.header.rstrip("?").strip().lower() + " |") for h in headers_low
        )

        # Pattern 6 — `unknown` in a fraction/percentage field
        if p.is_percent and p.role in ("numeric", "categorical", "text"):
            for row, val in p.cells:
                if val.lower() in NULL_PROXY_TOKENS:
                    findings.append(cell_finding(
                        "STD-10", "error", p, row, val,
                        "Sentinel in a fraction/percentage field; STD-10 pattern 6 "
                        "leaves the number blank and puts the reason alongside it",
                        f"(blank) + `{companion_name(p.header)}` = why it is unknown",
                    ))

        if p.role == "numeric" or UNIT_PARENTHETICAL_RE.search(p.header):
            # Pattern 1 — bounded assertions, reported once per column
            bounded = [v for _, v in p.cells if QUALIFIED_RE.match(v)]
            if bounded:
                findings.append(column_finding(
                    "STD-10", "warning", p,
                    f"{len(bounded):,} bounded assertions such as `{bounded[0]}`; "
                    f"STD-10 pattern 1 replaces these with a blank number and the "
                    f"STD-01 companion",
                    f"add `{companion_name(p.header)}` and blank the number",
                ))

            if p.n_null_proxy and not has_companion:
                findings.append(column_finding(
                    "STD-10", "info", p,
                    f"{p.n_null_proxy:,} cells hold a reason token but there is no "
                    f"companion column to move it into",
                    f"add `{companion_name(p.header)}`",
                ))

        # Pattern 5 — capacity factor needs a source and a year
        if "capacity factor" in p.header.lower() and not is_companion_header(p.header):
            stem = p.header.rstrip("?").strip().lower()
            related = [h for h in headers_low if h.startswith(stem + " |")]
            missing = []
            if not any("year" in h for h in related):
                missing.append("year")
            if not any("source" in h or "ref" in h for h in related):
                missing.append("source")
            if missing:
                findings.append(column_finding(
                    "STD-10", "warning", p,
                    f"Capacity factor with no {' and no '.join(missing)} alongside it; "
                    f"STD-10 pattern 5 treats it like production data — true only "
                    f"for a given year, and it has to come from somewhere",
                    f"add `{companion_name(p.header, 'Source')}` "
                    f"(national average / plant-specific) and "
                    f"`{companion_name(p.header, 'Year')}`",
                ))

        # Pattern 3 — startYearLow is not used
        if slugify(p.header) in ("startyearlow", "start_year_low"):
            findings.append(column_finding(
                "STD-10", "warning", p,
                "STD-10 pattern 3 records that `startYearLow` is not used",
                "drop the column; planned statuses go through the status timeline",
            ))
    return findings


STD_11_STANDARD_HEADERS = {
    "last updated": "Last Updated",
    "lastupdated": "Last Updated",
    "last_updated": "Last Updated",
    "last update": "Last Updated",
    "date updated": "Last Updated",
    "updated": "Last Updated",
    "research status": "Research Status",
    "researchstatus": "Research Status",
    "research_status": "Research Status",
}
URL_VALUE_RE = re.compile(r"^https?://\S+$", re.I)


def check_std_11(profiles, ctx):
    """STD-11 Data Provenance / Source Fields.

    Decision (Final): never publish a researcher name in public views (internal
    only). Standardize how `Last Updated` and `Research Status` appear so public
    reports align across trackers. Field-level provenance uses `{Field} | Ref`.
    Source content is a plain URL; when it points to a general resource rather
    than the specific document, add a Short name saying where to find it.

    The "Wiki URL" note in the original audit was a misread and is disregarded,
    per the discussion page.
    """
    findings = []
    for p in profiles:
        h = p.header
        low = h.strip().lower()

        if header_has(h, RESEARCHER_HEADER_HINTS):
            findings.append(column_finding(
                "STD-11", "error", p,
                "Researcher-identifying column; STD-11 never publishes these in "
                "public views (internal reports only)",
                "drop from the public export, or mark the column internal-only",
            ))

        standard = STD_11_STANDARD_HEADERS.get(low)
        if standard and h != standard:
            findings.append(column_finding(
                "STD-11", "warning", p,
                f"Non-standard provenance header; STD-11 aligns these with the "
                f"database so public reports match across trackers",
                standard, rename_to=standard,
            ))

        # `{Field} | Ref` holds a plain URL, optionally with a Short name label.
        # Legacy `[ref]` / `Data Source` columns carry the same content, so they
        # are checked too — STD-09 separately flags their naming.
        legacy = legacy_companion(h, {x.lower() for x in p.sibling_headers if x})
        is_source = (companion_kind(h).lower() in ("ref", "source")
                     or (legacy and legacy[1] == "Ref"))
        if is_source:
            for row, val in p.real_values:
                if "http" in val.lower():
                    continue        # carries a URL
                if len(val.split()) <= 6:
                    continue        # a Short name label, e.g. "IEA WEO 2024"
                findings.append(cell_finding(
                    "STD-11", "warning", p, row, val,
                    "Source companion holds prose; STD-11 wants a plain URL, "
                    "with a Short name only when it points to a general resource",
                    "a plain URL (plus a Short name label if needed)",
                ))
    return findings


def check_std_12(profiles, ctx):
    """STD-12 Geographic Hierarchy.

    Decision (Final): `Location` becomes `Address`; `City` becomes
    `Nearest City`; `Country/Area` is the top national-level field. Parentheses
    come off `Subnational Unit` and the explainer moves to metadata, while
    Major/Local area keep theirs for now. Pipeline Start/End headers align with
    the standard point-location list. Multi-country assets keep the
    Country 1 / Country 2 pattern with aligned naming. Basin-style geological
    hierarchies are out of scope.

    The open item — confirming `Location` really holds addresses before the
    rename goes live — means the Location finding is a warning, not an error.
    """
    findings = []
    for p in profiles:
        h = p.header.strip()
        low = h.lower()
        if is_companion_header(h):
            continue

        if low == "location":
            findings.append(column_finding(
                "STD-12", "warning", p,
                "`Location` is too vague; STD-12 renames it to `Address`",
                "Address (confirm the column really holds addresses first — "
                "this is still an open item)",
                rename_to="Address",
            ))
        elif low == "city":
            findings.append(column_finding(
                "STD-12", "error", p,
                "`City` is used interchangeably with address; STD-12 names it "
                "`Nearest City` so the meaning is explicit",
                "Nearest City", rename_to="Nearest City",
            ))
        elif low in ("country", "countries", "country/area", "country / area",
                     "country/areas", "country area") and h != "Country/Area":
            findings.append(column_finding(
                "STD-12", "error", p,
                "STD-12 uses `Country/Area` for the highest national-level field",
                "Country/Area", rename_to="Country/Area",
            ))
        elif low.startswith("subnational unit") and "(" in h:
            findings.append(column_finding(
                "STD-12", "error", p,
                "STD-12 removes the parentheses from `Subnational Unit` and puts "
                "the explainer in metadata",
                "Subnational Unit", rename_to="Subnational Unit",
            ))

        # Pipeline Start/End location headers align with the standard list.
        m = re.match(r"^(start|end)\s*(.+)$", h, re.I)
        if m:
            concept = m.group(2).strip().lower()
            target = STD_12_RENAMES.get(concept)
            if target:
                findings.append(column_finding(
                    "STD-12", "warning", p,
                    f"Pipeline {m.group(1).lower()} location header; STD-12 aligns "
                    f"these with the standard point-location names",
                    f"{m.group(1).capitalize()} {target}",
                    rename_to=f"{m.group(1).capitalize()} {target}",
                ))
    return findings


def check_std_13(profiles, ctx):
    """STD-13 "As Of" Dating.

    Decision (Final): the tracker's release date lives in metadata, not in a
    per-row column. Annual series and date columns align with the companion
    field pattern. `Last Updated` is the researcher's access date, not the
    reference or document date.

    A per-row release date is redundant on every row — granular last-update and
    companion fields carry time-varying changes instead.
    """
    findings = []
    for p in profiles:
        h = p.header
        low = h.strip().lower()

        if header_has(h, RELEASE_DATE_HINTS):
            constant = len({v.lower() for _, v in p.real_values}) <= 1
            findings.append(column_finding(
                "STD-13", "error" if constant else "warning", p,
                "Release/snapshot date stored per row"
                + (" with the same value on every row" if constant else "")
                + "; STD-13 puts the tracker's release date in metadata",
                "move to the tracker's metadata and drop the column",
            ))

        if low == "last updated":
            findings.append(column_finding(
                "STD-13", "info", p,
                "STD-13 defines `Last Updated` as the researcher's access or "
                "review date, not the reference document's date",
                "confirm the values are access dates; the document date belongs "
                "in the source itself",
            ))
    return findings


# All 13 items are implemented as of the Sep 2026 log rewrite. Mark any future
# scaffold here and an activated-but-empty check will say so out loud rather
# than reporting a silent pass.
STUBS = ()
for _fn in STUBS:
    _fn.stub = True


# The gate. Adding a check means adding it here; whether it *runs* is decided
# by the decision log, not by this table.
CHECKS = {
    "STD-01": check_std_01,
    "STD-02": check_std_02,
    "STD-03": check_std_03,
    "STD-04": check_std_04,
    "STD-05": check_std_05,
    "STD-06": check_std_06,
    "STD-07": check_std_07,
    "STD-08": check_std_08,
    "STD-09": check_std_09,
    "STD-10": check_std_10,
    "STD-11": check_std_11,
    "STD-12": check_std_12,
    "STD-13": check_std_13,
}


# =========================================================================
# STD-04 baseline — accumulating categorical history, one file per tracker
# =========================================================================

def baseline_path(tracker, baseline_dir):
    return Path(baseline_dir) / f"{tracker}.json"


def load_baseline(tracker, baseline_dir):
    path = baseline_path(tracker, baseline_dir)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"tracker": tracker, "releases": [], "value_history": {}}


def snapshot_categoricals(all_profiles):
    """-> {sheet: {column: {values, n_values, n_rows}}} for categorical columns."""
    snap = {}
    for p in all_profiles:
        if p.role != "categorical" or p.is_companion:
            continue
        seen = {}
        for _, v in p.real_values:
            seen[v] = seen.get(v, 0) + 1
        snap.setdefault(p.sheet, {})[p.header] = {
            "values": sorted(seen),
            "counts": {k: seen[k] for k in sorted(seen)},
            "n_values": len(seen),
            "n_rows": p.n_rows,
        }
    return snap


def record_release(baseline, label, snapshot, spreadsheet_id, spreadsheet_title):
    """Append a release to the tracker's history and roll the value history forward."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    baseline["spreadsheet_id"] = spreadsheet_id
    baseline["spreadsheet_title"] = spreadsheet_title
    baseline.setdefault("releases", []).append({
        "label": label,
        "recorded_at": now,
        "sheets": snapshot,
    })

    history = baseline.setdefault("value_history", {})
    for sheet, columns in snapshot.items():
        for column, info in columns.items():
            col_hist = history.setdefault(sheet, {}).setdefault(column, {})
            for value in info["values"]:
                entry = col_hist.get(value)
                if entry is None:
                    col_hist[value] = {
                        "first_seen": label, "last_seen": label, "releases": [label],
                    }
                else:
                    entry["last_seen"] = label
                    if label not in entry["releases"]:
                        entry["releases"].append(label)
    return baseline


def save_baseline(baseline, tracker, baseline_dir):
    path = baseline_path(tracker, baseline_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# =========================================================================
# Reports
# =========================================================================

# Which standard's opinion wins when several want to rename the same column.
# The more specific standard outranks the general naming one: a geographic
# field's real name matters more than its capitalisation.
RENAME_PRECEDENCE = ("STD-12", "STD-09", "STD-11", "STD-08")

RENAME_FIELDS = [
    "sheet", "column_letter", "current_header", "proposed_header",
    "proposed_by", "also_suggested", "needs_review", "reason",
]


def build_rename_plan(findings):
    """-> one row per column that needs a new header name.

    Several checks can want to rename the same column — `city` is both
    lowercase (STD-08) and the wrong word (STD-12). Those are not really in
    conflict: the more specific standard wins and the other is recorded. When
    two same-rank checks disagree, the row is marked for review instead.
    """
    by_column = {}
    for f in findings:
        if f.scope != "column" or not f.rename_to or f.rename_to == f.column:
            continue
        by_column.setdefault((f.sheet, f.column_letter, f.column), []).append(f)

    rows = []
    for (sheet, letter, header), group in by_column.items():
        def rank(f):
            return (RENAME_PRECEDENCE.index(f.check_id)
                    if f.check_id in RENAME_PRECEDENCE else len(RENAME_PRECEDENCE))
        group.sort(key=rank)
        winner = group[0]
        others = [f for f in group[1:] if f.rename_to != winner.rename_to]
        tied = [f for f in others if rank(f) == rank(winner)]
        rows.append({
            "sheet": sheet,
            "column_letter": letter,
            "current_header": header,
            "proposed_header": winner.rename_to,
            "proposed_by": winner.check_id,
            "also_suggested": "; ".join(
                f"{f.check_id}: {f.rename_to}" for f in others),
            "needs_review": "yes" if tied else "",
            "reason": winner.problem,
        })
    rows.sort(key=lambda r: (r["sheet"], len(r["column_letter"]), r["column_letter"]))
    return rows


def write_rename_plan(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RENAME_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


CSV_FIELDS = [
    "check_id", "check_title", "severity", "scope", "sheet", "cell", "row",
    "column", "column_letter", "value", "problem", "suggested_fix", "decision",
]


def write_csv(findings, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for f in findings:
            writer.writerow(f.as_row())
    return path


def group_findings(findings):
    """-> {check_id: {column: [findings]}}, both keys in a stable order."""
    grouped = {}
    for f in findings:
        grouped.setdefault(f.check_id, {}).setdefault(f"{f.sheet} · {f.column}", []).append(f)
    return {k: grouped[k] for k in sorted(grouped)}


def write_html(findings, path, meta):
    path.parent.mkdir(parents=True, exist_ok=True)
    grouped = group_findings(findings)
    e = html.escape

    counts = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    parts = [HTML_HEAD.format(
        title=e(meta["title"]),
        sheet=e(meta["title"]),
        generated=e(meta["generated"]),
        tracker=e(meta["tracker"]),
        n_error=counts["error"], n_warning=counts["warning"], n_info=counts["info"],
        n_total=len(findings),
        active=e(", ".join(meta["active"])) or "none",
        inactive=e(", ".join(meta["inactive"])) or "none",
    )]

    if not findings:
        parts.append('<p class="empty">No issues found by the active checks.</p>')

    for check_id, columns in grouped.items():
        item = meta["items"].get(check_id, {})
        n = sum(len(v) for v in columns.values())
        worst = min((SEVERITY_ORDER[f.severity] for v in columns.values() for f in v), default=2)
        sev = ["error", "warning", "info"][worst]
        parts.append(
            f'<details class="check" open>'
            f'<summary><span class="dot {sev}"></span>'
            f'<span class="cid">{e(check_id)}</span>'
            f'<span class="ctitle">{e(item.get("title", ""))}</span>'
            f'<span class="count">{n:,} in {len(columns)} column(s)</span></summary>'
            f'<p class="decision"><strong>Decision:</strong> {e(item.get("decision", ""))}</p>'
        )
        for column, items in sorted(columns.items(), key=lambda kv: -len(kv[1])):
            parts.append(
                f'<details class="col"><summary>{e(column)}'
                f'<span class="count">{len(items):,}</span></summary>'
                f'<table><thead><tr><th>Cell</th><th>Current value</th>'
                f'<th>Problem</th><th>Suggested fix</th></tr></thead><tbody>'
            )
            for f in items[:meta["max_rows"]]:
                parts.append(
                    f'<tr class="{e(f.severity)}">'
                    f'<td class="cell">{e(f.cell or "—")}</td>'
                    f'<td class="val">{e(f.value) or "<em>blank</em>"}</td>'
                    f'<td>{e(f.problem)}</td>'
                    f'<td class="fix">{e(f.suggested_fix)}</td></tr>'
                )
            if len(items) > meta["max_rows"]:
                parts.append(
                    f'<tr class="more"><td colspan="4">… and {len(items) - meta["max_rows"]:,} '
                    f'more — see issues.csv</td></tr>'
                )
            parts.append("</tbody></table></details>")
        parts.append("</details>")

    parts.append(HTML_FOOT)
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


HTML_HEAD = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — QC report</title>
<style>
  :root {{
    --bg: #ffffff; --fg: #1a1d21; --muted: #5d6570; --line: #e3e6ea;
    --card: #f7f8fa; --error: #c0392b; --warning: #b26a00; --info: #2f6f9f;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #14171a; --fg: #e8eaed; --muted: #9aa3ad; --line: #2b3035;
      --card: #1c2126; --error: #ff6b5a; --warning: #e8a33d; --info: #6fb3e0;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 32px 16px 80px; background: var(--bg); color: var(--fg);
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 1080px; margin: 0 auto; }}
  h1 {{ font-size: 24px; margin: 0 0 4px; }}
  .sub {{ color: var(--muted); font-size: 13px; margin: 0 0 20px; }}
  .tallies {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }}
  .tally {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px;
    padding: 10px 14px; font-size: 13px; }}
  .tally b {{ display: block; font-size: 20px; }}
  .gate {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px;
    padding: 12px 14px; font-size: 13px; color: var(--muted); margin-bottom: 24px; }}
  .gate b {{ color: var(--fg); }}
  details.check {{ border: 1px solid var(--line); border-radius: 10px; margin-bottom: 12px;
    background: var(--card); overflow: hidden; }}
  details.check > summary {{ cursor: pointer; padding: 14px 16px; display: flex;
    align-items: center; gap: 10px; flex-wrap: wrap; font-weight: 600; }}
  .dot {{ width: 9px; height: 9px; border-radius: 50%; flex: none; }}
  .dot.error {{ background: var(--error); }}
  .dot.warning {{ background: var(--warning); }}
  .dot.info {{ background: var(--info); }}
  .cid {{ font-variant-numeric: tabular-nums; }}
  .ctitle {{ font-weight: 500; }}
  .count {{ margin-left: auto; color: var(--muted); font-weight: 400; font-size: 13px; }}
  .decision {{ margin: 0 16px 12px; font-size: 13px; color: var(--muted); }}
  details.col {{ border-top: 1px solid var(--line); background: var(--bg); }}
  details.col > summary {{ cursor: pointer; padding: 10px 16px; display: flex;
    gap: 10px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 7px 16px; border-top: 1px solid var(--line);
    vertical-align: top; }}
  th {{ color: var(--muted); font-weight: 500; }}
  td.cell, td.val, td.fix {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
  tr.error td.cell {{ color: var(--error); }}
  tr.warning td.cell {{ color: var(--warning); }}
  tr.info td.cell {{ color: var(--info); }}
  tr.more td {{ color: var(--muted); font-style: italic; }}
  .empty {{ padding: 40px; text-align: center; color: var(--muted); }}
  footer {{ margin-top: 32px; color: var(--muted); font-size: 12px; }}
</style></head><body><main>
<h1>{sheet}</h1>
<p class="sub">Tracker <code>{tracker}</code> · generated {generated}</p>
<div class="tallies">
  <div class="tally"><b>{n_total:,}</b>findings</div>
  <div class="tally"><b>{n_error:,}</b>errors</div>
  <div class="tally"><b>{n_warning:,}</b>warnings</div>
  <div class="tally"><b>{n_info:,}</b>notes</div>
</div>
<div class="gate">
  <b>Active checks</b> (proposed in the decision log): {active}<br>
  <b>Not run</b> (no decision recorded yet): {inactive}
</div>
"""

HTML_FOOT = """<footer>Generated by qc_check.py. Which checks run is read from
docs/decision-log.md at runtime — change a Status there and rerun.</footer>
</main></body></html>"""


# =========================================================================
# main
# =========================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Run decision-log-gated QC checks against a Google Sheet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 qc_check.py --sheet https://docs.google.com/spreadsheets/d/<id>/edit\n"
            "  python3 qc_check.py --sheet <id> --record-release 2026-09-23\n"
            "  python3 qc_check.py --sheet <id> --only STD-03 STD-05\n"
        ),
    )
    ap.add_argument("--sheet", default=None,
                    help="Google Sheets share URL or bare spreadsheet ID")
    ap.add_argument("--credentials", default=str(DEFAULT_CREDENTIALS),
                    help=f"service-account or authorized-user JSON (default: {DEFAULT_CREDENTIALS})")
    ap.add_argument("--decision-log", default=str(DECISION_LOG_PATH),
                    help=f"decision log that gates the checks (default: {DECISION_LOG_PATH})")
    ap.add_argument("--tracker", default=None,
                    help="tracker slug for the STD-04 baseline (default: from the sheet title)")
    ap.add_argument("--out-dir", default=str(OUTPUT_DIR),
                    help=f"where to write issues.csv and report.html (default: {OUTPUT_DIR})")
    ap.add_argument("--baseline-dir", default=str(BASELINE_DIR),
                    help=f"STD-04 baseline history directory (default: {BASELINE_DIR})")
    ap.add_argument("--record-release", metavar="LABEL", default=None,
                    help="snapshot this run's categorical values as a new release "
                         "in the tracker's baseline history")
    ap.add_argument("--header-row", type=int, default=1,
                    help="1-based row holding the column headers (default: 1)")
    ap.add_argument("--tab", action="append", default=[], metavar="NAME",
                    help="only check this tab (repeatable)")
    ap.add_argument("--exclude-tab", action="append", default=[], metavar="NAME",
                    help="skip this tab (repeatable)")
    ap.add_argument("--only", nargs="+", default=None, metavar="STD-NN",
                    help="restrict to these checks (they must still be active)")
    ap.add_argument("--severity", choices=["error", "warning", "info"], default="info",
                    help="minimum severity to report (default: info, i.e. everything)")
    ap.add_argument("--max-html-rows", type=int, default=200,
                    help="max rows per column in the HTML report (default: 200)")
    ap.add_argument("--rename-plan", action="store_true",
                    help="also write qc/rename_plan.csv: one row per column "
                         "whose header needs a new name, deduplicated across checks")
    ap.add_argument("--list-checks", action="store_true",
                    help="print the gate from the decision log and exit")
    return ap.parse_args(argv)


def resolve_gate(items, only):
    """-> (active, inactive, narrowed).

    `inactive` is gated off by the decision log; `narrowed` is active but
    excluded by --only. --only narrows, it never activates.
    """
    active, inactive, narrowed = [], [], []
    for std_id in sorted(CHECKS):
        item = items.get(std_id)
        if item and item["active"]:
            if only and std_id not in only:
                narrowed.append(std_id)
            else:
                active.append(std_id)
        else:
            inactive.append(std_id)
    return active, inactive, narrowed


def print_gate(items, active, inactive, narrowed):
    print("\nChecks, per docs/decision-log.md:")
    for std_id in sorted(CHECKS):
        item = items.get(std_id, {})
        if std_id in active:
            mark = "RUN "
        elif std_id in narrowed:
            mark = "--only"
        else:
            mark = "skip"
        print(f"  [{mark}] {std_id}  {item.get('title', '(not in log)')}")
        print(f"         status: {item.get('status', '—')}")
    tail = f", {len(narrowed)} held back by --only" if narrowed else ""
    print(f"\n  {len(active)} active, {len(inactive)} awaiting a decision{tail}.")


def summarize(findings, items):
    """Terminal summary, grouped by check — the thing you read first."""
    by_check = {}
    for f in findings:
        d = by_check.setdefault(f.check_id, {"n": 0, "cols": set(), "sev": {}})
        d["n"] += 1
        d["cols"].add((f.sheet, f.column))
        d["sev"][f.severity] = d["sev"].get(f.severity, 0) + 1

    print("\n" + "=" * 72)
    print("QC SUMMARY")
    print("=" * 72)
    if not by_check:
        print("  No issues found by the active checks.")
        return
    for std_id in sorted(by_check):
        d = by_check[std_id]
        title = items.get(std_id, {}).get("title", "")
        sev = ", ".join(f"{n} {s}" for s, n in sorted(d["sev"].items(),
                                                      key=lambda kv: SEVERITY_ORDER[kv[0]]))
        print(f"\n  {std_id}  {title}")
        print(f"    {d['n']:,} findings across {len(d['cols'])} column(s)  ({sev})")
    total = sum(d["n"] for d in by_check.values())
    print(f"\n  {total:,} findings total.")


def main(argv=None):
    args = parse_args(argv)

    if not args.sheet and not args.list_checks:
        sys.exit("--sheet is required (or use --list-checks to just print the gate).")

    items = parse_decision_log(Path(args.decision_log))
    active, inactive, narrowed = resolve_gate(items, set(args.only) if args.only else None)

    if args.list_checks:
        print_gate(items, active, inactive, narrowed)
        return 0
    if not active:
        sys.exit("No active checks — every STD item in the decision log is still unreviewed.")

    print(f"Opening spreadsheet …")
    spreadsheet = open_spreadsheet(args.sheet, args.credentials)
    title = spreadsheet.title
    tracker = args.tracker or slugify(title)
    print(f"  {title}  (tracker slug: {tracker})")

    tabs = read_tabs(spreadsheet, args.header_row, args.tab, args.exclude_tab)
    if not tabs:
        sys.exit("No data tabs to check.")

    ref_sets = load_reference_sets()
    baseline = load_baseline(tracker, args.baseline_dir)
    ctx = {
        "ref_sets": ref_sets,
        "ref_all": all_reference_values(ref_sets),
        "baseline": baseline,
        "tracker": tracker,
        "args": args,
        "seen": {},
    }

    print_gate(items, active, inactive, narrowed)

    stubs = [c for c in active if getattr(CHECKS[c], "stub", False)]
    if stubs:
        print("\n  NOTE: the decision log now activates "
              f"{', '.join(stubs)}, but the check function(s) are still empty "
              "scaffolding. Nothing below reflects those items — fill in the "
              "matching check_std_NN() to enforce them.")

    findings, all_profiles = [], []
    for tab_name, header, rows in tabs:
        profiles = profile_tab(tab_name, header, rows, args.header_row)
        all_profiles.extend(profiles)
        for std_id in active:
            for f in CHECKS[std_id](profiles, ctx):
                f.check_title = items.get(std_id, {}).get("title", "")
                f.decision = items.get(std_id, {}).get("decision", "")
                findings.append(f)

    floor = SEVERITY_ORDER[args.severity]
    findings = [f for f in findings if SEVERITY_ORDER[f.severity] <= floor]
    findings.sort(key=lambda f: (
        f.check_id, SEVERITY_ORDER[f.severity], f.sheet, f.column, f.row or 0))

    out_dir = Path(args.out_dir)
    csv_path = write_csv(findings, out_dir / "issues.csv")
    html_path = write_html(findings, out_dir / "report.html", {
        "title": title,
        "tracker": tracker,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "items": items,
        "active": active,
        "inactive": inactive,
        "max_rows": args.max_html_rows,
    })

    if args.rename_plan:
        rows = build_rename_plan(findings)
        rename_path = write_rename_plan(rows, out_dir / "rename_plan.csv")

    summarize(findings, items)

    if args.rename_plan:
        print("\n" + "=" * 72)
        print("HEADER RENAME PLAN")
        print("=" * 72)
        if not rows:
            print("  No header renames needed.")
        for r in rows:
            mark = "  <-- REVIEW" if r["needs_review"] else ""
            print(f"  {r['column_letter'].ljust(3)} {r['current_header'][:34].ljust(34)}"
                  f" -> {r['proposed_header'][:30].ljust(30)} [{r['proposed_by']}]{mark}")
            if r["also_suggested"]:
                print(f"      also suggested — {r['also_suggested']}")
        print(f"\n  {len(rows)} column(s) to rename.")

    if args.record_release:
        snapshot = snapshot_categoricals(all_profiles)
        record_release(baseline, args.record_release, snapshot,
                       spreadsheet.id, title)
        path = save_baseline(baseline, tracker, args.baseline_dir)
        n_cols = sum(len(c) for c in snapshot.values())
        print(f"\n  Recorded release '{args.record_release}': "
              f"{n_cols} categorical column(s) -> {path}")
        print(f"  Releases on file for {tracker}: "
              f"{', '.join(r['label'] for r in baseline['releases'])}")
    elif not baseline.get("releases"):
        print(f"\n  No STD-04 baseline yet for '{tracker}'. Seed one with:")
        print(f"    python3 qc_check.py --sheet <url> --record-release <label>")

    print(f"\n  {csv_path}\n  {html_path}")
    if args.rename_plan:
        print(f"  {rename_path}")
    print()
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
