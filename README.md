# zugferd-pdf

[![PyPI Version](https://img.shields.io/pypi/v/zugferd-pdf.svg)](https://pypi.org/project/zugferd-pdf/)
[![Python Versions](https://img.shields.io/pypi/pyversions/zugferd-pdf.svg)](https://pypi.org/project/zugferd-pdf/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PDF/A Conformance](https://img.shields.io/badge/PDF%2FA-3U%20(ISO%2019005--3)-green.svg)](https://www.iso.org/standard/57222.html)
[![Non-AGPL](https://img.shields.io/badge/License-100%25%20Non--AGPL-brightgreen.svg)](#license--agpl-free-guarantee)

A fast, lightweight, and **commercially friendly (Non-AGPL)** Python library and CLI tool to generate and package **ZUGFeRD 2.x / Factur-X** hybrid electronic invoices conforming to **PDF/A-3U (ISO 19005-3)** and **EN 16931**.

---

## 🎯 Key Features

- ✅ **Strict PDF/A-3U Conformance (ISO 19005-3)**: Full Unicode mapping (`ToUnicode`) for embedded fonts.
- ✅ **Standard OutputIntent**: Valid embedded sRGB ICC profile (`Identifier: sRGB`, `Info: sRGB IEC61966-2.1`).
- ✅ **UN/CEFACT CII (EN 16931)**: Generates valid `factur-x.xml` adhering to European e-invoicing standards.
- ✅ **Multi-Attachment Safety**: Preserves existing attachments and allows adding extra `.xml` / `.pdf` documents with proper `/AFRelationship` (no corruption).
- ✅ **100% Non-AGPL / Commercially Friendly**: Replaces Ghostscript and PyMuPDF using permissive open-source libraries (BSD-3-Clause / MPL-2.0 / MIT).
- ✅ **CLI & Python API**: Use as a command-line tool or as an importable library.

---

## 📦 Installation

```bash
pip install zugferd-pdf
```

---

## 🚀 Quick Usage

### 1. Package an Existing PDF + XML into PDF/A-3U

```python
from zugferd import package_zugferd_pdfa3u

# Convert an existing PDF + invoice XML into a compliant PDF/A-3U document
pdfa_bytes = package_zugferd_pdfa3u(
    pdf_input="invoice.pdf",              # File path, bytes, or BytesIO
    xml_data="factur-x.xml",              # File path, string, or bytes
    output_target="zugferd_invoice.pdf",  # Optional: output file path
    conformance_level="EN 16931",         # 'EN 16931', 'BASIC', 'EXTENDED', etc.
    # Optional: Safely embed any extra attachments alongside factur-x.xml
    additional_attachments=[
        {
            "filename": "timesheet.xml",
            "data": b"<timesheet>...</timesheet>",
            "relationship": "/Supplement",
        }
    ],
)
```

---

### 2. End-to-End Invoice Generation in Python

```python
from datetime import date, timedelta
from decimal import Decimal
from zugferd import (
    Invoice,
    LineItem,
    PaymentMeans,
    PostalAddress,
    TradeParty,
    create_zugferd_invoice,
)

# 1. Define Parties
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

# 2. Define Line Items
items = [
    LineItem(
        line_id="1",
        name="Cloud Architecture Consulting",
        quantity=Decimal("10.00"),
        unit_code="HUR",  # Hours
        net_unit_price=Decimal("120.00"),
        vat_rate=Decimal("19.00"),
        vat_category="S",
        description="Design of secure cloud migration",
    ),
]

# 3. Define Payment Info
payment = PaymentMeans(
    type_code="58",  # SEPA Credit Transfer
    iban="DE89370400440532013000",
    bic="DBBADEFFXXX",
)

# 4. Create Invoice Object
invoice = Invoice(
    invoice_number="INV-2026-0001",
    issue_date=date.today(),
    due_date=date.today() + timedelta(days=30),
    currency="EUR",
    seller=seller,
    buyer=buyer,
    items=items,
    payment_means=payment,
    buyer_reference="PO-2026-0001",
    conformance_level="EN 16931",
)

# 5. Generate Compliant PDF/A-3U Document
pdf_bytes = create_zugferd_invoice(invoice, output_path="zugferd_invoice.pdf")
print("Invoice generated successfully!")
```

---

### 3. Extract XML from an Existing ZUGFeRD PDF

```python
from zugferd import extract_zugferd_xml

xml_bytes = extract_zugferd_xml("zugferd_invoice.pdf", target_file="extracted.xml")
print(xml_bytes.decode("utf-8"))
```

---

### 4. Validate Any PDF in Python

```python
from zugferd import validate_zugferd_pdf

# Returns a ValidationReport object
report = validate_zugferd_pdf("invoice.pdf", print_report=True)

if report.is_valid:
    print("PDF is 100% compliant!")
else:
    print(f"Validation failed with {len(report.errors)} error(s):")
    for err in report.errors:
        print(f" - {err}")
```

---

## 🛠️ Command-Line Interface (CLI)

The package installs a global CLI tool named `zugferd`:

```bash
# Validate any PDF for ZUGFeRD & PDF/A-3 compliance with detailed diagnostic summary
zugferd validate invoice.pdf

# Generate a sample invoice PDF/A-3U
zugferd create invoice.pdf

# Package existing PDF + XML into PDF/A-3U
zugferd package my_invoice.pdf factur-x.xml output_zugferd.pdf

# Package with extra attachments (.xml, .pdf, etc.)
zugferd package my_invoice.pdf factur-x.xml output_zugferd.pdf --attach extra_data.xml --attach timesheet.pdf

# Extract embedded factur-x.xml from any PDF
zugferd extract invoice.pdf -o extracted.xml
```

---

## 🔍 Validation

Upload your generated PDF to the official / popular German e-invoicing validator:
🔗 **[e-rechnung-vorlage.de/xrechnung-zugferd-validator](https://e-rechnung-vorlage.de/xrechnung-zugferd-validator/)**

Verified against:
- ✅ **VeraPDF**: Strict PDF/A-3U (ISO 19005-3:2012) conformance.
- ✅ **Factur-X / ZUGFeRD 2.x Schematron (`FACTUR-X_EN16931.xslt`)**: Valid specification identifier `urn:cen.eu:en16931:2017`.
- ✅ **ColorSync / OutputIntent**: Valid embedded sRGB profile.
- ✅ **Associated Files (`/AF`)**: Correct `/Alternative` and `/Supplement` relationships.

---

## 🚢 Publishing to PyPI

### Option 1: Manual Upload with Twine
1. Build distributions:
   ```bash
   pip install build twine
   python -m build
   ```
2. Verify package integrity:
   ```bash
   twine check dist/*
   ```
3. Upload to PyPI:
   ```bash
   twine upload dist/*
   ```

### Option 2: Automated via GitHub Actions (Trusted Publishing)
This repository includes `.github/workflows/publish.yml`. Connect your GitHub repository to PyPI via **Trusted Publishing (OIDC)** and create a new GitHub Release to automatically build and publish to PyPI.

---

## ⚖️ License & AGPL-Free Guarantee

Licensed under the **MIT License**.

All internal dependencies (`reportlab` [BSD], `pikepdf` [MPL-2.0], `pypdf` [BSD-3-Clause], `lxml` [BSD]) are commercially friendly and non-copyleft. No AGPL software (Ghostscript, MuPDF) is used.
