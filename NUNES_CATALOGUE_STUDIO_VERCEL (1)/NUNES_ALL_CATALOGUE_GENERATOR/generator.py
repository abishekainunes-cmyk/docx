"""
NUNES Instrumentation PDF Generation Engine.
Features:
1. Full Catalogue: Exactly TWO pages matching the certified NUNES reference template.
   - Page 1: Original header, clean product title, blue-framed uncropped image, magenta PRODUCT SPECIFICATION heading, exactly 5 approved specification rows.
   - Page 2: Magenta PRODUCT DESCRIPTION (approx 60-80 words), magenta KEY FEATURES (exactly 8 bullets), original company footer.
2. Mini Catalogue: Image-first layout without empty boxes, multiple product grid, and clean final page.
   - Completely removes unwanted labels: "RELATED SEARCH KEYWORDS", "RELATED PRODUCT NAMES", "VTech / Model VT internal catalogue label", and search phrases.
   - Uses only cleaned product names with model codes separated.
"""
from __future__ import annotations

import html
import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
CAT_DIR = ROOT / "Catalogue"
MINI_DIR = ROOT / "Mini Catalogue"
CACHE_DIR = ROOT / "cache"
LOG_DIR = ROOT / "logs"

FULL_HEADER = TEMPLATES / "full_header.png"
FULL_FOOTER = TEMPLATES / "full_footer.png"
MINI_HEADER = TEMPLATES / "mini_header.png"
MINI_FOOTER = TEMPLATES / "mini_footer.png"

PURPLE = colors.HexColor("#343399")
MAGENTA = colors.HexColor("#EC168C")
DARK = colors.HexColor("#1E293B")
GREY_BORDER = colors.HexColor("#CBD5E1")
ROW_BG = colors.HexColor("#F8FAFC")


def normalize_text(text: Any) -> str:
    cleaned = html.unescape(re.sub(r"<[^>]*>", " ", str(text or "")))
    return re.sub(r"\s+", " ", cleaned).strip()


def key_text(text: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def safe_filename(name: str, model: str = "") -> str:
    base = (name + (" " + model if model else "")).strip()
    safe = re.sub(r"[^\w\s-]", "", base)
    safe = re.sub(r"\s+", "_", safe)
    return safe[:90] or "NUNES_Product"


def wrap_lines(text: str, max_chars: int) -> List[str]:
    words = normalize_text(text).split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_header(c: canvas.Canvas, header: Path, y: float, h: float) -> None:
    if header.is_file():
        c.drawImage(str(header), 14 * mm, y, A4[0] - 28 * mm, h, preserveAspectRatio=True, mask="auto")


def draw_footer(c: canvas.Canvas, footer: Path, y: float, h: float) -> None:
    if footer.is_file():
        c.drawImage(str(footer), 10 * mm, y, A4[0] - 20 * mm, h, preserveAspectRatio=True, mask="auto")


def draw_contained_image(c: canvas.Canvas, img: Optional[Union[Path, str, bytes]], x: float, y: float, w: float, h: float) -> None:
    """Draws a wide royal-blue bordered photograph frame with uncropped, centered image."""
    c.setStrokeColor(PURPLE)
    c.setLineWidth(1.4)
    c.rect(x, y, w, h, stroke=1, fill=0)

    if not img:
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(colors.HexColor("#64748B"))
        c.drawCentredString(x + w / 2, y + h / 2 + 4, "PRODUCT PHOTOGRAPH")
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + w / 2, y + h / 2 - 9, "NUNES Certified Instrumentation")
        return

    try:
        if isinstance(img, bytes):
            im = Image.open(io.BytesIO(img))
            temp_p = ROOT / "cache" / "temp_draw_img.png"
            temp_p.parent.mkdir(parents=True, exist_ok=True)
            im.save(temp_p)
            img_path = temp_p
        else:
            img_path = Path(img)
            im = Image.open(img_path)

        iw, ih = im.size
        scale = min((w - 12) / iw, (h - 12) / ih)
        dw, dh = iw * scale, ih * scale
        c.drawImage(str(img_path), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, preserveAspectRatio=True, mask="auto")
    except Exception:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.HexColor("#64748B"))
        c.drawCentredString(x + w / 2, y + h / 2, "PRODUCT IMAGE")


def catalogue_pdf(
    out_path: Path,
    product: str,
    model: str,
    image: Optional[Union[Path, str, bytes]],
    research: Dict[str, Any],
    **kwargs
) -> Path:
    """Generates the certified NUNES Full Catalogue: Exactly TWO pages."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=A4)
    W, H = A4

    clean_prod = normalize_text(product).upper()
    clean_model = normalize_text(model)

    # ==================== PAGE 1: Header, Title, Image, 5 Specifications ====================
    # 1. Company Header
    draw_header(c, FULL_HEADER, H - 54 * mm, 48 * mm)

    # 2. Horizontal divider
    c.setStrokeColor(PURPLE)
    c.setLineWidth(1.5)
    c.line(16 * mm, H - 56 * mm, W - 16 * mm, H - 56 * mm)

    # 3. Product Title Heading
    c.setFillColor(PURPLE)
    c.setFont("Helvetica-Bold", 14)
    title_lines = wrap_lines(clean_prod, 52)[:2]
    ty = H - 65 * mm
    for line in title_lines:
        c.drawCentredString(W / 2, ty, line)
        ty -= 5.5 * mm

    # 4. Product Image Section
    img_y = H - 147 * mm
    draw_contained_image(c, image, 24 * mm, img_y, W - 48 * mm, 68 * mm)

    # 5. Product Specification Heading in Magenta
    c.setFillColor(MAGENTA)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawString(18 * mm, H - 159 * mm, "PRODUCT SPECIFICATION")

    # 6. Exactly FIVE Technical Specification Rows
    raw_specs = research.get("specs") or research.get("specifications") or []
    spec_rows: List[Tuple[str, str]] = []
    if isinstance(raw_specs, dict):
        spec_rows = [(k, str(v)) for k, v in raw_specs.items()]
    elif isinstance(raw_specs, list):
        for item in raw_specs:
            if isinstance(item, dict):
                k = item.get("key") or item.get("name") or "Specification"
                v = item.get("value") or "-"
                spec_rows.append((str(k), str(v)))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                spec_rows.append((str(item[0]), str(item[1])))
            elif isinstance(item, str) and ":" in item:
                k, v = item.split(":", 1)
                spec_rows.append((k.strip(), v.strip()))

    # Pad or select exactly 5 rows
    default_specs = [
        ("Product Name", product),
        ("Model / Series", clean_model or "Standard Series"),
        ("Measurement Principle", "Precision Electronic Metrology / Sensor"),
        ("Display / Readout", "High Contrast Digital Display"),
        ("Power Supply", "220V AC / Internal Rechargeable Battery")
    ]
    for dk, dv in default_specs:
        if len(spec_rows) < 5 and not any(r[0].lower() == dk.lower() for r in spec_rows):
            spec_rows.append((dk, dv))
    spec_rows = spec_rows[:5]

    style_k = ParagraphStyle("sk", fontName="Helvetica-Bold", fontSize=9.2, leading=11.5, textColor=PURPLE)
    style_v = ParagraphStyle("sv", fontName="Helvetica", fontSize=9.2, leading=11.5, textColor=DARK)

    table_data = [[
        Paragraph(f"<b>{html.escape(k)}</b>", style_k),
        Paragraph(html.escape(v or "-"), style_v)
    ] for k, v in spec_rows]

    table = Table(table_data, colWidths=[64 * mm, 110 * mm], rowHeights=None)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, ROW_BG])
    ]))
    tw, th = table.wrapOn(c, 174 * mm, 80 * mm)
    table.drawOn(c, 18 * mm, max(16 * mm, H - 165 * mm - th))

    # Page 1 Footer Note
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#777777"))
    c.drawRightString(W - 18 * mm, 8 * mm, "Page 1 of 2")
    c.showPage()

    # ==================== PAGE 2: Description, 8 Key Features, Company Footer ====================
    # 1. Product Description Heading in Magenta
    c.setFillColor(MAGENTA)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawString(18 * mm, H - 24 * mm, "PRODUCT DESCRIPTION")

    desc = normalize_text(research.get("description") or "")
    if not desc:
        desc = (
            f"The NUNES {product}" + (f" (Model: {clean_model})" if clean_model else "") +
            " is an advanced industrial instrument engineered for precision testing, quality verification, and analytical measurement. "
            "Designed for reliable long-term stability and high repeatability, this unit integrates rugged housing with ergonomic controls "
            "for effortless operation across manufacturing plants, research laboratories, and calibration workstations."
        )

    desc_style = ParagraphStyle("desc", fontName="Helvetica", fontSize=9.4, leading=14.5, alignment=TA_LEFT, textColor=DARK)
    p_desc = Paragraph(html.escape(desc[:900]), desc_style)
    pw, ph = p_desc.wrap(W - 36 * mm, 55 * mm)
    p_desc.drawOn(c, 18 * mm, H - 30 * mm - ph)
    y = H - 37 * mm - ph

    # 2. Key Features Heading in Magenta
    c.setFillColor(MAGENTA)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(18 * mm, y, "KEY FEATURES")
    y -= 6.5 * mm

    raw_features = research.get("key_features") or research.get("features") or []
    clean_features = [normalize_text(f) for f in raw_features if normalize_text(f)]
    default_features = [
        f"Engineered for high accuracy and certified measurement repeatability",
        f"Rugged industrial construction suitable for continuous daily operation",
        f"Clear, high-contrast digital display for instant parameter readings",
        f"Advanced thermal stability minimizing calibration drift during extended testing",
        f"Intuitive user interface with rapid calibration and zero-adjustment functions",
        f"Ergonomic, compact benchtop architecture saving valuable workspace",
        f"Built-in safety protections against operational overload and voltage surges",
        f"Complies with NUNES certified metrology and international quality standards"
    ]
    for df in default_features:
        if len(clean_features) < 8 and df not in clean_features:
            clean_features.append(df)
    clean_features = clean_features[:8]

    feat_style = ParagraphStyle("feat", fontName="Helvetica", fontSize=9.0, leading=13.2, alignment=TA_LEFT, textColor=DARK)
    for f in clean_features:
        # Strip leading numbers or bullets
        f_clean = re.sub(r"^\s*(?:\d+[\.\)]|•|\-)\s*", "", f).strip()
        colon_pos = f_clean.find(":")
        if 0 < colon_pos < 45:
            head = f_clean[:colon_pos + 1].strip()
            tail = f_clean[colon_pos + 1:].strip()
            text_line = f"<b>&bull; {html.escape(head)}</b> {html.escape(tail)}"
        else:
            text_line = f"<b>&bull;</b> {html.escape(f_clean)}"

        p_feat = Paragraph(text_line, feat_style)
        fw, fh = p_feat.wrap(W - 38 * mm, 30 * mm)
        if y - fh < 60 * mm:
            break
        p_feat.drawOn(c, 18 * mm, y - fh)
        y -= (fh + 2.2 * mm)

    # 3. Company Footer on Page 2
    draw_footer(c, FULL_FOOTER, 5 * mm, 54 * mm)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#777777"))
    c.drawRightString(W - 18 * mm, 8 * mm, "Page 2 of 2")

    c.save()
    return out_path


def mini_pdf(
    out_path: Path,
    product: str,
    model: str,
    rel: List[Tuple[Dict[str, Any], Optional[Union[Path, str, bytes]]]],
    keywords: Optional[List[str]] = None,
    **kwargs
) -> Path:
    """Generates the professional image-first NUNES Mini Catalogue.
    NO empty dummy boxes. NO unwanted labels like RELATED SEARCH KEYWORDS or VTech.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=A4)
    W, H = A4

    clean_rel = [item for item in rel if item and item[0] and (item[0].get("product") or item[0].get("title"))]
    if not clean_rel:
        clean_rel = [({"product": product or "NUNES Testing Instrument", "model": model or ""}, None)]

    total_items = len(clean_rel)
    total_pages = 2 if total_items <= 4 else 3
    cur_page = 1

    def card(x: float, y: float, w: float, h: float, r: Dict[str, Any], img: Any):
        draw_contained_image(c, img, x + 2 * mm, y + 16 * mm, w - 4 * mm, h - 19 * mm)
        c.setFillColor(colors.HexColor("#0B6B35"))
        c.setFont("Helvetica-Bold", 8.8)
        p_name = normalize_text(r.get("product") or r.get("title") or "")
        lines = wrap_lines(p_name, 34)[:2]
        yy = y + 11 * mm
        for line in lines:
            c.drawCentredString(x + w / 2, yy, line[:50])
            yy -= 4.5 * mm

    # ==================== PAGE 1: Header + Heading Banner + Up to 4 Products ====================
    draw_header(c, MINI_HEADER, H - 51 * mm, 44 * mm)
    c.setFillColor(colors.HexColor("#95118C"))
    c.roundRect(11 * mm, H - 72 * mm, W - 22 * mm, 16 * mm, 4 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    heading = normalize_text(product or "NUNES MINI CATALOGUE").upper()
    if len(heading) > 46:
        heading = heading[:43] + "..."
    c.drawCentredString(W / 2, H - 66.5 * mm, heading)

    p1_items = clean_rel[:4]
    if len(p1_items) == 1:
        positions1 = [(W / 2 - 44 * mm, H - 165 * mm)]
    elif len(p1_items) == 2:
        positions1 = [(13 * mm, H - 165 * mm), (108 * mm, H - 165 * mm)]
    elif len(p1_items) == 3:
        positions1 = [(13 * mm, H - 144 * mm), (108 * mm, H - 144 * mm), (W / 2 - 44 * mm, H - 221 * mm)]
    else:
        positions1 = [(13 * mm, H - 144 * mm), (108 * mm, H - 144 * mm), (13 * mm, H - 221 * mm), (108 * mm, H - 221 * mm)]

    for (r, img), (x, y) in zip(p1_items, positions1):
        card(x, y, 88 * mm, 68 * mm, r, img)

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#777777"))
    c.drawRightString(W - 18 * mm, 8 * mm, f"Page {cur_page} of {total_pages}")
    c.showPage()
    cur_page += 1

    # ==================== PAGE 2: Next 6 Products (Only if > 4 items) ====================
    if total_items > 4:
        p2_items = clean_rel[4:10]
        draw_header(c, MINI_HEADER, H - 51 * mm, 44 * mm)
        positions2 = []
        for rowy in [H - 80 * mm, H - 155 * mm, H - 230 * mm]:
            positions2 += [(13 * mm, rowy), (108 * mm, rowy)]

        for (r, img), (x, y) in zip(p2_items, positions2[:len(p2_items)]):
            card(x, y, 88 * mm, 68 * mm, r, img)

        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#777777"))
        c.drawRightString(W - 18 * mm, 8 * mm, f"Page {cur_page} of {total_pages}")
        c.showPage()
        cur_page += 1

    # ==================== FINAL PAGE: Clean Product Range & Footer ====================
    c.setFillColor(PURPLE)
    c.setFont("Helvetica-Bold", 13.5)
    c.drawString(18 * mm, H - 28 * mm, "CERTIFIED PRODUCT RANGE")

    # Extract clean product names without model numbers
    clean_names = []
    for r, _ in clean_rel:
        pnm = normalize_text(r.get("product") or r.get("title") or "")
        mod = normalize_text(r.get("model") or "")
        if mod:
            pnm = re.sub(re.escape(mod), "", pnm, flags=re.IGNORECASE).strip(" -:/")
        if pnm and pnm not in clean_names:
            clean_names.append(pnm)

    if keywords:
        for kw in keywords:
            ck = normalize_text(kw)
            if ck and ck not in clean_names:
                clean_names.append(ck)

    kw_style = ParagraphStyle(
        "kw",
        fontName="Helvetica-Bold",
        fontSize=9.8,
        leading=16.5,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#4B1D6D")
    )
    y = H - 38 * mm
    for name in clean_names[:32]:
        p_name = Paragraph(f"&bull; {html.escape(name)}", kw_style)
        kw_w, kw_h = p_name.wrap(W - 36 * mm, 25 * mm)
        if y - kw_h < 64 * mm:
            break
        p_name.drawOn(c, 18 * mm, y - kw_h)
        y -= (kw_h + 2 * mm)

    draw_footer(c, MINI_FOOTER, 5 * mm, 55 * mm)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#777777"))
    c.drawRightString(W - 18 * mm, 8 * mm, f"Page {cur_page} of {total_pages}")

    c.save()
    return out_path
