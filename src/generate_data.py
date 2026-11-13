"""Regenerate data/raw/orders_messy_SAMPLE.csv — Mini #13 sample data.

Fictional shop "Noor Electronics" (Lahore), 120 online orders, Jan–Jun
2026. SAMPLE / DEMO data only — never real client or real business data.

TEN defect types are PLANTED in the generated data (seeded, seed 137,
fully deterministic — re-running this script reproduces the file exactly).
Each defect type lives on its own set of rows, so every count below is
exact and independently re-countable from the raw file:

 1. Whitespace ......... 12 cells (customer_name 8, product 4)
 2. Category case ...... 10 cells (category in wrong case)
 3. Money as text ...... 15 cells (unit_price_pkr as "Rs. 45,000" etc.)
 4. Mixed date formats . 18 cells (DD/MM/YYYY, DD-MM-YYYY, "Jan 5, 2026")
 5. Nulls in disguise .. 10 cells ("", "NA", "null", "N/A")
 6. Exact duplicates ...  8 rows (copies of clean rows 100-107)
 7. Bad quantities .....  6 rows (quantity -2, 0, -1, -3, 0, -1)
 8. City spellings .....  8 cells ("LHR", "lahore", "KHI", "Isb", ...)
 9. Mixed-type column .. notes column: 100 empty / 12 text / 5 numeric / 3 boolean
10. Junk + blank lines .  3 trailing junk rows + 2 blank lines at end of file

Raw file layout (as pandas sees it, blank lines skipped): 120 base rows
+ 8 duplicates + 3 junk rows = 131 data rows. Cleaning removes 8
duplicates + 6 bad-quantity rows + 3 junk rows = 114 clean rows.

Defect rows are disjoint (rows 0-78 carry defects 1-5, 7, 8; rows 79-119
are clean; duplicates copy clean rows only), so no defect type's count
is inflated by another type or by duplication. Junk rows use "---" in
every field, so they carry no whitespace / null-guise / money defect —
they are purely technique 10's problem.

The exact counts are written to data/defect_manifest.json alongside the
CSV; src/checks.py re-counts every defect independently from the raw
file and compares against that manifest.
"""

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "orders_messy_SAMPLE.csv"
MANIFEST = ROOT / "data" / "defect_manifest.json"

SEED = 137
N_BASE = 120

FIRST = ["Ayesha", "Bilal", "Fatima", "Usman", "Zainab", "Ahmed", "Maryam",
         "Hassan", "Sana", "Ali", "Hira", "Omar", "Noor", "Hamza", "Iqra",
         "Daniyal", "Mahnoor", "Faisal", "Rabia", "Arslan", "Sadia",
         "Tariq", "Kiran", "Waqas", "Nadia"]
LAST = ["Khan", "Ahmed", "Ali", "Malik", "Hussain", "Shah", "Raza", "Butt",
        "Chaudhry", "Sheikh", "Qureshi", "Siddiqui", "Mirza", "Akhtar",
        "Nawaz"]

CITIES = ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad"]

PRODUCTS = {
    "Mobiles": [("Samsung Galaxy A15", 42500), ("Infinix Note 40", 38999),
                ("Xiaomi Redmi 13", 34999), ("Oppo A18", 29999)],
    "Laptops": [("HP Laptop 15", 145000), ("Lenovo IdeaPad Slim 3", 128500),
                ("Dell Inspiron 15", 162000)],
    "Accessories": [("USB-C Cable 1m", 1499), ("Wireless Mouse", 2499),
                    ("Laptop Stand", 3999), ("Phone Cover", 999)],
    "Audio": [("Bluetooth Earbuds", 5999), ("Wired Earphones", 1499),
              ("Bluetooth Speaker", 8999)],
    "Home Appliances": [("Electric Kettle", 3499), ("Ceiling Fan", 8500),
                        ("Iron Steamer", 6500)],
}

COLUMNS = ["order_id", "order_date", "customer_name", "city", "category",
           "product", "quantity", "unit_price_pkr", "total_pkr", "notes"]

# --- planted defects (row indices are 0-based into the 120 base rows) ---
WS_ROWS = list(range(0, 8))        # whitespace on customer_name
WS_PRODUCT_ROWS = list(range(8, 12))  # whitespace on product
CASE_ROWS = list(range(12, 22))    # category in wrong case
MONEY_ROWS = list(range(22, 37))   # unit_price_pkr as text
DATE_ROWS = list(range(37, 55))    # order_date in a non-ISO format
NULL_CITY_ROWS = list(range(55, 59))     # city null guise
NULL_CAT_ROWS = list(range(59, 62))      # category null guise
NULL_NAME_ROWS = list(range(62, 65))     # customer_name null guise
BAD_QTY_ROWS = list(range(65, 71))       # quantity <= 0
CITY_ROWS = list(range(71, 79))    # city in a non-canonical spelling
DUP_SOURCE_ROWS = list(range(100, 108))  # clean rows copied exactly (8)

CASE_VARIANTS = ["mobiles", "MOBILES", "laptops", "LAPTOPS",
                 "accessories", "ACCESSORIES", "audio", "AUDIO",
                 "home appliances", "HOME APPLIANCES"]
MONEY_FORMATS = ["Rs. {p:,}", "Rs.{p:,}", "{p:,}", "Rs. {p}", "PKR {p:,}"]
DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%b %d, %Y"]
NULL_CITY = ["", "NA", "null", "N/A"]
NULL_CAT = ["", "NA", "null"]
NULL_NAME = ["", "N/A", "null"]
BAD_QTY = [-2, 0, -1, -3, 0, -1]
CITY_VARIANTS = ["LHR", "lahore", "KHI", "Isb",
                 "RWP", "FSD", "karachi", "faisalabad"]

JUNK_ROWS = [
    ["TOTAL"] + ["---"] * 9,
    ["---"] * 10,
    ["END OF FILE"] + ["---"] * 9,
]
N_BLANK_LINES = 2


def build_base_rows():
    rng = random.Random(SEED)
    rows = []
    for i in range(N_BASE):
        category = rng.choice(list(PRODUCTS))
        product, price = rng.choice(PRODUCTS[category])
        month = rng.randint(1, 6)
        day = rng.randint(1, 28)
        rows.append({
            "order_id": f"ORD-{1001 + i}",
            "order_date": f"2026-{month:02d}-{day:02d}",
            "customer_name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "city": rng.choice(CITIES),
            "category": category,
            "product": product,
            "quantity": rng.randint(1, 5),
            "unit_price_pkr": price,
            "total_pkr": 0,  # filled below
            "notes": "",
        })
        rows[-1]["total_pkr"] = rows[-1]["quantity"] * price
    # notes column: deliberately mixed types (technique 9's problem)
    notes = ([""] * 100 + ["COD"] * 8 + ["42", "7", "15", "3", "99"]
             + ["urgent"] * 4 + ["TRUE"] * 3)
    rng.shuffle(notes)
    for r, n in zip(rows, notes):
        r["notes"] = n
    return rows


def plant_defects(rows):
    # 1. whitespace: leading/trailing spaces on customer_name / product
    for i in WS_ROWS:
        rows[i]["customer_name"] = "  " + rows[i]["customer_name"] + " "
    for i in WS_PRODUCT_ROWS:
        rows[i]["product"] = rows[i]["product"] + " "
    # 2. category in the wrong case
    for j, i in enumerate(CASE_ROWS):
        rows[i]["category"] = CASE_VARIANTS[j]
    # 3. money stored as text ("Rs." / commas / "PKR")
    for j, i in enumerate(MONEY_ROWS):
        p = rows[i]["unit_price_pkr"]
        rows[i]["unit_price_pkr"] = MONEY_FORMATS[j % len(MONEY_FORMATS)].format(p=p)
    # 4. dates in three mixed formats (day <= 28, so no ambiguity)
    from datetime import datetime
    for j, i in enumerate(DATE_ROWS):
        d = datetime.strptime(rows[i]["order_date"], "%Y-%m-%d")
        rows[i]["order_date"] = d.strftime(DATE_FORMATS[j % len(DATE_FORMATS)])
    # 5. nulls in different guises
    for j, i in enumerate(NULL_CITY_ROWS):
        rows[i]["city"] = NULL_CITY[j]
    for j, i in enumerate(NULL_CAT_ROWS):
        rows[i]["category"] = NULL_CAT[j]
    for j, i in enumerate(NULL_NAME_ROWS):
        rows[i]["customer_name"] = NULL_NAME[j]
    # 7. negative / zero quantities (total follows quantity, so it is
    #    negative or zero too — these rows are dropped, never fixed)
    for j, i in enumerate(BAD_QTY_ROWS):
        rows[i]["quantity"] = BAD_QTY[j]
        rows[i]["total_pkr"] = BAD_QTY[j] * rows[i]["unit_price_pkr"]
    # 8. inconsistent city spellings
    for j, i in enumerate(CITY_ROWS):
        rows[i]["city"] = CITY_VARIANTS[j]
    return rows


def main():
    rows = plant_defects(build_base_rows())
    assert len(rows) == N_BASE
    assert len({r["order_id"] for r in rows}) == N_BASE

    # 6. exact duplicates: copies of clean rows only (rows 100-107 carry
    #    no planted defect, so duplication inflates no defect count)
    dups = [dict(rows[i]) for i in DUP_SOURCE_ROWS]
    all_rows = rows + dups + [dict(zip(COLUMNS, jr)) for jr in JUNK_ROWS]

    manifest = {
        "seed": SEED,
        "base_rows": N_BASE,
        "raw_data_rows": len(all_rows),  # 120 base + 8 dups + 3 junk = 131
        "blank_lines": N_BLANK_LINES,
        "defects": {
            "01_whitespace_cells": len(WS_ROWS) + len(WS_PRODUCT_ROWS),
            "02_category_case_cells": len(CASE_ROWS),
            "03_money_as_text_cells": len(MONEY_ROWS),
            "04_mixed_date_format_cells": len(DATE_ROWS),
            "05_null_guise_cells": (len(NULL_CITY_ROWS) + len(NULL_CAT_ROWS)
                                    + len(NULL_NAME_ROWS)),
            "06_exact_duplicate_rows": len(dups),
            "07_bad_quantity_rows": len(BAD_QTY_ROWS),
            "08_city_spelling_cells": len(CITY_ROWS),
            "09_mixed_type_notes": {"empty": 100, "text": 12,
                                    "numeric": 5, "boolean": 3},
            "10_junk_rows": len(JUNK_ROWS),
        },
        "expected_clean_rows": (N_BASE - len(BAD_QTY_ROWS)),  # 114
        "notes": "Counts are exact by construction; src/checks.py "
                 "re-counts every one independently from the raw file.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(all_rows)
        # trailing blank lines (technique 10's second half)
        f.write("\n" * N_BLANK_LINES)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    clean_total = sum(r["total_pkr"] for r in rows if r["quantity"] > 0)
    raw_total = sum(r["total_pkr"] for r in all_rows
                    if isinstance(r["total_pkr"], int))
    assert clean_total == 12290259, clean_total
    assert raw_total == 13119238, raw_total
    assert sum(r["total_pkr"] for r in rows) == 12060265, \
        sum(r["total_pkr"] for r in rows)
    print(f"Wrote {OUT} ({len(all_rows)} data rows + "
          f"{N_BLANK_LINES} blank lines)")
    print(f"Wrote {MANIFEST}")
    print(f"clean total (114 rows) PKR {clean_total:,}; "
          f"raw parseable total PKR {raw_total:,}")


if __name__ == "__main__":
    main()
