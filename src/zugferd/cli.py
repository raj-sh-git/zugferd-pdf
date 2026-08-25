"""
ZUGFeRD / Factur-X Command Line Interface.
Provides global 'zugferd' CLI commands: create, package, extract.
"""

import argparse
from datetime import date, timedelta
from decimal import Decimal
import os
import sys

from zugferd.extractor import extract_zugferd_xml
from zugferd.models import (
    Invoice,
    LineItem,
    PaymentMeans,
    PostalAddress,
    TradeParty,
)
from zugferd.pdf_builder import generate_invoice_pdf
from zugferd.pdfa_packager import package_zugferd_pdfa3u
from zugferd.xml_generator import generate_facturx_xml


def create_sample_invoice() -> Invoice:
    """Creates a sample invoice for testing and demonstration."""
    seller = TradeParty(
        name="TechSolutions GmbH",
        address=PostalAddress(
            postcode="10115",
            line_one="Friedrichstraße 123",
            city_name="Berlin",
            country_id="DE",
        ),
        vat_id="DE123456789",
        contact_name="Max Mustermann",
        contact_email="billing@techsolutions.example.com",
        contact_phone="+49 30 12345678",
    )

    buyer = TradeParty(
        name="Global Cloud Logistics AG",
        address=PostalAddress(
            postcode="80331",
            line_one="Marienplatz 1",
            city_name="München",
            country_id="DE",
        ),
        vat_id="DE987654321",
    )

    items = [
        LineItem(
            line_id="1",
            name="Cloud Infrastructure Consulting",
            quantity=Decimal("16.00"),
            unit_code="HUR",
            net_unit_price=Decimal("125.00"),
            vat_rate=Decimal("19.00"),
            vat_category="S",
            description="Architecture design and cloud migration consulting",
        ),
        LineItem(
            line_id="2",
            name="Kubernetes Cluster Setup & Hardening",
            quantity=Decimal("1.00"),
            unit_code="C62",
            net_unit_price=Decimal("850.00"),
            vat_rate=Decimal("19.00"),
            vat_category="S",
            description="Automated setup of high-availability Kubernetes cluster",
        ),
    ]

    payment = PaymentMeans(
        type_code="58",
        iban="DE89370400440532013000",
        bic="DBBADEFFXXX",
        account_holder="TechSolutions GmbH",
    )

    today = date.today()
    due = today + timedelta(days=30)

    return Invoice(
        invoice_number="INV-2026-0001",
        issue_date=today,
        due_date=due,
        currency="EUR",
        seller=seller,
        buyer=buyer,
        items=items,
        payment_means=payment,
        buyer_reference="PO-2026-9876",
        notes=[
            "Thank you for choosing TechSolutions GmbH.",
            "Please transfer referencing invoice number INV-2026-0001.",
        ],
        conformance_level="EN 16931",
    )


def handle_create(args):
    invoice = create_sample_invoice()
    output_path = args.output
    
    # 1. Visual PDF
    pdf_bytes = generate_invoice_pdf(invoice)
    # 2. XML
    xml_bytes = generate_facturx_xml(invoice)
    # 3. PDF/A-3U package
    package_zugferd_pdfa3u(
        pdf_input=pdf_bytes,
        xml_data=xml_bytes,
        output_target=output_path,
        doc_filename="factur-x.xml",
        conformance_level=invoice.conformance_level,
        title=f"Invoice {invoice.invoice_number}",
        creator=invoice.seller.name,
    )
    print(f"✅ Generated compliant ZUGFeRD invoice: {output_path}")
    print("   Validate at: https://e-rechnung-vorlage.de/xrechnung-zugferd-validator/")


def handle_package(args):
    additional_att = []
    if args.attach:
        for fpath in args.attach:
            p = os.path.basename(fpath)
            additional_att.append({
                "filename": p,
                "data": fpath,
                "relationship": "/Supplement",
            })

    package_zugferd_pdfa3u(
        pdf_input=args.input_pdf,
        xml_data=args.xml_file,
        output_target=args.output_pdf,
        doc_filename=args.filename,
        conformance_level=args.profile,
        additional_attachments=additional_att if additional_att else None,
    )
    print(f"✅ Successfully created PDF/A-3U document: {args.output_pdf}")


def handle_extract(args):
    try:
        xml_bytes = extract_zugferd_xml(args.pdf_file, target_file=args.output)
        if args.output:
            print(f"✅ Extracted XML saved to: {args.output}")
        else:
            print(xml_bytes.decode("utf-8"))
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="zugferd",
        description="ZUGFeRD / Factur-X PDF/A-3U (ISO 19005-3) Generator & Packager CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: create
    p_create = subparsers.add_parser("create", help="Generate a sample ZUGFeRD PDF/A-3U invoice")
    p_create.add_argument("output", nargs="?", default="zugferd_invoice.pdf", help="Output PDF filename")
    p_create.set_defaults(func=handle_create)

    # Command: package
    p_package = subparsers.add_parser("package", help="Package existing PDF + XML into PDF/A-3U")
    p_package.add_argument("input_pdf", help="Input visual PDF file")
    p_package.add_argument("xml_file", help="Input ZUGFeRD / Factur-X XML invoice file")
    p_package.add_argument("output_pdf", help="Output PDF/A-3U file")
    p_package.add_argument("--profile", default="EN 16931", help="Profile (EN 16931, BASIC, EXTENDED)")
    p_package.add_argument("--filename", default="factur-x.xml", help="Attachment filename in PDF")
    p_package.add_argument("--attach", action="append", help="Extra attachment to embed (.xml, .pdf)")
    p_package.set_defaults(func=handle_package)

    # Command: extract
    p_extract = subparsers.add_parser("extract", help="Extract embedded ZUGFeRD XML from a PDF")
    p_extract.add_argument("pdf_file", help="PDF file to extract XML from")
    p_extract.add_argument("-o", "--output", help="Optional output XML file path")
    p_extract.set_defaults(func=handle_extract)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
