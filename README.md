# Mini #13 — Python pandas Data Cleaning Pack

**Status:** built and verified locally; GitHub publish pending.

**SAMPLE / DEMO data only.** Fictional shop, fictional orders,
fictional numbers. Never claimed as real client work.

The cleaning companion to the statistics pack: the same fictional
shop as Mini #12's "Noor Electronics" — 120 online orders, Jan–Jun
2026 — now taught as data cleaning. Ten defect types were planted in
the raw file, one technique per defect, and every count is exact:
12 whitespace cells, 10 wrong-case categories, 15 money-as-text
prices, 18 mixed-format dates, 10 nulls in disguise, 8 duplicate
rows, 6 impossible quantities, 8 city misspellings, 1 mixed-type
column, 3 junk rows + 2 blank lines. Cleaning removes 17 rows and
fixes 73 cells, leaving 114 clean rows worth PKR 12,290,259 — and the
money reconciles to the rupee.

## Business question

"Can we trust this orders file enough to report revenue from it?"
Before any dashboard or analysis, the file has to be cleaned — and
the cleaning has to be provable: every fix counted, every removal
logged, every rupee reconciled.

## What is inside

| File | What it does |
|---|---|
| `outputs/cleaning_guide.md` | The teaching write-up: 10 techniques, problem + pandas pattern + before/after row + count fixed |
| `outputs/summary.json` | Every verified number, machine-readable |
| `outputs/cleaning_log.json` | What each technique fixed, counts + examples |
| `data/raw/orders_messy_SAMPLE.csv` | The 131-row messy SAMPLE file the cleaning reads |
| `data/processed/orders_clean_SAMPLE.csv` | The 114-row clean file |
| `data/defect_manifest.json` | The exact planted defect counts |
| `data/README.md` | Data dictionary + how each defect was planted + known quirks |
| `src/generate_data.py` | Regenerates the messy CSV + manifest (seed 137, deterministic) |
| `src/clean.py` | The 10 pandas cleaning techniques, in order |
| `src/checks.py` | Checks as code — 84 checks, all passing |
| `requirements.txt` | pandas only (`pandas>=2.0,<3`) |

## Key numbers (real numbers, recomputed from the CSVs)

| KPI | Value |
|---|---|
| Raw data rows | 131 (+ 2 blank lines) |
| Clean rows | 114 |
| Rows removed | 17 (8 duplicates + 6 bad quantities + 3 junk) |
| Cells fixed in place | 73 (12 whitespace + 10 case + 15 money + 18 dates + 10 nulls + 8 cities) |
| Columns dropped | 1 (`notes` — mixed types, no consistent meaning) |
| Raw total | PKR 13,119,238 |
| Clean total | PKR 12,290,259 |
| Duplicate copies removed | PKR 1,058,973 |
| Bad-quantity rows removed | PKR −229,994 |
| Units sold (clean) | 358 |
| Average order value | PKR 107,809.29 |
| Checks | 84 passing (`python3 src/checks.py`) |

Money reconciliation: PKR 13,119,238 = PKR 12,290,259 + PKR 1,058,973
+ PKR (−229,994). No genuine order's total changed by a single rupee
— the money fixes only changed the *format* of the price, never its
value.

## The 10 techniques

1. **Strip whitespace** — `str.strip()` on text columns (12 cells).
2. **Standardise case** — lower-case, then map to canonical category
   names (10 cells).
3. **Money as text** — strip `Rs.` / `PKR` / commas, cast to int PKR
   (15 cells).
4. **Mixed date formats** — try each known format, write back ISO
   `yyyy-mm-dd` (18 cells).
5. **Nulls in disguise** — `"", "NA", "null", "N/A"` → real `NaN` →
   explicit `Unknown` fill (10 cells).
6. **Exact duplicates** — `drop_duplicates(keep="first")` (8 rows).
7. **Impossible quantities** — drop quantity ≤ 0, never invent a fix
   (6 rows).
8. **City spellings** — case-insensitive map (`"LHR"` → `"Lahore"`)
   (8 cells).
9. **Mixed-type column** — count the value kinds, then drop `notes`
   (100 empty / 12 text / 5 numeric / 3 boolean).
10. **Junk rows + blank lines** — drop rows with no valid `order_id`;
    count blank lines from the raw text (3 rows + 2 lines).

## What the pack teaches

1. **Clean in order: values, then rows, then columns.** Stripping
   first makes every later fix work; duplicates are caught only after
   the values match; junk rows go last so every count stays exact.
2. **A null is a value with many spellings.** `""`, `"NA"`,
   `"null"` and `"N/A"` are all the same missing value — normalise
   them to real `NaN` before you count or fill anything.
3. **Format fixes must not change values.** The money proof is the
   reconciliation: raw = clean + duplicates + bad rows. Only removed
   rows explain the difference.
4. **Some rows are removed, never fixed.** A negative quantity has no
   true value to recover; a junk row is not an order. Log the removal
   and move on — inventing a fix is worse than dropping the row.
5. **A column with no consistent meaning gets dropped, not
   standardised.** The `notes` column's four value kinds are
   documented in the log, then the column goes.

## Verified numbers

| KPI | Value |
|---|---|
| Raw rows | 131 |
| Clean rows | 114 |
| Clean total | PKR 12,290,259 |
| Checks | 84 passing (`python3 src/checks.py`) |

Verification: `python3 src/checks.py` — every defect count is
re-counted independently from the raw file with the standard library
only (no pandas), compared against `data/defect_manifest.json` and
`outputs/summary.json`; the clean file is re-scanned for zero
remaining defects of every type; row counts and money totals are
reconciled across raw, duplicate, bad-quantity and clean files; the
generator and cleaner are re-run and hash-checked for determinism
(see `outputs/summary.json`).

## How to run it

1. Install the one dependency: `pip install -r requirements.txt`.
2. Read `outputs/cleaning_guide.md` — that is the deliverable.
3. To regenerate the messy sample data: `python3 src/generate_data.py`.
4. To re-run the cleaning: `python3 src/clean.py`.
5. To check it: `python3 src/checks.py`.
6. To practise on your own data: replace the raw CSV (same columns)
   and re-run steps 4–5 only — do NOT re-run step 3, it regenerates
   the sample data and would overwrite your file.

## Two traps this pack teaches

- **"No nulls" does not mean clean.** `df.isna()` finds none of the
  10 disguised nulls — `"NA"` and `"null"` read as ordinary strings.
  Count the guises first, then normalise them.
- **Duplicates hide behind defects.** A duplicate of a misspelled
  row is not an exact duplicate until the spelling is fixed. Fix
  values first, deduplicate second — the other order misses copies.

## Limits

- **SAMPLE data only.** The shop and the orders are fictional; the
  defects are planted by the seeded generator so the techniques can
  be taught. The methods are real.
- **The fixes are the ones this file needs.** Real messy files carry
  defects this pack does not plant (fuzzy duplicates, wrong
  currencies, time zones, encoding errors) — the 10 patterns here are
  the starting set, not the whole job.
- **"Unknown" is a label, not data.** 3 names, 4 cities and 3
  categories are missing and labelled Unknown; any analysis that
  needs real names or cities must exclude those rows.

## Published

Not yet published on GitHub — local build only.
