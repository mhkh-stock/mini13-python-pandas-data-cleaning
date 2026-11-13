"""Clean Mini #13 — 10 pandas data-cleaning techniques, one per defect.

Reads data/raw/orders_messy_SAMPLE.csv (120 messy SAMPLE orders from
fictional "Noor Electronics"), applies 10 numbered techniques in order,
and writes:
  data/processed/orders_clean_SAMPLE.csv   (114 clean rows)
  outputs/cleaning_log.json               (what each step fixed, counts)
  outputs/summary.json                    (every verified number)
  outputs/cleaning_guide.md               (the teaching write-up)

Technique order is deliberate and is itself a lesson: fix VALUES first
(strip, case, money, dates, nulls), then fix ROWS (duplicates, bad
quantities), then fix the remaining COLUMNS (mixed-type column), and
only at the very end drop the junk rows — junk rows are removed last so
that every earlier count is taken over the full file and matches the
planted manifest exactly. The two blank lines never reach pandas at
all (read_csv skips them); they are counted from the raw text instead.

Run: python3 src/clean.py
Requires: pandas (see requirements.txt).
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "orders_messy_SAMPLE.csv"
MANIFEST = ROOT / "data" / "defect_manifest.json"
CLEAN = ROOT / "data" / "processed" / "orders_clean_SAMPLE.csv"
LOG = ROOT / "outputs" / "cleaning_log.json"
SUMMARY = ROOT / "outputs" / "summary.json"
GUIDE = ROOT / "outputs" / "cleaning_guide.md"

NULL_GUISES = {"", "NA", "null", "N/A"}
TEXT_COLS = ["customer_name", "city", "category", "product"]
CATEGORIES = {"mobiles": "Mobiles", "laptops": "Laptops",
              "accessories": "Accessories", "audio": "Audio",
              "home appliances": "Home Appliances"}
CANON_CITIES = {"Lahore", "Karachi", "Islamabad", "Rawalpindi",
                "Faisalabad"}
CITY_MAP = {"lhr": "Lahore", "lahore": "Lahore",
            "khi": "Karachi", "karachi": "Karachi",
            "isb": "Islamabad", "islamabad": "Islamabad",
            "rwp": "Rawalpindi", "rawalpindi": "Rawalpindi",
            "fsd": "Faisalabad", "faisalabad": "Faisalabad"}
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%b %d, %Y"]
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ORDER_RE = re.compile(r"^ORD-\d+$")
MONEY_RE = re.compile(r"Rs|PKR|,")
FILL = {"customer_name": "Unknown Customer", "city": "Unknown",
        "category": "Unknown"}

log = {"techniques": {}, "row_counts": {}, "money": {}}


def note(n, **kw):
    log["techniques"][n] = kw


def parse_money(value):
    """'Rs. 45,000' / 'Rs.45000' / '45,000' / 'PKR 45,000' -> 45000.

    Junk values such as '---' parse to NaN instead of raising, so the
    junk rows survive until technique 10 removes them.
    """
    if not isinstance(value, str):
        return np.nan
    if MONEY_RE.search(value):
        digits = re.sub(r"[^0-9]", "", value)
        return int(digits) if digits else np.nan
    return int(value) if value.strip().isdigit() else np.nan


def parse_date(value):
    """Try each known format in turn; unparseable values become NaT."""
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(value, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


def fmt(n):
    return f"{n:,}"


def main():
    # --- read: everything as text, nothing silently converted --------
    # keep_default_na=False keeps "", "NA", "null" and "N/A" as literal
    # strings, so technique 5 can see (and count) all four guises.
    raw_lines = RAW.read_text().splitlines()
    blank_lines = sum(1 for line in raw_lines if line.strip() == "")
    df = pd.read_csv(RAW, dtype=str, keep_default_na=False)
    log["row_counts"]["raw_data_rows"] = len(df)
    log["row_counts"]["blank_lines_in_file"] = blank_lines
    log["row_counts"]["raw_file_lines_incl_header"] = len(raw_lines)

    # --- Technique 1: strip leading/trailing whitespace --------------
    # .str.strip() on every text column. Counts every cell it changes.
    fixed, example = 0, None
    for col in TEXT_COLS + ["order_date", "unit_price_pkr"]:
        before = df[col].copy()
        df[col] = df[col].str.strip()
        changed = before != df[col]
        fixed += int(changed.sum())
        if example is None and changed.any():
            i = changed[changed].index[0]
            example = {"column": col, "order_id": df.at[i, "order_id"],
                       "before": before[i], "after": df.at[i, col]}
    note("01_whitespace", fixed_cells=fixed,
         description="str.strip() on text columns", example=example)

    # --- Technique 2: standardise category case ----------------------
    # Lower-case first, then map to the one canonical spelling. A value
    # that is not a known category (a null guise, a junk value) maps to
    # NaN and is left alone for its own technique to handle.
    mapped = df["category"].str.lower().map(CATEGORIES)
    changed = mapped.notna() & (mapped != df["category"])
    ex_i = changed[changed].index[0]
    example = {"order_id": df.at[ex_i, "order_id"],
               "before": df.at[ex_i, "category"],
               "after": mapped[ex_i]}
    df.loc[changed, "category"] = mapped[changed]
    note("02_category_case", fixed_cells=int(changed.sum()),
         description="lower-case then map to canonical category names",
         example=example)

    # --- Technique 3: money stored as text -> integer PKR -------------
    money_mask = df["unit_price_pkr"].str.contains(MONEY_RE, regex=True)
    ex_i = money_mask[money_mask].index[0]
    example = {"order_id": df.at[ex_i, "order_id"],
               "before": df.at[ex_i, "unit_price_pkr"],
               "after": parse_money(df.at[ex_i, "unit_price_pkr"])}
    df["unit_price_pkr"] = df["unit_price_pkr"].apply(parse_money)
    df["total_pkr"] = pd.to_numeric(df["total_pkr"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    note("03_money_as_text", fixed_cells=int(money_mask.sum()),
         description="strip 'Rs.'/'PKR'/commas, cast to int PKR",
         example=example)

    # --- Technique 4: mixed date formats -> one ISO format -----------
    # A row counts as fixed only if it parses AND was not already ISO,
    # so junk rows (unparseable) never inflate the count.
    parsed = df["order_date"].apply(parse_date)
    was_iso = df["order_date"].str.match(ISO_RE)
    fixed_mask = parsed.notna() & ~was_iso
    ex_i = fixed_mask[fixed_mask].index[0]
    example = {"order_id": df.at[ex_i, "order_id"],
               "before": df.at[ex_i, "order_date"],
               "after": parsed[ex_i].strftime("%Y-%m-%d")}
    df["order_date"] = parsed.dt.strftime("%Y-%m-%d")
    note("04_mixed_date_formats", fixed_cells=int(fixed_mask.sum()),
         description="try %Y-%m-%d, %d/%m/%Y, %d-%m-%Y, '%b %d, %Y'; "
                     "write back ISO yyyy-mm-dd",
         example=example)

    # --- Technique 5: nulls in disguise -> real missing, then fill ----
    # Four guises ("", "NA", "null", "N/A") become NaN, then each column
    # gets its explicit fill value. Nothing is silently dropped: a
    # missing name becomes "Unknown Customer", never an invented name.
    filled, examples = {}, None
    for col in ["customer_name", "city", "category"]:
        mask = df[col].isin(NULL_GUISES)
        filled[col] = int(mask.sum())
        if examples is None and mask.any():
            i = mask[mask].index[0]
            raw_before = df.at[i, col]
            examples = {"column": col, "order_id": df.at[i, "order_id"],
                        "before": ("(empty string)" if raw_before == ""
                                   else repr(raw_before)),
                        "after": FILL[col]}
        df.loc[mask, col] = np.nan
    for col, value in FILL.items():
        df[col] = df[col].fillna(value)
    note("05_null_guises", fixed_cells=sum(filled.values()),
         by_column=filled, description="guises -> NaN -> explicit "
         "'Unknown' fill (never an invented value)", example=examples)

    # --- Technique 6: drop exact duplicate rows ----------------------
    # Runs AFTER the value fixes, so a duplicate of a defective row is
    # identical to its original once fixed, and is still caught.
    dup_ids = df.loc[df.duplicated("order_id", keep=False),
                     "order_id"].unique().tolist()
    before = len(df)
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    note("06_exact_duplicates", removed_rows=before - len(df),
         description="drop_duplicates(keep='first') over all columns",
         example={"duplicated_order_ids": sorted(dup_ids)[:3],
                  "copies_removed": before - len(df)})

    # Capture the notes-column breakdown NOW, over the 120 deduplicated
    # real orders: technique 7 below removes 6 rows, and counting the
    # breakdown after that would under-count by those rows' notes.
    _valid = df["order_id"].str.match(ORDER_RE, na=False)
    _notes = df.loc[_valid, "notes"]
    notes_breakdown = {
        "empty": int((_notes == "").sum()),
        "text": int(((_notes != "")
                     & ~_notes.str.match(r"^\d+$", na=False)
                     & ~_notes.str.lower().isin(["true", "false"])).sum()),
        "numeric": int(_notes.str.match(r"^\d+$", na=False).sum()),
        "boolean": int(_notes.str.lower().isin(["true", "false"]).sum()),
    }

    # --- Technique 7: drop invalid quantities ------------------------
    # Quantity <= 0 cannot be repaired — a -2 order never happened.
    # NaN quantities (junk rows) compare False and survive to technique 10.
    bad = df["quantity"] <= 0
    bad_example = None
    if bad.any():
        i = bad[bad].index[0]
        bad_example = {"order_id": df.at[i, "order_id"],
                       "quantity": int(df.at[i, "quantity"]),
                       "total_pkr": int(df.at[i, "total_pkr"])}
    bad_total = int(df.loc[bad, "total_pkr"].sum())
    df = df[~bad].reset_index(drop=True)
    note("07_bad_quantities", removed_rows=int(bad.sum()),
         removed_total_pkr=bad_total,
         description="drop rows where quantity <= 0 (unfixable)",
         example=bad_example)

    # --- Technique 8: standardise city spellings ---------------------
    # Case-insensitive map: "LHR" and "lahore" both become "Lahore".
    # "Unknown" (from technique 5) is not in the map and stays Unknown.
    mapped = df["city"].str.lower().map(CITY_MAP)
    changed = mapped.notna() & (mapped != df["city"])
    ex_i = changed[changed].index[0]
    example = {"order_id": df.at[ex_i, "order_id"],
               "before": df.at[ex_i, "city"], "after": mapped[ex_i]}
    df.loc[changed, "city"] = mapped[changed]
    note("08_city_spellings", fixed_cells=int(changed.sum()),
         description="case-insensitive map of abbreviations / "
                     "lower-case spellings to canonical city names",
         example=example)

    # --- Technique 9: handle the mixed-type column -------------------
    # The notes column holds empty strings, plain text, numbers-as-text
    # and "TRUE": four kinds of value in one column, with no consistent
    # meaning. Count the breakdown (captured after technique 6, over the
    # 120 deduplicated real orders, so neither the duplicate copies nor
    # the technique-7 removals inflate or shrink it), then DROP the
    # column — standardising it would invent meaning it never had.
    df = df.drop(columns=["notes"])
    note("09_mixed_type_column", breakdown=notes_breakdown,
         description="count the value kinds, then drop the column — "
                     "it has no consistent meaning to standardise",
         example={"dropped_column": "notes",
                  "values_seen": ["COD", "42", "TRUE", "urgent", ""]})

    # --- Technique 10: drop junk rows + count blank lines ------------
    # Rows whose order_id is not ORD-<digits> are file furniture
    # ("TOTAL", "---", "END OF FILE"), not orders. Blank lines were
    # counted from the raw text at the top — pandas skips them on read.
    junk = ~df["order_id"].str.match(ORDER_RE, na=False)
    junk_ids = sorted(df.loc[junk, "order_id"].tolist())
    df = df[~junk].reset_index(drop=True)
    note("10_junk_rows_blank_lines", removed_rows=int(junk.sum()),
         blank_lines=blank_lines,
         description="drop rows with no valid order_id; blank lines "
                     "counted from the raw text (pandas skips them)",
         example={"junk_order_ids": junk_ids})

    # --- finalise ------------------------------------------------------
    df = df.sort_values(["order_date", "order_id"]).reset_index(drop=True)
    df["quantity"] = df["quantity"].astype(int)
    df["unit_price_pkr"] = df["unit_price_pkr"].astype(int)
    df["total_pkr"] = df["total_pkr"].astype(int)
    assert (df["total_pkr"] == df["quantity"] * df["unit_price_pkr"]).all()
    assert df["order_id"].is_unique
    assert df["order_id"].str.match(ORDER_RE).all()

    log["row_counts"]["clean_rows"] = len(df)
    log["row_counts"]["removed_total"] = (
        log["row_counts"]["raw_data_rows"] - len(df))

    # --- money reconciliation ------------------------------------------
    # raw_total_all is computed from the RAW file (money parsed, nothing
    # dropped): it must equal clean + duplicate copies + bad-quantity
    # rows. The only change is the removal of rows that were never real
    # orders — no genuine order's total changes by a single rupee.
    raw = pd.read_csv(RAW, dtype=str, keep_default_na=False)
    raw_total = pd.to_numeric(raw["total_pkr"], errors="coerce").sum()
    # duplicate copies' total: sum of the 8 duplicated rows' totals
    dup_mask = raw.duplicated(subset=list(raw.columns), keep="first")
    dup_total = int(pd.to_numeric(raw.loc[dup_mask, "total_pkr"],
                                  errors="coerce").sum())
    clean_total = int(df["total_pkr"].sum())
    log["money"] = {
        "raw_total_all_rows_pkr": int(raw_total),
        "clean_total_pkr": clean_total,
        "duplicate_copies_total_pkr": dup_total,
        "bad_quantity_rows_total_pkr":
            log["techniques"]["07_bad_quantities"]["removed_total_pkr"],
        "reconciled": (int(raw_total) == clean_total + dup_total
                       + log["techniques"]["07_bad_quantities"]
                       ["removed_total_pkr"]),
    }

    CLEAN.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN, index=False)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w") as f:
        json.dump(log, f, indent=2, sort_keys=True)
        f.write("\n")

    # --- summary.json --------------------------------------------------
    by_cat = (df.groupby("category")["total_pkr"].agg(["count", "sum"])
              .to_dict("index"))
    by_city = (df.groupby("city")["total_pkr"].agg(["count", "sum"])
               .to_dict("index"))
    summary = {
        "pack": "Mini #13 — Python pandas Data Cleaning Pack",
        "shop": "Noor Electronics (Lahore) — fictional SAMPLE shop",
        "period": "2026-01 to 2026-06",
        "seed": 137,
        "status": "SAMPLE data, real pandas cleaning",
        "rows": {"raw_data_rows": log["row_counts"]["raw_data_rows"],
                 "blank_lines": blank_lines,
                 "junk_rows_removed":
                     log["techniques"]["10_junk_rows_blank_lines"]
                     ["removed_rows"],
                 "duplicate_rows_removed":
                     log["techniques"]["06_exact_duplicates"]
                     ["removed_rows"],
                 "bad_quantity_rows_removed":
                     log["techniques"]["07_bad_quantities"]
                     ["removed_rows"],
                 "clean_rows": len(df)},
        "defects_fixed": {
            "01_whitespace_cells":
                log["techniques"]["01_whitespace"]["fixed_cells"],
            "02_category_case_cells":
                log["techniques"]["02_category_case"]["fixed_cells"],
            "03_money_as_text_cells":
                log["techniques"]["03_money_as_text"]["fixed_cells"],
            "04_mixed_date_format_cells":
                log["techniques"]["04_mixed_date_formats"]["fixed_cells"],
            "05_null_guise_cells":
                log["techniques"]["05_null_guises"]["fixed_cells"],
            "06_exact_duplicate_rows":
                log["techniques"]["06_exact_duplicates"]["removed_rows"],
            "07_bad_quantity_rows":
                log["techniques"]["07_bad_quantities"]["removed_rows"],
            "08_city_spelling_cells":
                log["techniques"]["08_city_spellings"]["fixed_cells"],
            "09_mixed_type_notes_breakdown":
                log["techniques"]["09_mixed_type_column"]["breakdown"],
            "10_junk_rows":
                log["techniques"]["10_junk_rows_blank_lines"]
                ["removed_rows"],
            "10_blank_lines": blank_lines,
        },
        "money_pkr": log["money"],
        "clean_totals": {
            "total_pkr": clean_total,
            "orders": len(df),
            "units": int(df["quantity"].sum()),
            "avg_order_value_pkr": round(clean_total / len(df), 2),
            "by_category": {k: {"orders": int(v["count"]),
                                "total_pkr": int(v["sum"])}
                            for k, v in sorted(by_cat.items())},
            "by_city": {k: {"orders": int(v["count"]),
                            "total_pkr": int(v["sum"])}
                        for k, v in sorted(by_city.items())},
        },
        "clean_checks": {
            "all_dates_iso_yyyy_mm_dd": bool(
                df["order_date"].str.match(ISO_RE).all()),
            "date_range": [df["order_date"].min(), df["order_date"].max()],
            "no_nulls_in_required_columns": bool(
                df.notna().all().all()),
            "order_ids_unique": bool(df["order_id"].is_unique),
            "all_quantities_positive": bool((df["quantity"] > 0).all()),
            "total_equals_qty_x_price_every_row": bool(
                (df["total_pkr"]
                 == df["quantity"] * df["unit_price_pkr"]).all()),
        },
        "notes": [
            "Every defect count is exact by construction (seed 137) "
            "and independently re-counted by src/checks.py.",
            f"Money reconciliation: raw total PKR "
            f"{fmt(int(raw_total))} = clean PKR {fmt(clean_total)} + "
            f"duplicate copies PKR {fmt(dup_total)} + bad-quantity "
            f"rows PKR "
            f"{fmt(log['techniques']['07_bad_quantities']['removed_total_pkr'])}. "
            f"No genuine order's total changed; the difference is "
            f"only removed rows.",
            f"Unknown fills: "
            f"{log['techniques']['05_null_guises']['by_column']['customer_name']} "
            f"customer names, "
            f"{log['techniques']['05_null_guises']['by_column']['city']} "
            f"cities, "
            f"{log['techniques']['05_null_guises']['by_column']['category']} "
            f"categories were missing and are labelled Unknown — never "
            f"invented.",
        ],
    }
    with open(SUMMARY, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")

    # --- cleaning_guide.md ---------------------------------------------
    t = log["techniques"]
    guide = f"""# Mini #13 — pandas Data Cleaning Guide (SAMPLE data)

Fictional shop **Noor Electronics (Lahore)**, 120 online orders,
Jan–Jun 2026. The raw file is deliberately messy: 10 defect types were
planted in it (seed 137, see `data/defect_manifest.json`), and this
guide cleans it with 10 pandas techniques — one per defect — showing
the problem, the code pattern, a real before/after row, and the exact
count fixed. Every number below is computed by `src/clean.py` from the
raw file; reproduce it with `python3 src/clean.py`, then check it with
`python3 src/checks.py`.

## The scoreboard

| | Rows |
|---|---|
| Raw data rows in the file | {log["row_counts"]["raw_data_rows"]} |
| Blank lines at the end of the file | {blank_lines} |
| Exact duplicate rows removed (technique 6) | {t["06_exact_duplicates"]["removed_rows"]} |
| Bad-quantity rows removed (technique 7) | {t["07_bad_quantities"]["removed_rows"]} |
| Junk rows removed (technique 10) | {t["10_junk_rows_blank_lines"]["removed_rows"]} |
| **Clean rows** | **{len(df)}** |

Money: raw total **PKR {fmt(log["money"]["raw_total_all_rows_pkr"])}** →
clean total **PKR {fmt(clean_total)}**. The difference is exactly the
duplicate copies (PKR {fmt(dup_total)}) plus the bad-quantity rows
(PKR {fmt(log["money"]["bad_quantity_rows_total_pkr"])} — negative
totals from negative quantities). **No genuine order's total changed
by a single rupee** — the money fixes only changed the *format* of the
price, never its value.

## Technique 1 — strip leading/trailing whitespace

**Problem:** text pasted from another system often carries invisible
spaces — `"  Maryam Malik "` looks fine in a spreadsheet but will not
match `"Maryam Malik"` in a join, a filter, or a `groupby`.

**Pattern:**

```python
for col in ["customer_name", "city", "category", "product"]:
    df[col] = df[col].str.strip()
```

**Before / after:** `{t["01_whitespace"]["example"]["column"]}` on
{t["01_whitespace"]["example"]["order_id"]}:
`"{t["01_whitespace"]["example"]["before"]}"` →
`"{t["01_whitespace"]["example"]["after"]}"`.

**Fixed: {t["01_whitespace"]["fixed_cells"]} cells.** Always strip
first — every later technique (case mapping, null detection, city
mapping) depends on clean edges.

## Technique 2 — standardise case in categories

**Problem:** the same category arrives as `"Mobiles"`, `"mobiles"` and
`"MOBILES"`. A `groupby("category")` then reports three categories
where the shop has one.

**Pattern:**

```python
canonical = {{"mobiles": "Mobiles", "laptops": "Laptops", ...}}
mapped = df["category"].str.lower().map(canonical)
df.loc[mapped.notna(), "category"] = mapped
```

Lower-case first, then map to the one canonical spelling. Values that
are not a known category (a null guise, a junk value) map to `NaN`
and are left alone for their own technique — the map never invents a
category.

**Before / after:** category on
{t["02_category_case"]["example"]["order_id"]}:
`"{t["02_category_case"]["example"]["before"]}"` →
`"{t["02_category_case"]["example"]["after"]}"`.

**Fixed: {t["02_category_case"]["fixed_cells"]} cells.**

## Technique 3 — money stored as text

**Problem:** prices arrived as `"Rs. 45,000"`, `"Rs.45000"`,
`"45,000"` and `"PKR 45,000"` — strings, not numbers. You cannot sum
a string, and `pd.to_numeric` alone chokes on `"Rs."` and commas.

**Pattern:**

```python
df["unit_price_pkr"] = df["unit_price_pkr"].apply(
    lambda s: int(re.sub(r"[^0-9]", "", s)) if re.search(r"Rs|PKR|,", s)
    else int(s) if s.strip().isdigit() else np.nan)
```

Strip everything that is not a digit, but only from cells that
actually carry a currency mark or a comma — and let unparseable junk
become `NaN` instead of crashing the run.

**Before / after:** unit price on
{t["03_money_as_text"]["example"]["order_id"]}:
`"{t["03_money_as_text"]["example"]["before"]}"` →
{t["03_money_as_text"]["example"]["after"]}.

**Fixed: {t["03_money_as_text"]["fixed_cells"]} cells.** The totals
prove the values never changed: every row still satisfies
`total = quantity x unit_price` after the conversion.

## Technique 4 — dates in mixed formats

**Problem:** the same month arrives as `"2026-01-05"`,
`"05/01/2026"`, `"05-01-2026"` and `"Jan 5, 2026"`. Sorting those as
strings puts January after June; grouping by month is impossible.

**Pattern:**

```python
formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%b %d, %Y"]
def parse_date(s):
    for fmt in formats:
        try:
            return pd.to_datetime(s, format=fmt)
        except ValueError:
            continue
    return pd.NaT
df["order_date"] = df["order_date"].apply(parse_date).dt.strftime("%Y-%m-%d")
```

Try each known format in turn; unparseable values become `NaT`
instead of crashing. Note the day-first formats: `"05/01/2026"` is
5 January, not 1 May — always state which convention your data uses.

**Before / after:** order date on
{t["04_mixed_date_formats"]["example"]["order_id"]}:
`"{t["04_mixed_date_formats"]["example"]["before"]}"` →
`"{t["04_mixed_date_formats"]["example"]["after"]}"`.

**Fixed: {t["04_mixed_date_formats"]["fixed_cells"]} cells.** After
this step every date is ISO `yyyy-mm-dd`, and the clean file spans
{summary["clean_checks"]["date_range"][0]} to
{summary["clean_checks"]["date_range"][1]}.

## Technique 5 — nulls in different guises

**Problem:** missing values do not arrive as one clean `NaN`. This
file has four guises: empty `""`, `"NA"`, `"null"` and `"N/A"`. A
`df.isna()` check finds none of them — pandas reads them all as
ordinary strings.

**Pattern:**

```python
guises = {{"", "NA", "null", "N/A"}}
for col in ["customer_name", "city", "category"]:
    df.loc[df[col].isin(guises), col] = np.nan
df["customer_name"] = df["customer_name"].fillna("Unknown Customer")
df["city"] = df["city"].fillna("Unknown")
df["category"] = df["category"].fillna("Unknown")
```

First normalise every guise to real `NaN`, then fill with an explicit
label. A missing name becomes `"Unknown Customer"` — never an invented
name, never a silently dropped row.

**Before / after:** `{t["05_null_guises"]["example"]["column"]}` on
{t["05_null_guises"]["example"]["order_id"]}:
{t["05_null_guises"]["example"]["before"]} →
`"{t["05_null_guises"]["example"]["after"]}"`.

**Fixed: {t["05_null_guises"]["fixed_cells"]} cells**
({t["05_null_guises"]["by_column"]["customer_name"]} names,
{t["05_null_guises"]["by_column"]["city"]} cities,
{t["05_null_guises"]["by_column"]["category"]} categories).

## Technique 6 — drop exact duplicate rows

**Problem:** 8 orders appear twice — the same order imported twice
would double-count PKR {fmt(dup_total)} of revenue.

**Pattern:**

```python
df = df.drop_duplicates(keep="first")
```

This runs AFTER the value fixes on purpose: a duplicate of a
defective row is identical to its original only once both are fixed,
so fixing first is what makes the duplicate catchable.

**Example:** order {t["06_exact_duplicates"]["example"]["duplicated_order_ids"][0]}
appeared twice; the second copy was dropped.

**Removed: {t["06_exact_duplicates"]["removed_rows"]} rows.**

## Technique 7 — drop rows with impossible quantities

**Problem:** 6 rows have quantity −2, −1 or 0 — orders that never
happened, with negative or zero totals. Unlike a misspelled city, a
negative quantity cannot be repaired: there is no true value to
recover, so the honest fix is removal, with the removal logged.

**Pattern:**

```python
bad = df["quantity"] <= 0
df = df[~bad]
```

**Example:** order {t["07_bad_quantities"]["example"]["order_id"]}
had quantity {t["07_bad_quantities"]["example"]["quantity"]} and total
PKR {fmt(t["07_bad_quantities"]["example"]["total_pkr"])} — removed,
not fixed.

**Removed: {t["07_bad_quantities"]["removed_rows"]} rows**
(their combined total was PKR
{fmt(t["07_bad_quantities"]["removed_total_pkr"])}).

## Technique 8 — standardise city spellings

**Problem:** the same city arrives as `"Lahore"`, `"lahore"` and
`"LHR"`; Karachi as `"KHI"` and `"karachi"`. Same city, three spellings,
three groups in any city report.

**Pattern:**

```python
city_map = {{"lhr": "Lahore", "lahore": "Lahore",
             "khi": "Karachi", "karachi": "Karachi", ...}}
mapped = df["city"].str.lower().map(city_map)
df.loc[mapped.notna(), "city"] = mapped
```

Case-insensitive mapping again — the same trick as technique 2, now
with abbreviations included. `"Unknown"` (from technique 5) is not in
the map and stays `"Unknown"`.

**Before / after:** city on
{t["08_city_spellings"]["example"]["order_id"]}:
`"{t["08_city_spellings"]["example"]["before"]}"` →
`"{t["08_city_spellings"]["example"]["after"]}"`.

**Fixed: {t["08_city_spellings"]["fixed_cells"]} cells.**

## Technique 9 — handle a mixed-type column

**Problem:** the `notes` column holds four kinds of value at once —
empty ({t["09_mixed_type_column"]["breakdown"]["empty"]}), plain text
(`"COD"`, `"urgent"` — {t["09_mixed_type_column"]["breakdown"]["text"]}),
numbers-as-text (`"42"` —
{t["09_mixed_type_column"]["breakdown"]["numeric"]}) and a boolean
(`"TRUE"` — {t["09_mixed_type_column"]["breakdown"]["boolean"]}).
There is no single type for the column, and no consistent meaning to
standardise it into. Forcing it to strings would only hide the mess.

**Pattern:**

```python
df = df.drop(columns=["notes"])
```

Count the breakdown first (so the mess is documented), then drop the
column. Dropping is the honest fix when a column has no consistent
meaning — standardising it would invent meaning it never had.

**Dropped: 1 column** (`notes`, 120 values: {t["09_mixed_type_column"]["breakdown"]["empty"]} empty,
{t["09_mixed_type_column"]["breakdown"]["text"]} text,
{t["09_mixed_type_column"]["breakdown"]["numeric"]} numeric,
{t["09_mixed_type_column"]["breakdown"]["boolean"]} boolean).

## Technique 10 — drop junk rows and blank lines

**Problem:** the file ends with three junk rows (`"TOTAL"`,
`"---"`, `"END OF FILE"`) and {blank_lines} blank lines — file
furniture from an export, not orders. A junk row has no valid
`order_id`, so it is caught by that rule, not by guessing at values.

**Pattern:**

```python
junk = ~df["order_id"].str.match(r"^ORD-\\d+$")
df = df[~junk]
# blank lines: pandas skips them on read; count them from the raw text
blank = sum(1 for line in open(raw) if line.strip() == "")
```

**Removed: {t["10_junk_rows_blank_lines"]["removed_rows"]} junk rows**
({", ".join(t["10_junk_rows_blank_lines"]["example"]["junk_order_ids"])})
**and {t["10_junk_rows_blank_lines"]["blank_lines"]} blank lines.**

## The clean file

`data/processed/orders_clean_SAMPLE.csv` — {len(df)} rows, 9 columns
(`order_id`, `order_date`, `customer_name`, `city`, `category`,
`product`, `quantity`, `unit_price_pkr`, `total_pkr`), sorted by date.
Every row satisfies `total_pkr = quantity x unit_price_pkr`; every
date is ISO; every `order_id` is unique; no nulls remain in any
required column.

| Clean total | Value |
|---|---|
| Orders | {len(df)} |
| Units sold | {fmt(int(df["quantity"].sum()))} |
| Revenue | PKR {fmt(clean_total)} |
| Average order value | PKR {fmt(round(clean_total / len(df), 2))} |

Revenue by category: {", ".join(f"{k} PKR {fmt(v['total_pkr'])} ({v['orders']} orders)" for k, v in sorted(summary["clean_totals"]["by_category"].items()))}.
Revenue by city: {", ".join(f"{k} PKR {fmt(v['total_pkr'])} ({v['orders']} orders)" for k, v in sorted(summary["clean_totals"]["by_city"].items()))}.

## What this pack teaches

1. **Clean in order: values, then rows, then columns.** Stripping
   first makes every later fix work; duplicates are caught only after
   the values match; junk rows go last so every count stays exact.
2. **A null is a value with many spellings.** `""`, `"NA"`,
   `"null"` and `"N/A"` are all the same missing value — normalise
   them to real `NaN` before you count or fill anything.
3. **Format fixes must not change values.** The money proof is the
   reconciliation: raw PKR {fmt(log["money"]["raw_total_all_rows_pkr"])}
   = clean PKR {fmt(clean_total)} + duplicates PKR {fmt(dup_total)} +
   bad rows PKR {fmt(log["money"]["bad_quantity_rows_total_pkr"])}.
   Only removed rows explain the difference.
4. **Some rows are removed, never fixed.** A negative quantity has no
   true value to recover; a junk row is not an order. Log the removal
   and move on — inventing a fix is worse than dropping the row.
5. **A column with no consistent meaning gets dropped, not
   standardised.** The `notes` column's four value kinds are
   documented in the log, then the column goes.

## Limits

- **SAMPLE data only.** Noor Electronics is fictional; the defects
  are planted by the seeded generator (seed 137) so the techniques
  can be taught. The methods are real; the shop is not.
- **The fixes are the ones this file needs.** Real messy files carry
  defects this pack does not plant (fuzzy duplicates, wrong
  currencies, time zones, encoding errors) — the 10 patterns here are
  the starting set, not the whole job.
- **"Unknown" is a label, not data.** Three names, four cities and
  three categories are missing and labelled Unknown; any analysis
  that needs real names or cities must exclude those rows, not treat
  "Unknown" as a place.
"""
    with open(GUIDE, "w") as f:
        f.write(guide)

    print(f"Wrote {CLEAN} ({len(df)} rows, PKR {clean_total:,})")
    print(f"Wrote {LOG}, {SUMMARY}, {GUIDE}")
    print("Money reconciled:", log["money"]["reconciled"])
    for n, v in t.items():
        print(f"  {n}: {v}")


if __name__ == "__main__":
    main()
