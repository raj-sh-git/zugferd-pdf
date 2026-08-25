"""
Automated Test Suite for ZUGFeRD / Factur-X PDF/A-3U Library.
Tests model calculations, XML generation, PDF/A-3U structure,
multi-attachment safety, and extraction.
"""

from datetime import date
from decimal import Decimal
import io
import unittest
import xml.etree.ElementTree as ET

import pikepdf

from zugferd import (
    Invoice,
    LineItem,
    PaymentMeans,
    PostalAddress,
    TradeParty,
    create_zugferd_invoice,
    extract_zugferd_xml,
    generate_facturx_xml,
    package_zugferd_pdfa3u,
)


class TestZugferdPdfA3u(unittest.TestCase):

    def setUp(self):
        self.invoice = Invoice(
            invoice_number="TEST-2026-99",
            issue_date=date(2026, 8, 25),
            due_date=date(2026, 9, 24),
            currency="EUR",
            seller=TradeParty(
                name="Test Seller GmbH",
                address=PostalAddress(
                    postcode="10115",
                    line_one="Testweg 1",
                    city_name="Berlin",
                    country_id="DE",
                ),
                vat_id="DE111222333",
            ),
            buyer=TradeParty(
                name="Test Buyer Corp",
                address=PostalAddress(
                    postcode="80331",
                    line_one="Kaufmannstraße 5",
                    city_name="München",
                    country_id="DE",
                ),
                vat_id="DE444555666",
            ),
            items=[
                LineItem(
                    line_id="1",
                    name="Test Service A",
                    quantity=Decimal("10.00"),
                    unit_code="HUR",
                    net_unit_price=Decimal("100.00"),
                    vat_rate=Decimal("19.00"),
                    vat_category="S",
                ),
                LineItem(
                    line_id="2",
                    name="Test Product B",
                    quantity=Decimal("2.00"),
                    unit_code="C62",
                    net_unit_price=Decimal("250.00"),
                    vat_rate=Decimal("19.00"),
                    vat_category="S",
                ),
            ],
            payment_means=PaymentMeans(
                iban="DE89370400440532013000",
                bic="DBBADEFFXXX",
            ),
            buyer_reference="PO-TEST-123",
            conformance_level="EN 16931",
        )

    def test_xml_generation(self):
        """Test UN/CEFACT CII XML structure, calculations, and namespaces."""
        xml_bytes = generate_facturx_xml(self.invoice)
        self.assertTrue(xml_bytes.startswith(b"<?xml"))

        # Parse XML
        root = ET.fromstring(xml_bytes)
        self.assertIn("CrossIndustryInvoice", root.tag)

        # Check total calculations
        self.assertEqual(self.invoice.line_total_amount, Decimal("1500.00"))
        self.assertEqual(self.invoice.tax_total_amount, Decimal("285.00"))
        self.assertEqual(self.invoice.grand_total_amount, Decimal("1785.00"))

    def test_pdfa3u_structure_and_parameters(self):
        """Verify PDF/A-3U and OutputIntent parameters in generated PDF."""
        pdf_bytes = create_zugferd_invoice(self.invoice)
        pdf = pikepdf.open(io.BytesIO(pdf_bytes))

        # 1. OutputIntents check
        self.assertIn("/OutputIntents", pdf.Root)
        output_intents = pdf.Root.OutputIntents
        self.assertGreater(len(output_intents), 0)
        oi = output_intents[0]

        self.assertEqual(str(oi.Type), "/OutputIntent")
        self.assertEqual(str(oi.S), "/GTS_PDFA1")
        self.assertEqual(str(oi.OutputConditionIdentifier), "sRGB")
        self.assertEqual(str(oi.Info), "sRGB IEC61966-2.1")
        self.assertEqual(str(oi.RegistryName), "http://www.color.org")
        self.assertIn("/DestOutputProfile", oi)

        # 2. Associated Files (/AF) check
        self.assertIn("/AF", pdf.Root)
        af_list = pdf.Root.AF
        self.assertGreater(len(af_list), 0)
        filespec = af_list[0]

        self.assertEqual(str(filespec.Type), "/Filespec")
        self.assertEqual(str(filespec.F), "factur-x.xml")
        self.assertEqual(str(filespec.UF), "factur-x.xml")
        self.assertEqual(str(filespec.AFRelationship), "/Alternative")
        self.assertIn("/EF", filespec)

        # 3. EmbeddedFiles Name Tree check
        self.assertIn("/Names", pdf.Root)
        self.assertIn("/EmbeddedFiles", pdf.Root.Names)
        embedded_files = pdf.Root.Names.EmbeddedFiles
        self.assertIn("/Names", embedded_files)

        # 4. XMP Metadata check
        self.assertIn("/Metadata", pdf.Root)
        metadata_stream = pdf.Root.Metadata.read_bytes().decode("utf-8")

        # Check PDF/A-3U identification
        self.assertIn("<pdfaid:part>3</pdfaid:part>", metadata_stream)
        self.assertIn("<pdfaid:conformance>U</pdfaid:conformance>", metadata_stream)

        # Check Factur-X / ZUGFeRD XMP extension
        self.assertIn("urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#", metadata_stream)
        self.assertIn("<fx:DocumentType>INVOICE</fx:DocumentType>", metadata_stream)
        self.assertIn("<fx:DocumentFileName>factur-x.xml</fx:DocumentFileName>", metadata_stream)
        self.assertIn("<fx:Version>1.0</fx:Version>", metadata_stream)
        self.assertIn("<fx:ConformanceLevel>EN 16931</fx:ConformanceLevel>", metadata_stream)

    def test_preserves_existing_xml_and_other_attachments(self):
        """Verify that existing .xml and .pdf attachments in a PDF are preserved and not corrupted."""
        base_pdf = pikepdf.new()
        base_pdf.add_blank_page()

        custom_xml_content = b'<?xml version="1.0"?><deliveryNote><id>DN-12345</id></deliveryNote>'
        custom_pdf_content = b'%PDF-1.4 dummy payload timesheet'

        base_pdf.attachments["delivery_note.xml"] = pikepdf.AttachedFileSpec(
            base_pdf,
            custom_xml_content,
            filename="delivery_note.xml",
            mime_type="text/xml",
            description="Delivery Note XML",
            relationship=pikepdf.Name("/Supplement"),
        )
        base_pdf.attachments["timesheet.pdf"] = pikepdf.AttachedFileSpec(
            base_pdf,
            custom_pdf_content,
            filename="timesheet.pdf",
            mime_type="application/pdf",
            description="Timesheet PDF",
            relationship=pikepdf.Name("/Supplement"),
        )

        buf = io.BytesIO()
        base_pdf.save(buf)
        input_pdf_bytes = buf.getvalue()

        extra_xml_content = b'<?xml version="1.0"?><extraData><key>value</key></extraData>'
        invoice_xml_bytes = generate_facturx_xml(self.invoice)

        packaged_bytes = package_zugferd_pdfa3u(
            pdf_input=input_pdf_bytes,
            xml_data=invoice_xml_bytes,
            doc_filename="factur-x.xml",
            additional_attachments=[
                {
                    "filename": "extra_data.xml",
                    "data": extra_xml_content,
                    "relationship": "/Supplement",
                    "description": "Additional Custom XML",
                }
            ],
        )

        result_pdf = pikepdf.open(io.BytesIO(packaged_bytes))
        attachment_names = list(result_pdf.attachments.keys())

        self.assertIn("delivery_note.xml", attachment_names)
        self.assertIn("timesheet.pdf", attachment_names)
        self.assertIn("extra_data.xml", attachment_names)
        self.assertIn("factur-x.xml", attachment_names)

        # Verify content integrity
        self.assertEqual(result_pdf.attachments["delivery_note.xml"].get_file().read_bytes(), custom_xml_content)
        self.assertEqual(result_pdf.attachments["timesheet.pdf"].get_file().read_bytes(), custom_pdf_content)
        self.assertEqual(result_pdf.attachments["extra_data.xml"].get_file().read_bytes(), extra_xml_content)
        self.assertEqual(result_pdf.attachments["factur-x.xml"].get_file().read_bytes(), invoice_xml_bytes)

        # Verify /AF array contains all 4 attachments
        self.assertEqual(len(result_pdf.Root.AF), 4)

    def test_extract_zugferd_xml(self):
        """Verify XML extraction from a generated PDF."""
        pdf_bytes = create_zugferd_invoice(self.invoice)
        extracted = extract_zugferd_xml(pdf_bytes)
        self.assertIn(b"CrossIndustryInvoice", extracted)
        self.assertIn(b"TEST-2026-99", extracted)

    def test_validate_zugferd_pdf(self):
        """Verify the built-in validator function on valid and invalid invoices."""
        from zugferd import validate_zugferd_pdf

        # 1. Test Valid PDF
        valid_pdf_bytes = create_zugferd_invoice(self.invoice)
        report = validate_zugferd_pdf(valid_pdf_bytes)
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.errors), 0)
        self.assertEqual(report.guideline_id, "urn:cen.eu:en16931:2017")
        self.assertEqual(report.conformance_level, "PDF/A-3U")

        # 2. Test Invalid XML (BR-DEC-23 violation: 4 decimals on line total)
        invalid_xml = b'''<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017#invalid_id</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:SupplyChainTradeTransaction>
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:SpecifiedTradeSettlementLineMonetarySummation>
        <ram:LineTotalAmount>100.0000</ram:LineTotalAmount>
      </ram:SpecifiedTradeSettlementLineMonetarySummation>
    </ram:IncludedSupplyChainTradeLineItem>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>'''

        invalid_pdf_bytes = package_zugferd_pdfa3u(valid_pdf_bytes, invalid_xml)
        bad_report = validate_zugferd_pdf(invalid_pdf_bytes)
        self.assertFalse(bad_report.is_valid)
        self.assertGreater(len(bad_report.errors), 0)
        # Check that both BR-DEC-23 and invalid ram:ID were caught
        error_text = " ".join(bad_report.errors)
        self.assertIn("BR-DEC-23", error_text)
        self.assertIn("GuidelineSpecifiedDocumentContextParameter", error_text)


if __name__ == "__main__":
    unittest.main()
