"""
ZUGFeRD / Factur-X PDF/A-3U Generation & Validation Library.
Creates and validates compliant electronic invoices conforming to PDF/A-3U (ISO 19005-3) and EN 16931.
Non-AGPL, commercially friendly open-source implementation.
"""

from typing import Any, Dict, List, Optional

from zugferd.extractor import extract_zugferd_xml
from zugferd.models import (
    Invoice,
    LineItem,
    PaymentMeans,
    PostalAddress,
    TaxSummary,
    TradeParty,
)
from zugferd.pdf_builder import generate_invoice_pdf
from zugferd.pdfa_packager import generate_xmp_metadata, package_zugferd_pdfa3u
from zugferd.validator import CheckItem, ValidationReport, validate_zugferd_pdf
from zugferd.xml_generator import generate_facturx_xml

__version__ = "0.1.2"


def create_zugferd_invoice(
    invoice: Invoice,
    output_path: Optional[str] = None,
    additional_attachments: Optional[List[Dict[str, Any]]] = None,
) -> bytes:
    """
    End-to-end generation of a ZUGFeRD / Factur-X PDF/A-3U electronic invoice.

    1. Generates visual PDF layout with embedded TrueType fonts (PDF/A-3U Unicode).
    2. Generates UN/CEFACT CII (EN 16931) factur-x.xml.
    3. Packages everything into a PDF/A-3U document with sRGB OutputIntent, XMP metadata,
       and safely embeds both factur-x.xml and any additional XML/PDF attachments.

    Parameters:
        invoice: Invoice data model.
        output_path: Optional file path to write the PDF.
        additional_attachments: Optional list of additional attachments, e.g.:
            [{"filename": "contract.xml", "data": b"<xml>...</xml>", "relationship": "/Supplement"}]

    Returns:
        bytes: The resulting PDF/A-3U document bytes.
    """
    # 1. Generate visual PDF
    pdf_bytes = generate_invoice_pdf(invoice)

    # 2. Generate CII XML
    xml_bytes = generate_facturx_xml(invoice)

    # 3. Package into PDF/A-3U
    return package_zugferd_pdfa3u(
        pdf_input=pdf_bytes,
        xml_data=xml_bytes,
        output_target=output_path,
        doc_filename="factur-x.xml",
        conformance_level=invoice.conformance_level,
        title=f"Invoice {invoice.invoice_number}",
        creator=invoice.seller.name,
        additional_attachments=additional_attachments,
    )


__all__ = [
    "__version__",
    "Invoice",
    "LineItem",
    "TradeParty",
    "PostalAddress",
    "PaymentMeans",
    "TaxSummary",
    "create_zugferd_invoice",
    "generate_invoice_pdf",
    "generate_facturx_xml",
    "package_zugferd_pdfa3u",
    "generate_xmp_metadata",
    "extract_zugferd_xml",
    "validate_zugferd_pdf",
    "ValidationReport",
    "CheckItem",
]
