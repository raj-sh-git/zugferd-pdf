#!/usr/bin/env python3
"""
ZUGFeRD & PDF/A-3 Compliance Inspector.

Validates any given PDF file against PDF/A-3 and ZUGFeRD / Factur-X requirements:
1. PDF Header & Version
2. PDF/A Identification (Part 3, Conformance U/B) in XMP Metadata
3. OutputIntent Dictionary & ICC Color Profile (sRGB)
4. Associated Files (/AF) and Name Tree (/Names/EmbeddedFiles)
5. Embedded XML validation (factur-x.xml / zugferd-invoice.xml)
6. Business Profile & Guideline Check (EN 16931, BASIC, EXTENDED, etc.)

Usage:
  python validate_pdf.py path/to/your_invoice.pdf
"""

from decimal import Decimal
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pikepdf


def inspect_compliance(pdf_path: str) -> bool:
    print("=" * 65)
    print(f"🔍 Inspecting Compliance for: {pdf_path}")
    print("=" * 65)

    if not os.path.exists(pdf_path):
        print(f"❌ Error: File not found: {pdf_path}", file=sys.stderr)
        return False

    all_passed = True

    try:
        pdf = pikepdf.open(pdf_path)
    except Exception as e:
        print(f"❌ Failed to open PDF file: {e}")
        return False

    # 1. PDF Version Check
    print("\n1. PDF Header & Catalog")
    version = str(pdf.pdf_version)
    if version in ["1.7", "1.6", "1.5", "1.4"]:
        print(f"   ✅ PDF Version: {version}")
    else:
        print(f"   ⚠️ PDF Version: {version} (PDF/A-3 is typically 1.7)")

    # 2. Check XMP Metadata & PDF/A Identification
    print("\n2. PDF/A-3 XMP Metadata")
    if "/Metadata" not in pdf.Root:
        print("   ❌ Missing /Metadata stream in PDF Catalog!")
        all_passed = False
    else:
        try:
            xmp_bytes = pdf.Root.Metadata.read_bytes()
            xmp_str = xmp_bytes.decode("utf-8", errors="ignore")

            # Check PDF/A ID
            has_part3 = "<pdfaid:part>3</pdfaid:part>" in xmp_str or "<pdfaid:part>3" in xmp_str
            has_conf_u = "<pdfaid:conformance>U</pdfaid:conformance>" in xmp_str
            has_conf_b = "<pdfaid:conformance>B</pdfaid:conformance>" in xmp_str

            if has_part3:
                print("   ✅ PDF/A Part: 3 (ISO 19005-3)")
            else:
                print("   ❌ Missing or invalid <pdfaid:part> (expected 3 for PDF/A-3)")
                all_passed = False

            if has_conf_u:
                print("   ✅ PDF/A Conformance Level: U (Unicode - PDF/A-3U)")
            elif has_conf_b:
                print("   ℹ️ PDF/A Conformance Level: B (Basic - PDF/A-3B)")
            else:
                print("   ⚠️ Unrecognized or missing <pdfaid:conformance>")

            # Check Factur-X / ZUGFeRD extension
            if "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#" in xmp_str or "urn:ferd:pdfa:CrossIndustryDocument:invoice:1p0#" in xmp_str:
                print("   ✅ Factur-X / ZUGFeRD XMP Extension Schema present")
            else:
                print("   ⚠️ Factur-X / ZUGFeRD XMP Extension Schema not detected in metadata")
        except Exception as e:
            print(f"   ❌ Error reading XMP metadata: {e}")
            all_passed = False

    # 3. Check OutputIntent
    print("\n3. Color Management / OutputIntent")
    if "/OutputIntents" not in pdf.Root or len(pdf.Root.OutputIntents) == 0:
        print("   ❌ Missing /OutputIntents dictionary (Required for PDF/A)")
        all_passed = False
    else:
        oi = pdf.Root.OutputIntents[0]
        oi_type = str(oi.get("/Type", ""))
        oi_s = str(oi.get("/S", ""))
        oi_id = str(oi.get("/OutputConditionIdentifier", ""))
        oi_info = str(oi.get("/Info", ""))

        print(f"   ✅ Subtype (/S): {oi_s}")
        print(f"   ✅ Identifier: {oi_id}")
        print(f"   ✅ Info: {oi_info}")

        if "/DestOutputProfile" in oi:
            print("   ✅ Embedded ICC Destination Output Profile present")
        else:
            print("   ❌ Missing embedded /DestOutputProfile ICC stream")
            all_passed = False

    # 4. Check Attachments & /AF
    print("\n4. Embedded Attachments & Associated Files (/AF)")
    attachments = list(pdf.attachments.keys())
    print(f"   Attached files count: {len(attachments)}")
    for name in attachments:
        spec = pdf.attachments[name]
        rel = getattr(spec, "relationship", None)
        size = len(spec.get_file().read_bytes())
        print(f"   - {name} ({size:,} bytes) [AFRelationship: {rel}]")

    has_zugferd_xml = any(name.lower() in ["factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml"] for name in attachments)
    if has_zugferd_xml:
        print("   ✅ Primary ZUGFeRD / Factur-X XML invoice attachment found")
    else:
        print("   ❌ No 'factur-x.xml' or 'zugferd-invoice.xml' attachment found")
        all_passed = False

    if "/AF" in pdf.Root:
        print(f"   ✅ Catalog /AF (Associated Files) array present ({len(pdf.Root.AF)} registered)")
    else:
        print("   ❌ Missing /AF array in PDF Catalog (Required for PDF/A-3)")
        all_passed = False

    # 5. Extract & Validate the XML Content
    print("\n5. XML Content & Profile Validation")
    xml_data = None
    target_xml_name = None
    for name in ["factur-x.xml", "zugferd-invoice.xml", "ZUGFeRD-invoice.xml", "xrechnung.xml"]:
        if name in pdf.attachments:
            xml_data = pdf.attachments[name].get_file().read_bytes()
            target_xml_name = name
            break

    if xml_data:
        try:
            root = ET.fromstring(xml_data)
            print(f"   ✅ Well-formed XML in '{target_xml_name}'")
            print(f"   Root tag: {root.tag.split('}')[-1]}")

            # Find Guideline ID
            ns = {
                "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
                "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
            }
            guideline = root.find(".//ram:GuidelineSpecifiedDocumentContextParameter/ram:ID", ns)
            if guideline is not None and guideline.text:
                print(f"   ✅ Profile Identifier (BT-24): {guideline.text}")
            else:
                print("   ⚠️ Guideline ID (BT-24) not found in ExchangedDocumentContext")

            # Find Invoice Number & Total
            doc_id = root.find(".//rsm:ExchangedDocument/ram:ID", ns)
            if doc_id is not None and doc_id.text:
                print(f"   Invoice Number: {doc_id.text}")

            grand_total = root.find(".//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount", ns)
            if grand_total is not None and grand_total.text:
                print(f"   Grand Total Amount: {grand_total.text}")

        except Exception as e:
            print(f"   ❌ XML Parsing failed: {e}")
            all_passed = False

    # Summary
    print("\n" + "=" * 65)
    if all_passed:
        print("🎉 RESULT: VALID PDF/A-3 ZUGFeRD INVOICE STRUCTURE")
        print("   Upload to official validator for full Schematron report:")
        print("   👉 https://e-rechnung-vorlage.de/xrechnung-zugferd-validator/")
    else:
        print("⚠️ RESULT: ISSUES DETECTED - See errors above.")
    print("=" * 65)

    return all_passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_pdf.py <path_to_invoice.pdf>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    success = inspect_compliance(pdf_file)
    sys.exit(0 if success else 1)
