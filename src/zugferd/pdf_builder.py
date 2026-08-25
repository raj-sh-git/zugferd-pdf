"""
Visual PDF Generator for Invoices using ReportLab.
Renders clean invoice layouts with embedded TrueType fonts for PDF/A-3U Unicode compliance.
"""

from decimal import Decimal
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from zugferd.models import Invoice

# Global font initialization flag
_FONT_INITIALIZED = False
_DEFAULT_FONT = "Helvetica"
_DEFAULT_FONT_BOLD = "Helvetica-Bold"


def setup_fonts() -> tuple:
    """
    Registers a TrueType font if available for full ToUnicode embedding (PDF/A-3U).
    Falls back gracefully to standard fonts.
    """
    global _FONT_INITIALIZED, _DEFAULT_FONT, _DEFAULT_FONT_BOLD
    if _FONT_INITIALIZED:
        return _DEFAULT_FONT, _DEFAULT_FONT_BOLD

    candidate_fonts = [
        # macOS
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "CustomArial", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "CustomArial-Bold"),
        ("/Library/Fonts/Arial.ttf", "CustomArial", "/Library/Fonts/Arial Bold.ttf", "CustomArial-Bold"),
        # Linux / Debian / Ubuntu
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "LibSans", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "LibSans-Bold"),
        ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "FreeSans", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", "FreeSans-Bold"),
        # Windows
        ("C:/Windows/Fonts/arial.ttf", "CustomArial", "C:/Windows/Fonts/arialbd.ttf", "CustomArial-Bold"),
    ]

    for reg_path, reg_name, bold_path, bold_name in candidate_fonts:
        if Path(reg_path).exists():
            try:
                pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                if Path(bold_path).exists():
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                    _DEFAULT_FONT_BOLD = bold_name
                else:
                    _DEFAULT_FONT_BOLD = reg_name
                _DEFAULT_FONT = reg_name
                _FONT_INITIALIZED = True
                return _DEFAULT_FONT, _DEFAULT_FONT_BOLD
            except Exception:
                pass

    _FONT_INITIALIZED = True
    return _DEFAULT_FONT, _DEFAULT_FONT_BOLD


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """
    Generates a visual PDF invoice from an Invoice model.
    Returns the generated PDF as bytes.
    """
    font_normal, font_bold = setup_fonts()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {invoice.invoice_number}",
        author=invoice.seller.name,
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A365D"),
    )
    style_subtitle = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName=font_normal,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
    )
    style_header = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
    )
    style_body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName=font_normal,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2D3748"),
    )
    style_body_bold = ParagraphStyle(
        "BodyBold",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2D3748"),
    )
    style_cell_r = ParagraphStyle(
        "CellRight",
        parent=style_body,
        alignment=2,  # Right aligned
    )
    style_cell_r_bold = ParagraphStyle(
        "CellRightBold",
        parent=style_body_bold,
        alignment=2,
    )

    story = []

    # Header section: Seller info & Invoice title
    header_data = [
        [
            Paragraph(f"<b>{invoice.seller.name}</b>", style_header),
            Paragraph("<b>INVOICE</b>", style_title),
        ],
        [
            Paragraph(
                f"{invoice.seller.address.line_one}<br/>"
                f"{invoice.seller.address.postcode} {invoice.seller.address.city_name}, {invoice.seller.address.country_id}<br/>"
                f"{'VAT ID: ' + invoice.seller.vat_id if invoice.seller.vat_id else ''}",
                style_body,
            ),
            Paragraph(
                f"<b>Invoice #:</b> {invoice.invoice_number}<br/>"
                f"<b>Date:</b> {invoice.issue_date.strftime('%d.%m.%Y')}<br/>"
                f"<b>Due Date:</b> {invoice.due_date.strftime('%d.%m.%Y')}<br/>"
                f"{'<b>Buyer Ref:</b> ' + invoice.buyer_reference if invoice.buyer_reference else ''}",
                style_body,
            ),
        ],
    ]
    t_header = Table(header_data, colWidths=[90 * mm, 84 * mm])
    t_header.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(t_header)
    story.append(Spacer(1, 10 * mm))

    # Bill To Section
    story.append(Paragraph("<b>BILL TO:</b>", style_header))
    story.append(Spacer(1, 1 * mm))
    buyer_lines = [
        f"<b>{invoice.buyer.name}</b>",
        invoice.buyer.address.line_one,
    ]
    if invoice.buyer.address.line_two:
        buyer_lines.append(invoice.buyer.address.line_two)
    buyer_lines.append(f"{invoice.buyer.address.postcode} {invoice.buyer.address.city_name}, {invoice.buyer.address.country_id}")
    if invoice.buyer.vat_id:
        buyer_lines.append(f"VAT ID: {invoice.buyer.vat_id}")

    story.append(Paragraph("<br/>".join(buyer_lines), style_body))
    story.append(Spacer(1, 8 * mm))

    # Line Items Table
    table_headers = [
        Paragraph("<b>#</b>", style_body_bold),
        Paragraph("<b>Description</b>", style_body_bold),
        Paragraph("<b>Qty</b>", style_cell_r_bold),
        Paragraph("<b>Unit Price</b>", style_cell_r_bold),
        Paragraph("<b>VAT</b>", style_cell_r_bold),
        Paragraph("<b>Total</b>", style_cell_r_bold),
    ]
    table_rows = [table_headers]

    for item in invoice.items:
        desc = f"<b>{item.name}</b>"
        if item.description:
            desc += f"<br/><font color='#718096'>{item.description}</font>"
        table_rows.append([
            Paragraph(str(item.line_id), style_body),
            Paragraph(desc, style_body),
            Paragraph(f"{item.quantity:.2f} {item.unit_code}", style_cell_r),
            Paragraph(f"{item.net_unit_price:.2f} {invoice.currency}", style_cell_r),
            Paragraph(f"{item.vat_rate:.0f}%", style_cell_r),
            Paragraph(f"{item.line_total:.2f} {invoice.currency}", style_cell_r),
        ])

    t_items = Table(
        table_rows,
        colWidths=[10 * mm, 74 * mm, 22 * mm, 24 * mm, 16 * mm, 28 * mm],
    )
    t_items.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
            ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor("#CBD5E0")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.append(t_items)
    story.append(Spacer(1, 6 * mm))

    # Summary & Totals Table
    totals_rows = [
        [
            Paragraph("<b>Net Total:</b>", style_body),
            Paragraph(f"{invoice.line_total_amount:.2f} {invoice.currency}", style_cell_r),
        ]
    ]
    for tax in invoice.tax_summaries:
        totals_rows.append([
            Paragraph(f"VAT ({tax.rate_percent:.0f}% on {tax.basis_amount:.2f}):", style_body),
            Paragraph(f"{tax.calculated_amount:.2f} {invoice.currency}", style_cell_r),
        ])
    totals_rows.append([
        Paragraph("<b>Total Due:</b>", style_header),
        Paragraph(f"<b>{invoice.grand_total_amount:.2f} {invoice.currency}</b>", style_cell_r_bold),
    ])

    t_totals = Table(totals_rows, colWidths=[50 * mm, 35 * mm])
    t_totals.setStyle(
        TableStyle([
            ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.HexColor("#1A365D")),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#CBD5E0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )

    summary_wrapper = Table(
        [[Paragraph("", style_body), t_totals]],
        colWidths=[89 * mm, 85 * mm],
    )
    summary_wrapper.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(summary_wrapper)
    story.append(Spacer(1, 10 * mm))

    # Payment & Notes Section
    if invoice.payment_means or invoice.notes:
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=4 * mm))
        pay_info = []
        if invoice.payment_means:
            pay_info.append(f"<b>Payment Terms:</b> Due within 30 days ({invoice.due_date.strftime('%d.%m.%Y')})")
            if invoice.payment_means.iban:
                pay_info.append(f"<b>Bank Account (IBAN):</b> {invoice.payment_means.iban}")
            if invoice.payment_means.bic:
                pay_info.append(f"<b>BIC / SWIFT:</b> {invoice.payment_means.bic}")

        for note in invoice.notes:
            pay_info.append(f"<i>Note: {note}</i>")

        story.append(Paragraph("<br/>".join(pay_info), style_subtitle))

    doc.build(story)
    return buffer.getvalue()
