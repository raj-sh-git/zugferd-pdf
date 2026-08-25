"""
PDF/A-3U Packager for ZUGFeRD / Factur-X Invoices.
Converts standard PDFs or ReportLab PDFs into ISO 19005-3 compliant PDF/A-3U documents
with embedded factur-x.xml, sRGB IEC61966-2.1 OutputIntent, valid XMP metadata,
and robust preservation of any existing or additional .xml / .pdf attachments.
"""

from datetime import datetime, timezone
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pikepdf
from zugferd.icc_profile import get_srgb_icc_bytes


def generate_xmp_metadata(
    title: str = "Invoice",
    creator: str = "Billing System",
    doc_filename: str = "factur-x.xml",
    conformance_level: str = "EN 16931",
    version: str = "1.0",
    creation_date: Optional[datetime] = None,
) -> bytes:
    """
    Generates standard-compliant XMP RDF metadata for PDF/A-3U and Factur-X / ZUGFeRD.
    Includes PDF/A Identification (PDF/A-3U) and PDF/A Extension Schemas for Factur-X.
    """
    if creation_date is None:
        creation_date = datetime.now(timezone.utc)

    # ISO 8601 string: YYYY-MM-DDThh:mm:ss+00:00
    iso_date = creation_date.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    xmp_rdf = f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    
    <!-- PDF/A Identification: PDF/A-3U (ISO 19005-3) -->
    <rdf:Description rdf:about=""
        xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">
      <pdfaid:part>3</pdfaid:part>
      <pdfaid:conformance>U</pdfaid:conformance>
    </rdf:Description>

    <!-- Dublin Core Metadata -->
    <rdf:Description rdf:about=""
        xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:format>application/pdf</dc:format>
      <dc:title>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">{title}</rdf:li>
        </rdf:Alt>
      </dc:title>
      <dc:creator>
        <rdf:Seq>
          <rdf:li>{creator}</rdf:li>
        </rdf:Seq>
      </dc:creator>
      <dc:description>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">ZUGFeRD / Factur-X Electronic Invoice</rdf:li>
        </rdf:Alt>
      </dc:description>
      <dc:date>
        <rdf:Seq>
          <rdf:li>{iso_date}</rdf:li>
        </rdf:Seq>
      </dc:date>
    </rdf:Description>

    <!-- XMP Basic Metadata -->
    <rdf:Description rdf:about=""
        xmlns:xmp="http://ns.adobe.com/xap/1.0/">
      <xmp:CreatorTool>Python ZUGFeRD PDF/A-3U Packager</xmp:CreatorTool>
      <xmp:CreateDate>{iso_date}</xmp:CreateDate>
      <xmp:ModifyDate>{iso_date}</xmp:ModifyDate>
      <xmp:MetadataDate>{iso_date}</xmp:MetadataDate>
    </rdf:Description>

    <!-- PDF/A Extension Schema Declaration for Factur-X / ZUGFeRD -->
    <rdf:Description rdf:about=""
        xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"
        xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#"
        xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#">
      <pdfaExtension:schemas>
        <rdf:Bag>
          <rdf:li rdf:parseType="Resource">
            <pdfaSchema:schema>Factur-X PDFA Extension Schema</pdfaSchema:schema>
            <pdfaSchema:namespaceURI>urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#</pdfaSchema:namespaceURI>
            <pdfaSchema:prefix>fx</pdfaSchema:prefix>
            <pdfaSchema:property>
              <rdf:Seq>
                <rdf:li rdf:parseType="Resource">
                  <pdfaProperty:name>DocumentFileName</pdfaProperty:name>
                  <pdfaProperty:valueType>Text</pdfaProperty:valueType>
                  <pdfaProperty:category>external</pdfaProperty:category>
                  <pdfaProperty:description>The name of the embedded invoice file</pdfaProperty:description>
                </rdf:li>
                <rdf:li rdf:parseType="Resource">
                  <pdfaProperty:name>DocumentType</pdfaProperty:name>
                  <pdfaProperty:valueType>Text</pdfaProperty:valueType>
                  <pdfaProperty:category>external</pdfaProperty:category>
                  <pdfaProperty:description>The type of the hybrid document in (INVOICE, ORDER)</pdfaProperty:description>
                </rdf:li>
                <rdf:li rdf:parseType="Resource">
                  <pdfaProperty:name>Version</pdfaProperty:name>
                  <pdfaProperty:valueType>Text</pdfaProperty:valueType>
                  <pdfaProperty:category>external</pdfaProperty:category>
                  <pdfaProperty:description>The actual version of the standard</pdfaProperty:description>
                </rdf:li>
                <rdf:li rdf:parseType="Resource">
                  <pdfaProperty:name>ConformanceLevel</pdfaProperty:name>
                  <pdfaProperty:valueType>Text</pdfaProperty:valueType>
                  <pdfaProperty:category>external</pdfaProperty:category>
                  <pdfaProperty:description>The conformance level of the embedded invoice</pdfaProperty:description>
                </rdf:li>
              </rdf:Seq>
            </pdfaSchema:property>
          </rdf:li>
        </rdf:Bag>
      </pdfaExtension:schemas>
    </rdf:Description>

    <!-- Factur-X / ZUGFeRD Properties -->
    <rdf:Description rdf:about=""
        xmlns:fx="urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#">
      <fx:DocumentType>INVOICE</fx:DocumentType>
      <fx:DocumentFileName>{doc_filename}</fx:DocumentFileName>
      <fx:Version>{version}</fx:Version>
      <fx:ConformanceLevel>{conformance_level}</fx:ConformanceLevel>
    </rdf:Description>

  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    return xmp_rdf.encode("utf-8")


def package_zugferd_pdfa3u(
    pdf_input: Union[bytes, str, Path],
    xml_data: Union[bytes, str, Path],
    output_target: Optional[Union[str, Path, io.BytesIO]] = None,
    doc_filename: str = "factur-x.xml",
    conformance_level: str = "EN 16931",
    version: str = "1.0",
    title: str = "Invoice",
    creator: str = "Billing System",
    additional_attachments: Optional[List[Dict[str, Any]]] = None,
) -> bytes:
    """
    Packages a visual PDF and ZUGFeRD XML into a valid PDF/A-3U document.
    Preserves all existing attachments (XML, PDF, CSV, etc.) and correctly
    manages the PDF/A-3 /AF (Associated Files) relationship tree.

    Parameters:
        pdf_input: Input PDF as bytes, file path, or Path object.
        xml_data: Primary invoice XML as bytes, string, or file path.
        output_target: Optional file path or BytesIO to write the result.
        doc_filename: Attachment name (default 'factur-x.xml').
        conformance_level: Factur-X profile (default 'EN 16931').
        version: Factur-X version (default '1.0').
        title: Document title for metadata.
        creator: Creator / Author name for metadata.
        additional_attachments: Optional list of additional files to attach.

    Returns:
        bytes: Compliant PDF/A-3U document bytes.
    """
    # Load input PDF
    if isinstance(pdf_input, (str, Path)):
        pdf = pikepdf.open(pdf_input)
    else:
        pdf = pikepdf.open(io.BytesIO(pdf_input))

    # Load XML bytes
    if isinstance(xml_data, (str, Path)) and (
        isinstance(xml_data, Path)
        or (isinstance(xml_data, str) and (Path(xml_data).exists() or xml_data.endswith(".xml")))
    ):
        try:
            xml_bytes = Path(xml_data).read_bytes()
        except Exception:
            xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data
    elif isinstance(xml_data, str):
        xml_bytes = xml_data.encode("utf-8")
    else:
        xml_bytes = xml_data

    now = datetime.now(timezone.utc)

    # 1. Add any additional attachments requested by the caller
    if additional_attachments:
        for att in additional_attachments:
            att_name = att.get("filename", "attachment.dat")
            att_data = att.get("data")
            if isinstance(att_data, (str, Path)) and Path(att_data).exists():
                raw_bytes = Path(att_data).read_bytes()
            elif isinstance(att_data, str):
                raw_bytes = att_data.encode("utf-8")
            else:
                raw_bytes = att_data

            att_mime = att.get("mime_type")
            if not att_mime:
                if att_name.endswith(".xml"):
                    att_mime = "text/xml"
                elif att_name.endswith(".pdf"):
                    att_mime = "application/pdf"
                else:
                    att_mime = "application/octet-stream"

            rel_str = att.get("relationship", "/Supplement")
            if not rel_str.startswith("/"):
                rel_str = "/" + rel_str
            att_rel = pikepdf.Name(rel_str)

            spec = pikepdf.AttachedFileSpec(
                pdf,
                raw_bytes,
                filename=att_name,
                mime_type=att_mime,
                description=att.get("description", att_name),
                relationship=att_rel,
            )
            pdf.attachments[att_name] = spec

    # 2. Attach / Update the primary ZUGFeRD / Factur-X invoice XML
    primary_spec = pikepdf.AttachedFileSpec(
        pdf,
        xml_bytes,
        filename=doc_filename,
        mime_type="text/xml",
        description="Factur-X / ZUGFeRD XML Invoice",
        relationship=pikepdf.Name("/Alternative"),
    )
    pdf.attachments[doc_filename] = primary_spec

    # 3. Synchronize /AF (Associated Files) array for strict PDF/A-3 compliance
    af_array = pikepdf.Array()
    for filename, attached_spec in pdf.attachments.items():
        spec_obj = attached_spec.obj
        if "/AFRelationship" not in spec_obj:
            if filename == doc_filename:
                spec_obj["/AFRelationship"] = pikepdf.Name("/Alternative")
            else:
                spec_obj["/AFRelationship"] = pikepdf.Name("/Supplement")
        af_array.append(spec_obj)

    pdf.Root.AF = af_array

    # 4. OutputIntent (sRGB IEC61966-2.1)
    icc_bytes = get_srgb_icc_bytes()
    icc_stream = pdf.make_stream(icc_bytes)
    icc_stream["/N"] = 3
    icc_stream["/Alternate"] = pikepdf.Name("/DeviceRGB")

    output_intent = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name("/OutputIntent"),
            S=pikepdf.Name("/GTS_PDFA1"),
            OutputConditionIdentifier=pikepdf.String("sRGB"),
            Info=pikepdf.String("sRGB IEC61966-2.1"),
            RegistryName=pikepdf.String("http://www.color.org"),
            DestOutputProfile=icc_stream,
        )
    )
    pdf.Root.OutputIntents = pikepdf.Array([output_intent])

    # 5. PDF/A-3U XMP Metadata Stream
    xmp_bytes = generate_xmp_metadata(
        title=title,
        creator=creator,
        doc_filename=doc_filename,
        conformance_level=conformance_level,
        version=version,
        creation_date=now,
    )
    metadata_stream = pdf.make_stream(xmp_bytes)
    metadata_stream["/Type"] = pikepdf.Name("/Metadata")
    metadata_stream["/Subtype"] = pikepdf.Name("/XML")
    pdf.Root.Metadata = metadata_stream

    # 6. Viewer Preferences & Save with PDF 1.7
    if "/ViewerPreferences" not in pdf.Root:
        pdf.Root.ViewerPreferences = pikepdf.Dictionary()
    pdf.Root.ViewerPreferences["/DisplayDocTitle"] = True

    out_buf = io.BytesIO()
    pdf.save(out_buf, min_version="1.7")
    result_bytes = out_buf.getvalue()

    if output_target:
        if isinstance(output_target, (str, Path)):
            Path(output_target).write_bytes(result_bytes)
        elif hasattr(output_target, "write"):
            output_target.write(result_bytes)

    return result_bytes
