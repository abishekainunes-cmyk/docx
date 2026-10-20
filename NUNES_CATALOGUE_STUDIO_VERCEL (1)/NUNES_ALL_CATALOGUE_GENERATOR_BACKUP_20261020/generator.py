from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
import sqlite3
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
SETTINGS = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
DATA_ROOT = Path("/tmp/nunes_catalogue") if os.environ.get("VERCEL") else ROOT
CAT_DIR = DATA_ROOT / SETTINGS["output_catalogue_dir"]
MINI_DIR = DATA_ROOT / SETTINGS["output_mini_dir"]
CACHE_DIR = DATA_ROOT / "cache"
LOG_DIR = DATA_ROOT / "logs"
CAT_DIR.mkdir(exist_ok=True)
MINI_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

FULL_HEADER = ROOT / "templates" / "full_header.png"
FULL_FOOTER = ROOT / "templates" / "full_footer.png"
MINI_HEADER = ROOT / "templates" / "mini_header.png"
MINI_FOOTER = ROOT / "templates" / "mini_footer.png"
DB_PATH = DATA_ROOT / SETTINGS.get("progress_db", "progress.sqlite3")

PURPLE = colors.HexColor("#343399")
MAGENTA = colors.HexColor("#EC168C")
GREEN = colors.HexColor("#0B6B35")
DARK = colors.HexColor("#161616")
LIGHT_GREY = colors.HexColor("#E7E7E7")

STOPWORDS = {
    "the","and","with","for","of","to","in","on","a","an","type","model","machine",
    "meter","tester","test","digital","automatic","auto","portable","system","device","instrument",
    "equipment","apparatus","unit","kit","set","make","new","used","laboratory","lab","industrial",
    "plus","mini","standard","high","low","smart","pro","basic","electronic","electric"
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
})


def log(msg: str) -> None:
    print(msg, flush=True)
    with (LOG_DIR / "generator.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg + "\n")


def normalize_text(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def key_text(s: str) -> str:
    s = normalize_text(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def safe_filename(product: str, model: str = "") -> str:
    base = normalize_text(product)
    if model and key_text(model) not in key_text(base):
        base += " " + normalize_text(model)
    base = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", base)
    base = re.sub(r"\s+", " ", base).strip(" .")
    if not base:
        base = "Product"
    digest = hashlib.sha1((product + "|" + model).encode("utf-8", "ignore")).hexdigest()[:8]
    if len(base) > 145:
        base = base[:145].rstrip()
    return f"{base}_{digest}"


def product_key(product: str, model: str) -> str:
    if SETTINGS.get("deduplicate_by_product_and_model", True):
        return key_text(product) + "|" + key_text(model)
    return hashlib.sha1((product + model + str(time.time_ns())).encode()).hexdigest()


def setup_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS generated (
            product_key TEXT PRIMARY KEY,
            product_name TEXT,
            model TEXT,
            catalogue_path TEXT,
            mini_path TEXT,
            status TEXT,
            error TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    return db


def is_done(db: sqlite3.Connection, pkey: str) -> bool:
    row = db.execute("SELECT catalogue_path, mini_path, status FROM generated WHERE product_key=?", (pkey,)).fetchone()
    if not row or row[2] != "done":
        return False
    return (ROOT / row[0]).exists() and (ROOT / row[1]).exists()


def mark(db: sqlite3.Connection, pkey: str, product: str, model: str, cat: str, mini: str, status: str, error: str = "") -> None:
    db.execute("""
        INSERT INTO generated(product_key,product_name,model,catalogue_path,mini_path,status,error,updated_at)
        VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(product_key) DO UPDATE SET
        product_name=excluded.product_name, model=excluded.model, catalogue_path=excluded.catalogue_path,
        mini_path=excluded.mini_path, status=excluded.status, error=excluded.error, updated_at=CURRENT_TIMESTAMP
    """, (pkey, product, model, cat, mini, status, error[:2000]))
    db.commit()


def get_google_client():
    """Use existing service-account JSON first; otherwise OAuth client JSON; public CSV is a final fallback."""
    import gspread
    from google.oauth2.service_account import Credentials

    candidates = [
        ROOT / "google_service_account.json",
        ROOT / "config" / "google_service_account.json",
        ROOT.parent / "config" / "google_service_account.json",
    ]
    for p in candidates:
        if p.exists():
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
            creds = Credentials.from_service_account_file(str(p), scopes=scopes)
            return gspread.authorize(creds), f"service account: {p.name}"

    client_secret = ROOT / "client_secret.json"
    if client_secret.exists():
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials as UserCredentials
        from google.auth.transport.requests import Request

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        token_file = ROOT / "token.json"
        creds = None
        if token_file.exists():
            creds = UserCredentials.from_authorized_user_file(str(token_file), scopes)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
            creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        return gspread.authorize(creds), "Google OAuth"
    return None, "public CSV fallback"


def col_to_num(col: str) -> int:
    n = 0
    for ch in col.upper():
        n = n * 26 + ord(ch) - 64
    return n


def fetch_drive_rows() -> List[Dict[str, str]]:
    sid = SETTINGS["spreadsheet_id"]
    sheet_name = SETTINGS["sheet_name"]
    start = int(SETTINGS.get("start_row", 2))
    end = int(SETTINGS.get("end_row", 0) or 0)
    chunk = int(SETTINGS.get("chunk_rows", 1000))
    cols = SETTINGS["columns"]
    max_col = max(col_to_num(c) for c in cols.values())
    end_col = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[max_col - 1] if max_col <= 26 else "K"

    gc, mode = get_google_client()
    log(f"[DRIVE] Reading Google Sheet directly ({mode})")
    rows: List[Dict[str, str]] = []

    if gc is not None:
        sh = gc.open_by_key(sid)
        ws = sh.worksheet(sheet_name)
        if end <= 0:
            end = int(ws.row_count)
        for s in range(start, end + 1, chunk):
            e = min(end, s + chunk - 1)
            values = ws.get(f"A{s}:{end_col}{e}", value_render_option="FORMATTED_VALUE")
            for offset, r in enumerate(values):
                def cell(letter: str) -> str:
                    i = col_to_num(letter) - 1
                    return normalize_text(r[i] if i < len(r) else "")
                product = cell(cols["product_name"])
                if not product:
                    continue
                rows.append({
                    "row": str(s + offset),
                    "product": product,
                    "model": cell(cols["model"]),
                    "specifications": cell(cols["specifications"]),
                    "image_link": cell(cols["image_link"]),
                })
            log(f"[DRIVE] Loaded rows {s:,}-{e:,}; products collected: {len(rows):,}")
        return rows

    # Public-sheet fallback. This does NOT create or store Excel.
    export_url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid=0"
    resp = SESSION.get(export_url, timeout=60)
    resp.raise_for_status()
    reader = csv.reader(io.StringIO(resp.text))
    header = next(reader, [])
    for row_no, r in enumerate(reader, 2):
        if row_no < start:
            continue
        if end > 0 and row_no > end:
            continue
        def cell(letter: str) -> str:
            i = col_to_num(letter) - 1
            return normalize_text(r[i] if i < len(r) else "")
        product = cell(cols["product_name"])
        if not product:
            continue
        rows.append({"row": str(row_no), "product": product, "model": cell(cols["model"]),
                     "specifications": cell(cols["specifications"]), "image_link": cell(cols["image_link"])})
    return rows


def parse_specs(raw: str) -> List[Tuple[str, str]]:
    raw = normalize_text(raw)
    if not raw:
        return []
    pairs: List[Tuple[str, str]] = []
    # Accept key:value, key-value, semicolon, pipe or newline styles.
    chunks = re.split(r"[\n;|]+", raw)
    for chunk in chunks:
        chunk = chunk.strip(" -:,")
        if not chunk:
            continue
        m = re.match(r"^([^:]{2,45})\s*:\s*(.+)$", chunk)
        if m:
            pairs.append((normalize_text(m.group(1)), normalize_text(m.group(2))))
        else:
            m = re.match(r"^([A-Za-z][A-Za-z0-9 /()%+._-]{2,35})\s+-\s+(.+)$", chunk)
            if m:
                pairs.append((normalize_text(m.group(1)), normalize_text(m.group(2))))
    return pairs[: SETTINGS.get("max_spec_rows", 8)]


def query_tokens(product: str, model: str = "") -> List[str]:
    toks = [t for t in re.findall(r"[a-z0-9]+", key_text(product + " " + model)) if len(t) > 2 and t not in STOPWORDS]
    return toks


def exactish_score(text: str, product: str, model: str) -> float:
    a = set(query_tokens(product, model))
    b = set(query_tokens(text))
    if not a:
        return 0
    score = len(a & b) / max(1, len(a))
    if model and key_text(model) and key_text(model) in key_text(text):
        score += 0.55
    return score


def ddgs_text(query: str, max_results: int = 8) -> List[dict]:
    if not SETTINGS.get("web_search_enabled", True):
        return []
    try:
        from ddgs import DDGS
        return list(DDGS().text(query, max_results=max_results))
    except Exception as e:
        log(f"[SEARCH] DDGS text failed: {e}")
        return []


def ddgs_images(query: str, max_results: int = 20) -> List[dict]:
    if not SETTINGS.get("web_search_enabled", True):
        return []
    try:
        from ddgs import DDGS
        return list(DDGS().images(query, max_results=max_results, safesearch="moderate"))
    except Exception as e:
        log(f"[SEARCH] DDGS images failed: {e}")
        return []


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        if not url.lower().startswith(("http://", "https://")):
            return None
        r = SESSION.get(url, timeout=15, allow_redirects=True)
        if r.status_code >= 400 or len(r.content) < 500:
            return None
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and not r.text.lstrip().startswith("<"):
            return None
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


def extract_specs_from_soup(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen = set()
    for tr in soup.find_all("tr")[:120]:
        cells = [normalize_text(x.get_text(" ", strip=True)) for x in tr.find_all(["th", "td"])]
        if len(cells) >= 2 and 1 < len(cells[0]) <= 50 and cells[1]:
            k, v = cells[0], cells[1]
            kk = key_text(k)
            if kk and kk not in seen and len(v) < 220:
                seen.add(kk); out.append((k, v))
        if len(out) >= SETTINGS.get("max_spec_rows", 8):
            return out
    for dt in soup.find_all("dt")[:80]:
        dd = dt.find_next_sibling("dd")
        if dd:
            k = normalize_text(dt.get_text(" ", strip=True)); v = normalize_text(dd.get_text(" ", strip=True))
            kk = key_text(k)
            if k and v and kk not in seen:
                seen.add(kk); out.append((k, v))
        if len(out) >= SETTINGS.get("max_spec_rows", 8):
            return out
    return out


def extract_features_from_soup(soup: BeautifulSoup) -> List[str]:
    vals = []
    for li in soup.find_all("li")[:120]:
        t = normalize_text(li.get_text(" ", strip=True))
        if 12 <= len(t) <= 150 and not re.search(r"(cookie|privacy|login|cart|shipping|return|wishlist)", t, re.I):
            vals.append(t)
        if len(vals) >= 8:
            break
    return vals


def extract_description_from_soup(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    if meta and meta.get("content"):
        t = normalize_text(meta.get("content"))
        if 50 <= len(t) <= 700:
            return t
    for p in soup.find_all("p")[:50]:
        t = normalize_text(p.get_text(" ", strip=True))
        if 80 <= len(t) <= 700 and not re.search(r"cookie|privacy|terms|shipping", t, re.I):
            return t
    return ""


def research_product(product: str, model: str, drive_specs: str) -> Dict:
    result = {
        "specs": parse_specs(drive_specs),
        "description": "",
        "features": [],
        "applications": [],
        "sources": [],
        "image_url": "",
    }
    need_specs = len(result["specs"]) < 4
    q = f'"{product}" {model} specifications'.strip()
    search = ddgs_text(q, 8)
    # IndiaMART is a fallback, not first choice.
    if (not search or need_specs) and SETTINGS.get("indiamart_fallback", True):
        search += ddgs_text(f'site:indiamart.com "{product}" {model}', 6)
    ranked = sorted(search, key=lambda r: exactish_score((r.get("title", "") + " " + r.get("body", "")), product, model), reverse=True)
    for r in ranked[:5]:
        href = r.get("href") or r.get("url") or ""
        title = r.get("title", "")
        if exactish_score(title + " " + r.get("body", ""), product, model) < 0.20:
            continue
        soup = fetch_page(href)
        if not soup:
            continue
        if href not in result["sources"]:
            result["sources"].append(href)
        if need_specs:
            found = extract_specs_from_soup(soup)
            for kv in found:
                if key_text(kv[0]) not in {key_text(x[0]) for x in result["specs"]}:
                    result["specs"].append(kv)
                if len(result["specs"]) >= SETTINGS.get("max_spec_rows", 8):
                    break
        if not result["description"]:
            result["description"] = extract_description_from_soup(soup)
        if len(result["features"]) < 5:
            result["features"].extend([x for x in extract_features_from_soup(soup) if x not in result["features"]])
        # og:image is safer than arbitrary image search when exact page matches.
        og = soup.find("meta", property="og:image")
        if not result["image_url"] and og and og.get("content"):
            result["image_url"] = og.get("content")
        if len(result["specs"]) >= 5 and result["description"] and len(result["features"]) >= 5:
            break

    if not result["description"]:
        body = next((normalize_text(r.get("body", "")) for r in ranked if len(normalize_text(r.get("body", ""))) > 50), "")
        result["description"] = body[:650]

    # Conservative applications inferred only from clear product-family terms.
    name_l = key_text(product)
    if "balance" in name_l or "weigh" in name_l or "scale" in name_l:
        result["applications"] = ["Weighing and measurement tasks where the stated capacity and resolution are suitable."]
    elif "meter" in name_l or "tester" in name_l or "analyzer" in name_l or "analyser" in name_l:
        result["applications"] = ["Testing, measurement, inspection, or maintenance work appropriate to this instrument category."]
    elif "machine" in name_l:
        result["applications"] = ["Production or workshop use appropriate to the stated machine type and model."]

    result["specs"] = result["specs"][: SETTINGS.get("max_spec_rows", 8)]
    result["features"] = result["features"][:7]
    return result


def download_image(url: str, cache_key: str) -> Optional[Path]:
    if not url:
        return None
    ext = ".jpg"
    path = CACHE_DIR / f"{cache_key}{ext}"
    if path.exists() and path.stat().st_size > 1000:
        return path
    try:
        r = SESSION.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content))
        im = ImageOps.exif_transpose(im).convert("RGB")
        if im.width < 120 or im.height < 120:
            return None
        # White background and normalized JPEG.
        im.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
        im.save(path, "JPEG", quality=90, optimize=True)
        return path
    except Exception:
        return None


def find_exact_image(product: str, model: str, preferred_urls: Sequence[str]) -> Optional[Path]:
    ck = hashlib.sha1((product + "|" + model).encode("utf-8", "ignore")).hexdigest()[:18]
    for u in preferred_urls:
        p = download_image(u, ck)
        if p:
            return p
    q = f'"{product}" {model}'.strip()
    for r in ddgs_images(q, 16):
        title = (r.get("title") or "") + " " + (r.get("url") or "")
        if exactish_score(title, product, model) < 0.20:
            continue
        u = r.get("image") or r.get("thumbnail")
        p = download_image(u, ck)
        if p:
            return p
    if SETTINGS.get("indiamart_fallback", True):
        for r in ddgs_images(f'site:indiamart.com "{product}" {model}', 12):
            u = r.get("image") or r.get("thumbnail")
            p = download_image(u, ck)
            if p:
                return p
    return None


def wrap_lines(text: str, max_chars: int) -> List[str]:
    words = normalize_text(text).split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def draw_contained_image(c: canvas.Canvas, img: Optional[Path], x: float, y: float, w: float, h: float) -> None:
    c.setStrokeColor(PURPLE); c.setLineWidth(1.8); c.rect(x, y, w, h, stroke=1, fill=0)
    if not img:
        c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.HexColor("#666666"))
        c.drawCentredString(x + w/2, y + h/2 + 4, "PRODUCT IMAGE")
        c.setFont("Helvetica", 8); c.drawCentredString(x + w/2, y + h/2 - 9, "pending exact-model verification")
        return
    try:
        im = Image.open(img)
        iw, ih = im.size
        scale = min((w-10)/iw, (h-10)/ih)
        dw, dh = iw*scale, ih*scale
        c.drawImage(str(img), x+(w-dw)/2, y+(h-dh)/2, dw, dh, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass


def draw_header(c: canvas.Canvas, header: Path, y: float, h: float) -> None:
    c.drawImage(str(header), 14*mm, y, A4[0]-28*mm, h, preserveAspectRatio=True, mask='auto')


def draw_footer(c: canvas.Canvas, footer: Path, y: float, h: float) -> None:
    c.drawImage(str(footer), 10*mm, y, A4[0]-20*mm, h, preserveAspectRatio=True, mask='auto')


def catalogue_pdf(out_path: Path, product: str, model: str, image: Optional[Path], research: Dict) -> None:
    c = canvas.Canvas(str(out_path), pagesize=A4)
    W,H = A4

    # Page 1 - exact Nunes-style header, product, image, specs.
    draw_header(c, FULL_HEADER, H-56*mm, 47*mm)
    c.setStrokeColor(PURPLE); c.setLineWidth(1.5); c.line(22*mm, H-58*mm, W-22*mm, H-58*mm)
    title = product.upper()
    if model and key_text(model) not in key_text(product):
        title += " - " + model.upper()
    c.setFillColor(PURPLE); c.setFont("Helvetica-Bold", 13.5)
    title_lines = wrap_lines(title, 52)[:2]
    ty = H-73*mm
    for line in title_lines:
        c.drawCentredString(W/2, ty, line); ty -= 6*mm

    img_y = H-151*mm
    draw_contained_image(c, image, 55*mm, img_y, W-110*mm, 66*mm)

    c.setFillColor(MAGENTA); c.setFont("Helvetica-Bold", 12)
    c.drawString(20*mm, H-163*mm, "PRODUCT SPECIFICATION")

    specs = list(research.get("specs") or [])
    if model and all(key_text(k) != "model" for k,_ in specs):
        specs.insert(0, ("Model", model))
    if not specs:
        specs = [("Product", product), ("Model", model or "Refer exact product listing")]
    specs = specs[: SETTINGS.get("max_spec_rows", 8)]
    data = [[Paragraph(f"<b>{html.escape(k)}</b>", ParagraphStyle('k', fontName='Helvetica', fontSize=8.8, leading=10.5)),
             Paragraph(html.escape(v or "-"), ParagraphStyle('v', fontName='Helvetica', fontSize=8.8, leading=10.5))] for k,v in specs]
    table = Table(data, colWidths=[58*mm, 105*mm], rowHeights=None)
    table.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#C7C7C7')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
    ]))
    tw,th = table.wrapOn(c, 163*mm, 85*mm)
    table.drawOn(c, 20*mm, max(18*mm, H-170*mm-th))
    c.showPage()

    # Page 2 - description / features / applications + Nunes footer.
    c.setFillColor(MAGENTA); c.setFont("Helvetica-Bold", 12); c.drawString(17*mm, H-25*mm, "PRODUCT DESCRIPTION")
    desc = normalize_text(research.get("description") or "")
    if not desc:
        desc = f"{product}{(' ' + model) if model else ''}. Technical content is limited to verified Drive and source data; confirm additional specifications against the manufacturer documentation before quotation."
    style = ParagraphStyle('desc', fontName='Helvetica', fontSize=9.4, leading=15, alignment=TA_LEFT, textColor=DARK)
    p = Paragraph(html.escape(desc[:1500]), style)
    pw,ph = p.wrap(W-34*mm, 62*mm)
    p.drawOn(c, 17*mm, H-32*mm-ph)
    y = H-39*mm-ph

    c.setFillColor(MAGENTA); c.setFont("Helvetica-Bold", 11.5); c.drawString(20*mm, y, "Key Features")
    y -= 7*mm
    features = [normalize_text(x) for x in research.get("features", []) if normalize_text(x)]
    if not features:
        features = [f"Exact product identification: {product}" + (f", model {model}" if model else "")]
        features += [f"Specification data shown on page 1 is taken only from available verified fields/sources."]
    c.setFillColor(DARK); c.setFont("Helvetica", 9.1)
    for f in features[:7]:
        lines = wrap_lines(f, 88)[:2]
        c.drawString(22*mm, y, u"•")
        tx = 28*mm
        for line in lines:
            c.drawString(tx, y, line[:110]); y -= 5*mm
        y -= 1.5*mm
        if y < 75*mm: break

    apps = research.get("applications", []) or []
    if apps and y > 78*mm:
        c.setFillColor(MAGENTA); c.setFont("Helvetica-Bold", 11.5); c.drawString(20*mm, y, "Applications")
        y -= 7*mm; c.setFillColor(DARK); c.setFont("Helvetica", 9.1)
        for a in apps[:4]:
            for line in wrap_lines(a, 90)[:2]:
                c.drawString(24*mm, y, line); y -= 5*mm
            y -= 1*mm

    draw_footer(c, FULL_FOOTER, 5*mm, 54*mm)
    c.save()


def build_related_index(rows: List[Dict[str,str]]):
    unique: List[Dict[str,str]] = []
    seen = set()
    token_index = defaultdict(list)
    freq = Counter()
    for r in rows:
        pk = product_key(r["product"], r.get("model", ""))
        if pk in seen: continue
        seen.add(pk)
        i = len(unique); unique.append(r)
        toks = set(query_tokens(r["product"], r.get("model", "")))
        for t in toks: freq[t] += 1
        r["_tokens"] = toks
    for i,r in enumerate(unique):
        for t in r["_tokens"]:
            if freq[t] <= 15000:
                token_index[t].append(i)
    return unique, token_index, freq


def related_products(row: Dict[str,str], unique: List[Dict[str,str]], token_index, freq, count: int) -> List[Dict[str,str]]:
    toks = list(row.get("_tokens") or set(query_tokens(row["product"], row.get("model", ""))))
    toks.sort(key=lambda t: freq.get(t, 10**9))
    cand_ids = set()
    for t in toks[:4]:
        cand_ids.update(token_index.get(t, [])[:3000])
    if not cand_ids:
        return []
    base = set(toks)
    scored = []
    pk0 = product_key(row["product"], row.get("model", ""))
    for i in cand_ids:
        r = unique[i]
        if product_key(r["product"], r.get("model", "")) == pk0: continue
        rt = r.get("_tokens") or set()
        shared = len(base & rt)
        if shared == 0: continue
        score = shared * 2.0 / max(1, len(base | rt))
        if row.get("model") and r.get("model") and key_text(row["model"]) == key_text(r["model"]):
            score -= 1
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _,r in scored[:count]]


def mini_pdf(out_path: Path, product: str, model: str, rel: List[Tuple[Dict[str,str], Optional[Path]]]) -> None:
    c = canvas.Canvas(str(out_path), pagesize=A4)
    W,H = A4
    # Page 1 header + 4 products
    draw_header(c, MINI_HEADER, H-51*mm, 44*mm)
    c.setFillColor(colors.HexColor("#95118C")); c.roundRect(11*mm, H-74*mm, W-22*mm, 18*mm, 5*mm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 15)
    heading = product.upper()
    if len(heading) > 48: heading = heading[:45] + "..."
    c.drawCentredString(W/2, H-68*mm, heading)

    def card(x,y,w,h,r,img):
        draw_contained_image(c,img,x+2*mm,y+15*mm,w-4*mm,h-18*mm)
        c.setFillColor(GREEN); c.setFont("Helvetica-Bold",8.8)
        nm = r["product"] + ((" - " + r.get("model","")) if r.get("model") and key_text(r.get("model","")) not in key_text(r["product"]) else "")
        lines=wrap_lines(nm,34)[:2]
        yy=y+10*mm
        for line in lines:
            c.drawCentredString(x+w/2,yy,line[:52]); yy-=4.5*mm

    rel = rel[:10]
    while len(rel) < 10:
        rel.append(({"product": product, "model": model, "image_link": ""}, None))
    positions1=[(13*mm,H-144*mm),(108*mm,H-144*mm),(13*mm,H-221*mm),(108*mm,H-221*mm)]
    for (r,img),(x,y) in zip(rel[:4],positions1): card(x,y,88*mm,68*mm,r,img)
    c.showPage()

    # Page 2 - 6 products
    positions2=[]
    for rowy in [H-80*mm,H-155*mm,H-230*mm]:
        positions2 += [(13*mm,rowy),(108*mm,rowy)]
    for (r,img),(x,y) in zip(rel[4:10],positions2): card(x,y,88*mm,68*mm,r,img)
    c.showPage()

    # Page 3 - search keywords / related category names + footer.
    c.setFillColor(PURPLE); c.setFont("Helvetica-Bold", 14); c.drawString(18*mm,H-28*mm,"RELATED PRODUCT SEARCH NAMES")
    names=[]
    for r,_ in rel:
        if r["product"] not in names: names.append(r["product"])
    base_words=[w for w in normalize_text(product).split() if len(w)>2]
    keyword_phrases=[]
    for n in names:
        keyword_phrases.append(n)
    if base_words:
        keyword_phrases += [" ".join(base_words), " ".join(base_words[-2:]) if len(base_words)>1 else base_words[0]]
    keyword_phrases = [x for i,x in enumerate(keyword_phrases) if x and x not in keyword_phrases[:i]]
    c.setFillColor(PURPLE); c.setFont("Helvetica-Bold", 10.5)
    y=H-43*mm
    for k in keyword_phrases[:36]:
        for line in wrap_lines(k,82)[:2]:
            c.drawString(20*mm,y,line[:105]); y-=7*mm
        if y < 72*mm: break
    draw_footer(c, MINI_FOOTER, 5*mm, 55*mm)
    c.save()


def unique_rows(rows: List[Dict[str,str]]) -> List[Dict[str,str]]:
    if not SETTINGS.get("deduplicate_by_product_and_model", True):
        return rows
    out=[]; seen=set()
    for r in rows:
        k=product_key(r["product"],r.get("model",""))
        if k in seen: continue
        seen.add(k); out.append(r)
    return out


def self_test() -> int:
    samples = [
        {"row":"2","product":"Current 4215x171 Vac Transformer","model":"4215x171","specifications":"Product: Current Transformer; Model: 4215x171","image_link":""},
        {"row":"3","product":"Jewellery Weighning Balance","model":"PEB235","specifications":"Model: PEB235","image_link":""},
        {"row":"4","product":"Lux Meter","model":"BEETECH B-105","specifications":"Model: BEETECH B-105","image_link":""},
    ]
    unique, idx, freq = build_related_index(samples)
    r = unique[0]
    research={"specs":parse_specs(r["specifications"]),"description":"Current transformer product catalogue generated from the configured Nunes template for system verification.","features":["Model identification retained from the Drive product row.","No unverified electrical ratings are invented during the self-test."],"applications":["Electrical measurement systems where the selected current-transformer rating is suitable."],"sources":[]}
    cat=CAT_DIR/"SELF_TEST_Current_Transformer.pdf"; mini=MINI_DIR/"SELF_TEST_Current_Transformer_mini.pdf"
    catalogue_pdf(cat,r["product"],r["model"],None,research)
    rel=[(x,None) for x in unique[1:]]
    mini_pdf(mini,r["product"],r["model"],rel)
    log(f"[SELF TEST] Created {cat.name} and {mini.name}")
    return 0


def main() -> int:
    if os.environ.get("NUNES_SELF_TEST") == "1" or "--self-test" in sys.argv:
        return self_test()

    log("="*68)
    log("NUNES ALL CATALOGUE GENERATOR - DIRECT GOOGLE DRIVE SOURCE")
    log("No Excel queue is created. Output is only Catalogue/ and Mini Catalogue/.")
    log("="*68)
    db=setup_db()
    try:
        rows=fetch_drive_rows()
    except Exception as e:
        log("[ERROR] Could not read the Google Sheet directly.")
        log("Place your existing google_service_account.json in this folder (or config/) and share the 'total price list' sheet with that service account email.")
        log(f"Details: {e}")
        return 2

    unique, token_index, freq = build_related_index(rows)
    todo=unique_rows(unique)
    log(f"[READY] Drive rows with product names: {len(rows):,}")
    log(f"[READY] Unique product+model catalogues to generate: {len(todo):,}")
    log("[READY] Processing sequentially; safe to close and restart because progress is saved.")
    total=len(todo); generated=0; skipped=0; failed=0

    for n,row in enumerate(todo,1):
        product=row["product"]; model=row.get("model",""); pkey=product_key(product,model)
        base=safe_filename(product,model)
        cat_rel=f"{SETTINGS['output_catalogue_dir']}/{base}.pdf"
        mini_rel=f"{SETTINGS['output_mini_dir']}/{base}_mini.pdf"
        cat=ROOT/cat_rel; mini=ROOT/mini_rel
        if is_done(db,pkey):
            skipped+=1
            if n % 100 == 0: log(f"[{n:,}/{total:,}] already done - skipped {skipped:,}")
            continue
        log(f"[{n:,}/{total:,}] {product}" + (f" | {model}" if model else ""))
        mark(db,pkey,product,model,cat_rel,mini_rel,"working","")
        try:
            research=research_product(product,model,row.get("specifications",""))
            preferred=[row.get("image_link","")]
            if research.get("image_url"): preferred.append(research["image_url"])
            image=find_exact_image(product,model,preferred)
            catalogue_pdf(cat,product,model,image,research)

            rel_rows=related_products(row,unique,token_index,freq,int(SETTINGS.get("mini_related_count",10)))
            rel_with_images=[]
            for rr in rel_rows:
                ri=find_exact_image(rr["product"],rr.get("model",""),[rr.get("image_link","")])
                rel_with_images.append((rr,ri))
            mini_pdf(mini,product,model,rel_with_images)
            mark(db,pkey,product,model,cat_rel,mini_rel,"done","")
            generated+=1
            log(f"    OK -> {cat.name} | {mini.name}")
        except KeyboardInterrupt:
            mark(db,pkey,product,model,cat_rel,mini_rel,"pending","Interrupted by user")
            raise
        except Exception as e:
            failed+=1
            err=f"{type(e).__name__}: {e}"
            mark(db,pkey,product,model,cat_rel,mini_rel,"failed",err)
            log(f"    FAILED: {err}")
            with (LOG_DIR/"failures.log").open("a",encoding="utf-8") as f:
                f.write(f"{row.get('row','')}\t{product}\t{model}\t{err}\n")
        time.sleep(float(SETTINGS.get("search_delay_seconds",1.0)))

    log("="*68)
    log(f"COMPLETE. Generated now: {generated:,}; skipped existing: {skipped:,}; failed: {failed:,}")
    log(f"Catalogue folder: {CAT_DIR}")
    log(f"Mini Catalogue folder: {MINI_DIR}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("Stopped safely. Run again to continue from saved progress.")
        raise SystemExit(130)
