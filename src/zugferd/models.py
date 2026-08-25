"""
Data models for ZUGFeRD / Factur-X invoices.
Defines structured classes for invoice headers, seller/buyer parties,
line items, taxes, payment terms, and totals.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional


@dataclass
class PostalAddress:
    postcode: str
    line_one: str
    city_name: str
    country_id: str  # ISO 3166-1 alpha-2 (e.g. "DE", "FR", "AT")
    line_two: Optional[str] = None


@dataclass
class TradeParty:
    name: str
    address: PostalAddress
    vat_id: Optional[str] = None  # e.g. "DE123456789"
    tax_number: Optional[str] = None  # Local tax number (FC)
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


@dataclass
class LineItem:
    line_id: str
    name: str
    quantity: Decimal
    unit_code: str  # UN/ECE Rec 20 unit code (e.g. "C62" for piece, "HUR" for hour, "KGM" for kg)
    net_unit_price: Decimal
    vat_rate: Decimal  # e.g. Decimal("19.00")
    vat_category: str = "S"  # S = Standard, Z = Zero rated, E = Exempt, AE = Reverse charge
    description: Optional[str] = None

    @property
    def line_total(self) -> Decimal:
        """Net total for this line item (quantity * net unit price)."""
        return (self.quantity * self.net_unit_price).quantize(Decimal("0.01"))


@dataclass
class TaxSummary:
    category_code: str  # "S", "Z", "E", "AE"
    rate_percent: Decimal
    basis_amount: Decimal
    calculated_amount: Decimal


@dataclass
class PaymentMeans:
    type_code: str = "58"  # 58 = SEPA credit transfer, 30 = Credit transfer, 48 = Direct debit
    iban: Optional[str] = None
    bic: Optional[str] = None
    account_holder: Optional[str] = None
    payment_reference: Optional[str] = None


@dataclass
class Invoice:
    invoice_number: str
    issue_date: date
    due_date: date
    currency: str  # ISO 4217 (e.g. "EUR")
    seller: TradeParty
    buyer: TradeParty
    items: List[LineItem] = field(default_factory=list)
    payment_means: Optional[PaymentMeans] = None
    buyer_reference: Optional[str] = None  # Leitweg-ID or Buyer Reference / PO number
    notes: List[str] = field(default_factory=list)
    type_code: str = "380"  # 380 = Commercial Invoice, 381 = Credit Note
    conformance_level: str = "EN 16931"  # "EN 16931", "BASIC", "EXTENDED", "COMFORT"

    @property
    def line_total_amount(self) -> Decimal:
        """Sum of all line item net amounts."""
        return sum((item.line_total for item in self.items), Decimal("0.00")).quantize(Decimal("0.01"))

    @property
    def tax_summaries(self) -> List[TaxSummary]:
        """Group and calculate taxes by (category, rate)."""
        groups = {}
        for item in self.items:
            key = (item.vat_category, item.vat_rate)
            groups[key] = groups.get(key, Decimal("0.00")) + item.line_total

        summaries = []
        for (cat, rate), basis in sorted(groups.items()):
            calc_tax = (basis * rate / Decimal("100.00")).quantize(Decimal("0.01"))
            summaries.append(
                TaxSummary(
                    category_code=cat,
                    rate_percent=rate,
                    basis_amount=basis,
                    calculated_amount=calc_tax,
                )
            )
        return summaries

    @property
    def tax_total_amount(self) -> Decimal:
        """Total VAT amount."""
        return sum((s.calculated_amount for s in self.tax_summaries), Decimal("0.00")).quantize(Decimal("0.01"))

    @property
    def grand_total_amount(self) -> Decimal:
        """Grand total amount including VAT."""
        return (self.line_total_amount + self.tax_total_amount).quantize(Decimal("0.01"))

    @property
    def due_payable_amount(self) -> Decimal:
        """Amount due for payment."""
        return self.grand_total_amount
