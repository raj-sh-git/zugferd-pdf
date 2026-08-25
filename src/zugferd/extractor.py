"""
ZUGFeRD XML Extractor Utility.
Extracts embedded factur-x.xml or zugferd-invoice.xml from any PDF/A-3 invoice.
"""

import io
from pathlib import Path
from typing import Optional, Union

import pikepdf


def extract_zugferd_xml(pdf_input: Union[bytes, str, Path], target_file: Optional[Union[str, Path]] = None) -> bytes:
    """
    Extracts the embedded ZUGFeRD / Factur-X XML invoice from a PDF document.

    Parameters:
        pdf_input: Path to the PDF file or PDF bytes.
        target_file: Optional path to write the extracted XML file.

    Returns:
        bytes: The XML invoice content.

    Raises:
        FileNotFoundError: If no ZUGFeRD/Factur-X XML attachment is found.
    """
    if isinstance(pdf_input, (str, Path)):
        pdf = pikepdf.open(pdf_input)
    else:
        pdf = pikepdf.open(io.BytesIO(pdf_input))

    # Look for standard ZUGFeRD XML attachment names
    target_names = ["factur-x.xml", "zugferd-invoice.xml", "ZUGFeRD-invoice.xml", "xrechnung.xml"]

    for name in target_names:
        if name in pdf.attachments:
            xml_bytes = pdf.attachments[name].get_file().read_bytes()
            if target_file:
                Path(target_file).write_bytes(xml_bytes)
            return xml_bytes

    # Fallback: check any attachment ending with .xml
    for name, attached_spec in pdf.attachments.items():
        if name.lower().endswith(".xml"):
            xml_bytes = attached_spec.get_file().read_bytes()
            if target_file:
                Path(target_file).write_bytes(xml_bytes)
            return xml_bytes

    raise FileNotFoundError("No ZUGFeRD / Factur-X XML invoice attachment found in the provided PDF.")
