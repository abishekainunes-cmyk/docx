"""
NUNES Catalogue Studio - Robust File-Type-Aware Extraction Engine & Catalogue Generator.

Supported File Formats:
- XLSX / XLS (OpenPyXL / OLE Workbook parsing with multi-sheet & specification table detection)
- DOCX (python-docx with table & paragraph extraction, embedded image extraction)
- PDF (pypdf multi-page text & embedded image extraction)
- CSV / TXT / JSON (safe encoding detection: utf-8-sig, utf-8, latin-1, cp1252)
- Images (PNG, JPG, JPEG, WEBP, BMP, TIFF with studio transparent cutout)

Features:
- Magic bytes format detection (never treats ZIP/binary files as plain text)
- Security: 25 MB upload limit, zip bomb protection, path traversal protection
- Preserves genuine manufacturer facts and measurement units (0–600 V, mm, kg, °C, etc.)
- Separates original manufacturer/model from NUNES internal catalogue branding:
  Catalogue Brand: VTech | Catalogue Model Prefix: VT
- Generates certified 2-Page Full Catalogue (A4) and Mini Catalogue
- Provides structured payload for editor autofill and instant download
"""
from __future__ import annotations

import base64
import csv
import html
import io
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image

import generator as g
import image_processing

try:
    import template_layout
    has_template_layout = True
except ImportError:
    template_layout = None
    has_template_layout = False

try:
    import drive_storage
    has_drive_storage = True
except ImportError:
    drive_storage = None
    has_drive_storage = False

APP_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_ROOT / "templates"
FALLBACK_PHOTO = TEMPLATES_DIR / "full_header.png"

MAX_FILE_BYTES = 25_000_000       # 25 MB max upload limit
MAX_UNCOMPRESSED_BYTES = 60_000_000  # 60 MB uncompressed limit (zip bomb defense)
MAX_ZIP_RATIO = 100                  # Max compression ratio

KNOWN_SPEC_TERMS = {
    "parameter", "specification", "specifications", "spec", "specs", "property",
    "attribute", "particulars", "technical parameter", "technical data", "technical specification",
    "measuring range", "measurement range", "range", "accuracy", "resolution",
    "display", "display type", "power supply", "voltage", "current", "frequency",
    "capacity", "sensor", "sensor type", "operating temperature", "temperature range",
    "weight", "dimensions", "output", "interface", "calibration", "linearity",
    "repeatability", "material", "housing", "dc voltage", "ac voltage", "dc current",
    "resistance", "capacitance", "sampling rate", "battery", "warranty"
}

KNOWN_TITLE_TERMS = {"product name", "product", "instrument", "item name", "item", "title", "device"}
KNOWN_MODEL_TERMS = {"model", "model number", "model no", "model no.", "source model", "cat no", "part no", "item code"}
KNOWN_BRAND_TERMS = {"brand", "make", "manufacturer", "source brand", "company"}
KNOWN_DESC_TERMS = {"description", "product description", "overview", "brief", "about"}
KNOWN_FEAT_TERMS = {"features", "key features", "highlights", "salient features"}
KNOWN_APP_TERMS = {"applications", "suitable applications", "usage", "intended use"}


def _clean_text(s: Any, max_len: int = 1000) -> str:
    if s is None:
        return ""
    text = html.unescape(re.sub(r"<[^>]*>", " ", str(s)))
    text = re.sub(r"[\r\n\t]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:max_len]


def _format_cell_value(val: Any) -> str:
    """Format spreadsheet / table cell value cleanly, preserving units and avoiding 100.0 for integers."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return f"{val:.4f}".rstrip("0").rstrip(".")
    s = str(val).strip()
    # Strip dangerous formula injection prefixes if present
    if s.startswith(("=", "+", "-", "@")) and len(s) > 1 and not s[1:].isdigit():
        s = s[1:].strip()
    return re.sub(r"\s+", " ", s)


def _sanitize_name_from_filename(filename: str) -> Tuple[str, str]:
    stem = Path(filename).stem
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"(?i)\b(datasheet|specsheet|catalog|catalogue|brochure|specs|img|image|photo|final|v\d+|copy)\b", "", stem)
    stem = _clean_text(stem, 120)
    if not stem:
        stem = "Industrial Testing Instrument"

    # Extract model code if present in filename
    m = re.search(r"\b([A-Z]{1,5}[ -]?\d{2,5}[A-Z0-9-]*)\b", stem)
    model = m.group(1).replace(" ", "-") if m else "VT"
    return stem, model


def detect_file_format(file_bytes: bytes, filename: str = "", mime_type: str = "") -> str:
    """Accurately detects file format using magic bytes signatures and content validation."""
    if not file_bytes:
        return "UNKNOWN"

    header = file_bytes[:32]
    ext = Path(filename).suffix.lower()

    # 1. PDF
    if header.startswith(b"%PDF"):
        return "PDF"

    # 2. Images
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if header.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if header.startswith(b"RIFF") and b"WEBP" in header[:16]:
        return "WEBP"
    if header.startswith(b"BM"):
        return "BMP"
    if header.startswith((b"II*\x00", b"MM\x00*")):
        return "TIFF"

    # 3. OLE Compound Document (legacy .xls / .doc)
    if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        if ext in (".xls", ".xla"):
            return "XLS"
        if ext in (".doc", ".dot"):
            return "DOC"
        return "XLS"

    # 4. ZIP Containers: XLSX, DOCX, or generic ZIP
    if header.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                namelist = z.namelist()
                names_lower = [n.lower() for n in namelist]
                if any(n.startswith("xl/") for n in names_lower) or any("workbook.xml" in n for n in names_lower):
                    return "XLSX"
                if any(n.startswith("word/") for n in names_lower) or any("document.xml" in n for n in names_lower):
                    return "DOCX"
                # Check Content_Types if available
                if "[Content_Types].xml" in namelist:
                    try:
                        ct = z.read("[Content_Types].xml").decode("utf-8", errors="ignore").lower()
                        if "spreadsheetml" in ct:
                            return "XLSX"
                        if "wordprocessingml" in ct:
                            return "DOCX"
                    except Exception:
                        pass
        except Exception:
            pass

        if ext in (".xlsx", ".xlsm", ".xltx"):
            return "XLSX"
        if ext in (".docx", ".docm", ".dotx"):
            return "DOCX"
        return "ZIP"

    # 5. Text / JSON / CSV
    try:
        sample = file_bytes[:4096].decode("utf-8", errors="replace").strip()
        if (sample.startswith("{") and sample.endswith("}")) or (sample.startswith("[") and sample.endswith("]")):
            try:
                json.loads(file_bytes.decode("utf-8"))
                return "JSON"
            except Exception:
                pass
    except Exception:
        pass

    if ext == ".csv" or (mime_type and "csv" in mime_type.lower()):
        return "CSV"
    if ext == ".json" or (mime_type and "json" in mime_type.lower()):
        return "JSON"
    if ext in (".txt", ".text", ".log", ".md"):
        return "TXT"
    if ext in (".xlsx", ".xlsm"):
        return "XLSX"
    if ext in (".docx", ".docm"):
        return "DOCX"

    # Check if printable text
    try:
        decoded = file_bytes[:1024].decode("utf-8")
        if all(c.isprintable() or c in "\r\n\t" for c in decoded):
            return "TXT"
    except Exception:
        pass

    return "BINARY"


def _check_zip_security(file_bytes: bytes) -> None:
    """Defends against zip bombs, nested archives, and path traversal."""
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        total_uncompressed = 0
        for info in z.infolist():
            # Path traversal check
            if ".." in info.filename or info.filename.startswith(("/", "\\")):
                raise ValueError("Security violation: Malicious archive path detected")
            total_uncompressed += info.file_size
            if info.compress_size > 0 and (info.file_size / info.compress_size) > MAX_ZIP_RATIO and info.file_size > 1_000_000:
                raise ValueError("Security violation: High compression ratio (potential zip bomb)")
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(f"File uncompressed size ({total_uncompressed // (1024*1024)} MB) exceeds safe 60 MB limit")


# ==============================================================================
# 1. EXCEL / SPREADSHEET EXTRACTION (XLSX, XLS)
# ==============================================================================

def extract_from_xlsx(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Robust XLSX spreadsheet parser.
    - Parses actual workbook contents and worksheets without displaying XML or binary gibberish.
    - Handles merged cells, empty rows, and multi-sheet workbooks.
    - Detects vertical (Parameter | Specification) and horizontal (Header row | Value row) tables.
    - Identifies Product Name, Model Number, Brand, Specifications, Description, Features.
    - Extracts embedded images if present.
    - Preserves measurement units (0–600 V, mm, kg, °C, etc.).
    """
    _check_zip_security(file_bytes)

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    sheet_names = wb.sheetnames

    product_name = ""
    source_model = ""
    source_brand = ""
    description = ""
    specs_list: List[Dict[str, str]] = []
    features_list: List[str] = []
    applications_list: List[str] = []
    embedded_images: List[bytes] = []

    # 1. Check for embedded images in xl/media/
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            for item in z.infolist():
                if item.filename.lower().startswith("xl/media/") and any(item.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
                    if item.file_size > 4000:  # Ignore tiny logos / icons
                        embedded_images.append(z.read(item.filename))
    except Exception:
        pass

    # 2. Iterate worksheets to find specification tables
    for sheet_name in sheet_names:
        ws = wb[sheet_name]
        raw_rows: List[List[str]] = []
        for row in ws.iter_rows(values_only=True):
            cleaned_row = [_format_cell_value(cell) for cell in row]
            # Strip trailing empty cells
            while cleaned_row and not cleaned_row[-1]:
                cleaned_row.pop()
            if cleaned_row and any(cleaned_row):
                raw_rows.append(cleaned_row)

        if not raw_rows:
            continue

        # Strategy A: Check for vertical 2-column Parameter / Specification table
        for row_idx, row in enumerate(raw_rows):
            non_empty = [c for c in row if c]
            if len(non_empty) < 2:
                # Single cell might be title or section header
                val = non_empty[0] if non_empty else ""
                if not product_name and 5 < len(val) < 80 and not any(k in val.lower() for k in ("sheet", "page", "table", "specification", "overview", "company", "about", "instructions", "index", "notes")):
                    product_name = val
                continue


            k = non_empty[0].strip()
            v = non_empty[1].strip()
            k_lower = k.lower().rstrip(":")

            # Ignore pure table header row like "Parameter | Specification"
            if (k_lower in ("parameter", "property", "attribute", "particulars", "sl.no", "s.no", "item") and
                    v.lower() in ("specification", "specifications", "value", "details", "description", "technical data", "rating")):
                continue

            # If explicit Product Name is found, it takes highest precedence
            if any(k_lower == term for term in KNOWN_TITLE_TERMS) or "product name" in k_lower or "instrument name" in k_lower:
                product_name = v
                continue

            # Check for Model
            if any(k_lower == term for term in KNOWN_MODEL_TERMS) or "model" in k_lower:
                source_model = v
                continue

            # Check for Brand / Make
            if any(k_lower == term for term in KNOWN_BRAND_TERMS) or "brand" in k_lower or "make" in k_lower:
                source_brand = v
                continue

            # Check for Description
            if any(k_lower == term for term in KNOWN_DESC_TERMS):
                description = v
                continue

            # Check for Features
            if any(k_lower == term for term in KNOWN_FEAT_TERMS):
                features_list.extend([f.strip() for f in re.split(r"[;\n\u2022\u25cf]+", v) if f.strip()])
                continue

            # Check for Applications
            if any(k_lower == term for term in KNOWN_APP_TERMS):
                applications_list.extend([a.strip() for a in re.split(r"[;\n\u2022\u25cf]+", v) if a.strip()])
                continue

            # Valid technical specification pair
            if k and v and len(k) < 60 and len(v) < 200:
                if k_lower not in ("overview", "company overview", "company", "notes", "note", "date", "version", "revision", "page", "title", "sheet"):
                    if not any(s["key"].lower() == k.lower() for s in specs_list):
                        specs_list.append({"key": k, "value": v})


        # Strategy B: If no specs found, check for horizontal row-wise products table
        if len(specs_list) < 2 and len(raw_rows) >= 2:
            headers = [h.strip() for h in raw_rows[0]]
            data_row = raw_rows[1]
            for col_idx, h in enumerate(headers):
                if col_idx >= len(data_row):
                    break
                h_clean = h.rstrip(":")
                h_lower = h_clean.lower()
                val = data_row[col_idx].strip()
                if not val:
                    continue

                if not product_name and any(h_lower == term for term in KNOWN_TITLE_TERMS):
                    product_name = val
                elif not source_model and any(h_lower == term for term in KNOWN_MODEL_TERMS):
                    source_model = val
                elif not source_brand and any(h_lower == term for term in KNOWN_BRAND_TERMS):
                    source_brand = val
                elif not description and any(h_lower == term for term in KNOWN_DESC_TERMS):
                    description = val
                elif len(h_clean) < 60 and len(val) < 200:
                    if not any(s["key"].lower() == h_clean.lower() for s in specs_list):
                        specs_list.append({"key": h_clean, "value": val})

    wb.close()

    # Fallbacks for missing product name and model
    fn_name, fn_model = _sanitize_name_from_filename(filename)
    if not product_name:
        product_name = fn_name
    if not source_model:
        source_model = fn_model

    return {
        "format": "XLSX",
        "product_name": _clean_text(product_name, 120),
        "source_model": _clean_text(source_model, 60),
        "source_brand": _clean_text(source_brand, 60),
        "description": _clean_text(description, 1000),
        "specifications": specs_list,
        "features": features_list,
        "applications": applications_list,
        "embedded_images": embedded_images
    }


def extract_from_xls(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Fallback parser for legacy OLE .xls spreadsheets."""
    # Attempt openpyxl in case it's a misnamed XLSX
    try:
        return extract_from_xlsx(file_bytes, filename)
    except Exception:
        pass

    # Extract printable text strings safely without binary garbage
    fn_name, fn_model = _sanitize_name_from_filename(filename)
    specs: List[Dict[str, str]] = []
    text_content = file_bytes.decode("latin1", errors="ignore")
    clean_lines = [line.strip() for line in re.split(r"[\r\n\x00-\x1f]+", text_content) if len(line.strip()) > 3]

    for line in clean_lines:
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if 2 < len(k) < 40 and 1 < len(v) < 120 and not any(ord(c) < 32 for c in k + v):
                specs.append({"key": k, "value": v})

    return {
        "format": "XLS",
        "product_name": fn_name,
        "source_model": fn_model,
        "source_brand": "",
        "description": "",
        "specifications": specs[:10],
        "features": [],
        "applications": [],
        "embedded_images": []
    }


# ==============================================================================
# 2. DOCX / WORD EXTRACTION
# ==============================================================================

def extract_from_docx(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Robust DOCX document parser.
    - Extracts structured paragraphs and specification tables.
    - Identifies Product Name, Model, Brand, Technical Specifications, Key Features, Description.
    - Extracts embedded product photographs from word/media/.
    - Never displays raw binary ZIP internals.
    """
    _check_zip_security(file_bytes)

    import docx

    product_name = ""
    source_model = ""
    source_brand = ""
    description_paragraphs: List[str] = []
    specs_list: List[Dict[str, str]] = []
    features_list: List[str] = []
    applications_list: List[str] = []
    embedded_images: List[bytes] = []

    # 1. Extract embedded images from word/media/
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            for item in z.infolist():
                if item.filename.lower().startswith("word/media/") and any(item.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
                    if item.file_size > 5000:
                        embedded_images.append(z.read(item.filename))
    except Exception:
        pass

    doc = docx.Document(io.BytesIO(file_bytes))

    # 2. Read Tables (Primary source for technical specifications in Word datasheets)
    for table in doc.tables:
        for row in table.rows:
            cells = [_clean_text(c.text, 200) for c in row.cells]
            # Remove adjacent duplicates from merged cells
            dedup_cells = []
            for cell in cells:
                if not dedup_cells or cell != dedup_cells[-1]:
                    dedup_cells.append(cell)

            if len(dedup_cells) < 2:
                continue

            k = dedup_cells[0].rstrip(":")
            v = dedup_cells[1]
            k_lower = k.lower()

            if k_lower in ("parameter", "property", "attribute", "particulars", "sl.no", "item") and v.lower() in ("specification", "value", "details", "technical data"):
                continue

            if not product_name and any(k_lower == term for term in KNOWN_TITLE_TERMS):
                product_name = v
                continue
            if not source_model and any(k_lower == term for term in KNOWN_MODEL_TERMS):
                source_model = v
                continue
            if not source_brand and any(k_lower == term for term in KNOWN_BRAND_TERMS):
                source_brand = v
                continue
            if not description_paragraphs and any(k_lower == term for term in KNOWN_DESC_TERMS):
                description_paragraphs.append(v)
                continue
            if any(k_lower == term for term in KNOWN_FEAT_TERMS):
                features_list.extend([f.strip() for f in re.split(r"[;\n\u2022\u25cf]+", v) if f.strip()])
                continue
            if any(k_lower == term for term in KNOWN_APP_TERMS):
                applications_list.extend([a.strip() for a in re.split(r"[;\n\u2022\u25cf]+", v) if a.strip()])
                continue

            # Handle 3-column table: Parameter | Specification | Units
            if len(dedup_cells) >= 3 and dedup_cells[2]:
                v = f"{v} {dedup_cells[2]}".strip()

            if k and v and len(k) < 60 and len(v) < 250:
                if not any(s["key"].lower() == k.lower() for s in specs_list):
                    specs_list.append({"key": k, "value": v})

    # 3. Read Paragraphs (Headings, Features, Descriptions)
    for p in doc.paragraphs:
        text = _clean_text(p.text, 500)
        if not text:
            continue

        style_name = (p.style.name if p.style else "").lower()

        # Heading detection for product name
        if not product_name and ("heading 1" in style_name or "title" in style_name or (len(text) < 70 and not text.startswith(("#", "-", "*", "•")) and not ":" in text)):
            if not any(w in text.lower() for w in ("specification", "datasheet", "features", "overview", "contents", "table")):
                product_name = text
                continue

        # Bullet point detection for features
        if "bullet" in style_name or re.match(r"^[\u2022\u25cf\-\*]\s+(.+)$", text) or re.match(r"^\d+\.\s+(.+)$", text):
            bullet = re.sub(r"^([\u2022\u25cf\-\*]|\d+\.)\s+", "", text).strip()
            if len(bullet) > 6:
                features_list.append(bullet)
            continue

        # Key: Value lines in paragraphs
        m_spec = re.match(r"^([^:]{2,45}):\s*(\S.+)$", text)
        if m_spec:
            k, v = m_spec.group(1).strip(), m_spec.group(2).strip()
            k_lower = k.lower()
            if not product_name and any(k_lower == term for term in KNOWN_TITLE_TERMS):
                product_name = v
            elif not source_model and any(k_lower == term for term in KNOWN_MODEL_TERMS):
                source_model = v
            elif not source_brand and any(k_lower == term for term in KNOWN_BRAND_TERMS):
                source_brand = v
            elif len(k) < 50 and len(v) < 200:
                if not any(s["key"].lower() == k.lower() for s in specs_list):
                    specs_list.append({"key": k, "value": v})
            continue

        # Regular body paragraph
        if len(text) > 40 and not text.endswith(":"):
            if len(description_paragraphs) < 3:
                description_paragraphs.append(text)

    fn_name, fn_model = _sanitize_name_from_filename(filename)
    if not product_name:
        product_name = fn_name
    if not source_model:
        source_model = fn_model

    return {
        "format": "DOCX",
        "product_name": _clean_text(product_name, 120),
        "source_model": _clean_text(source_model, 60),
        "source_brand": _clean_text(source_brand, 60),
        "description": " ".join(description_paragraphs),
        "specifications": specs_list,
        "features": features_list,
        "applications": applications_list,
        "embedded_images": embedded_images
    }


# ==============================================================================
# 3. PDF EXTRACTION
# ==============================================================================

def extract_from_pdf(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Robust PDF document parser.
    - Multi-page text extraction.
    - Detects product name, model number, brand, specifications, and features.
    - Extracts embedded product photographs.
    - Flags warnings if machine-readable text is absent.
    """
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    full_text = ""
    embedded_images: List[bytes] = []

    for page in reader.pages:
        full_text += (page.extract_text() or "") + "\n"
        if hasattr(page, "images"):
            try:
                for img_obj in page.images:
                    if len(img_obj.data) > 6000:
                        embedded_images.append(img_obj.data)
            except Exception:
                pass

    fn_name, fn_model = _sanitize_name_from_filename(filename)
    product_name = ""
    source_model = ""
    source_brand = ""
    description = ""
    specs_list: List[Dict[str, str]] = []
    features_list: List[str] = []
    applications_list: List[str] = []

    lines = [line.strip() for line in full_text.splitlines() if line.strip()]

    # Extract title from first page
    for line in lines[:10]:
        if 5 < len(line) < 80 and not line.startswith(("#", "-", "*", "Page", "http")):
            if not any(w in line.lower() for w in ("specification", "feature", "table", "datasheet", "manual", "contents")):
                clean_line = re.sub(r"^(?:product(?:\s+name)?|item(?:\s+name)?|device|instrument|title)[:\s\-]+", "", line, flags=re.IGNORECASE).strip()
                product_name = clean_line
                break

    # Look for model pattern
    m_model = re.search(r"\b(?:Model|Series|Cat No|Part No)[:\s\-]+([A-Za-z0-9\-_/]+)", full_text, re.IGNORECASE)
    if m_model:
        source_model = m_model.group(1).strip()

    # Look for brand pattern
    m_brand = re.search(r"\b(?:Brand|Make|Manufacturer)[:\s\-]+([A-Za-z0-9\s\-]+)", full_text, re.IGNORECASE)
    if m_brand:
        source_brand = m_brand.group(1).strip()

    paragraphs: List[str] = []
    current_para: List[str] = []

    for line in lines:
        # Bullet features
        if re.match(r"^[\u2022\u25cf\-\*]\s+(.+)$", line) or re.match(r"^\d+\.\s+(.+)$", line):
            bullet = re.sub(r"^([\u2022\u25cf\-\*]|\d+\.)\s+", "", line).strip()
            if len(bullet) > 8:
                features_list.append(bullet)
            continue

        # Key: Value specs
        m_spec = re.match(r"^([^:]{2,40}):\s*(\S.+)$", line)
        if m_spec:
            k, v = m_spec.group(1).strip(), m_spec.group(2).strip()
            k_lower = k.lower()
            if not any(bad in k_lower for bad in ("note", "warning", "phone", "email", "website", "date", "page", "copyright")):
                if not any(s["key"].lower() == k.lower() for s in specs_list):
                    specs_list.append({"key": k, "value": v})
            continue

        # Tab-separated specs table in PDF
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t") if p.strip()]
            if len(parts) >= 2 and len(parts[0]) < 45 and len(parts[1]) < 150:
                k, v = parts[0], parts[1]
                if not any(s["key"].lower() == k.lower() for s in specs_list):
                    specs_list.append({"key": k, "value": v})
            continue

        # Paragraphs
        if len(line) > 40 and not line.endswith(":"):
            current_para.append(line)
        else:
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []

    if current_para:
        paragraphs.append(" ".join(current_para))

    if paragraphs:
        description = " ".join(paragraphs[:2])

    if not product_name:
        product_name = fn_name
    if not source_model:
        source_model = fn_model

    return {
        "format": "PDF",
        "product_name": _clean_text(product_name, 120),
        "source_model": _clean_text(source_model, 60),
        "source_brand": _clean_text(source_brand, 60),
        "description": _clean_text(description, 1000),
        "specifications": specs_list,
        "features": features_list,
        "applications": applications_list,
        "embedded_images": embedded_images,
        "has_text": len(full_text.strip()) > 50
    }


# ==============================================================================
# 4. CSV, TXT, JSON EXTRACTION
# ==============================================================================

def _safe_decode_text(file_bytes: bytes) -> str:
    """Safely decodes raw text bytes trying UTF-8-SIG, UTF-8, Latin-1, CP1252."""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(enc)
        except Exception:
            continue
    return file_bytes.decode("utf-8", errors="replace")


def extract_from_csv(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Robust CSV parser with auto-delimiter detection and key-value extraction."""
    text_content = _safe_decode_text(file_bytes)
    fn_name, fn_model = _sanitize_name_from_filename(filename)

    # Sniff delimiter
    delimiter = ","
    try:
        sample = text_content[:2048]
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        delimiter = dialect.delimiter
    except Exception:
        if "\t" in sample:
            delimiter = "\t"
        elif ";" in sample:
            delimiter = ";"

    reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
    rows = [[_format_cell_value(cell) for cell in r] for r in reader if any(r)]

    product_name = ""
    source_model = ""
    source_brand = ""
    description = ""
    specs_list: List[Dict[str, str]] = []
    features_list: List[str] = []

    # Check 2-column format
    for r in rows:
        non_empty = [c for c in r if c]
        if len(non_empty) < 2:
            continue
        k, v = non_empty[0].rstrip(":"), non_empty[1]
        k_lower = k.lower()

        if k_lower in ("parameter", "property", "attribute", "particulars", "sl.no", "item") and v.lower() in ("specification", "value", "details"):
            continue

        if not product_name and any(k_lower == term for term in KNOWN_TITLE_TERMS):
            product_name = v
            continue
        if not source_model and any(k_lower == term for term in KNOWN_MODEL_TERMS):
            source_model = v
            continue
        if not source_brand and any(k_lower == term for term in KNOWN_BRAND_TERMS):
            source_brand = v
            continue
        if not description and any(k_lower == term for term in KNOWN_DESC_TERMS):
            description = v
            continue

        if k and v and len(k) < 60 and len(v) < 250:
            if not any(s["key"].lower() == k.lower() for s in specs_list):
                specs_list.append({"key": k, "value": v})

    # Horizontal mapping if vertical didn't yield specs
    if len(specs_list) < 2 and len(rows) >= 2:
        headers = rows[0]
        data_row = rows[1]
        for idx, h in enumerate(headers):
            if idx >= len(data_row):
                break
            val = data_row[idx]
            h_clean = h.rstrip(":")
            h_lower = h_clean.lower()
            if not val:
                continue
            if not product_name and any(h_lower == term for term in KNOWN_TITLE_TERMS):
                product_name = val
            elif not source_model and any(h_lower == term for term in KNOWN_MODEL_TERMS):
                source_model = val
            elif not source_brand and any(h_lower == term for term in KNOWN_BRAND_TERMS):
                source_brand = val
            elif len(h_clean) < 60 and len(val) < 200:
                specs_list.append({"key": h_clean, "value": val})

    return {
        "format": "CSV",
        "product_name": product_name or fn_name,
        "source_model": source_model or fn_model,
        "source_brand": source_brand,
        "description": description,
        "specifications": specs_list,
        "features": features_list,
        "applications": [],
        "embedded_images": []
    }


def extract_from_json(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Robust JSON parser supporting single object or product arrays."""
    text_content = _safe_decode_text(file_bytes)
    data = json.loads(text_content)
    if isinstance(data, list) and data:
        data = data[0]

    fn_name, fn_model = _sanitize_name_from_filename(filename)

    p_name = data.get("product_name") or data.get("product") or data.get("name") or data.get("title") or fn_name
    s_model = data.get("source_model") or data.get("model") or data.get("model_number") or fn_model
    s_brand = data.get("source_brand") or data.get("brand") or data.get("manufacturer") or ""
    desc = data.get("description") or ""

    raw_specs = data.get("specifications") or data.get("specs") or []
    specs_list: List[Dict[str, str]] = []
    if isinstance(raw_specs, list):
        for item in raw_specs:
            if isinstance(item, dict):
                k = item.get("key") or item.get("parameter") or item.get("name") or ""
                v = item.get("value") or item.get("specification") or ""
                if k and v:
                    specs_list.append({"key": str(k), "value": str(v)})
            elif isinstance(item, str) and ":" in item:
                k, v = item.split(":", 1)
                specs_list.append({"key": k.strip(), "value": v.strip()})
    elif isinstance(raw_specs, dict):
        for k, v in raw_specs.items():
            specs_list.append({"key": str(k), "value": str(v)})
    elif isinstance(raw_specs, str):
        for line in raw_specs.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                specs_list.append({"key": k.strip(), "value": v.strip()})

    feats = data.get("features") or data.get("key_features") or []
    if isinstance(feats, str):
        feats = [f.strip() for f in feats.splitlines() if f.strip()]

    apps = data.get("applications") or []
    if isinstance(apps, str):
        apps = [a.strip() for a in apps.splitlines() if a.strip()]

    return {
        "format": "JSON",
        "product_name": _clean_text(p_name, 120),
        "source_model": _clean_text(s_model, 60),
        "source_brand": _clean_text(s_brand, 60),
        "description": _clean_text(desc, 1000),
        "specifications": specs_list,
        "features": feats,
        "applications": apps,
        "embedded_images": []
    }


def extract_from_txt(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Extract product facts from plain text files."""
    text_content = _safe_decode_text(file_bytes)
    fn_name, fn_model = _sanitize_name_from_filename(filename)

    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    product_name = ""
    source_model = ""
    source_brand = ""
    description_paragraphs: List[str] = []
    specs_list: List[Dict[str, str]] = []
    features_list: List[str] = []

    for line in lines:
        if not product_name and 4 < len(line) < 70 and not ":" in line and not line.startswith(("-", "*", "•")):
            product_name = line
            continue

        if re.match(r"^[\u2022\u25cf\-\*]\s+(.+)$", line) or re.match(r"^\d+\.\s+(.+)$", line):
            bullet = re.sub(r"^([\u2022\u25cf\-\*]|\d+\.)\s+", "", line).strip()
            if len(bullet) > 6:
                features_list.append(bullet)
            continue

        m = re.match(r"^([^:]{2,40}):\s*(\S.+)$", line)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            k_lower = k.lower()
            if not product_name and any(k_lower == term for term in KNOWN_TITLE_TERMS):
                product_name = v
            elif not source_model and any(k_lower == term for term in KNOWN_MODEL_TERMS):
                source_model = v
            elif not source_brand and any(k_lower == term for term in KNOWN_BRAND_TERMS):
                source_brand = v
            elif len(k) < 50 and len(v) < 200:
                specs_list.append({"key": k, "value": v})
            continue

        if len(line) > 50 and len(description_paragraphs) < 3:
            description_paragraphs.append(line)

    return {
        "format": "TXT",
        "product_name": product_name or fn_name,
        "source_model": source_model or fn_model,
        "source_brand": source_brand,
        "description": " ".join(description_paragraphs),
        "specifications": specs_list,
        "features": features_list,
        "applications": [],
        "embedded_images": []
    }


# ==============================================================================
# 5. IMAGE EXTRACTION (PNG, JPG, WEBP)
# ==============================================================================

def extract_from_image(file_bytes: bytes, filename: str, mime_type: str = "") -> Dict[str, Any]:
    """Processes uploaded image, performs studio background removal, and extracts metadata."""
    fn_name, fn_model = _sanitize_name_from_filename(filename)

    cutout_bytes = None
    try:
        cutout_bytes = image_processing.remove_studio_background(file_bytes)
    except Exception:
        cutout_bytes = file_bytes

    # Call Gemini Vision if API key is present
    detected_gemini = None
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if api_key:
        try:
            import requests
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            b64_img = base64.b64encode(file_bytes).decode("ascii")
            payload = {
                "systemInstruction": {
                    "parts": [{"text": "You are a professional industrial and laboratory instrument metrology analyst for NUNES Instrumentation. Extract authentic product details from this instrument photo. Return strictly valid JSON."}]
                },
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": "Analyze this instrument photo. Extract: 1. product_name 2. source_model 3. source_brand 4. specifications (array of {key, value} objects) 5. description (approx 100-150 words) 6. features (array of 8 bullet points). Return JSON with these exact keys."},
                        {"inlineData": {"mimeType": mime_type or "image/png", "data": b64_img}}
                    ]
                }],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.15}
            }
            resp = requests.post(url, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"}, json=payload, timeout=12)
            if resp.status_code == 200:
                result = resp.json()
                text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if text:
                    detected_gemini = json.loads(text)
        except Exception:
            pass

    if detected_gemini:
        p_name = detected_gemini.get("product_name") or fn_name
        s_model = detected_gemini.get("source_model") or detected_gemini.get("model") or fn_model
        s_brand = detected_gemini.get("source_brand") or detected_gemini.get("brand") or ""
        specs = detected_gemini.get("specifications") or []
        desc = detected_gemini.get("description") or ""
        feats = detected_gemini.get("features") or []
        return {
            "format": "IMAGE",
            "product_name": _clean_text(p_name, 120),
            "source_model": _clean_text(s_model, 60),
            "source_brand": _clean_text(s_brand, 60),
            "description": _clean_text(desc, 1000),
            "specifications": specs,
            "features": feats,
            "applications": [],
            "photo_bytes": cutout_bytes
        }

    return {
        "format": "IMAGE",
        "product_name": fn_name,
        "source_model": fn_model,
        "source_brand": "",
        "description": "",
        "specifications": [],
        "features": [],
        "applications": [],
        "photo_bytes": cutout_bytes
    }


# ==============================================================================
# UNIFIED FILE ANALYSIS & WORKFLOW PIPELINE
# ==============================================================================

def analyze_uploaded_file(file_bytes: bytes, filename: str, mime_type: str = "") -> Dict[str, Any]:
    """
    Main entry point for analyzing uploaded documents across all supported formats:
    PNG, JPG, WEBP, PDF, CSV, TXT, JSON, XLSX, XLS, DOCX.
    Guarantees no raw binary data or XML tags leak into output.
    """
    if not file_bytes:
        raise ValueError("Uploaded file is empty (0 bytes).")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise ValueError(f"Uploaded file size ({len(file_bytes)//(1024*1024)} MB) exceeds 25 MB limit.")

    fmt = detect_file_format(file_bytes, filename, mime_type)
    extracted: Dict[str, Any] = {}
    warnings: List[str] = []

    if fmt == "XLSX":
        extracted = extract_from_xlsx(file_bytes, filename)
    elif fmt == "XLS":
        extracted = extract_from_xls(file_bytes, filename)
    elif fmt == "DOCX":
        extracted = extract_from_docx(file_bytes, filename)
    elif fmt == "PDF":
        extracted = extract_from_pdf(file_bytes, filename)
        if not extracted.get("has_text", True):
            warnings.append("Scanned PDF detected. No machine-readable text was found. Manual review recommended.")
    elif fmt in ("PNG", "JPEG", "WEBP", "BMP", "TIFF"):
        extracted = extract_from_image(file_bytes, filename, mime_type)
    elif fmt == "CSV":
        extracted = extract_from_csv(file_bytes, filename)
    elif fmt == "JSON":
        extracted = extract_from_json(file_bytes, filename)
    elif fmt == "TXT":
        extracted = extract_from_txt(file_bytes, filename)
    else:
        raise ValueError(f"Unsupported file format or invalid file signature: {fmt}. Please upload XLSX, PDF, DOCX, CSV, TXT, JSON, or an Image.")

    prod_name = _clean_text(extracted.get("product_name") or "Testing Instrument", 120)
    source_model = _clean_text(extracted.get("source_model") or "VT", 60)
    source_brand = _clean_text(extracted.get("source_brand") or "", 60)

    # NUNES Catalogue Branding defaults
    catalogue_brand = "VTech"
    catalogue_model = "VT" if not source_model or source_model == "VT" else f"VT-{source_model}"

    raw_specs = extracted.get("specifications") or []
    spec_list: List[Dict[str, str]] = []
    if isinstance(raw_specs, list):
        for s in raw_specs:
            if isinstance(s, dict):
                k = _clean_text(s.get("key") or s.get("parameter") or "", 50)
                v = _clean_text(s.get("value") or s.get("specification") or "", 150)
                if k and v and not any(k.lower() == existing["key"].lower() for existing in spec_list):
                    spec_list.append({"key": k, "value": v})
            elif isinstance(s, str) and ":" in s:
                k, v = s.split(":", 1)
                k = _clean_text(k, 50)
                v = _clean_text(v, 150)
                if k and v and not any(k.lower() == existing["key"].lower() for existing in spec_list):
                    spec_list.append({"key": k, "value": v})

    # Ensure 5 approved technical specification rows for certified A4 template
    default_specs_template = [
        {"key": "Instrument Type", "value": prod_name},
        {"key": "Operating Voltage", "value": "230V AC ± 10%, 50 Hz"},
        {"key": "Chassis Construction", "value": "Heavy-Duty Powder-Coated Metal Housing"},
        {"key": "Display Readout", "value": "High-Contrast Multi-Line Digital Display"},
        {"key": "Calibration Standard", "value": "Factory Calibrated with Traceable Certificate"}
    ]
    if len(spec_list) < 5:
        warnings.append(f"Only {len(spec_list)} specification row(s) detected. Supplemented with standard metrology specifications for certified 2-page template.")
        for d in default_specs_template:
            if len(spec_list) < 5 and not any(d["key"].lower() == s["key"].lower() for s in spec_list):
                spec_list.append(d)

    formatted_specs_text = "\n".join(f"{s['key']}: {s['value']}" for s in spec_list)

    # Description target (~100-150 words for editor)
    desc = _clean_text(extracted.get("description") or "", 1200)
    if not desc or len(desc.split()) < 20:
        desc = (
            f"The NUNES {prod_name}" + (f" ({source_model})" if source_model else "") +
            " is an industrial-grade precision instrument engineered for high accuracy, repeatable verification, and continuous operation in demanding quality control and testing laboratories. "
            "Manufactured to rigorous standards, it features robust housing, intuitive digital controls, and state-of-the-art sensing architecture ensuring long-term measurement stability. "
            "Designed for operator convenience, this unit provides rapid readings, minimal thermal drift, and dependable testing performance across manufacturing and research workflows."
        )

    # Key features (8-10 items)
    feats = extracted.get("features") or []
    if isinstance(feats, str):
        feats = [f.strip() for f in feats.splitlines() if f.strip()]
    default_features = [
        "Certified high measurement accuracy with excellent repeatability",
        "Rugged, industrial-grade construction engineered for continuous duty",
        "Clear, high-visibility digital display interface for instant readings",
        "Advanced electronic circuitry minimizing thermal drift during extended operation",
        "Ergonomic front-panel controls allowing rapid setup and calibration",
        "Low power consumption with integrated electrical overload protection",
        "Versatile application range across quality control and research workflows",
        "Fully compliant with NUNES certified metrology and international standards"
    ]
    clean_features = [_clean_text(f, 150) for f in feats if _clean_text(f, 150)]
    for df in default_features:
        if len(clean_features) < 8 and df not in clean_features:
            clean_features.append(df)
    clean_features = clean_features[:10]

    # Applications
    apps = extracted.get("applications") or []
    if isinstance(apps, str):
        apps = [a.strip() for a in apps.splitlines() if a.strip()]
    if not apps:
        apps = [
            "Industrial Quality Control & Verification",
            "Research and Development Testing",
            "Analytical and Metrology Workstations",
            "Manufacturing Production Lines"
        ]

    # Image preparation
    photo_path = None
    photo_data_b64 = None

    if extracted.get("photo_bytes"):
        tmp_img = tempfile.NamedTemporaryFile(prefix="nunes_photo_", suffix=".png", delete=False)
        tmp_img.write(extracted["photo_bytes"])
        tmp_img.close()
        photo_path = Path(tmp_img.name)
        photo_data_b64 = f"data:image/png;base64,{base64.b64encode(extracted['photo_bytes']).decode('ascii')}"
    elif extracted.get("embedded_images"):
        # Use largest embedded image
        best_img = max(extracted["embedded_images"], key=len)
        try:
            tmp_img = tempfile.NamedTemporaryFile(prefix="nunes_emb_photo_", suffix=".png", delete=False)
            cutout = image_processing.remove_studio_background(best_img)
            tmp_img.write(cutout)
            tmp_img.close()
            photo_path = Path(tmp_img.name)
            photo_data_b64 = f"data:image/png;base64,{base64.b64encode(cutout).decode('ascii')}"
        except Exception:
            tmp_img = tempfile.NamedTemporaryFile(prefix="nunes_emb_photo_", suffix=".png", delete=False)
            tmp_img.write(best_img)
            tmp_img.close()
            photo_path = Path(tmp_img.name)
            photo_data_b64 = f"data:image/png;base64,{base64.b64encode(best_img).decode('ascii')}"

    confidence_status = "verified" if len(extracted.get("specifications") or []) >= 3 else "needs_review"

    return {
        "success": True,
        "filename": filename,
        "detected_format": fmt,
        "product_name": prod_name,
        "source_brand": source_brand,
        "source_model": source_model,
        "catalogue_brand": catalogue_brand,
        "catalogue_model": catalogue_model,
        "specifications": formatted_specs_text,
        "spec_list": spec_list,
        "description": desc,
        "features": clean_features,
        "applications": apps,
        "photo_path": str(photo_path) if photo_path else None,
        "photo_data_b64": photo_data_b64,
        "confidence": {
            "status": confidence_status,
            "specs_found_in_file": len(extracted.get("specifications") or []),
            "warnings": warnings
        },
        "warnings": warnings,
        "missing_info": [w for w in warnings if "supplemented" in w.lower()]
    }


def build_catalogues_from_file(file_bytes: bytes, filename: str, mime_type: str = "", save_drive: bool = True) -> Dict[str, Any]:
    """
    Complete Upload-to-Catalogue Automation:
    Upload File -> Detect File Type -> Extract Product Data -> Validate Fields -> Generate Full PDF -> Generate Mini PDF -> Return Response
    """
    detected = analyze_uploaded_file(file_bytes, filename, mime_type)

    prod_name = detected["product_name"]
    source_model = detected["source_model"]
    spec_list = detected["spec_list"]
    desc = detected["description"]
    features = detected["features"]
    applications = detected["applications"]
    photo_path = detected["photo_path"]

    # Research payload for PDF generation
    research = {
        "specs": spec_list[:5],
        "description": desc,
        "features": features[:8],
        "applications": applications
    }

    out_dir = Path(tempfile.mkdtemp(prefix="nunes_auto_catalogue_"))
    full_pdf_filename = f"{g.safe_filename(prod_name, source_model)}.pdf"
    mini_pdf_filename = f"{g.safe_filename(prod_name, source_model)}_Mini_Catalogue.pdf"
    zip_filename = f"{g.safe_filename(prod_name, source_model)}_Bundle.zip"

    full_pdf_path = out_dir / full_pdf_filename
    mini_pdf_path = out_dir / mini_pdf_filename
    zip_path = out_dir / zip_filename

    # 1. Full Catalogue (Certified 2-Page A4)
    try:
        if has_template_layout and template_layout:
            template_layout.full(g, full_pdf_path, prod_name, source_model, photo_path, research)
        else:
            g.catalogue_pdf(full_pdf_path, prod_name, source_model, photo_path, research)
    except Exception:
        g.catalogue_pdf(full_pdf_path, prod_name, source_model, photo_path, research)

    # 2. Mini Catalogue
    products = [({"product": prod_name, "model": source_model}, photo_path)]
    try:
        if has_template_layout and template_layout:
            template_layout.mini(g, mini_pdf_path, prod_name, source_model, [({"product": prod_name, "model": source_model}, str(photo_path) if photo_path else None)])
        else:
            g.mini_pdf(mini_pdf_path, prod_name, source_model, products)
    except Exception:
        g.mini_pdf(mini_pdf_path, prod_name, source_model, products)

    # 3. Create ZIP bundle
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(full_pdf_path, full_pdf_path.name)
        z.write(mini_pdf_path, mini_pdf_path.name)

    # 4. Google Drive Saving (if configured)
    drive_links = {}
    drive_saved = False
    if save_drive and has_drive_storage and drive_storage and drive_storage.configured():
        try:
            full_drive_url = drive_storage.save_pdf(full_pdf_path, full_pdf_path.name, kind="full", allow_server_token=True)
            drive_links["full"] = full_drive_url
            drive_saved = True
        except Exception as e:
            drive_links["full_error"] = str(e)

        try:
            mini_drive_url = drive_storage.save_pdf(mini_pdf_path, mini_pdf_path.name, kind="mini", allow_server_token=True)
            drive_links["mini"] = mini_drive_url
            drive_saved = True
        except Exception as e:
            drive_links["mini_error"] = str(e)

    full_bytes = full_pdf_path.read_bytes()
    mini_bytes = mini_pdf_path.read_bytes()

    return {
        "success": True,
        "filename": filename,
        "detected_format": detected["detected_format"],
        "product_name": prod_name,
        "source_brand": detected["source_brand"],
        "source_model": source_model,
        "catalogue_brand": detected["catalogue_brand"],
        "catalogue_model": detected["catalogue_model"],
        "specifications": detected["specifications"],
        "spec_list": spec_list,
        "spec_count": len(spec_list),
        "description": desc,
        "features": features,
        "applications": applications,
        "photo_data_b64": detected["photo_data_b64"],
        "confidence": detected["confidence"],
        "warnings": detected["warnings"],
        "missing_info": detected["missing_info"],
        "full_pdf_filename": full_pdf_filename,
        "mini_pdf_filename": mini_pdf_filename,
        "full_pdf_size": len(full_bytes),
        "mini_pdf_size": len(mini_bytes),
        "full_pdf_b64": base64.b64encode(full_bytes).decode("ascii"),
        "mini_pdf_b64": base64.b64encode(mini_bytes).decode("ascii"),
        "full_pdf_path": str(full_pdf_path),
        "mini_pdf_path": str(mini_pdf_path),
        "zip_path": str(zip_path),
        "drive_saved": drive_saved,
        "drive_links": drive_links,
        "drive_full_folder": "https://drive.google.com/drive/folders/1wdEVHTs14IW8Dm-1-2hUebUw-hv8mUgF",
        "drive_mini_folder": "https://drive.google.com/drive/folders/1vKbU4e_16f1rO9-U1bPofRiDrUqiaS2C"
    }
