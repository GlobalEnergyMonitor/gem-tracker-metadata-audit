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

STD_01_CATEGORICAL_NULL = "not found"
STD_01_COMPANION_VOCAB = {"null", "not found", "not applicable", "not available"}
STD_02_SEPARATOR = ";"
STD_03_TRUE = "True"
STD_03_FALSE = "False"
STD_06_DATE_FORMAT = "YYYY-MM-DD"
STD_10_COMPANION_SUFFIX = "_reason"

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

BOOLEAN_TOKEN_MAP = {
    "true": STD_03_TRUE, "t": STD_03_TRUE, "yes": STD_03_TRUE, "y": STD_03_TRUE, "1": STD_03_TRUE,
    "false": STD_03_FALSE, "f": STD_03_FALSE, "no": STD_03_FALSE, "n": STD_03_FALSE, "0": STD_03_FALSE,
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


def base_name(header):
    """Header reduced to the stem used for companion columns: no unit or
    explainer parentheses, no trailing `?` (STD-08 removes those anyway)."""
    return strip_parentheticals(header).rstrip("?").strip()


# =========================================================================
# Findings
# =========================================================================

class Finding:
    """One thing a person needs to go fix (or at least look at)."""

    __slots__ = (
        "check_id", "check_title", "severity", "scope", "sheet", "cell",
        "row", "column", "column_letter", "value", "problem", "suggested_fix",
        "decision",
    )

    def __init__(self, check_id, severity, sheet, column, problem,
                 suggested_fix="", value="", row=None, column_letter="",
                 scope="cell"):
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


def column_finding(check_id, severity, prof, problem, fix=""):
    return Finding(
        check_id, severity, prof.sheet, prof.header, problem,
        suggested_fix=fix, column_letter=prof.letter, scope="column",
    )


# =========================================================================
# Decision log — this is what decides which checks run
# =========================================================================

ROW_ID_RE = re.compile(r"^\|\s*(STD-\d{2})\s*\|")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def split_md_row(line):
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def strip_md(text):
    text = LINK_RE.sub(r"\1", text)
    text = text.replace("<br>", " ").replace("**", "")
    return re.sub(r"\s+", " ", text).strip()


def status_is_active(status):
    """A check is active once someone has actually proposed a decision.

    'Proposed by group' / 'Proposed by Taylor ...' -> active.
    'Not yet reviewed ...' -> not active, even if the cell also says 'flagged
    as quick'. The 'not yet reviewed' wording always wins.
    """
    low = status.lower()
    if "not yet reviewed" in low:
        return False
    return "proposed" in low


def parse_decision_log(path):
    """Read docs/decision-log.md -> {std_id: {...}} including active flag."""
    if not path.exists():
        sys.exit(f"Decision log not found at {path} — pass --decision-log.")

    items = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW_ID_RE.match(line)
        if not m:
            continue
        cells = split_md_row(line)
        if len(cells) < 5:
            continue
        std_id = m.group(1)
        if std_id in items:        # first table wins; later tables are sub-tables
            continue
        items[std_id] = {
            "id": std_id,
            "title": strip_md(cells[1]),
            "decision": strip_md(cells[2]),
            "detail": strip_md(cells[3]),
            "status": strip_md(cells[4]),
            "active": status_is_active(cells[4]),
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
        self.is_companion = (
            header.lower().endswith(STD_10_COMPANION_SUFFIX)
            or header.lower().endswith(" reason")
            or header.lower().endswith("data source")
            or header.lower().endswith("[ref]")
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

def check_std_01(profiles, ctx):
    """STD-01 Null / Missing Value Encoding.

    Decision: categorical -> `not found`; numeric -> keep the column pure and
    put the reason in a companion column. Companion vocabulary should cover
    null, not found, not applicable, not available.

    Owns: null proxies in non-numeric columns, and the vocabulary used inside
    `_reason` companion columns. Numeric cells belong to STD-05; a *missing*
    companion column belongs to STD-10.
    """
    findings = []
    for p in profiles:
        if p.role in ("boolean", "numeric", "year", "date", "empty"):
            continue
        if UNIT_PARENTHETICAL_RE.search(p.header) or p.is_percent:
            continue        # numeric by intent — STD-05 and STD-10 own these

        if is_reason_companion(p.header):
            for row, val in p.cells:
                if val.lower() not in STD_01_COMPANION_VOCAB:
                    findings.append(cell_finding(
                        "STD-01", "warning", p, row, val,
                        "Companion column value is outside the STD-01 vocabulary "
                        "(null / not found / not applicable / not available)",
                        "one of: not found, not applicable, not available, null",
                    ))
            continue

        for row, val in p.cells:
            low = val.lower()
            if low in NULL_PROXY_TOKENS and low != STD_01_CATEGORICAL_NULL:
                findings.append(cell_finding(
                    "STD-01", "error", p, row, val,
                    f"Non-standard missing-value token in a {p.role} column",
                    STD_01_CATEGORICAL_NULL,
                ))
    return findings


def is_reason_companion(header):
    low = header.lower()
    return low.endswith(STD_10_COMPANION_SUFFIX) or low.endswith(" reason")


def check_std_02(profiles, ctx):
    """STD-02 Multi-value Separators.

    Decision: use `;`.

    Reference-aware, because `&` is vocabulary (`iron & steel`, `Central &
    South America`) far more often than it is a separator. A comma is only
    called a separator when the parts it produces are themselves values —
    either members of a reference set, or values that appear standalone
    elsewhere in the same column.
    """
    findings = []
    ref_all = ctx["ref_all"]

    for p in profiles:
        if p.role not in ("categorical", "text"):
            continue
        if p.is_companion or is_reason_companion(p.header):
            continue
        if header_has(p.header, GEOMETRY_HEADER_HINTS + URL_HEADER_HINTS + FREETEXT_HEADER_HINTS):
            continue

        # Values in this column that stand alone with no separator in them.
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

    Decision: use `True` / `False`.

    Also reports the sparse pattern (only `True` present, `False` implied by
    an empty cell) because an empty cell there is ambiguous between "no" and
    "not checked".
    """
    findings = []
    for p in profiles:
        if p.role != "boolean":
            continue

        for row, val in p.cells:
            low = val.lower()
            if val in (STD_03_TRUE, STD_03_FALSE):
                continue
            if low in BOOLEAN_TOKEN_MAP:
                findings.append(cell_finding(
                    "STD-03", "error", p, row, val,
                    "Boolean encoded as something other than True / False",
                    BOOLEAN_TOKEN_MAP[low],
                ))
            elif low in NULL_PROXY_TOKENS:
                findings.append(cell_finding(
                    "STD-03", "error", p, row, val,
                    "Third value in a boolean column; True/False are the only "
                    "allowed values, so the reason belongs in a companion column",
                    f"(blank) + record `{val}` in `{base_name(p.header)}{STD_10_COMPANION_SUFFIX}`",
                ))

        real = {v.lower() for _, v in p.real_values}
        if real and real <= {"true", "yes", "y", "1"} and p.n_blank:
            findings.append(column_finding(
                "STD-03", "info", p,
                f"Sparse boolean: only true values are recorded and "
                f"{p.n_blank:,} cells are empty, so `False` and `not checked` "
                f"are indistinguishable",
                f"write `{STD_03_FALSE}` explicitly where the answer is no",
            ))
    return findings


def check_std_04(profiles, ctx):
    """STD-04 Categorical Allowed Values.

    Decision: a QC script that runs on categorical columns of the working data
    and flags new values against the last release.

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
        if p.role != "categorical" or p.is_companion:
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
            # A multi-value cell is checked part by part. Whether the separator
            # is the right one is STD-02's business, not this check's.
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

    Decision: remove `#N/A` and coordinate pairs; no ranges, pick a single
    value; a standardized placeholder for blanks is allowed outside the
    database and is transformed to blank in ETL.

    STD-05 permits that placeholder while STD-01 keeps the numeric column
    pure. Taylor resolved the conflict in STD-01's favour on 2026-09-24: no
    placeholder token survives in a numeric column. The reason belongs in the
    companion column, so a missing-value token here is an error, not a warning.

    Owns every non-numeric cell sitting in a numeric column.
    """
    findings = []
    for p in profiles:
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
    base = base_name(prof.header)

    if low in EXCEL_ERRORS:
        return ("error", "Excel error value carried into the export", "(blank)")
    if COORD_PAIR_RE.match(val):
        return ("error",
                "A coordinate pair is stored in a single numeric column",
                f"keep only this column's own coordinate; move the other to its own column")
    if RANGE_RE.match(val):
        return ("error", "A range, not a value — STD-05 says pick a single value",
                "a single number")
    if QUALIFIED_RE.match(val):
        return ("error",
                "Qualified assertion in a numeric column (see also STD-10 pattern 1)",
                f"(blank) + record the qualifier in `{base}{STD_10_COMPANION_SUFFIX}`")
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
                f"(blank) + record the reason in `{base}{STD_10_COMPANION_SUFFIX}`")
    m = TRAILING_UNIT_RE.match(val)
    if m:
        return ("error", f"Unit `{m.group(2)}` stored alongside the number",
                m.group(1).replace(",", ""))
    return ("error", "Non-numeric value in a numeric column", "a single number")


def check_std_06(profiles, ctx):
    """STD-06 Date / Year Format.

    Decision: three separate columns in ISO format `YYYY-MM-DD`. Fiscal year
    (GCMT): a start-year `YYYY` column only, plus an associated column saying
    it is a fiscal year for a given country.

    Read as: a date-bearing field is split into Year / Month / Day columns so a
    record with only a year can fill the year column, which is what resolves
    the mixed-precision problem the STD-06 draft describes.
    """
    findings = []
    headers_low = {h.lower() for h in (profiles[0].sibling_headers if profiles else [])}

    for p in profiles:
        if p.role not in ("year", "date"):
            continue
        fiscal = "fiscal" in p.header.lower()

        for row, val in p.cells:
            severity, problem, fix = classify_date_value(val, p.role, fiscal, p)
            if problem:
                findings.append(cell_finding("STD-06", severity, p, row, val, problem, fix))

        if p.role == "date":
            base = base_name(p.header)
            base = re.sub(r"\s*\b(date|dates)\b\s*$", "", base, flags=re.I).strip() or base
            wanted = [f"{base} {part}".lower() for part in ("Year", "Month", "Day")]
            if not all(w in headers_low for w in wanted):
                findings.append(column_finding(
                    "STD-06", "warning", p,
                    "Date field is a single column; STD-06 splits a date across "
                    "three columns so partly-known dates can still be recorded",
                    f"split into `{base} Year`, `{base} Month`, `{base} Day`",
                ))
    return findings


def classify_date_value(val, role, fiscal, prof):
    """-> (severity, problem, suggested_fix) for one date/year cell."""
    low = val.strip().lower()
    base = base_name(prof.header)

    if low in NULL_PROXY_TOKENS:
        return ("warning", "Missing-value token in a date/year column",
                f"(blank) + record the reason in `{base}{STD_10_COMPANION_SUFFIX}`")
    if low in ("0", "0.0", "0.00"):
        return ("error", "`0` is Excel's empty-date artifact, not a date", "(blank)")

    m = FISCAL_YEAR_RE.match(val)
    if m:
        if fiscal:
            return ("warning",
                    "Fiscal year spans two years in one cell; STD-06 keeps the "
                    "start year only, with a companion column marking it fiscal",
                    f"{m.group(1)} + a companion column flagging the fiscal year")
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


def check_std_07(profiles, ctx):
    """STD-07 Required Fields / Nullability. NOT ACTIVE.

    Decision log: "No decision recorded in notes", status "Not yet reviewed -
    flagged as quick." Nothing to enforce until a required-field list exists.

    When it is decided, this becomes: for each field marked is_required, flag
    every blank cell.
    """
    return []


# Generic words that should be lowercase mid-header under STD-08. Kept small
# and explicit so the casing check stays quiet on proper nouns and acronyms.
GENERIC_HEADER_WORDS = {
    "name", "names", "year", "years", "date", "dates", "capacity", "status",
    "type", "types", "number", "unit", "units", "area", "region", "country",
    "state", "province", "city", "location", "owner", "operator", "parent",
    "company", "source", "sources", "start", "end", "retired", "planned",
    "total", "annual", "output", "production", "project", "plant", "mine",
    "phase", "level", "value", "values", "code", "id", "note", "notes",
    "comment", "comments", "detail", "details", "fuel", "technology",
    "method", "grade", "size", "age", "share", "percent", "latitude",
    "longitude", "coordinates", "address", "link", "url", "reference",
}


def check_std_08(profiles, ctx):
    """STD-08 Field Naming Conventions.

    Decision: lowercase unless a proper noun or a header column, which take
    title case. No question marks in column headers. Option B for geographic
    fields — explainer parentheses move into the documentation. Units of
    measurement get two separate columns.

    Header-level, so findings are scoped to the column, not a cell. The
    still-open parts of STD-08 (language variants, plurality hints) are
    deliberately not checked — see the Open items in the decision log.
    """
    findings = []
    for p in profiles:
        h = p.header

        if "?" in h:
            findings.append(column_finding(
                "STD-08", "error", p,
                "Question mark in a column header",
                h.replace("?", "").strip(),
            ))

        m = UNIT_PARENTHETICAL_RE.search(h)
        if m:
            base = strip_parentheticals(h)
            unit = m.group(0).strip("()")
            findings.append(column_finding(
                "STD-08", "warning", p,
                f"Unit `{unit}` is baked into the header; STD-08 keeps the unit "
                f"in its own column so conversions stay formula-friendly",
                f"`{base}` + `{base} Unit` (with `{unit}` as the value)",
            ))

        m = GEO_EXPLAINER_RE.search(h)
        if m:
            findings.append(column_finding(
                "STD-08", "warning", p,
                "Geographic explainer in parentheses; STD-08 Option B moves it "
                "into the documentation to shorten the header",
                strip_parentheticals(h),
            ))

        offenders = [
            w for w in strip_parentheticals(h).split()[1:]
            if w[:1].isupper() and not w.isupper() and w.lower().strip(",") in GENERIC_HEADER_WORDS
        ]
        if offenders:
            findings.append(column_finding(
                "STD-08", "info", p,
                f"Title case on common word(s) {', '.join(offenders)}; STD-08 is "
                f"lowercase unless a proper noun",
                lowercase_generic_words(h),
            ))
    return findings


def lowercase_generic_words(header):
    def repl(match):
        w = match.group(0)
        return w.lower() if w.lower() in GENERIC_HEADER_WORDS else w
    words = header.split()
    return " ".join(
        [words[0]] + [re.sub(r"^\w+", repl, w) for w in words[1:]]
    )


def check_std_09(profiles, ctx):
    """STD-09 Cross-field Links. NOT ACTIVE.

    Decision log: "No decision recorded in notes", status "Not yet reviewed -
    flagged as quick."

    When decided, this becomes: verify that linked field pairs agree — e.g. a
    year-of-X field populated only where X is populated, and entity IDs
    resolving to the name recorded alongside them.
    """
    return []


def check_std_10(profiles, ctx):
    """STD-10 Imputed Values.

    From the pattern and decision-point tables:
      - Pattern 1 (Proposed/Open): `>0` bounded assertions use the STD-01
        `not found` companion and leave the numeric column blank.
      - Pattern 5 (Proposed): a capacity factor needs a year and a source
        alongside it, like production data.
      - Pattern 6 (Open): `unknown` in a fraction/percentage field becomes
        blank, with the reason in the adjacent descriptive column.
      - Decision point 4: the companion is a categorical `{field}_reason`.

    Patterns 2 (deferred), 4 and 7 (closed) are intentionally not checked.
    Owns the *missing or misnamed* companion column; STD-01 owns what goes
    inside one.
    """
    findings = []
    headers_low = {h.lower() for h in (profiles[0].sibling_headers if profiles else [])}

    for p in profiles:
        base = base_name(p.header)
        companion = f"{base}{STD_10_COMPANION_SUFFIX}".lower()
        has_companion = companion in headers_low or f"{base} reason".lower() in headers_low

        # Pattern 6 — `unknown` in a fraction/percentage field
        if p.is_percent and p.role in ("numeric", "categorical", "text"):
            for row, val in p.cells:
                if val.lower() in NULL_PROXY_TOKENS:
                    findings.append(cell_finding(
                        "STD-10", "error", p, row, val,
                        "Sentinel in a fraction/percentage field; STD-10 pattern 6 "
                        "leaves the number blank and puts the reason alongside it",
                        f"(blank) + `{base}{STD_10_COMPANION_SUFFIX}` = why it is unknown",
                    ))

        # Pattern 1 — bounded assertions, reported once per column
        if p.role == "numeric" or UNIT_PARENTHETICAL_RE.search(p.header):
            bounded = [v for _, v in p.cells if QUALIFIED_RE.match(v)]
            if bounded:
                findings.append(column_finding(
                    "STD-10", "warning", p,
                    f"{len(bounded):,} bounded assertions such as `{bounded[0]}`; "
                    f"STD-10 pattern 1 replaces these with a blank number and the "
                    f"STD-01 `not found` companion",
                    f"add `{base}{STD_10_COMPANION_SUFFIX}` and blank the number",
                ))

            # Decision point 4 — companion naming
            if p.n_null_proxy and not has_companion:
                findings.append(column_finding(
                    "STD-10", "info", p,
                    f"{p.n_null_proxy:,} cells hold a reason token but there is no "
                    f"companion column to move it into",
                    f"add a categorical `{base}{STD_10_COMPANION_SUFFIX}` column",
                ))

        # Pattern 5 — capacity factor needs a year and a source
        if "capacity factor" in p.header.lower():
            stem = base_name(p.header).lower()
            related = [h for h in headers_low if h.startswith(stem) and h != p.header.lower()]
            missing = []
            if not any("year" in h for h in related):
                missing.append("year")
            if not any(("source" in h or "[ref]" in h) for h in related):
                missing.append("data source")
            if missing:
                findings.append(column_finding(
                    "STD-10", "warning", p,
                    f"Capacity factor with no {' and no '.join(missing)} alongside it; "
                    f"STD-10 pattern 5 treats it like production data — true only "
                    f"for a given year, and it has to come from somewhere",
                    f"add `{base} Year` and `{base} Data Source`",
                ))

        # Pattern 3 — startYearLow is not used
        if slugify(p.header) in ("startyearlow", "start_year_low"):
            findings.append(column_finding(
                "STD-10", "warning", p,
                "STD-10 pattern 3 records that `startYearLow` is not used",
                "drop the column; use a planned-start-year checkbox instead",
            ))
    return findings


def check_std_11(profiles, ctx):
    """STD-11 Data Provenance / Source Fields. NOT ACTIVE.

    Decision log: "No decision recorded in notes - flagged as quick, and ignore
    wiki url point", status "Not yet reviewed".

    When decided, this becomes: every data field has a companion source field
    under one naming convention (`[ref]` vs `{Field} Data Source`), and a
    populated data field implies a populated source.
    """
    return []


def check_std_12(profiles, ctx):
    """STD-12 Geographic Hierarchy. NOT ACTIVE.

    Decision log: "No decision recorded in notes", status "Not yet reviewed".

    When decided, this becomes: subnational names validate against the country
    recorded on the row, and the country/major-area/local-area levels are
    populated consistently down the hierarchy.
    """
    return []


def check_std_13(profiles, ctx):
    """STD-13 Temporal Snapshots / "As Of" Dating. NOT ACTIVE.

    Decision log: "No decision recorded in notes", status "Not yet reviewed".

    When decided, this becomes: every release carries an as-of date, and
    point-in-time fields say which snapshot they belong to.
    """
    return []


# Scaffolded but not yet written. If the decision log activates one of these,
# the run says so out loud rather than reporting a silent pass.
for _fn in (check_std_07, check_std_09, check_std_11, check_std_12, check_std_13):
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

    summarize(findings, items)

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

    print(f"\n  {csv_path}\n  {html_path}\n")
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
