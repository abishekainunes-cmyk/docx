"""
Google Sheets Integration Service for NUNES Catalogue Generator.
Handles reading, searching, importing and updating product records in Google Sheets.
Credentials are kept secure server-side via GOOGLE_SERVICE_ACCOUNT_JSON.
"""
from __future__ import annotations

import csv
import io
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parent

DEFAULT_SPREADSHEET_ID = "1jYUA7SqSBlkGUs-IaybfEM8lI1ors2w3h62z8yYLC5I"
DEFAULT_SHEET_NAME = "Sheet1"


@lru_cache(maxsize=1)
def get_sheets_client():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        candidate_paths = [
            ROOT / "google_service_account.json",
            ROOT / "config" / "google_service_account.json",
            ROOT.parent / "config" / "google_service_account.json",
        ]
        for p in candidate_paths:
            if p.exists():
                try:
                    raw = p.read_text(encoding="utf-8")
                    break
                except Exception:
                    pass

    if not raw:
        return None, "No credentials found; using public CSV fallback"

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        info = json.loads(raw)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        return client, "Service Account Authorized"
    except Exception as exc:
        return None, f"Service account authentication error: {exc}"


def check_sheets_health() -> Dict[str, Any]:
    client, message = get_sheets_client()
    sid = os.environ.get("GOOGLE_SPREADSHEET_ID") or DEFAULT_SPREADSHEET_ID
    if client:
        try:
            ws = client.open_by_key(sid).worksheet(DEFAULT_SHEET_NAME)
            return {
                "available": True,
                "mode": "service_account",
                "spreadsheet_id": sid,
                "sheet_name": DEFAULT_SHEET_NAME,
                "row_count": ws.row_count,
                "message": "Connected to Google Sheets API"
            }
        except Exception as exc:
            return {
                "available": False,
                "mode": "service_account_error",
                "message": f"Connected to client but failed to open sheet: {exc}"
            }

    # Test public CSV fallback
    try:
        url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid=0"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and "<html" not in resp.text[:300].lower():
            return {
                "available": True,
                "mode": "public_csv_read_only",
                "spreadsheet_id": sid,
                "sheet_name": DEFAULT_SHEET_NAME,
                "message": "Connected via public CSV stream"
            }
    except Exception:
        pass

    return {
        "available": False,
        "mode": "unconfigured",
        "message": "Google Sheets credentials not configured. Local database is active."
    }


def fetch_sheet_rows(query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    client, _ = get_sheets_client()
    sid = os.environ.get("GOOGLE_SPREADSHEET_ID") or DEFAULT_SPREADSHEET_ID
    sheet_name = DEFAULT_SHEET_NAME
    q = query.strip().casefold()

    if client:
        try:
            ws = client.open_by_key(sid).worksheet(sheet_name)
            data = ws.get("D2:G" + str(min(ws.row_count, 50000)), value_render_option="FORMATTED_VALUE")
        except Exception as exc:
            print(f"[Sheets] gspread read failed: {exc}. Trying CSV export fallback.")
            client = None

    if not client:
        url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid=0"
        resp = requests.get(url, timeout=25)
        resp.raise_for_status()
        if "<html" in resp.text[:300].lower():
            raise ValueError("Sheet is private. Add GOOGLE_SERVICE_ACCOUNT_JSON and share sheet with service account email.")
        data = [row[3:7] for row in csv.reader(io.StringIO(resp.text))][1:]

    found = []
    seen = set()
    for idx, row in enumerate(data, 2):
        row = list(row) + [""] * max(0, 4 - len(row))
        img, name, model, specs = row[:4]
        if not name:
            continue
        full_text = f"{name} {model} {specs}".casefold()
        if q and q not in full_text:
            continue
        key = (name.casefold().strip(), model.casefold().strip())
        if key in seen:
            continue
        seen.add(key)
        found.append({
            "row": idx,
            "product": name.strip(),
            "model": model.strip(),
            "specifications": specs.strip(),
            "image_link": img.strip(),
            "source": "google_sheets"
        })
        if len(found) >= limit:
            break

    return found


def export_row_to_sheet(product: str, model: str, specs: str, image_link: str) -> bool:
    """Append row to Google Sheet if service account has write permission."""
    client, _ = get_sheets_client()
    if not client:
        raise ValueError("Cannot write to Google Sheet without GOOGLE_SERVICE_ACCOUNT_JSON configured with write permissions.")
    sid = os.environ.get("GOOGLE_SPREADSHEET_ID") or DEFAULT_SPREADSHEET_ID
    ws = client.open_by_key(sid).worksheet(DEFAULT_SHEET_NAME)
    ws.append_row(["", "", "", image_link, product, model, specs])
    return True
