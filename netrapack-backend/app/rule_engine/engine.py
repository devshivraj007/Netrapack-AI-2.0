"""NetraPack rule engine.

Runs each Day-1 compliance check against a parsed scan submission and
produces per-field results plus an overall verdict.

Legal citations reference the Legal Metrology (Packaged Commodities)
Rules, 2011 (LMPC 2011) and the FSS Act / FSSAI licensing framework.
These citations were provided as legally reviewed for this project.
"""

from __future__ import annotations

import re
from typing import Optional

from app.schemas.scan import (
    FieldResult,
    FieldStatus,
    OverallStatus,
    ScanRequest,
    ScanVerdict,
    Violation,
)

from . import parsers

# ---------------------------------------------------------------------------
# Rule citations (centralised so text stays consistent)
#
# STATUS: PROVISIONAL. These strings are working attributions only. Exact
# final wording will be confirmed by our legal reviewer (Gemini) BEFORE Day 4,
# when these citations feed the generated PDF notices. A wrong citation there
# is the Section-24-vs-36 class of mistake we already caught once, so do not
# treat these as final. All citation strings live here in one place on purpose
# so the review is a single-pass edit.
# ---------------------------------------------------------------------------
CITATION_MRP = "LMPC Rules 2011, Rule 6(1)(e) & Rule 18(2) - Retail sale price (MRP) declaration"
CITATION_NET_QTY = "LMPC Rules 2011, Rule 6(1)(d) - Net quantity declaration"
CITATION_MFG_DATE = "LMPC Rules 2011, Rule 6(1)(c) - Month and year of manufacture/pre-packing"
CITATION_EXPIRY = "LMPC Rules 2011, Rule 6(1)(c) - 'Best before'/expiry (month and year)"
CITATION_USP = "LMPC Rules 2011, Rule 6(1)(f) & Rule 18 - Unit sale price declaration"
CITATION_ORIGIN = "LMPC Rules 2011, Rule 6(1) - Country of origin declaration"
CITATION_MANUFACTURER = "LMPC Rules 2011, Rule 6(1)(a) - Name and address of manufacturer/packer/importer"
CITATION_CONSUMER_CARE = "LMPC Rules 2011, Rule 6(1) - Consumer care contact details"
CITATION_FSSAI = "FSS Act 2006 & FSS (Licensing & Registration) Regulations 2011 - 14-digit FSSAI licence number"


# Unit-sale-price match tolerance. This is an ENGINEERING judgment (not a
# legal rule): it stops honest label rounding from tripping a false mismatch.
# Easy to adjust after real product testing on Day 2 if it proves too strict
# or too loose. A declared USP passes if it is within either bound of expected.
USP_TOLERANCE_FRACTION = 0.02  # 2% of expected
USP_TOLERANCE_MIN_RUPEES = 0.05  # absolute floor in rupees


# Field keys used in the response.
F_MRP = "mrp"
F_NET_QTY = "net_quantity"
F_MFG = "manufacturing_date"
F_EXPIRY = "expiry_date"
F_USP = "unit_sale_price"
F_ORIGIN = "country_of_origin"
F_MANUFACTURER = "manufacturer_name_address"
F_CONSUMER_CARE = "consumer_care"
F_FSSAI = "fssai_license"


_ORIGIN_PHRASE_RE = re.compile(
    r"(?:made in|product of|manufactured in|produce of|origin[:\s]+country[:\s]*|country of origin[:\s]*)\s*([A-Za-z][A-Za-z .'\-]+)",
    re.IGNORECASE,
)

_TAX_INCL_RE = re.compile(
    r"(?:incl(?:usive)?\.?\s*(?:of\s*)?(?:all\s*)?taxes?|all\s*taxes)",
    re.IGNORECASE,
)


# Categories for which the FSSAI (food-specific) check applies. Everything
# else - and the "general" fallback - runs standard Legal Metrology checks only.
FSSAI_CATEGORIES = {"food_and_beverage", "baby_care"}


class RuleEngine:
    """Evaluates a ScanRequest and returns a ScanVerdict."""

    def evaluate(
        self, req: ScanRequest, product_category: str = "general"
    ) -> ScanVerdict:
        """Run the checks. Day 1 rule logic is unchanged.

        `product_category` (from the AI recognition step, or "general") only
        gates whether the category-specific FSSAI check runs. For "general" -
        including the low-confidence / no-AI fallback - the FSSAI check is
        skipped entirely and ONLY the standard checks run (Part D #2). This is
        done by simply not adding the FSSAI check to the list, so there is no
        error path and nothing downstream can crash on a missing result.
        """
        results: dict[str, FieldResult] = {}
        violations: list[Violation] = []

        # Parse shared inputs once.
        price = parsers.parse_prices(req.mrp_declaration)
        qty = parsers.parse_quantity(req.net_quantity_declaration)

        # Standard Legal Metrology checks - always run, regardless of category.
        checks = [
            self._check_mrp(req, price),
            self._check_net_quantity(req, qty),
            self._check_mfg_date(req),
            self._check_expiry_date(req),
            self._check_unit_sale_price(req, price, qty),
            self._check_country_of_origin(req),
            self._check_manufacturer(req),
            self._check_consumer_care(req),
        ]

        # Category-specific check: FSSAI only for food-type categories.
        # "general" (unavailable or low-confidence AI) skips this cleanly.
        if (product_category or "general").lower() in FSSAI_CATEGORIES:
            checks.append(self._check_fssai(req))

        for result, violation in checks:
            results[result.field] = result
            if violation:
                violations.append(violation)

        return self._build_verdict(req.scan_id, results, violations)

    # ------------------------------------------------------------------
    # Verdict assembly
    # ------------------------------------------------------------------
    def _build_verdict(
        self,
        scan_id: str,
        results: dict[str, FieldResult],
        violations: list[Violation],
    ) -> ScanVerdict:
        # DECISION (confirmed): use a VARIABLE denominator. "not_required"
        # checks are excluded from the passed/checked tally, so the total
        # shrinks when exemptions apply (e.g. "8/8 - USP not required for this
        # product"). This is intentional, not a bug: the UI shows the exemption
        # reason (carried in each FieldResult.parsed/notes) so the system
        # visibly proves it understood the exemption rather than hiding it.
        counted = [r for r in results.values() if r.status != FieldStatus.NOT_REQUIRED]
        rules_checked = len(counted)
        rules_passed = sum(1 for r in counted if r.status == FieldStatus.COMPLIANT)

        has_violation = any(r.status == FieldStatus.VIOLATION for r in results.values())
        has_review = any(r.status == FieldStatus.NEEDS_MANUAL_REVIEW for r in results.values())

        if has_violation:
            overall = OverallStatus.NON_COMPLIANT
        elif has_review:
            overall = OverallStatus.NEEDS_MANUAL_REVIEW
        else:
            overall = OverallStatus.FULLY_COMPLIANT

        return ScanVerdict(
            scan_id=scan_id,
            overall_status=overall,
            rules_passed=rules_passed,
            rules_checked=rules_checked,
            violations=violations,
            parsed_fields=results,
        )

    # ------------------------------------------------------------------
    # MRP
    # ------------------------------------------------------------------
    def _check_mrp(self, req: ScanRequest, price: parsers.PriceParseResult):
        raw = req.mrp_declaration
        if not raw or not raw.strip():
            return (
                FieldResult(field=F_MRP, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={"prices": [], "tax_included_declared": False}, notes="No MRP declared."),
                Violation(field=F_MRP, rule_citation=CITATION_MRP,
                          description="Maximum Retail Price (MRP) is not declared."),
            )

        tax_incl = bool(_TAX_INCL_RE.search(raw))

        if price.is_ambiguous:
            return (
                FieldResult(
                    field=F_MRP, status=FieldStatus.NEEDS_MANUAL_REVIEW, raw_input=raw,
                    parsed={"candidate_prices": price.prices, "tax_included_declared": tax_incl},
                    notes="Multiple prices found; cannot auto-resolve which is the MRP.",
                ),
                None,
            )

        if price.single is None:
            return (
                FieldResult(field=F_MRP, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={"prices": [], "tax_included_declared": tax_incl}, notes="No numeric price found in MRP text."),
                Violation(field=F_MRP, rule_citation=CITATION_MRP,
                          description="MRP text present but no valid price value could be read."),
            )

        note = "Single MRP value detected."
        if tax_incl:
            note += " Statutory text '(incl. of all taxes)' verified."
        else:
            note += " Advisory: Statutory text '(incl. of all taxes)' not explicitly found (Rule 6(1)(e))."

        return (
            FieldResult(field=F_MRP, status=FieldStatus.COMPLIANT, raw_input=raw,
                        parsed={"mrp": price.single, "tax_included_declared": tax_incl},
                        notes=note),
            None,
        )

    # ------------------------------------------------------------------
    # Net quantity
    # ------------------------------------------------------------------
    def _check_net_quantity(self, req: ScanRequest, qty: parsers.QuantityParseResult):
        raw = req.net_quantity_declaration
        if not raw or not raw.strip():
            return (
                FieldResult(field=F_NET_QTY, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={}, notes="No net quantity declared."),
                Violation(field=F_NET_QTY, rule_citation=CITATION_NET_QTY,
                          description="Net quantity is not declared."),
            )

        if not qty.ok:
            return (
                FieldResult(field=F_NET_QTY, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={"error": qty.error, "pattern": qty.pattern},
                            notes="Could not parse a valid net quantity."),
                Violation(field=F_NET_QTY, rule_citation=CITATION_NET_QTY,
                          description=f"Net quantity could not be interpreted ({qty.error})."),
            )

        parsed = {
            "pattern": qty.pattern,
            "dimension": qty.dimension,
            "base_unit": qty.base_unit,
            "total_quantity_base": qty.total_base,
            "paid_quantity_base": qty.paid_base,
            "display_total": qty.display_total,
            "display_paid": qty.display_paid,
        }
        note = f"Parsed as {qty.pattern}; declared total = {qty.display_total}"
        if qty.pattern == "bonus":
            note += f", paid-only = {qty.display_paid} (bonus excluded for USP math)"
        return (
            FieldResult(field=F_NET_QTY, status=FieldStatus.COMPLIANT, raw_input=raw,
                        parsed=parsed, notes=note),
            None,
        )

    # ------------------------------------------------------------------
    # Manufacturing date
    # ------------------------------------------------------------------
    def _check_mfg_date(self, req: ScanRequest):
        raw = req.manufacturing_date_declaration
        if not raw or not raw.strip():
            return (
                FieldResult(field=F_MFG, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={}, notes="No manufacturing date declared."),
                Violation(field=F_MFG, rule_citation=CITATION_MFG_DATE,
                          description="Month and year of manufacture is not declared."),
            )

        d = parsers.parse_month_year(raw)
        if not d.ok:
            return (
                FieldResult(field=F_MFG, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={"error": d.error},
                            notes="Date not in accepted Month+Year format."),
                Violation(field=F_MFG, rule_citation=CITATION_MFG_DATE,
                          description="Month and year of manufacture/pre-packing is not declared."),
            )

        # Default to 1st of month for internal math; day is NOT required.
        internal = d.as_first_of_month()
        return (
            FieldResult(
                field=F_MFG, status=FieldStatus.COMPLIANT, raw_input=raw,
                parsed={"month": d.month, "year": d.year,
                        "internal_date": internal.isoformat() if internal else None},
                notes="Month+Year of manufacture/pre-packing verified (Rule 6(1)(c)).",
            ),
            None,
        )

    # ------------------------------------------------------------------
    # Expiry date (optional field / Best Before)
    # ------------------------------------------------------------------
    def _check_expiry_date(self, req: ScanRequest):
        raw = req.expiry_date_declaration
        if not raw or not raw.strip():
            return (
                FieldResult(field=F_EXPIRY, status=FieldStatus.NOT_REQUIRED, raw_input=raw,
                            parsed={}, notes="No expiry declared; not flagged as mandatory today."),
                None,
            )

        d = parsers.parse_month_year(raw)
        if not d.ok:
            return (
                FieldResult(field=F_EXPIRY, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={"error": d.error},
                            notes="Expiry/Best-Before date not in recognised format."),
                Violation(field=F_EXPIRY, rule_citation=CITATION_EXPIRY,
                          description="Expiry/best-before date is not a valid declaration."),
            )

        if d.is_best_before_statement:
            return (
                FieldResult(
                    field=F_EXPIRY, status=FieldStatus.COMPLIANT, raw_input=raw,
                    parsed={"best_before_duration": d.best_before_duration, "type": "relative_duration"},
                    notes=f"Statutory Best Before declaration verified ({d.best_before_duration}) under FSSAI & Rule 6(1)(c).",
                ),
                None,
            )

        # Default expiry to LAST day of month for internal math.
        internal = d.as_last_of_month()
        return (
            FieldResult(
                field=F_EXPIRY, status=FieldStatus.COMPLIANT, raw_input=raw,
                parsed={"month": d.month, "year": d.year,
                        "internal_date": internal.isoformat() if internal else None},
                notes="Calendar expiry Month+Year verified.",
            ),
            None,
        )

    # ------------------------------------------------------------------
    # Unit sale price - exemptions FIRST
    # ------------------------------------------------------------------
    def _check_unit_sale_price(
        self,
        req: ScanRequest,
        price: parsers.PriceParseResult,
        qty: parsers.QuantityParseResult,
    ):
        raw = req.unit_sale_price_declaration
        mrp = price.single

        # Exemption evaluation needs a parsed quantity. If quantity is
        # unparseable we cannot assess exemptions or math -> manual review.
        if not qty.ok:
            return (
                FieldResult(field=F_USP, status=FieldStatus.NEEDS_MANUAL_REVIEW, raw_input=raw,
                            parsed={}, notes="Cannot assess USP: net quantity not parseable."),
                None,
            )

        exemption = self._usp_exemption(mrp, qty)
        if exemption:
            return (
                FieldResult(
                    field=F_USP, status=FieldStatus.NOT_REQUIRED, raw_input=raw,
                    parsed={"exemption": exemption},
                    notes=f"Unit sale price not legally required: {exemption}.",
                ),
                None,
            )

        # Not exempt -> USP must be declared.
        if not raw or not raw.strip():
            return (
                FieldResult(field=F_USP, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={}, notes="Unit sale price required but not declared."),
                Violation(field=F_USP, rule_citation=CITATION_USP,
                          description="Unit sale price is required for this product but is not declared."),
            )

        # Declared -> verify the math using PAID quantity only.
        declared = parsers.parse_prices(raw)
        if declared.single is None:
            return (
                FieldResult(field=F_USP, status=FieldStatus.NEEDS_MANUAL_REVIEW, raw_input=raw,
                            parsed={"candidate_prices": declared.prices},
                            notes="Could not read a single unit price value to verify."),
                None,
            )

        if mrp is None:
            # No clean MRP to compute against.
            return (
                FieldResult(field=F_USP, status=FieldStatus.NEEDS_MANUAL_REVIEW, raw_input=raw,
                            parsed={"declared_usp": declared.single},
                            notes="Cannot verify USP math without a single resolved MRP."),
                None,
            )

        expected, basis = self._expected_usp(mrp, qty)
        # Allow a small rounding tolerance (see USP_TOLERANCE_* constants).
        tolerance = max(USP_TOLERANCE_MIN_RUPEES, expected * USP_TOLERANCE_FRACTION)
        matches = abs(declared.single - expected) <= tolerance
        parsed = {
            "declared_usp": declared.single,
            "expected_usp": round(expected, 4),
            "basis": basis,
            "paid_quantity_base": qty.paid_base,
            "mrp_used": mrp,
        }
        if matches:
            return (
                FieldResult(field=F_USP, status=FieldStatus.COMPLIANT, raw_input=raw,
                            parsed=parsed, notes=f"USP matches expected ({basis})."),
                None,
            )
        return (
            FieldResult(field=F_USP, status=FieldStatus.VIOLATION, raw_input=raw,
                        parsed=parsed, notes="Declared USP does not match computed value."),
            Violation(field=F_USP, rule_citation=CITATION_USP,
                      description=(
                          f"Unit sale price mismatch: declared {declared.single}, "
                          f"expected {round(expected, 2)} ({basis})."
                      )),
        )

    def _usp_exemption(
        self, mrp: Optional[float], qty: parsers.QuantityParseResult
    ) -> Optional[str]:
        """Return an exemption reason string if USP is not required, else None."""
        dim = qty.dimension
        total = qty.total_base or 0.0

        # Exemption: exactly 1kg / 1L / 1 unit / 1 metre.
        if dim == parsers.MASS and total == 1000.0:
            return "net quantity is exactly 1kg"
        if dim == parsers.VOLUME and total == 1000.0:
            return "net quantity is exactly 1 litre"
        if dim == parsers.COUNT and total == 1.0:
            return "net quantity is exactly 1 unit/piece"
        if dim == parsers.LENGTH and total == 1.0:
            return "net quantity is exactly 1 metre"

        # Exemption: MRP <= Rs 35.
        if mrp is not None and mrp <= 35.0:
            return "MRP is Rs 35 or less"

        # Exemption: tiny pack <= 10g / 10ml.
        if dim == parsers.MASS and total <= 10.0:
            return "net quantity is 10g or less"
        if dim == parsers.VOLUME and total <= 10.0:
            return "net quantity is 10ml or less"

        return None

    def _expected_usp(
        self, mrp: float, qty: parsers.QuantityParseResult
    ) -> tuple[float, str]:
        """Compute the expected unit sale price using PAID quantity only.

        Basis rules:
          * total <= 1kg/1L  -> per 100g / per 100ml
          * total  > 1kg/1L  -> per kg / per litre
        For count/length we express per single unit / per metre.
        """
        dim = qty.dimension
        paid = qty.paid_base or 0.0
        total = qty.total_base or 0.0

        if dim in (parsers.MASS, parsers.VOLUME):
            per_label = "100g" if dim == parsers.MASS else "100ml"
            big_label = "kg" if dim == parsers.MASS else "litre"
            if total <= 1000.0:
                expected = mrp / paid * 100.0  # per 100 base units
                basis = f"per {per_label} on paid quantity {paid:g}"
            else:
                expected = mrp / paid * 1000.0  # per kg / per litre
                basis = f"per {big_label} on paid quantity {paid:g}"
            return expected, basis

        # count / length -> per single base unit
        unit_label = parsers._BASE_UNIT_LABEL.get(dim, "unit")
        expected = mrp / paid
        return expected, f"per {unit_label} on paid quantity {paid:g}"

    # ------------------------------------------------------------------
    # Country of origin - explicit phrase only, never barcode-based
    # ------------------------------------------------------------------
    def _check_country_of_origin(self, req: ScanRequest):
        raw = req.country_of_origin_declaration
        m = _ORIGIN_PHRASE_RE.search(raw) if raw else None
        if m:
            country = m.group(1).strip().rstrip(".").strip()
            return (
                FieldResult(field=F_ORIGIN, status=FieldStatus.COMPLIANT, raw_input=raw,
                            parsed={"country": country, "source": "explicit_phrase"},
                            notes=f"Explicit origin phrase found: '{country}'."),
                None,
            )

        # No explicit phrase and no verified reference record (Day 2) ->
        # manual review, never auto-compliant.
        return (
            FieldResult(
                field=F_ORIGIN, status=FieldStatus.NEEDS_MANUAL_REVIEW, raw_input=raw,
                parsed={"country": None, "source": None},
                notes="No explicit 'Made in / Product of' phrase; no verified reference. "
                      "Barcode-prefix guessing is not used (legally unreliable).",
            ),
            None,
        )

    # ------------------------------------------------------------------
    # Manufacturer name & address - presence check only (Day 1)
    # ------------------------------------------------------------------
    def _check_manufacturer(self, req: ScanRequest):
        raw = req.manufacturer_name_address
        if raw and raw.strip():
            return (
                FieldResult(field=F_MANUFACTURER, status=FieldStatus.COMPLIANT, raw_input=raw,
                            parsed={"present": True},
                            notes="Manufacturer name/address present (deep parsing is Day 2)."),
                None,
            )
        return (
            FieldResult(field=F_MANUFACTURER, status=FieldStatus.VIOLATION, raw_input=raw,
                        parsed={"present": False}, notes="Manufacturer name/address missing."),
            Violation(field=F_MANUFACTURER, rule_citation=CITATION_MANUFACTURER,
                      description="Name and address of manufacturer/packer/importer is missing."),
        )

    # ------------------------------------------------------------------
    # Consumer care - phone or email present
    # ------------------------------------------------------------------
    def _check_consumer_care(self, req: ScanRequest):
        raw = req.consumer_care_details
        email = parsers.find_email(raw)
        phone = parsers.find_phone(raw)
        if email or phone:
            return (
                FieldResult(field=F_CONSUMER_CARE, status=FieldStatus.COMPLIANT, raw_input=raw,
                            parsed={"email": email, "phone": phone},
                            notes="Contact detail (phone/email) present."),
                None,
            )
        return (
            FieldResult(field=F_CONSUMER_CARE, status=FieldStatus.VIOLATION, raw_input=raw,
                        parsed={"email": None, "phone": None},
                        notes="No phone number or email found."),
            Violation(field=F_CONSUMER_CARE, rule_citation=CITATION_CONSUMER_CARE,
                      description="Consumer care details lack a valid phone number or email."),
        )

    # ------------------------------------------------------------------
    # FSSAI - 14-digit number required
    # ------------------------------------------------------------------
    def _check_fssai(self, req: ScanRequest):
        raw = req.fssai_license_number
        number = parsers.find_fssai_14(raw)
        if number:
            return (
                FieldResult(field=F_FSSAI, status=FieldStatus.COMPLIANT, raw_input=raw,
                            parsed={"license_number": number},
                            notes="Valid 14-digit FSSAI licence number found."),
                None,
            )

        if parsers.mentions_fssai(raw):
            return (
                FieldResult(field=F_FSSAI, status=FieldStatus.VIOLATION, raw_input=raw,
                            parsed={"license_number": None},
                            notes="'FSSAI' mentioned but no valid 14-digit number nearby."),
                Violation(field=F_FSSAI, rule_citation=CITATION_FSSAI,
                          description="Incomplete or invalid FSSAI licence number "
                                      "(14-digit number not found)."),
            )

        return (
            FieldResult(field=F_FSSAI, status=FieldStatus.VIOLATION, raw_input=raw,
                        parsed={"license_number": None},
                        notes="No FSSAI licence number present."),
            Violation(field=F_FSSAI, rule_citation=CITATION_FSSAI,
                      description="FSSAI licence number is not declared."),
        )
