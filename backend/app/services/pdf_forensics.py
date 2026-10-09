
import pymupdf


def analyze_pdf_bytes(pdf_bytes: bytes) -> dict:
    """
    Inspect PDF structure without saving the uploaded original.

    Coordinates are in PDF page points, with the origin at the
    top-left of the page. Structural indicators require review;
    they do not establish document fraud.
    """
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("Invalid or corrupted PDF file.") from exc

    try:
        if not doc.is_pdf:
            raise ValueError("The uploaded file is not a PDF.")

        if doc.needs_pass:
            raise ValueError(
                "This PDF is password-protected and cannot be analyzed without its password."
            )

        if doc.page_count < 1:
            raise ValueError("The PDF contains no pages.")

        if doc.page_count > 200:
            raise ValueError("PDF exceeds the 200-page analysis limit.")

        if doc.xref_length() > 100_000:
            raise ValueError("PDF contains too many objects for this analysis limit.")

        findings = []
        page_results = []

        def add_finding(
            category,
            finding_type,
            severity,
            page_number,
            message,
            confidence,
            evidence=None,
        ):
            findings.append({
                "finding_id": f"pdf-{len(findings) + 1:03d}",
                "category": category,
                "type": finding_type,
                "severity": severity,
                "page": page_number,
                "message": message,
                "confidence": confidence,
                "evidence": evidence or {},
            })

        # Inspect document-level structures.
        object_count = doc.xref_length()
        embedded_file_count = doc.embfile_count()

        if embedded_file_count:
            add_finding(
                "pdf_structure",
                "embedded_files_present",
                "medium",
                None,
                f"The PDF contains {embedded_file_count} embedded file(s). Review their purpose.",
                0.95,
            )

        # These keys can indicate actions or optional content.
        # Presence alone does not imply malicious behavior.
        for key in ("OpenAction", "AA"):
            try:
                value_type, value = doc.xref_get_key(-1, key)

                if value_type not in ("null", "none") and value:
                    add_finding(
                        "pdf_structure",
                        "document_action_present",
                        "medium",
                        None,
                        f"The PDF catalog contains a {key} entry that requires review.",
                        0.80,
                        {"details": {"catalog_key": key}},
                    )
            except Exception:
                pass

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_number = page_index + 1

            images = page.get_images(full=True)
            fonts = page.get_fonts(full=True)

            annotations = []
            try:
                for annot in page.annots() or []:
                    rect = annot.rect
                    annotations.append({
                        "type": annot.type[1],
                        "x": round(rect.x0, 2),
                        "y": round(rect.y0, 2),
                        "width": round(rect.width, 2),
                        "height": round(rect.height, 2),
                    })
            except Exception:
                pass

            form_fields = []
            try:
                for widget in page.widgets() or []:
                    rect = widget.rect
                    form_fields.append({
                        "name": widget.field_name,
                        "type": widget.field_type_string,
                        "x": round(rect.x0, 2),
                        "y": round(rect.y0, 2),
                        "width": round(rect.width, 2),
                        "height": round(rect.height, 2),
                    })

                    # Signature fields are not automatically proof
                    # of a valid cryptographic signature.
                    if "signature" in str(widget.field_type_string).lower():
                        add_finding(
                            "signature",
                            "signature_field_present",
                            "low",
                            page_number,
                            "A PDF signature field is present. Cryptographic validity has not been verified.",
                            0.99,
                            {"x": rect.x0, "y": rect.y0,
                             "width": rect.width, "height": rect.height},
                        )
            except Exception:
                pass

            # Detect intersecting text spans as a review candidate.
            # Ordinary layouts can also contain overlapping text.
            try:
                text_dict = page.get_text("dict")
                spans = []

                for block in text_dict.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            bbox = span.get("bbox")
                            text = span.get("text", "").strip()

                            if bbox and text:
                                spans.append((bbox, text))

                overlap_found = False

                for i, (a, text_a) in enumerate(spans):
                    for b, text_b in spans[i + 1:]:
                        intersection_width = min(a[2], b[2]) - max(a[0], b[0])
                        intersection_height = min(a[3], b[3]) - max(a[1], b[1])

                        if intersection_width > 2 and intersection_height > 2:
                            add_finding(
                                "pdf_structure",
                                "overlapping_text_objects",
                                "medium",
                                page_number,
                                "Overlapping text regions were detected. This can occur in normal layouts and requires review.",
                                0.55,
                                {
                                    "x": max(a[0], b[0]),
                                    "y": max(a[1], b[1]),
                                    "width": intersection_width,
                                    "height": intersection_height,
                                },
                            )
                            overlap_found = True
                            break

                    if overlap_found:
                        break
            except Exception:
                pass

            page_results.append({
                "page": page_number,
                "width": round(page.rect.width, 2),
                "height": round(page.rect.height, 2),
                "embedded_images": len(images),
                "fonts": len(fonts),
                "annotations": annotations,
                "form_fields": form_fields,
                "drawing_objects": len(page.get_drawings()),
            })

        # PyMuPDF does not provide a general guarantee that
        # incremental updates or every digital signature can
        # be reliably validated through this structural scan.
        try:
            catalog_type, catalog_value = doc.xref_get_key(-1, "AcroForm")
            has_acroform = catalog_type not in ("null", "none")
        except Exception:
            has_acroform = False

        return {
            "page_count": doc.page_count,
            "pdf_object_count": object_count,
            "embedded_file_count": embedded_file_count,
            "has_form_catalog": has_acroform,
            "pages": page_results,
            "findings": findings,
            "signature_validation": "unknown_unverified",
            "incremental_updates": "not reliably determined by this scan",
            "original_document_stored": False,
        }

    finally:
        doc.close()