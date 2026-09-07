"""Seed data: 21 REAL reference products + rule definitions.

Extracted from the photographed product set. BARCODE POLICY (important):
a wrong barcode digit silently breaks cross-verification, so we store a
barcode ONLY when the reference data gives it as clearly confirmed. Products
whose barcode was flagged "garbled / appears to be / not legible / not
visible" are seeded with barcode = None and a note, rather than a guessed
digit string.

Product codes (NP-01..NP-21) are stable so re-seeding is idempotent.
"""

from __future__ import annotations

# Each product: (product_code, barcode, name, category, mrp, net_quantity,
#                manufacturer, country_of_origin, fssai_number, notes)
#
# barcode = None  -> flagged uncertain or not visible in photos (NOT stored).
PRODUCTS = [
    ("NP-01", None, "Chheda's Long Masala Banana Chips", "food_and_beverage",
     75.0, "150g",
     "Chheda Specialities Foods Pvt. Ltd., Village Ambhai, Manor-Wada Road, Dist. Palghar-421303, Maharashtra",
     "India", None,
     "promo strikethrough 85.10->75; barcode+FSSAI flagged unclear -> not stored"),

    ("NP-02", None, "Amul PRO Malt Beverage (Chocolate)", "food_and_beverage",
     None, "500g",
     "Kaira District Co-op Milk Producers Union Ltd., Anand-388001",
     "India", "10012021000071",
     "MRP+barcode not visible in photos"),

    ("NP-03", "8901499008343", "Kellogg's Corn Flakes Real Almonds & Honey", "food_and_beverage",
     None, None,
     "Kellogg India", "India", None,
     "barcode confirmed; MRP/net-wt/mfg not visible in crop"),

    ("NP-04", None, "Maggi Rich Tomato Ketchup (Super Saver Pack)", "food_and_beverage",
     100.0, "800g",
     "Nestle India Ltd", "India", "10012011000168",
     "barcode garbled -> not stored; manufacturer OCR-garbled, confirm"),

    ("NP-05", None, "MyFitness Chocolate Peanut Butter Crunchy", "food_and_beverage",
     None, "900g",
     "MyFitness", "India", None,
     "MRP/barcode/mfg not visible; care +91 7996699111"),

    ("NP-06", "8906010504335", "Balaji Wafers Instant Bhel Mix", "food_and_beverage",
     35.0, None,
     "Balaji Wafers Private Limited", "India", "10012021000039",
     "barcode confirmed; MRP ~35 (<=Rs35 USP-exemption demo, confirm)"),

    ("NP-07", None, "King Organic Phool Makhana", "food_and_beverage",
     None, None,
     "King", "India", None,
     "MRP/barcode/net-wt/manufacturer not visible"),

    ("NP-08", "8901499010728", "Kellogg's Multigrain Chocos", "food_and_beverage",
     210.0, "385g",
     "Kellogg India Pvt Ltd", "India", "10013022002031",
     "CLEAN baseline; barcode confirmed; USP Rs55/100g checks out"),

    ("NP-09", "8906136651951", "Pintola High Protein Oats (Chocolate)", "food_and_beverage",
     310.0, "400g",
     "Das Superfoods Pvt Ltd, Sonasan, Gujarat", "India", "10020021006076",
     "CLEAN baseline; barcode confirmed; USP Rs77/100g checks out"),

    ("NP-10", "8901542001642", "Glucon-D Tangy Orange", "food_and_beverage",
     215.0, "450g",
     "Zydus Wellness Products Ltd, Ahmedabad", "India", "10020021005270",
     "CLEAN baseline; barcode confirmed; USP Rs48/100g checks out"),

    ("NP-11", None, "Coolberg Lemon-Ginger (non-alcoholic)", "food_and_beverage",
     None, "300ml",
     "Coolberg", "India", None,
     "curved can; MRP/barcode/manufacturer/FSSAI not visible"),

    ("NP-12", "8902080000333", "Pepsi Zero Sugar (can)", "food_and_beverage",
     None, "300ml",
     "Varun Beverages Ltd", "India", "10014064000456",
     "curved can; barcode confirmed; MRP 'See Bottom' not visible"),

    ("NP-13", None, "Hell Energy Drink (Black Cherry, can)", "food_and_beverage",
     80.0, "250ml",
     "Ceylon Beverage Int. (Pvt) Ltd, Sri Lanka", "Sri Lanka", "10019022010557",
     "import example (origin Sri Lanka); barcode not captured -> not stored"),

    ("NP-14", None, "Monster Energy Zero Sugar (can)", "food_and_beverage",
     None, "500ml",
     "Monster Energy (UK/EU address only)", None, None,
     "possible VIOLATION: no Indian importer/FSSAI/MRP visible; barcode not captured"),

    ("NP-15", None, "Parle B Fizz Malt Sparkling Drink", "food_and_beverage",
     20.0, "250ml",
     "Parle Agro Pvt Ltd, Mumbai", "India", "10013022002068",
     "MRP Rs20 (<=Rs35 exemption); barcode 'appears to be' -> not stored; net-qty confirm"),

    ("NP-16", "0840493611488", "Motorola Edge 70 Fusion (smartphone)", "electronics",
     None, "1 unit",
     "Motorola", "India", None,
     "barcode confirmed; 1-unit USP exemption; MRP not visible"),

    ("NP-17", "8901012155080", "Johnson's Buds Cotton Swabs", "personal_care",
     None, "75 units",
     "JNTL Consumer Health (India) Pvt. Ltd., Palghar", "India", None,
     "barcode confirmed; non-food (no FSSAI); MRP/mfg not visible"),

    ("NP-18", None, "Boost Malt Based Food", "food_and_beverage",
     None, "500g",
     "Hindustan Unilever Ltd", "India", "10013022001897",
     "worn/dirty label edge case; barcode 'appears to be' -> not stored"),

    ("NP-19", "8906087779292", "The Derma Co Oil-Free Daily Face Moisturizer", "personal_care",
     349.0, "100g",
     "Honasa Consumer Ltd, Gurugram (Mfd: Risiveda Herbal Products, Haridwar)",
     "India", None,
     "CLEAN baseline; barcode confirmed; non-food; USP Rs349/100g exact"),

    ("NP-20", "8904336813858", "Portronics Vader Pro Wireless Gaming Mouse", "electronics",
     1999.0, "1 unit",
     "Portronics Digital Pvt. Ltd., Noida (Imported)", "China", None,
     "CLEAN import example; barcode confirmed; 1-unit USP exemption; origin China"),

    ("NP-21", None, "Nescafe Classic (single-serve sachet)", "food_and_beverage",
     5.0, None,
     "Nestle India Ltd., Nanjangud, Karnataka", "India", "10012011000168",
     "MRP Rs5 (double exemption <=Rs35 & possibly <=10g); barcode not visible; net-wt confirm ~2g"),
]


# Rule definitions with effective-date ranges. effective_to = NULL means the
# rule is currently in force.
# (rule_key, citation, description, effective_from, effective_to, params_json)
RULES = [
    ("usp_exemption_unit_pack",
     "LMPC Rules 2011, Rule 18",
     "USP not required when net quantity is exactly 1kg/1L/1unit/1metre.",
     "2011-04-01", None, '{"exact_units": ["1kg", "1L", "1unit", "1m"]}'),
    ("usp_exemption_low_mrp",
     "LMPC Rules 2011, Rule 18",
     "USP not required when MRP is Rs 35 or less.",
     "2011-04-01", None, '{"mrp_max": 35}'),
    ("usp_exemption_tiny_pack",
     "LMPC Rules 2011, Rule 18",
     "USP not required for packs of 10g/10ml or less.",
     "2011-04-01", None, '{"tiny_max_g_ml": 10}'),
    ("mrp_declaration",
     "LMPC Rules 2011, Rule 6(1)(e) & Rule 18(2)",
     "Retail sale price (MRP) must be declared.",
     "2011-04-01", None, None),
    ("net_quantity_declaration",
     "LMPC Rules 2011, Rule 6(1)(d)",
     "Net quantity must be declared.",
     "2011-04-01", None, None),
    ("mfg_date_month_year",
     "LMPC Rules 2011, Rule 6(1)(c)",
     "Month and year of manufacture/pre-packing must be declared.",
     "2011-04-01", None, None),
    ("fssai_license",
     "FSS Act 2006 & FSS (Licensing & Registration) Regulations 2011",
     "14-digit FSSAI licence number required on food products.",
     "2011-08-05", None, '{"digits": 14}'),
]
