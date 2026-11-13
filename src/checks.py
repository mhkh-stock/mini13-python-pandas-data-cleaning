"""Checks for Mini #13 (run: python3 src/checks.py).

Every planted defect count is re-counted here from the raw CSV with the
Python standard library only (csv, re, json — no pandas), so the checks
stay independent of the pandas code in clean.py they verify. Counts are
compared against data/defect_manifest.json, outputs/summary.json and
outputs/cleaning_log.json; the clean file is re-scanned for zero
remaining defects of every type; row counts and money totals are
reconciled across the raw, duplicate, bad-quantity and clean files.

A check fails loudly (AssertionError naming the check); the run prints
the pass count only when all checks pass.
"""

import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "orders_messy_SAMPLE.csv"
CLEAN = ROOT / "data" / "processed" / "orders_clean_SAMPLE.csv"
MANIFEST = ROOT / "data" / "defect_manifest.json"
LOG = ROOT / "outputs" / "cleaning_log.json"
SUMMARY = ROOT / "outputs" / "summary.json"
GUIDE = ROOT / "outputs" / "cleaning_guide.md"
MINI12 = (ROOT.parent / "mini12-statistics-correlation-regression"
          / "LICENSE")

PASSED = 0

NULL_GUISES = {"", "NA", "null", "N/A"}
TEXT_COLS = ["customer_name", "city", "category", "product",
             "order_date", "unit_price_pkr"]
CANON_LOWER = {"mobiles": "Mobiles", "laptops": "Laptops",
               "accessories": "Accessories", "audio": "Audio",
               "home appliances": "Home Appliances"}
CANON_CITIES = {"Lahore", "Karachi", "Islamabad", "Rawalpindi",
                "Faisalabad"}
CANON_CATS = set(CANON_LOWER.values())
ORDER_RE = re.compile(r"^ORD-\d+$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONEY_RE = re.compile(r"Rs|PKR|,")
COLUMNS = ["order_id", "order_date", "customer_name", "city", "category",
           "product", "quantity", "unit_price_pkr", "total_pkr", "notes"]
CLEAN_COLUMNS = [c for c in COLUMNS if c != "notes"]


def check(name, cond):
    global PASSED
    assert cond, f"FAIL: {name}"
    PASSED += 1


def close(a, b, tol):
    return abs(a - b) <= tol


# ------------------------------------------------------- independent counts
def count_defects(rows):
    """Count all 10 defect types over deduplicated real-order rows."""
    valid = [d for d in rows if ORDER_RE.match(d["order_id"])]
    seen, uniq = set(), []
    for d in valid:
        key = tuple(d[c] for c in COLUMNS)
        if key not in seen:
            seen.add(key)
            uniq.append(d)
    junk = [d for d in rows if not ORDER_RE.match(d["order_id"])]
    notes = [d["notes"] for d in uniq]
    return {
        "n_rows": len(rows),
        "n_valid": len(valid),
        "n_unique_valid": len(uniq),
        "n_junk": len(junk),
        "duplicates": len(valid) - len(uniq),
        "whitespace": sum(1 for d in uniq for c in TEXT_COLS
                          if d[c] != d[c].strip()),
        "category_case": sum(
            1 for d in uniq
            if d["category"].strip() not in NULL_GUISES
            and d["category"].strip().lower() in CANON_LOWER
            and d["category"].strip()
            != CANON_LOWER[d["category"].strip().lower()]),
        "money_as_text": sum(1 for d in uniq
                             if MONEY_RE.search(d["unit_price_pkr"])),
        "mixed_dates": sum(1 for d in uniq
                           if not ISO_RE.match(d["order_date"])),
        "null_guises": sum(1 for d in uniq for c in
                           ("customer_name", "city", "category")
                           if d[c] in NULL_GUISES),
        "bad_qty": sum(1 for d in uniq if int(d["quantity"]) <= 0),
        "city_spellings": sum(
            1 for d in uniq
            if d["city"].strip() not in CANON_CITIES
            and d["city"].strip() not in NULL_GUISES
            # "Unknown" is technique 5's explicit fill, not a misspelling
            and d["city"].strip() != "Unknown"),
        "notes_breakdown": {
            "empty": sum(1 for v in notes if v == ""),
            "text": sum(1 for v in notes
                        if v != "" and not re.match(r"^\d+$", v)
                        and v.lower() not in ("true", "false")),
            "numeric": sum(1 for v in notes
                           if re.match(r"^\d+$", v)),
            "boolean": sum(1 for v in notes
                           if v.lower() in ("true", "false")),
        },
    }


def parseable_int(s):
    s = s.strip()
    return int(s) if re.match(r"^-?\d+$", s) else None


# ------------------------------------------------------------------ raw file
raw_lines = RAW.read_text().splitlines()
raw_reader = list(csv.reader(open(RAW)))
header = raw_reader[0]
raw_data = [r for r in raw_reader[1:] if r]
blank_lines = len([r for r in raw_reader[1:] if not r])
raw_dicts = [dict(zip(header, r)) for r in raw_data]
D = count_defects(raw_dicts)
M = json.loads(MANIFEST.read_text())
MD = M["defects"]

check("raw header is the 10 expected columns", header == COLUMNS)
check("raw file has 131 data rows", D["n_rows"] == 131)
check("raw file has 134 lines incl. header (131 + 2 blank + header)",
      len(raw_lines) == 134)
check("raw file has 2 blank lines", blank_lines == 2)
check("raw file has 128 valid order rows", D["n_valid"] == 128)
check("raw file has 120 unique valid orders", D["n_unique_valid"] == 120)
check("raw file has 3 junk rows", D["n_junk"] == 3)
check("manifest seed is 137", M["seed"] == 137)
check("manifest base rows = 120", M["base_rows"] == 120)
check("manifest raw data rows = 131", M["raw_data_rows"] == 131)
check("manifest blank lines = 2", M["blank_lines"] == 2)
check("manifest expected clean rows = 114",
      M["expected_clean_rows"] == 114)

# each planted count matches the independent re-count, exactly
check("defect 01 whitespace = 12", D["whitespace"] == 12
      and MD["01_whitespace_cells"] == 12)
check("defect 02 category case = 10", D["category_case"] == 10
      and MD["02_category_case_cells"] == 10)
check("defect 03 money as text = 15", D["money_as_text"] == 15
      and MD["03_money_as_text_cells"] == 15)
check("defect 04 mixed dates = 18", D["mixed_dates"] == 18
      and MD["04_mixed_date_format_cells"] == 18)
check("defect 05 null guises = 10", D["null_guises"] == 10
      and MD["05_null_guise_cells"] == 10)
check("defect 06 exact duplicates = 8", D["duplicates"] == 8
      and MD["06_exact_duplicate_rows"] == 8)
check("defect 07 bad quantities = 6", D["bad_qty"] == 6
      and MD["07_bad_quantity_rows"] == 6)
check("defect 08 city spellings = 8", D["city_spellings"] == 8
      and MD["08_city_spelling_cells"] == 8)
check("defect 09 notes breakdown = 100/12/5/3",
      D["notes_breakdown"] == {"empty": 100, "text": 12,
                               "numeric": 5, "boolean": 3}
      and MD["09_mixed_type_notes"] == D["notes_breakdown"])
check("defect 10 junk rows = 3", D["n_junk"] == 3
      and MD["10_junk_rows"] == 3)

# ---------------------------------------------------------------- clean file
clean_rows = list(csv.DictReader(open(CLEAN)))
C = count_defects([{**{c: "" for c in COLUMNS}, **d,
                    "notes": ""} for d in clean_rows])
# (count_defects expects all 10 columns; clean rows lack notes, so the
#  notes column is padded with "" — the padding is documented here, not
#  hidden: the clean file has no notes column, checked below.)

check("clean file has 114 rows", len(clean_rows) == 114)
check("clean columns are the 9 expected (notes dropped)",
      list(clean_rows[0].keys()) == CLEAN_COLUMNS)
check("clean order_ids are unique",
      len({r["order_id"] for r in clean_rows}) == 114)
check("clean file: 0 whitespace defects", C["whitespace"] == 0)
check("clean file: 0 category-case defects", C["category_case"] == 0)
check("clean file: 0 money-as-text defects", C["money_as_text"] == 0)
check("clean file: 0 mixed-date defects", C["mixed_dates"] == 0)
check("clean file: 0 null-guise defects", C["null_guises"] == 0)
check("clean file: 0 duplicate rows", C["duplicates"] == 0)
check("clean file: 0 bad-quantity rows", C["bad_qty"] == 0)
check("clean file: 0 city-spelling defects", C["city_spellings"] == 0)
check("clean file: 0 junk rows", C["n_junk"] == 0)
check("clean file: no empty cells in any column",
      all(v != "" for r in clean_rows for v in r.values()))
check("clean file: all dates ISO and within Jan–Jun 2026",
      all(ISO_RE.match(r["order_date"]) for r in clean_rows)
      and all(datetime.strptime(r["order_date"], "%Y-%m-%d").month <= 6
              for r in clean_rows))
check("clean file: date range 2026-01-02 to 2026-06-28",
      min(r["order_date"] for r in clean_rows) == "2026-01-02"
      and max(r["order_date"] for r in clean_rows) == "2026-06-28")
check("clean file: all quantities positive",
      all(int(r["quantity"]) > 0 for r in clean_rows))
check("clean file: total = quantity x unit_price on every row",
      all(int(r["total_pkr"]) == int(r["quantity"])
          * int(r["unit_price_pkr"]) for r in clean_rows))
check("clean file: categories are canonical or Unknown",
      all(r["category"] in CANON_CATS | {"Unknown"}
          for r in clean_rows))
check("clean file: cities are canonical or Unknown",
      all(r["city"] in CANON_CITIES | {"Unknown"}
          for r in clean_rows))
check("clean file: exactly 3 Unknown categories, 4 Unknown cities, "
      "3 Unknown Customer names",
      sum(1 for r in clean_rows if r["category"] == "Unknown") == 3
      and sum(1 for r in clean_rows if r["city"] == "Unknown") == 4
      and sum(1 for r in clean_rows
              if r["customer_name"] == "Unknown Customer") == 3)

# --------------------------------------------------------- money + row recon
clean_total = sum(int(r["total_pkr"]) for r in clean_rows)
raw_total = sum(v for d in raw_dicts
                for v in [parseable_int(d["total_pkr"])] if v is not None)
seen, dup_total = set(), 0
for d in raw_dicts:
    if not ORDER_RE.match(d["order_id"]):
        continue
    key = tuple(d[c] for c in COLUMNS)
    if key in seen:
        dup_total += int(d["total_pkr"])
    seen.add(key)
bad_total = sum(int(d["total_pkr"]) for d in raw_dicts
                if ORDER_RE.match(d["order_id"])
                and int(d["quantity"]) <= 0)
# bad_total over ALL valid rows (incl. copies) equals the deduped sum:
# the 6 bad rows are clean rows, never duplicated.
check("row reconciliation: 131 - 3 junk - 8 dups - 6 bad = 114",
      131 - 3 - 8 - 6 == len(clean_rows) == 114)
check("clean total is PKR 12,290,259", clean_total == 12290259)
check("raw parseable total is PKR 13,119,238", raw_total == 13119238)
check("duplicate copies total PKR 1,058,973", dup_total == 1058973)
check("bad-quantity rows total PKR -229,994", bad_total == -229994)
check("money reconciles: raw = clean + dups + bad",
      raw_total == clean_total + dup_total + bad_total)
check("clean units total is 358",
      sum(int(r["quantity"]) for r in clean_rows) == 358)
check("clean average order value is PKR 107,809.29",
      close(clean_total / len(clean_rows), 107809.29, 0.01))

# ------------------------------------------------------- summary.json match
S = json.loads(SUMMARY.read_text())
check("summary clean rows = 114", S["rows"]["clean_rows"] == 114)
check("summary raw rows = 131", S["rows"]["raw_data_rows"] == 131)
check("summary removals are 8 dups / 6 bad / 3 junk",
      S["rows"]["duplicate_rows_removed"] == 8
      and S["rows"]["bad_quantity_rows_removed"] == 6
      and S["rows"]["junk_rows_removed"] == 3)
check("summary defects_fixed match independent counts",
      S["defects_fixed"]["01_whitespace_cells"] == 12
      and S["defects_fixed"]["02_category_case_cells"] == 10
      and S["defects_fixed"]["03_money_as_text_cells"] == 15
      and S["defects_fixed"]["04_mixed_date_format_cells"] == 18
      and S["defects_fixed"]["05_null_guise_cells"] == 10
      and S["defects_fixed"]["06_exact_duplicate_rows"] == 8
      and S["defects_fixed"]["07_bad_quantity_rows"] == 6
      and S["defects_fixed"]["08_city_spelling_cells"] == 8
      and S["defects_fixed"]["09_mixed_type_notes_breakdown"]
      == {"empty": 100, "text": 12, "numeric": 5, "boolean": 3}
      and S["defects_fixed"]["10_junk_rows"] == 3
      and S["defects_fixed"]["10_blank_lines"] == 2)
check("summary money block reconciles",
      S["money_pkr"]["raw_total_all_rows_pkr"] == 13119238
      and S["money_pkr"]["clean_total_pkr"] == 12290259
      and S["money_pkr"]["duplicate_copies_total_pkr"] == 1058973
      and S["money_pkr"]["bad_quantity_rows_total_pkr"] == -229994
      and S["money_pkr"]["reconciled"] is True)
check("summary clean totals match recompute",
      S["clean_totals"]["total_pkr"] == clean_total
      and S["clean_totals"]["orders"] == 114
      and S["clean_totals"]["units"] == 358
      and close(S["clean_totals"]["avg_order_value_pkr"], 107809.29,
                0.01))
by_cat, by_city = {}, {}
for r in clean_rows:
    by_cat.setdefault(r["category"], [0, 0])
    by_cat[r["category"]][0] += 1
    by_cat[r["category"]][1] += int(r["total_pkr"])
    by_city.setdefault(r["city"], [0, 0])
    by_city[r["city"]][0] += 1
    by_city[r["city"]][1] += int(r["total_pkr"])
check("summary by-category breakdown matches recompute",
      all(S["clean_totals"]["by_category"][k]["orders"] == v[0]
          and S["clean_totals"]["by_category"][k]["total_pkr"] == v[1]
          for k, v in by_cat.items())
      and len(S["clean_totals"]["by_category"]) == len(by_cat))
check("summary by-city breakdown matches recompute",
      all(S["clean_totals"]["by_city"][k]["orders"] == v[0]
          and S["clean_totals"]["by_city"][k]["total_pkr"] == v[1]
          for k, v in by_city.items())
      and len(S["clean_totals"]["by_city"]) == len(by_city))
check("summary labels the data SAMPLE", "SAMPLE" in S["status"])

# ------------------------------------------------------------- log + guide
L = json.loads(LOG.read_text())
T = L["techniques"]
check("cleaning log counts match independent counts",
      T["01_whitespace"]["fixed_cells"] == 12
      and T["02_category_case"]["fixed_cells"] == 10
      and T["03_money_as_text"]["fixed_cells"] == 15
      and T["04_mixed_date_formats"]["fixed_cells"] == 18
      and T["05_null_guises"]["fixed_cells"] == 10
      and T["05_null_guises"]["by_column"]
      == {"customer_name": 3, "city": 4, "category": 3}
      and T["06_exact_duplicates"]["removed_rows"] == 8
      and T["07_bad_quantities"]["removed_rows"] == 6
      and T["08_city_spellings"]["fixed_cells"] == 8
      and T["09_mixed_type_column"]["breakdown"]
      == {"empty": 100, "text": 12, "numeric": 5, "boolean": 3}
      and T["10_junk_rows_blank_lines"]["removed_rows"] == 3
      and T["10_junk_rows_blank_lines"]["blank_lines"] == 2)
check("cleaning log row counts reconcile",
      L["row_counts"]["raw_data_rows"] == 131
      and L["row_counts"]["clean_rows"] == 114
      and L["row_counts"]["removed_total"] == 17)

g = GUIDE.read_text()
check("guide contains all 10 technique fixed/removed counts",
      "Fixed: 12 cells" in g and "Fixed: 10 cells" in g
      and "Fixed: 15 cells" in g and "Fixed: 18 cells" in g
      and "Removed: 8 rows" in g and "Removed: 6 rows" in g
      and "Fixed: 8 cells" in g and "Removed: 3 junk rows" in g)
check("guide contains the clean and raw totals",
      "12,290,259" in g and "13,119,238" in g
      and "1,058,973" in g and "-229,994" in g)
check("guide shows a before/after money example",
      '"Rs. 1,499"' in g and "1499" in g)
check("guide shows a before/after date example",
      '"25/03/2026"' in g and '"2026-03-25"' in g)
check("guide shows a before/after city example",
      '"LHR"' in g and '"Lahore"' in g)
check("guide states the money reconciliation identity",
      "No genuine order's total changed" in g)
check("guide labels the data SAMPLE", "SAMPLE" in g)

# ------------------------------------------------------- labels & files
readme = (ROOT / "README.md").read_text()
check("README labels the data SAMPLE", "SAMPLE" in readme)
check("README states the data is never real client work",
      "never claimed as real client work" in readme.lower())
check("README contains the clean total", "12,290,259" in readme)
check("README contains the raw total", "13,119,238" in readme)
check("README contains the clean row count", "114" in readme)
check("README lists all 10 techniques by name",
      all(t in readme for t in
          ("Strip whitespace", "Standardise case", "Money as text",
           "Mixed date formats", "Nulls in disguise",
           "Exact duplicates", "Impossible quantities",
           "City spellings", "Mixed-type column",
           "Junk rows + blank lines")))
check("data README exists and documents all 10 columns",
      (ROOT / "data" / "README.md").exists()
      and all(c in (ROOT / "data" / "README.md").read_text()
              for c in COLUMNS))
check("requirements.txt names pandas",
      "pandas" in (ROOT / "requirements.txt").read_text().lower())
check("LICENSE exists and is identical to Mini #12's MIT license",
      (ROOT / "LICENSE").exists()
      and (ROOT / "LICENSE").read_bytes() == MINI12.read_bytes())
check("guide file exists", GUIDE.exists())
check("summary file exists", SUMMARY.exists())
check("cleaning log file exists", LOG.exists())
check("manifest file exists", MANIFEST.exists())

# ------------------------------------------------------- determinism (re-run)
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


csv_before = sha(RAW)
subprocess.run([sys.executable, str(ROOT / "src" / "generate_data.py")],
               check=True, capture_output=True)
check("generate_data.py is deterministic (CSV hash unchanged)",
      sha(RAW) == csv_before)
clean_before, sum_before = sha(CLEAN), sha(SUMMARY)
subprocess.run([sys.executable, str(ROOT / "src" / "clean.py")],
               check=True, capture_output=True)
check("clean.py is deterministic (clean CSV hash unchanged)",
      sha(CLEAN) == clean_before)
check("clean.py is deterministic (summary hash unchanged)",
      sha(SUMMARY) == sum_before)

print(f"\n{PASSED} checks passed, 0 failed.")
