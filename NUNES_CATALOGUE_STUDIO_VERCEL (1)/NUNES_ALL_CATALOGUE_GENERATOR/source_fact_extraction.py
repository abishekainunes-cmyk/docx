"""Conservative, source-attributed extraction of explicit technical facts.

Only parse labelled technical details from exact matching public product pages.
Never synthesize a numerical specification from a category, photo or name.
"""
from __future__ import annotations
import ipaddress
import re
import socket
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import requests

# Normalised names; descriptions and marketplace metadata are intentionally excluded.
FIELDS = {
    "brand", "manufacturer", "model", "model number", "model no", "type",
    "product type", "instrument type", "usage/application", "material",
    "top plate", "top plate material", "body", "body material", "heating",
    "heating plate", "number of positions", "stirring positions",
    "stirrer type", "maximum stirring volume", "stirring capacity",
    "speed range", "speed control", "power supply", "operating voltage",
    "voltage", "capacity", "measuring range", "measurement range",
    "testing range", "frequency", "power consumption", "accuracy",
    "resolution", "repeatability", "sensitivity", "display", "display type",
    "sensor type", "sensor", "number of channels", "channel", "dimensions",
    "weight", "operating temperature", "working temperature",
    "temperature range", "temperature", "pressure range",
    "throughput", "sample volume", "automation grade",
    "interface", "technology", "country of origin"
}
NON_FACT_VALUES = {"n/a", "na", "unknown", "not specified", "contact us",
                   "ask for price", "request a quote", "get latest price"}
SKIP = ("wholesale", "supplier", "manufacturer list", "buy online",
        "add to cart", "price", "gst", "call now", "request callback")


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip(" *#|:-")


def extract_pairs(text, limit=30):
    """Only explicit 'Parameter: Value', 'Parameter | Value', or table rows."""
    pairs = []
    seen = set()
    for line in str(text or "").splitlines():
        item = _norm(re.sub(r"^[-•*]\s*", "", line))
        match = re.match(r"^([A-Za-z][A-Za-z0-9 /().-]{1,70})\s*(?::|\||\t)\s*(.{1,180})$", item)
        if not match:
            continue
        key, value = _norm(match.group(1)), _norm(match.group(2))
        if key.casefold().rstrip(".") not in FIELDS:
            continue
        if (not value or value.casefold() in NON_FACT_VALUES
                or any(bad in value.casefold() for bad in SKIP)
                or len(value)>120 or "http" in value.casefold()
                or re.search(r"[<>\\[\\]{}]", value)):
            continue
        if key.casefold() in seen:
            continue
        seen.add(key.casefold())
        pairs.append((key, value))
        if len(pairs)>=limit:
            break
    return pairs


def _public_https(url):
    try:
        u = urlsplit(str(url))
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            return False
        if u.port not in (None, 443):
            return False
        host = u.hostname.lower().rstrip(".")
        if host in ("localhost", "localhost.localdomain") or host.endswith((".local", ".internal", ".localhost")):
            return False
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (OSError, ValueError):
        return False


def public_product_page(url, product, model=""):
    """Read a bounded exact-product public HTML page; no redirects/private IPs."""
    empty = {"description": "", "specifications": ""}
    if not _public_https(url):
        return empty
    try:
        resp = requests.get(url, timeout=(2, 4), allow_redirects=False,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; NUNES-Catalogue/1.0)"},
                            stream=True)
        with resp:
            if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", "").lower():
                return empty
            data = bytearray()
            for chunk in resp.iter_content(chunk_size=16384):
                data.extend(chunk)
                if len(data)>600000:
                    return empty
        soup=BeautifulSoup(bytes(data), "html.parser")
        title=_norm(soup.title.get_text(" ",strip=True) if soup.title else "")
        from product_discovery import _tokens
        wanted=_tokens(product)
        if len(_tokens(title)&wanted)<max(1,min(2,len(wanted))):
            return empty
        if model and model.casefold() not in soup.get_text(" ",strip=True)[:50000].casefold():
            return empty
        pairs=[]
        def add(k,v):
            k=_norm(k).rstrip(".")
            v=_norm(v)
            if k.casefold() not in FIELDS or not v:
                return
            pairs.extend(extract_pairs(k+": "+v))
        for tr in soup.select("tr")[:150]:
            cells=tr.find_all(["td","th"],recursive=False)
            if len(cells)==2:
                add(cells[0].get_text(" ",strip=True),cells[1].get_text(" ",strip=True))
        for dt in soup.select("dt")[:80]:
            dd=dt.find_next_sibling("dd")
            if dd:
                add(dt.get_text(" ",strip=True),dd.get_text(" ",strip=True))
        for tag in soup.select("li,p")[:180]:
            text=_norm(tag.get_text(" ",strip=True))
            pairs.extend(extract_pairs(text))
        unique={}
        for k,v in pairs:
            if k.casefold() not in unique:
                unique[k.casefold()]=(k,v)
        description=""
        for attributes in ({"name":"description"},{"property":"og:description"}):
            tag=soup.find("meta",attrs=attributes)
            candidate=_norm(tag.get("content")) if tag else ""
            if (40<=len(candidate)<=900 and not any(x in candidate.casefold()
                for x in ("find suppliers", "get best price", "wholesalers", "latest price"))):
                description=candidate
                break
        return {"description":description, "specifications":"\n".join(k+": "+v for k,v in list(unique.values())[:25])}
    except (requests.RequestException, ValueError, OSError):
        return empty
