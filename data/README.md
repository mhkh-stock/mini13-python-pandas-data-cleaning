# Mini #13 — data dictionary (SAMPLE / DEMO only)

Fictional shop "Noor Electronics" (Lahore), 120 online orders,
Jan–Jun 2026. The shop, the orders and every number are invented for
teaching — the cleaning methods are real, the business is not.
Regenerate exactly with `python3 src/generate_data.py` (seed 137,
deterministic). Clean with `python3 src/clean.py`.

## data/raw/orders_messy_SAMPLE.csv (131 data rows + 2 blank lines)

| Column | Meaning |
|---|---|
| `order_id` | Order number, `ORD-1001` … `ORD-1120` (unique per order) |
| `order_date` | Order date — ISO `yyyy-mm-dd` on clean rows, 3 other formats planted |
| `customer_name` | Customer's name (Pakistani names, fictional) |
| `city` | Delivery city: Lahore, Karachi, Islamabad, Rawalpindi, Faisalabad |
| `category` | Product category: Mobiles, Laptops, Accessories, Audio, Home Appliances |
| `product` | Product name (price is fixed per product) |
| `quantity` | Units ordered (1–5 on genuine orders) |
| `unit_price_pkr` | Price per unit, PKR — plain digits on clean rows, "Rs. 45,000" style text planted |
| `total_pkr` | Line total = quantity x unit_price_pkr |
| `notes` | Free-text column with mixed value kinds — dropped by technique 9 |

## data/processed/orders_clean_SAMPLE.csv (114 rows)

Same columns except `notes` (dropped), sorted by `order_date` then
`order_id`. Every row satisfies `total_pkr = quantity x unit_price_pkr`;
every date is ISO; every `order_id` is unique; no nulls remain in any
required column. Missing names/cities/categories are labelled
`Unknown` / `Unknown Customer` — never invented.

## How the defects were planted (seed 137)

Ten defect types, each on its own rows, so every count is exact
(full manifest in `data/defect_manifest.json`):

- **Whitespace (12 cells):** leading/trailing spaces on 8 customer
  names and 4 product names.
- **Category case (10 cells):** `"mobiles"`, `"MOBILES"`,
  `"laptops"`, `"LAPTOPS"`, `"accessories"`, `"ACCESSORIES"`,
  `"audio"`, `"AUDIO"`, `"home appliances"`, `"HOME APPLIANCES"`.
- **Money as text (15 cells):** `"Rs. 45,000"`, `"Rs.45000"`,
  `"45,000"`, `"Rs. 45000"`, `"PKR 45,000"` (cycled).
- **Mixed dates (18 cells):** `"05/01/2026"` (DD/MM/YYYY),
  `"05-01-2026"` (DD-MM-YYYY), `"Jan 5, 2026"` (cycled). All days
  are 1–28, so no date is ambiguous between conventions.
- **Null guises (10 cells):** `""`, `"NA"`, `"null"`, `"N/A"` across
  city (4), category (3) and customer_name (3).
- **Exact duplicates (8 rows):** copies of clean rows 100–107, so
  duplication inflates no other defect count.
- **Bad quantities (6 rows):** quantity −2, 0, −1, −3, 0, −1; their
  totals are negative or zero (combined PKR −229,994).
- **City spellings (8 cells):** `"LHR"`, `"lahore"`, `"KHI"`,
  `"Isb"`, `"RWP"`, `"FSD"`, `"karachi"`, `"faisalabad"`.
- **Mixed-type notes (120 values):** 100 empty, 12 text (`"COD"`,
  `"urgent"`), 5 numeric (`"42"`, `"7"`, `"15"`, `"3"`, `"99"`),
  3 boolean (`"TRUE"`).
- **Junk rows (3) + blank lines (2):** `"TOTAL"`, `"---"`,
  `"END OF FILE"` rows with `"---"` in every other field, then two
  empty lines at the end of the file.

## Totals (verified)

- Raw file: 131 data rows; parseable total PKR 13,119,238.
- Removed: 8 duplicate rows (PKR 1,058,973) + 6 bad-quantity rows
  (PKR −229,994) + 3 junk rows (no parseable total).
- Clean file: 114 rows, 358 units, total PKR 12,290,259, average
  order value PKR 107,809.29.
- Reconciliation: PKR 13,119,238 = PKR 12,290,259 + PKR 1,058,973
  + PKR (−229,994). No genuine order's total changed.

## Known quirks

- **"Unknown" is a label, not data.** 3 names, 4 cities and 3
  categories were missing and are labelled Unknown; exclude those
  rows from any analysis that needs real names or cities.
- **Junk rows use `"---"` in every field**, so they carry no
  whitespace, null-guise or money defect — they are purely
  technique 10's problem, and every earlier count is taken over the
  full file without interference.
- **Duplicate copies are exact copies of clean rows**, so the
  duplicate count (8) is independent of every other defect count.
