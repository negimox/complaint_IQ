"""Document Loader node: parses and extracts structured text and tables from uploaded files."""
import os
import email
from email import policy
import logging
from pathlib import Path
from typing import Dict, Any, List

import pdfplumber
import docx
from PIL import Image

try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

from app.agents.state import ComplaintGraphState

logger = logging.getLogger(__name__)


def _extract_pdf(file_path: str) -> str:
    """Extracts text and formatted tables from a PDF using pdfplumber."""
    extracted_sections: List[str] = []

    with pdfplumber.open(file_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_sections.append(f"--- Page {idx} ---\n{page_text.strip()}")

            # Extract any embedded tables
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables, start=1):
                if not table:
                    continue
                table_lines = [f"\n[Table {t_idx} (Page {idx})]:"]
                for row in table:
                    cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
                    table_lines.append(" | ".join(cleaned_row))
                extracted_sections.append("\n".join(table_lines))

    # If text is suspiciously empty (scanned image PDF), attempt OCR fallback
    combined = "\n\n".join(extracted_sections).strip()
    if len(combined) < 50 and HAS_PYTESSERACT:
        try:
            with pdfplumber.open(file_path) as pdf:
                ocr_texts = []
                for idx, page in enumerate(pdf.pages, start=1):
                    img = page.to_image(resolution=200).original
                    ocr_page = pytesseract.image_to_string(img)
                    if ocr_page.strip():
                        ocr_texts.append(f"--- Page {idx} (OCR) ---\n{ocr_page.strip()}")
                if ocr_texts:
                    return "\n\n".join(ocr_texts)
        except Exception as ocr_err:
            logger.warning(f"OCR fallback failed on PDF: {ocr_err}")

    return combined


def _extract_docx(file_path: str) -> str:
    """Extracts text and table contents from a Microsoft Word .docx file."""
    doc = docx.Document(file_path)
    sections: List[str] = []

    # Paragraphs
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt:
            sections.append(txt)

    # Tables
    for t_idx, table in enumerate(doc.tables, start=1):
        table_lines = [f"\n[Table {t_idx}]:"]
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells]
            table_lines.append(" | ".join(row_cells))
        sections.append("\n".join(table_lines))

    return "\n\n".join(sections)


def _extract_eml(file_path: str) -> str:
    """Parses email .eml / .msg message headers and body."""
    with open(file_path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    headers = [
        f"From: {msg.get('From', 'N/A')}",
        f"To: {msg.get('To', 'N/A')}",
        f"Date: {msg.get('Date', 'N/A')}",
        f"Subject: {msg.get('Subject', 'N/A')}",
        "--- Body ---",
    ]

    body_parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", errors="replace"))
            elif content_type == "text/html" and not body_parts:
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_parts.append(payload.decode("utf-8", errors="replace"))

    return "\n".join(headers) + "\n\n" + "\n\n".join(body_parts)


def _extract_image(file_path: str) -> str:
    """Performs OCR on an image file using pytesseract."""
    if not HAS_PYTESSERACT:
        return "Image uploaded. Note: pytesseract OCR engine is not configured on this host."

    try:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        return text.strip() or "No text recognized in image."
    except Exception as e:
        logger.warning(f"Failed to OCR image: {e}")
        return f"Image processing error: {e}"


def _extract_text_file(file_path: str) -> str:
    """Reads plain text or CSV file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            return f.read()


def document_loader_node(state: ComplaintGraphState) -> Dict[str, Any]:
    """
    Parses and extracts text from an uploaded document.
    Updates state with raw_text and advances pipeline to entity extraction.
    """
    file_path = state.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return {
            "raw_text": state.get("raw_text", ""),
            "step": "document_loader",
            "progress": 20,
            "status_message": f"Document file not found at path: {file_path}",
        }

    ext = Path(file_path).suffix.lower()
    filename = Path(file_path).name

    extracted_text = ""
    try:
        if ext == ".pdf":
            extracted_text = _extract_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            extracted_text = _extract_docx(file_path)
        elif ext in [".eml", ".msg"]:
            extracted_text = _extract_eml(file_path)
        elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
            extracted_text = _extract_image(file_path)
        else:
            extracted_text = _extract_text_file(file_path)
    except Exception as e:
        logger.error(f"Error loading document {file_path}: {e}")
        extracted_text = f"Error extracting document text: {e}"

    char_count = len(extracted_text)
    msg = f"Extracted {char_count:,} characters from '{filename}'."

    return {
        "raw_text": extracted_text,
        "step": "document_loader",
        "progress": 25,
        "status_message": msg,
    }
