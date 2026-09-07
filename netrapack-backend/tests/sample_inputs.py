"""Five sample scan inputs simulating real-world label scenarios.

Each entry is a dict that maps directly onto ScanRequest fields.
"""

SAMPLES = [
    # 1) Clean, fully compliant simple product.
    {
        "scan_id": "scan-001-clean",
        "barcode": "8901234567890",
        "mrp_declaration": "MRP Rs. 90 (incl. of all taxes)",
        "net_quantity_declaration": "200g",
        "manufacturing_date_declaration": "MAR 2026",
        "expiry_date_declaration": "MAR 2027",
        "unit_sale_price_declaration": "Rs 45 per 100g",
        "manufacturer_name_address": "ABC Foods Pvt Ltd, Plot 5, MIDC, Pune, MH 411001",
        "country_of_origin_declaration": "Made in India",
        "consumer_care_details": "care@abcfoods.com, 1800-123-456",
        "fssai_license_number": "FSSAI Lic. No. 10012345678901",
    },
    # 2) USP exemption via 1kg pack + double-price MRP -> manual review on MRP.
    {
        "scan_id": "scan-002-1kg-double-price",
        "barcode": "8909999999999",
        "mrp_declaration": "MRP Rs. 250  Rs. 240",  # two prices printed together
        "net_quantity_declaration": "1kg",
        "manufacturing_date_declaration": "03/2026",
        "expiry_date_declaration": "09/2026",
        "unit_sale_price_declaration": None,  # not required (1kg exemption)
        "manufacturer_name_address": "Grain Mills Ltd, Sector 22, Chandigarh 160022",
        "country_of_origin_declaration": "Product of India",
        "consumer_care_details": "support@grainmills.in",
        "fssai_license_number": "FSSAI 22334455667788",
    },
    # 3) USP exemption via low price (Rs 10) + tiny sachet; FSSAI mentioned but invalid.
    {
        "scan_id": "scan-003-cheap-sachet",
        "barcode": "8905555555555",
        "mrp_declaration": "MRP Rs. 10",
        "net_quantity_declaration": "9g",
        "manufacturing_date_declaration": "JAN 2026",
        "expiry_date_declaration": None,
        "unit_sale_price_declaration": None,
        "manufacturer_name_address": "Snack Co, Mumbai 400001",
        "country_of_origin_declaration": "Made in India",
        "consumer_care_details": "1800-222-333",
        "fssai_license_number": "FSSAI No. 1234",  # mentioned but not 14 digits
    },
    # 4) Bonus pack: 100g + 20g extra. MRP 60. USP must use PAID 100g.
    #    Declared USP Rs 60 per 100g is correct (60 / 100g * 100 = 60).
    {
        "scan_id": "scan-004-bonus-pack",
        "barcode": "8907777777777",
        "mrp_declaration": "MRP Rs. 60",
        "net_quantity_declaration": "100g + 20g extra",
        "manufacturing_date_declaration": "FEB 2026",
        "expiry_date_declaration": "FEB 2027",
        "unit_sale_price_declaration": "Rs 60 per 100g",
        "manufacturer_name_address": "Value Foods, Nagpur 440001",
        "country_of_origin_declaration": "Made in India",
        "consumer_care_details": "help@valuefoods.com, +91 98765 43210",
        "fssai_license_number": "FSSAI 98765432109876",
    },
    # 5) Non-compliant mess: USP mismatch, no origin phrase, no consumer contact,
    #    missing FSSAI, invalid date.
    {
        "scan_id": "scan-005-noncompliant",
        "barcode": "8903333333333",
        "mrp_declaration": "MRP Rs. 200",
        "net_quantity_declaration": "500g",
        "manufacturing_date_declaration": "2026",  # year only -> invalid
        "expiry_date_declaration": "13/2026",       # invalid month
        "unit_sale_price_declaration": "Rs 25 per 100g",  # wrong; expected 40
        "manufacturer_name_address": "Mystery Brand",
        "country_of_origin_declaration": "Premium quality guaranteed",  # no origin phrase
        "consumer_care_details": "Visit our stores",  # no phone/email
        "fssai_license_number": "",  # missing
    },
]
