# Mini #13 — pandas Data Cleaning Guide (SAMPLE data)

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
| Raw data rows in the file | 131 |
| Blank lines at the end of the file | 2 |
| Exact duplicate rows removed (technique 6) | 8 |
| Bad-quantity rows removed (technique 7) | 6 |
| Junk rows removed (technique 10) | 3 |
| **Clean rows** | **114** |

Money: raw total **PKR 13,119,238** →
clean total **PKR 12,290,259**. The difference is exactly the
duplicate copies (PKR 1,058,973) plus the bad-quantity rows
(PKR -229,994 — negative
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

**Before / after:** `customer_name` on
ORD-1001:
`"  Maryam Malik "` →
`"Maryam Malik"`.

**Fixed: 12 cells.** Always strip
first — every later technique (case mapping, null detection, city
mapping) depends on clean edges.

## Technique 2 — standardise case in categories

**Problem:** the same category arrives as `"Mobiles"`, `"mobiles"` and
`"MOBILES"`. A `groupby("category")` then reports three categories
where the shop has one.

**Pattern:**

```python
canonical = {"mobiles": "Mobiles", "laptops": "Laptops", ...}
mapped = df["category"].str.lower().map(canonical)
df.loc[mapped.notna(), "category"] = mapped
```

Lower-case first, then map to the one canonical spelling. Values that
are not a known category (a null guise, a junk value) map to `NaN`
and are left alone for their own technique — the map never invents a
category.

**Before / after:** category on
ORD-1013:
`"mobiles"` →
`"Mobiles"`.

**Fixed: 10 cells.**

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
ORD-1023:
`"Rs. 1,499"` →
1499.

**Fixed: 15 cells.** The totals
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
ORD-1038:
`"25/03/2026"` →
`"2026-03-25"`.

**Fixed: 18 cells.** After
this step every date is ISO `yyyy-mm-dd`, and the clean file spans
2026-01-02 to
2026-06-28.

## Technique 5 — nulls in different guises

**Problem:** missing values do not arrive as one clean `NaN`. This
file has four guises: empty `""`, `"NA"`, `"null"` and `"N/A"`. A
`df.isna()` check finds none of them — pandas reads them all as
ordinary strings.

**Pattern:**

```python
guises = {"", "NA", "null", "N/A"}
for col in ["customer_name", "city", "category"]:
    df.loc[df[col].isin(guises), col] = np.nan
df["customer_name"] = df["customer_name"].fillna("Unknown Customer")
df["city"] = df["city"].fillna("Unknown")
df["category"] = df["category"].fillna("Unknown")
```

First normalise every guise to real `NaN`, then fill with an explicit
label. A missing name becomes `"Unknown Customer"` — never an invented
name, never a silently dropped row.

**Before / after:** `customer_name` on
ORD-1063:
(empty string) →
`"Unknown Customer"`.

**Fixed: 10 cells**
(3 names,
4 cities,
3 categories).

## Technique 6 — drop exact duplicate rows

**Problem:** 8 orders appear twice — the same order imported twice
would double-count PKR 1,058,973 of revenue.

**Pattern:**

```python
df = df.drop_duplicates(keep="first")
```

This runs AFTER the value fixes on purpose: a duplicate of a
defective row is identical to its original only once both are fixed,
so fixing first is what makes the duplicate catchable.

**Example:** order ORD-1101
appeared twice; the second copy was dropped.

**Removed: 8 rows.**

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

**Example:** order ORD-1066
had quantity -2 and total
PKR -77,998 — removed,
not fixed.

**Removed: 6 rows**
(their combined total was PKR
-229,994).

## Technique 8 — standardise city spellings

**Problem:** the same city arrives as `"Lahore"`, `"lahore"` and
`"LHR"`; Karachi as `"KHI"` and `"karachi"`. Same city, three spellings,
three groups in any city report.

**Pattern:**

```python
city_map = {"lhr": "Lahore", "lahore": "Lahore",
             "khi": "Karachi", "karachi": "Karachi", ...}
mapped = df["city"].str.lower().map(city_map)
df.loc[mapped.notna(), "city"] = mapped
```

Case-insensitive mapping again — the same trick as technique 2, now
with abbreviations included. `"Unknown"` (from technique 5) is not in
the map and stays `"Unknown"`.

**Before / after:** city on
ORD-1072:
`"LHR"` →
`"Lahore"`.

**Fixed: 8 cells.**

## Technique 9 — handle a mixed-type column

**Problem:** the `notes` column holds four kinds of value at once —
empty (100), plain text
(`"COD"`, `"urgent"` — 12),
numbers-as-text (`"42"` —
5) and a boolean
(`"TRUE"` — 3).
There is no single type for the column, and no consistent meaning to
standardise it into. Forcing it to strings would only hide the mess.

**Pattern:**

```python
df = df.drop(columns=["notes"])
```

Count the breakdown first (so the mess is documented), then drop the
column. Dropping is the honest fix when a column has no consistent
meaning — standardising it would invent meaning it never had.

**Dropped: 1 column** (`notes`, 120 values: 100 empty,
12 text,
5 numeric,
3 boolean).

## Technique 10 — drop junk rows and blank lines

**Problem:** the file ends with three junk rows (`"TOTAL"`,
`"---"`, `"END OF FILE"`) and 2 blank lines — file
furniture from an export, not orders. A junk row has no valid
`order_id`, so it is caught by that rule, not by guessing at values.

**Pattern:**

```python
junk = ~df["order_id"].str.match(r"^ORD-\d+$")
df = df[~junk]
# blank lines: pandas skips them on read; count them from the raw text
blank = sum(1 for line in open(raw) if line.strip() == "")
```

**Removed: 3 junk rows**
(---, END OF FILE, TOTAL)
**and 2 blank lines.**

## The clean file

`data/processed/orders_clean_SAMPLE.csv` — 114 rows, 9 columns
(`order_id`, `order_date`, `customer_name`, `city`, `category`,
`product`, `quantity`, `unit_price_pkr`, `total_pkr`), sorted by date.
Every row satisfies `total_pkr = quantity x unit_price_pkr`; every
date is ISO; every `order_id` is unique; no nulls remain in any
required column.

| Clean total | Value |
|---|---|
| Orders | 114 |
| Units sold | 358 |
| Revenue | PKR 12,290,259 |
| Average order value | PKR 107,809.29 |

Revenue by category: Accessories PKR 251,451 (14 orders), Audio PKR 478,427 (23 orders), Home Appliances PKR 479,975 (27 orders), Laptops PKR 7,766,996 (19 orders), Mobiles PKR 3,049,922 (28 orders), Unknown PKR 263,488 (3 orders).
Revenue by city: Faisalabad PKR 1,027,465 (15 orders), Islamabad PKR 1,475,953 (17 orders), Karachi PKR 4,984,440 (28 orders), Lahore PKR 2,107,461 (26 orders), Rawalpindi PKR 2,259,953 (24 orders), Unknown PKR 434,987 (4 orders).

## What this pack teaches

1. **Clean in order: values, then rows, then columns.** Stripping
   first makes every later fix work; duplicates are caught only after
   the values match; junk rows go last so every count stays exact.
2. **A null is a value with many spellings.** `""`, `"NA"`,
   `"null"` and `"N/A"` are all the same missing value — normalise
   them to real `NaN` before you count or fill anything.
3. **Format fixes must not change values.** The money proof is the
   reconciliation: raw PKR 13,119,238
   = clean PKR 12,290,259 + duplicates PKR 1,058,973 +
   bad rows PKR -229,994.
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
