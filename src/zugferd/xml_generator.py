"""
XML Generator for Factur-X / ZUGFeRD 2.x (EN 16931 / CII standard).
Produces standard compliant CrossIndustryInvoice XML.
"""

from decimal import Decimal
import xml.etree.ElementTree as ET
from zugferd.models import Invoice

# XML Namespaces
NS_RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
NS_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
NS_UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
NS_QDT = "urn:un:unece:uncefact:data:standard:QualifiedDataType:100"
NS_CCTS = "urn:un:unece:uncefact:documentation:standard:CoreComponentsTechnicalSpecification:2"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def format_amount(val: Decimal) -> str:
    """Format Decimal amount to two decimal places string."""
    return f"{val:.2f}"


def format_quantity(val: Decimal) -> str:
    """Format Decimal quantity with up to four decimal places, trimming trailing zeros if clean."""
    formatted = f"{val:.4f}".rstrip("0").rstrip(".")
    if "." not in formatted:
        formatted += ".00"
    elif len(formatted.split(".")[1]) == 1:
        formatted += "0"
    return formatted


def generate_facturx_xml(invoice: Invoice) -> bytes:
    """
    Generate valid UN/CEFACT CII XML bytes conforming to EN 16931 (Factur-X / ZUGFeRD 2.x).
    """
    # Register namespaces
    ET.register_namespace("rsm", NS_RSM)
    ET.register_namespace("ram", NS_RAM)
    ET.register_namespace("udt", NS_UDT)
    ET.register_namespace("qdt", NS_QDT)
    ET.register_namespace("ccts", NS_CCTS)
    ET.register_namespace("xsi", NS_XSI)

    root = ET.Element(f"{{{NS_RSM}}}CrossIndustryInvoice")

    # 1. ExchangedDocumentContext
    ctx = ET.SubElement(root, f"{{{NS_RSM}}}ExchangedDocumentContext")
    guideline = ET.SubElement(ctx, f"{{{NS_RAM}}}GuidelineSpecifiedDocumentContextParameter")
    guideline_id = ET.SubElement(guideline, f"{{{NS_RAM}}}ID")

    # Profile identifier (BT-24 Specification Identifier)
    if invoice.conformance_level == "BASIC":
        guideline_id.text = "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic"
    elif invoice.conformance_level == "BASIC_WL":
        guideline_id.text = "urn:factur-x.eu:1p0:basicwl"
    elif invoice.conformance_level == "MINIMUM":
        guideline_id.text = "urn:factur-x.eu:1p0:minimum"
    elif invoice.conformance_level == "EXTENDED":
        guideline_id.text = "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended"
    elif invoice.conformance_level == "XRECHNUNG":
        guideline_id.text = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
    else:  # Default to EN 16931 (COMFORT profile)
        guideline_id.text = "urn:cen.eu:en16931:2017"

    # 2. ExchangedDocument
    doc = ET.SubElement(root, f"{{{NS_RSM}}}ExchangedDocument")
    doc_id = ET.SubElement(doc, f"{{{NS_RAM}}}ID")
    doc_id.text = invoice.invoice_number

    type_code = ET.SubElement(doc, f"{{{NS_RAM}}}TypeCode")
    type_code.text = invoice.type_code

    issue_date = ET.SubElement(doc, f"{{{NS_RAM}}}IssueDateTime")
    issue_date_str = ET.SubElement(issue_date, f"{{{NS_UDT}}}DateTimeString", format="102")
    issue_date_str.text = invoice.issue_date.strftime("%Y%m%d")

    for note_text in invoice.notes:
        note = ET.SubElement(doc, f"{{{NS_RAM}}}IncludedNote")
        content = ET.SubElement(note, f"{{{NS_RAM}}}Content")
        content.text = note_text

    # 3. SupplyChainTradeTransaction
    trans = ET.SubElement(root, f"{{{NS_RSM}}}SupplyChainTradeTransaction")

    # 3.1 Line Items
    for item in invoice.items:
        line = ET.SubElement(trans, f"{{{NS_RAM}}}IncludedSupplyChainTradeLineItem")

        # Line Document ID
        line_doc = ET.SubElement(line, f"{{{NS_RAM}}}AssociatedDocumentLineDocument")
        line_doc_id = ET.SubElement(line_doc, f"{{{NS_RAM}}}LineID")
        line_doc_id.text = str(item.line_id)

        # Product
        prod = ET.SubElement(line, f"{{{NS_RAM}}}SpecifiedTradeProduct")
        prod_name = ET.SubElement(prod, f"{{{NS_RAM}}}Name")
        prod_name.text = item.name
        if item.description:
            prod_desc = ET.SubElement(prod, f"{{{NS_RAM}}}Description")
            prod_desc.text = item.description

        # Agreement (Price)
        agree = ET.SubElement(line, f"{{{NS_RAM}}}SpecifiedLineTradeAgreement")
        net_price = ET.SubElement(agree, f"{{{NS_RAM}}}NetPriceProductTradePrice")
        charge_amt = ET.SubElement(net_price, f"{{{NS_RAM}}}ChargeAmount")
        charge_amt.text = format_amount(item.net_unit_price)

        # Delivery (Quantity)
        delivery = ET.SubElement(line, f"{{{NS_RAM}}}SpecifiedLineTradeDelivery")
        billed_qty = ET.SubElement(delivery, f"{{{NS_RAM}}}BilledQuantity", unitCode=item.unit_code)
        billed_qty.text = format_quantity(item.quantity)

        # Settlement (Tax & Line Total)
        settlement = ET.SubElement(line, f"{{{NS_RAM}}}SpecifiedLineTradeSettlement")
        trade_tax = ET.SubElement(settlement, f"{{{NS_RAM}}}ApplicableTradeTax")
        tax_type = ET.SubElement(trade_tax, f"{{{NS_RAM}}}TypeCode")
        tax_type.text = "VAT"
        tax_cat = ET.SubElement(trade_tax, f"{{{NS_RAM}}}CategoryCode")
        tax_cat.text = item.vat_category
        tax_rate = ET.SubElement(trade_tax, f"{{{NS_RAM}}}RateApplicablePercent")
        tax_rate.text = format_amount(item.vat_rate)

        summation = ET.SubElement(settlement, f"{{{NS_RAM}}}SpecifiedTradeSettlementLineMonetarySummation")
        line_tot = ET.SubElement(summation, f"{{{NS_RAM}}}LineTotalAmount")
        line_tot.text = format_amount(item.line_total)

    # 3.2 Header Agreement (Seller & Buyer)
    header_agree = ET.SubElement(trans, f"{{{NS_RAM}}}ApplicableHeaderTradeAgreement")

    if invoice.buyer_reference:
        buyer_ref = ET.SubElement(header_agree, f"{{{NS_RAM}}}BuyerReference")
        buyer_ref.text = invoice.buyer_reference

    # Seller Party
    seller_party = ET.SubElement(header_agree, f"{{{NS_RAM}}}SellerTradeParty")
    seller_name = ET.SubElement(seller_party, f"{{{NS_RAM}}}Name")
    seller_name.text = invoice.seller.name

    if invoice.seller.contact_name or invoice.seller.contact_email or invoice.seller.contact_phone:
        contact = ET.SubElement(seller_party, f"{{{NS_RAM}}}DefinedTradeContact")
        if invoice.seller.contact_name:
            c_name = ET.SubElement(contact, f"{{{NS_RAM}}}PersonName")
            c_name.text = invoice.seller.contact_name
        if invoice.seller.contact_phone:
            c_tel = ET.SubElement(contact, f"{{{NS_RAM}}}TelephoneUniversalCommunication")
            c_num = ET.SubElement(c_tel, f"{{{NS_RAM}}}CompleteNumber")
            c_num.text = invoice.seller.contact_phone
        if invoice.seller.contact_email:
            c_mail = ET.SubElement(contact, f"{{{NS_RAM}}}EmailURIUniversalCommunication")
            c_uri = ET.SubElement(c_mail, f"{{{NS_RAM}}}URIID")
            c_uri.text = invoice.seller.contact_email

    seller_addr = ET.SubElement(seller_party, f"{{{NS_RAM}}}PostalTradeAddress")
    s_postcode = ET.SubElement(seller_addr, f"{{{NS_RAM}}}PostcodeCode")
    s_postcode.text = invoice.seller.address.postcode
    s_line1 = ET.SubElement(seller_addr, f"{{{NS_RAM}}}LineOne")
    s_line1.text = invoice.seller.address.line_one
    if invoice.seller.address.line_two:
        s_line2 = ET.SubElement(seller_addr, f"{{{NS_RAM}}}LineTwo")
        s_line2.text = invoice.seller.address.line_two
    s_city = ET.SubElement(seller_addr, f"{{{NS_RAM}}}CityName")
    s_city.text = invoice.seller.address.city_name
    s_country = ET.SubElement(seller_addr, f"{{{NS_RAM}}}CountryID")
    s_country.text = invoice.seller.address.country_id

    if invoice.seller.vat_id:
        s_tax_reg = ET.SubElement(seller_party, f"{{{NS_RAM}}}SpecifiedTaxRegistration")
        s_tax_id = ET.SubElement(s_tax_reg, f"{{{NS_RAM}}}ID", schemeID="VA")
        s_tax_id.text = invoice.seller.vat_id
    elif invoice.seller.tax_number:
        s_tax_reg = ET.SubElement(seller_party, f"{{{NS_RAM}}}SpecifiedTaxRegistration")
        s_tax_id = ET.SubElement(s_tax_reg, f"{{{NS_RAM}}}ID", schemeID="FC")
        s_tax_id.text = invoice.seller.tax_number

    # Buyer Party
    buyer_party = ET.SubElement(header_agree, f"{{{NS_RAM}}}BuyerTradeParty")
    buyer_name = ET.SubElement(buyer_party, f"{{{NS_RAM}}}Name")
    buyer_name.text = invoice.buyer.name

    buyer_addr = ET.SubElement(buyer_party, f"{{{NS_RAM}}}PostalTradeAddress")
    b_postcode = ET.SubElement(buyer_addr, f"{{{NS_RAM}}}PostcodeCode")
    b_postcode.text = invoice.buyer.address.postcode
    b_line1 = ET.SubElement(buyer_addr, f"{{{NS_RAM}}}LineOne")
    b_line1.text = invoice.buyer.address.line_one
    if invoice.buyer.address.line_two:
        b_line2 = ET.SubElement(buyer_addr, f"{{{NS_RAM}}}LineTwo")
        b_line2.text = invoice.buyer.address.line_two
    b_city = ET.SubElement(buyer_addr, f"{{{NS_RAM}}}CityName")
    b_city.text = invoice.buyer.address.city_name
    b_country = ET.SubElement(buyer_addr, f"{{{NS_RAM}}}CountryID")
    b_country.text = invoice.buyer.address.country_id

    if invoice.buyer.vat_id:
        b_tax_reg = ET.SubElement(buyer_party, f"{{{NS_RAM}}}SpecifiedTaxRegistration")
        b_tax_id = ET.SubElement(b_tax_reg, f"{{{NS_RAM}}}ID", schemeID="VA")
        b_tax_id.text = invoice.buyer.vat_id

    # 3.3 Header Delivery
    header_delivery = ET.SubElement(trans, f"{{{NS_RAM}}}ApplicableHeaderTradeDelivery")
    event = ET.SubElement(header_delivery, f"{{{NS_RAM}}}ActualDeliverySupplyChainEvent")
    occ_date = ET.SubElement(event, f"{{{NS_RAM}}}OccurrenceDateTime")
    occ_date_str = ET.SubElement(occ_date, f"{{{NS_UDT}}}DateTimeString", format="102")
    occ_date_str.text = invoice.issue_date.strftime("%Y%m%d")

    # 3.4 Header Settlement
    header_settlement = ET.SubElement(trans, f"{{{NS_RAM}}}ApplicableHeaderTradeSettlement")
    curr_code = ET.SubElement(header_settlement, f"{{{NS_RAM}}}InvoiceCurrencyCode")
    curr_code.text = invoice.currency

    # Payment Means
    if invoice.payment_means:
        pay_means = ET.SubElement(header_settlement, f"{{{NS_RAM}}}SpecifiedTradeSettlementPaymentMeans")
        p_type = ET.SubElement(pay_means, f"{{{NS_RAM}}}TypeCode")
        p_type.text = invoice.payment_means.type_code

        if invoice.payment_means.iban:
            payee_acc = ET.SubElement(pay_means, f"{{{NS_RAM}}}PayeePartyCreditorFinancialAccount")
            iban_elem = ET.SubElement(payee_acc, f"{{{NS_RAM}}}IBANID")
            iban_elem.text = invoice.payment_means.iban
            if invoice.payment_means.account_holder:
                acc_name = ET.SubElement(payee_acc, f"{{{NS_RAM}}}AccountName")
                acc_name.text = invoice.payment_means.account_holder

        if invoice.payment_means.bic:
            payee_inst = ET.SubElement(pay_means, f"{{{NS_RAM}}}PayeeSpecifiedCreditorFinancialInstitution")
            bic_elem = ET.SubElement(payee_inst, f"{{{NS_RAM}}}BICID")
            bic_elem.text = invoice.payment_means.bic

    # Applicable Trade Taxes (Summary per rate)
    for tax in invoice.tax_summaries:
        tax_elem = ET.SubElement(header_settlement, f"{{{NS_RAM}}}ApplicableTradeTax")
        calc_amt = ET.SubElement(tax_elem, f"{{{NS_RAM}}}CalculatedAmount")
        calc_amt.text = format_amount(tax.calculated_amount)
        t_code = ET.SubElement(tax_elem, f"{{{NS_RAM}}}TypeCode")
        t_code.text = "VAT"
        basis_amt = ET.SubElement(tax_elem, f"{{{NS_RAM}}}BasisAmount")
        basis_amt.text = format_amount(tax.basis_amount)
        cat_code = ET.SubElement(tax_elem, f"{{{NS_RAM}}}CategoryCode")
        cat_code.text = tax.category_code
        rate_elem = ET.SubElement(tax_elem, f"{{{NS_RAM}}}RateApplicablePercent")
        rate_elem.text = format_amount(tax.rate_percent)

    # Payment Terms
    payment_terms = ET.SubElement(header_settlement, f"{{{NS_RAM}}}SpecifiedTradePaymentTerms")
    terms_desc = ET.SubElement(payment_terms, f"{{{NS_RAM}}}Description")
    terms_desc.text = f"Payment due on {invoice.due_date.strftime('%Y-%m-%d')}"
    due_dt = ET.SubElement(payment_terms, f"{{{NS_RAM}}}DueDateDateTime")
    due_dt_str = ET.SubElement(due_dt, f"{{{NS_UDT}}}DateTimeString", format="102")
    due_dt_str.text = invoice.due_date.strftime("%Y%m%d")

    # Monetary Summation
    mon_sum = ET.SubElement(header_settlement, f"{{{NS_RAM}}}SpecifiedTradeSettlementHeaderMonetarySummation")
    line_tot_elem = ET.SubElement(mon_sum, f"{{{NS_RAM}}}LineTotalAmount")
    line_tot_elem.text = format_amount(invoice.line_total_amount)

    tax_basis_elem = ET.SubElement(mon_sum, f"{{{NS_RAM}}}TaxBasisTotalAmount")
    tax_basis_elem.text = format_amount(invoice.line_total_amount)

    tax_tot_elem = ET.SubElement(mon_sum, f"{{{NS_RAM}}}TaxTotalAmount", currencyID=invoice.currency)
    tax_tot_elem.text = format_amount(invoice.tax_total_amount)

    grand_tot_elem = ET.SubElement(mon_sum, f"{{{NS_RAM}}}GrandTotalAmount")
    grand_tot_elem.text = format_amount(invoice.grand_total_amount)

    due_amt_elem = ET.SubElement(mon_sum, f"{{{NS_RAM}}}DuePayableAmount")
    due_amt_elem.text = format_amount(invoice.due_payable_amount)

    # Convert to XML string with XML declaration
    xml_declaration = b'<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content = ET.tostring(root, encoding="utf-8")
    return xml_declaration + xml_content
