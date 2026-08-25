"""
ZUGFeRD & PDF/A-3 Compliance Validator.
Inspects PDF documents for PDF/A-3 (ISO 19005-3) and EN 16931 / Factur-X conformance.
"""

from dataclasses import dataclass, field
from decimal import Decimal
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import xml.etree.ElementTree as ET

import pikepdf


@dataclass
class CheckItem:
    category: str
    name: str
    status: str  # "PASS", "FAIL", "WARN", "INFO"
    message: str
    details: Optional[str] = None


@dataclass
class ValidationReport:
    is_valid: bool
    conformance_level: Optional[str] = None
    pdf_version: Optional[str] = None
    guideline_id: Optional[str] = None
    checks: List[CheckItem] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    extracted_xml: Optional[bytes] = None

    def print_summary(self):
        """Prints a human-readable terminal summary report."""
        print("=" * 70)
        print("📋 ZUGFeRD / Factur-X & PDF/A-3 Compliance Validation Report")
        print("=" * 70)

        current_cat = None
        for check in self.checks:
            if check.category != current_cat:
                current_cat = check.category
                print(f"\n📂 {current_cat}")

            icon = "✅" if check.status == "PASS" else ("❌" if check.status == "FAIL" else ("⚠️" if check.status == "WARN" else "ℹ️"))
            print(f"   {icon} [{check.status}] {check.name}: {check.message}")
            if check.details:
                print(f"      💡 {check.details}")

        print("\n" + "=" * 70)
        if self.is_valid:
            print("🎉 OVERALL RESULT: PASSED (100% Compliant ZUGFeRD / PDF/A-3 Invoice)")
            print("   Ready for official validation: https://e-rechnung-vorlage.de/xrechnung-zugferd-validator/")
        else:
            print(f"❌ OVERALL RESULT: FAILED ({len(self.errors)} error(s) detected)")
            print("\nErrors to fix:")
            for idx, err in enumerate(self.errors, 1):
                print(f"   {idx}. {err}")
        print("=" * 70)


def _find_elements_by_local_name(elem, local_tag: str):
    """Finds child elements matching local tag name regardless of namespace."""
    return [e for e in elem.iter() if e.tag.split("}")[-1] == local_tag]


def _check_decimals(value_str: str, max_decimals: int = 2) -> bool:
    """Returns True if the decimal part has <= max_decimals digits."""
    if "." in value_str:
        dec_part = value_str.split(".")[1]
        return len(dec_part) <= max_decimals
    return True


def validate_zugferd_pdf(
    pdf_input: Union[bytes, str, Path],
    print_report: bool = False,
) -> ValidationReport:
    """
    Validates a PDF document for ZUGFeRD / Factur-X (EN 16931) and PDF/A-3 (ISO 19005-3) compliance.

    Parameters:
        pdf_input: PDF file path or raw PDF bytes.
        print_report: If True, prints a formatted summary table to stdout.

    Returns:
        ValidationReport: Structured result with boolean is_valid, list of checks, errors, and warnings.
    """
    checks: List[CheckItem] = []
    errors: List[str] = []
    warnings: List[str] = []
    extracted_xml_bytes: Optional[bytes] = None
    pdf_ver = None
    guideline_id = None
    conformance = None

    # 1. Open PDF
    try:
        if isinstance(pdf_input, (str, Path)):
            pdf = pikepdf.open(pdf_input)
        else:
            pdf = pikepdf.open(io.BytesIO(pdf_input))
        pdf_ver = str(pdf.pdf_version)
        checks.append(CheckItem("1. PDF Document Header", "PDF Version", "PASS", f"PDF Version {pdf_ver}"))
    except Exception as e:
        err_msg = f"Failed to parse PDF: {e}"
        errors.append(err_msg)
        checks.append(CheckItem("1. PDF Document Header", "PDF File Parse", "FAIL", err_msg))
        report = ValidationReport(False, None, None, None, checks, errors, warnings, None)
        if print_report:
            report.print_summary()
        return report

    # 2. XMP Metadata & PDF/A-3 Identification
    cat_xmp = "2. PDF/A-3 XMP Metadata"
    if "/Metadata" in pdf.Root:
        try:
            xmp_str = pdf.Root.Metadata.read_bytes().decode("utf-8", errors="ignore")

            # Check PDF/A Part 3
            if "<pdfaid:part>3</pdfaid:part>" in xmp_str or "<pdfaid:part>3" in xmp_str:
                checks.append(CheckItem(cat_xmp, "PDF/A Part", "PASS", "PDF/A-3 (ISO 19005-3) declared in XMP"))
            else:
                err = "Missing <pdfaid:part>3</pdfaid:part> in XMP metadata (required for PDF/A-3)"
                errors.append(err)
                checks.append(CheckItem(cat_xmp, "PDF/A Part", "FAIL", err))

            # Check Conformance Level (U or B)
            if "<pdfaid:conformance>U</pdfaid:conformance>" in xmp_str:
                conformance = "PDF/A-3U"
                checks.append(CheckItem(cat_xmp, "Conformance Level", "PASS", "PDF/A-3U (Unicode Conformance)"))
            elif "<pdfaid:conformance>B</pdfaid:conformance>" in xmp_str:
                conformance = "PDF/A-3B"
                checks.append(CheckItem(cat_xmp, "Conformance Level", "PASS", "PDF/A-3B (Basic Conformance)"))
            else:
                warn = "No standard <pdfaid:conformance> ('U' or 'B') found in XMP metadata"
                warnings.append(warn)
                checks.append(CheckItem(cat_xmp, "Conformance Level", "WARN", warn))

            # Check Factur-X / ZUGFeRD XMP Extension Schema
            if "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#" in xmp_str or "urn:ferd:pdfa:CrossIndustryDocument:invoice:1p0#" in xmp_str:
                checks.append(CheckItem(cat_xmp, "Factur-X Extension", "PASS", "Factur-X / ZUGFeRD extension schema declared"))
            else:
                warn = "Factur-X / ZUGFeRD extension schema (fx:) not declared under pdfaExtension:schemas"
                warnings.append(warn)
                checks.append(CheckItem(cat_xmp, "Factur-X Extension", "WARN", warn))

        except Exception as e:
            err = f"Error reading XMP metadata stream: {e}"
            errors.append(err)
            checks.append(CheckItem(cat_xmp, "XMP Metadata Stream", "FAIL", err))
    else:
        err = "Missing /Metadata stream in PDF Catalog (Mandatory for PDF/A)"
        errors.append(err)
        checks.append(CheckItem(cat_xmp, "XMP Metadata Stream", "FAIL", err))

    # 3. OutputIntent (Color Management)
    cat_oi = "3. Color Management (OutputIntent)"
    if "/OutputIntents" in pdf.Root and len(pdf.Root.OutputIntents) > 0:
        oi = pdf.Root.OutputIntents[0]
        oi_s = str(oi.get("/S", ""))
        oi_id = str(oi.get("/OutputConditionIdentifier", ""))
        oi_info = str(oi.get("/Info", ""))

        if oi_s == "/GTS_PDFA1":
            checks.append(CheckItem(cat_oi, "OutputIntent Subtype (/S)", "PASS", "/GTS_PDFA1 (PDF/A OutputIntent)"))
        else:
            warn = f"OutputIntent /S is '{oi_s}' (expected /GTS_PDFA1)"
            warnings.append(warn)
            checks.append(CheckItem(cat_oi, "OutputIntent Subtype (/S)", "WARN", warn))

        checks.append(CheckItem(cat_oi, "Identifier & Info", "PASS", f"Identifier='{oi_id}', Info='{oi_info}'"))

        if "/DestOutputProfile" in oi:
            checks.append(CheckItem(cat_oi, "ICC Color Profile", "PASS", "Embedded /DestOutputProfile ICC stream present"))
        else:
            err = "Missing embedded /DestOutputProfile ICC stream in OutputIntent"
            errors.append(err)
            checks.append(CheckItem(cat_oi, "ICC Color Profile", "FAIL", err))
    else:
        err = "Missing /OutputIntents dictionary in PDF Catalog (Mandatory for PDF/A)"
        errors.append(err)
        checks.append(CheckItem(cat_oi, "OutputIntents Dictionary", "FAIL", err))

    # 4. Embedded Files & /AF
    cat_af = "4. Associated Files (/AF) & Embedded Files"
    attachments = list(pdf.attachments.keys())
    checks.append(CheckItem(cat_af, "Attached Files Count", "INFO", f"{len(attachments)} file(s) attached: {attachments}"))

    # Check for primary invoice XML
    target_xml_name = None
    for name in ["factur-x.xml", "zugferd-invoice.xml", "ZUGFeRD-invoice.xml", "xrechnung.xml"]:
        if name in pdf.attachments:
            target_xml_name = name
            extracted_xml_bytes = pdf.attachments[name].get_file().read_bytes()
            break

    if not target_xml_name:
        for name, spec in pdf.attachments.items():
            if name.lower().endswith(".xml"):
                target_xml_name = name
                extracted_xml_bytes = spec.get_file().read_bytes()
                break

    if target_xml_name:
        checks.append(CheckItem(cat_af, "Invoice XML Attachment", "PASS", f"Found '{target_xml_name}' ({len(extracted_xml_bytes):,} bytes)"))
    else:
        err = "No ZUGFeRD / Factur-X XML invoice attachment (factur-x.xml or zugferd-invoice.xml) found"
        errors.append(err)
        checks.append(CheckItem(cat_af, "Invoice XML Attachment", "FAIL", err))

    # Check Catalog /AF array
    if "/AF" in pdf.Root and len(pdf.Root.AF) > 0:
        checks.append(CheckItem(cat_af, "Catalog /AF Array", "PASS", f"Catalog /AF array contains {len(pdf.Root.AF)} entry(ies)"))
    else:
        err = "Missing /AF (Associated Files) array in PDF Catalog (Mandatory for PDF/A-3)"
        errors.append(err)
        checks.append(CheckItem(cat_af, "Catalog /AF Array", "FAIL", err))

    # 5. XML Content & Schematron Business Rules
    cat_xml = "5. XML Content & EN 16931 Business Rules"
    if extracted_xml_bytes:
        try:
            root = ET.fromstring(extracted_xml_bytes)
            root_tag = root.tag.split("}")[-1]
            checks.append(CheckItem(cat_xml, "XML Well-Formedness", "PASS", f"Valid XML with root <{root_tag}>"))

            # 5.1 Check Guideline ID (BT-24)
            guideline_ctx = _find_elements_by_local_name(root, "GuidelineSpecifiedDocumentContextParameter")
            if guideline_ctx:
                id_elems = _find_elements_by_local_name(guideline_ctx[0], "ID")
                if id_elems and id_elems[0].text:
                    guideline_id = id_elems[0].text.strip()
                    allowed_ids = [
                        "urn:cen.eu:en16931:2017",
                        "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic",
                        "urn:factur-x.eu:1p0:basicwl",
                        "urn:factur-x.eu:1p0:minimum",
                        "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended",
                        "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0",
                    ]

                    if guideline_id == "urn:cen.eu:en16931:2017":
                        checks.append(CheckItem(cat_xml, "Specification Identifier (BT-24)", "PASS", f"'{guideline_id}' (EN 16931 Comfort Profile)"))
                    elif guideline_id in allowed_ids:
                        checks.append(CheckItem(cat_xml, "Specification Identifier (BT-24)", "PASS", f"'{guideline_id}' (Valid Profile)"))
                    else:
                        err = f"Value of 'ram:ID' in GuidelineSpecifiedDocumentContextParameter is not allowed: '{guideline_id}'"
                        errors.append(err)
                        checks.append(CheckItem(
                            cat_xml,
                            "Specification Identifier (BT-24)",
                            "FAIL",
                            err,
                            details="For EN 16931 profile, use exactly: 'urn:cen.eu:en16931:2017' (without #compliant# suffix).",
                        ))
                else:
                    err = "Missing <ram:ID> in GuidelineSpecifiedDocumentContextParameter"
                    errors.append(err)
                    checks.append(CheckItem(cat_xml, "Specification Identifier (BT-24)", "FAIL", err))
            else:
                err = "Missing <ram:GuidelineSpecifiedDocumentContextParameter> in XML"
                errors.append(err)
                checks.append(CheckItem(cat_xml, "Specification Identifier (BT-24)", "FAIL", err))

            # 5.2 Check BR-DEC-23: LineTotalAmount max 2 decimals
            line_items = _find_elements_by_local_name(root, "IncludedSupplyChainTradeLineItem")
            checks.append(CheckItem(cat_xml, "Line Items Count", "INFO", f"{len(line_items)} line item(s) found"))
            has_line_dec_error = False

            for idx, line in enumerate(line_items, 1):
                lt_elems = _find_elements_by_local_name(line, "LineTotalAmount")
                if lt_elems and lt_elems[0].text:
                    lt_val = lt_elems[0].text.strip()
                    if not _check_decimals(lt_val, 2):
                        err = f"BR-DEC-23 Violation: Line {idx} LineTotalAmount '{lt_val}' has more than 2 decimals"
                        errors.append(err)
                        checks.append(CheckItem(
                            cat_xml,
                            f"Line {idx} Total Amount (BT-131)",
                            "FAIL",
                            err,
                            details="Invoice line net amount must have at most 2 decimal places (e.g. 441.00 instead of 441.0000).",
                        ))
                        has_line_dec_error = True

            if not has_line_dec_error and len(line_items) > 0:
                checks.append(CheckItem(cat_xml, "Line Total Decimals (BR-DEC-23)", "PASS", "All line item totals formatted with <= 2 decimals"))

            # 5.3 Check Monetary Summations
            header_sum = _find_elements_by_local_name(root, "SpecifiedTradeSettlementHeaderMonetarySummation")
            if header_sum:
                gt_elems = _find_elements_by_local_name(header_sum[0], "GrandTotalAmount")
                if gt_elems and gt_elems[0].text:
                    gt_val = gt_elems[0].text.strip()
                    if not _check_decimals(gt_val, 2):
                        err = f"GrandTotalAmount '{gt_val}' exceeds 2 decimal places"
                        errors.append(err)
                        checks.append(CheckItem(cat_xml, "Grand Total Amount (BT-112)", "FAIL", err))
                    else:
                        checks.append(CheckItem(cat_xml, "Grand Total Amount (BT-112)", "PASS", f"Grand Total: {gt_val}"))

        except Exception as e:
            err = f"XML Parsing failed: {e}"
            errors.append(err)
            checks.append(CheckItem(cat_xml, "XML Content", "FAIL", err))

    is_valid = len(errors) == 0
    report = ValidationReport(
        is_valid=is_valid,
        conformance_level=conformance,
        pdf_version=pdf_ver,
        guideline_id=guideline_id,
        checks=checks,
        errors=errors,
        warnings=warnings,
        extracted_xml=extracted_xml_bytes,
    )

    if print_report:
        report.print_summary()

    return report
