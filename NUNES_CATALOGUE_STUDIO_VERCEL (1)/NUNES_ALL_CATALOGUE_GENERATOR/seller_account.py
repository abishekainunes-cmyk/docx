"""Read owner-supplied IndiaMART seller exports without collecting credentials.

CSV and JSON exports can come from the owner's authorized seller account or
the read-only local Playwright tool. Product source/manufacturer identities
remain intact; 'VTech' / 'VT' are NUNES house catalogue labels only.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
from urllib.parse import urlsplit

FIELD_ALIASES={
    "product":("product name","product","item name","item","product/service name",
               "product service name","name","title","itemname","product title"),
    "source_model":("model","model no","model number","model name","product model"),
    "source_brand":("brand","brand name","manufacturer","make","original brand"),
    "source_url":("product url","url","product link","listing url",
                  "indiamart url","source_url","product detail url","link"),
    "image_link":("image url","image link","photo url","image_link","product image"),
    "description":("description","product description","details"),
    "specifications":("specifications","technical specifications","specs"),
    "source_id":("product id","item id","product code","product/service code",
                 "product_service_code","sku","id"),
}
MAX_PRODUCTS=10000
def clean(value,limit=300):
    return re.sub(r"\s+"," ",str(value or "")).strip()[:limit]
def field_name(key):
    return re.sub(r"[^a-z0-9]+"," ",str(key or "").casefold()).strip()
def is_public_listing_url(value):
    try:
        u=urlsplit(str(value or ""))
        host=(u.hostname or "").lower()
        return (u.scheme=="https" and
                (host=="indiamart.com" or host=="www.indiamart.com"
                 or host.endswith(".indiamart.com") and not host.startswith(
                     ("seller.","my.","m.","manage.")))
                and re.search(r"/(?:proddetail|product)/",u.path,re.I) is not None
                and not u.username and not u.password and u.port in (None,443))
    except ValueError:
        return False
def normalize(row):
    if not isinstance(row,dict):return None
    lowered={field_name(k):v for k,v in row.items()}
    def value(field):
        for name in FIELD_ALIASES[field]:
            if field_name(name) in lowered and str(lowered[field_name(name)] or "").strip():
                return lowered[field_name(name)]
        if field in row:return row[field]
        return ""
    name=clean(value("product"),180)
    if len(name)<4:return None
    model=clean(value("source_model"),110)
    source_url=clean(value("source_url"),500)
    if source_url and not is_public_listing_url(source_url):
        # A seller dashboard edit URL is not a public source document:
        # keep product identity, but do not send private URLs to Vercel.
        source_url=""
    key=clean(value("source_id"),120)
    if not key:
        key=hashlib.sha256((name.casefold()+"|"+model.casefold()).encode()).hexdigest()[:20]
    description=clean(value("description"),3600)
    specs=str(value("specifications") or "")[:6000]
    return {
        "product":name,"model":model,"source_model":model,
        "source_brand":clean(value("source_brand"),120),
        "source_id":key,"source_url":source_url,
        "image_link":clean(value("image_link"),1500),
        "description":description,"specifications":specs,
        "catalogue_brand":"VTech","catalogue_model":"VT",
        "review_status":"source_identity_requires_review",
    }
def read_records(data,filename=""):
    """Return stable, deduped rows from a user-exported CSV or JSON document."""
    if isinstance(data,bytes):
        try:data=data.decode("utf-8-sig")
        except UnicodeDecodeError:data=data.decode("cp1252")
    if isinstance(data,str):
        if len(data)>18_000_000:raise ValueError("Export exceeds 18 MB")
        if filename.lower().endswith(".json") or data.lstrip().startswith(("{","[")):
            data=json.loads(data)
        else:
            sample=data[:5000]
            try:dialect=csv.Sniffer().sniff(sample,delimiters=",;\t")
            except csv.Error:dialect=csv.excel
            parsed=list(csv.DictReader(io.StringIO(data),dialect=dialect))
            data=parsed
    if isinstance(data,dict):
        data=data.get("products",data.get("items",data.get("records",[])))
    if not isinstance(data,list):
        raise ValueError("Supply an IndiaMART product export CSV or JSON 'products' array")
    if len(data)>MAX_PRODUCTS:
        raise ValueError("Export exceeds the 10,000-product safety limit; split it")
    out=[];by_id=set()
    for row in data:
        norm=normalize(row)
        if not norm:continue
        fingerprint=(norm["source_id"],norm["product"].casefold(),norm["source_model"].casefold())
        if fingerprint in by_id:continue
        by_id.add(fingerprint)
        out.append(norm)
    if not out:raise ValueError("No product names were found in the export")
    return out
def fingerprint(row):
    fields=("product","source_model","source_brand","source_url","image_link",
            "description","specifications")
    raw=json.dumps([str(row.get(k) or "") for k in fields],
                   ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
def change_set(current,prior):
    """Client can rerun imports and generate catalogues only for new/changed."""
    prior=prior or {}
    changed=[];unchanged=[]
    for row in current:
        if prior.get(row["source_id"])==fingerprint(row):
            unchanged.append(row)
        else:changed.append(row)
    return changed,unchanged
