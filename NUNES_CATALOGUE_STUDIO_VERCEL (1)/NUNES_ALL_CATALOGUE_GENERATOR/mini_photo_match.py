"""Conservative evidence matching for Mini Catalogue product photographs.

A shared product category is NOT enough to attach one instrument's photo to
another product or model. Exact source pages and exact listing titles are
acceptable evidence; every other unmatched result stays name-only.
"""
import re
from urllib.parse import urlsplit, unquote
from product_discovery import _tokens

def canonical_title(value):
    text=re.sub(r"\s+"," ",str(value or "")).strip()
    text=re.split(r"\s+\|\s+(?:IndiaMART|Amazon|Best Price|Ubuy|Grainger)\b",
                  text,maxsplit=1,flags=re.I)[0]
    text=re.sub(r"(?i)^(?:Amazon\.com|Snapklik\.com)\s*:\s*","",text)
    text=re.sub(r"\s+(?:at best price|buy online in india).*$","",text,flags=re.I)
    return re.sub(r"[^a-z0-9]+"," ",text.casefold()).strip()

def canonical_page(value):
    try:
        url=urlsplit(str(value or "").strip())
        if url.scheme!="https" or not url.hostname:return ""
        return url.hostname.casefold().removeprefix("www.")+unquote(url.path).rstrip("/").casefold()
    except ValueError:
        return ""

def _model_markers(text):
    # Distinct alphanumeric identifiers are more meaningful than category
    # words. Do not substitute an image of a different Abbott/Fluke model.
    return {
        s.casefold() for s in re.findall(r"\b(?=[a-z0-9-]*\d)[a-z][a-z0-9-]{2,}\b",
                                         str(text or ""),flags=re.I)
        if len(s)>=4
    }

def evidence_match(listing,candidate):
    """Return 'same_source_page', 'exact_title' or an empty rejection."""
    item=str(listing.get('product') or "")
    candidate_title=str(candidate.get('product') or "")
    if not item or not candidate_title:return ""
    listing_tokens=_tokens(item)
    title_tokens=_tokens(candidate_title)
    if len(listing_tokens & title_tokens)<max(1,min(2,len(listing_tokens))):
        return ""
    given_model=str(listing.get('model') or "").strip()
    if given_model and given_model.casefold() not in (
            candidate_title+' '+str(candidate.get('source_url') or "")).casefold():
        return ""
    source_id=canonical_page(listing.get('source_url'))
    candidate_id=canonical_page(candidate.get('source_url'))
    if source_id and source_id==candidate_id:
        return "same_source_page"
    original=canonical_title(item)
    candidate_clean=canonical_title(candidate_title)
    if original and original==candidate_clean:
        return "exact_title"
    # Long marketing headlines may append seller names, but matching generic
    # category tokens alone is not sufficient; reject these by default.
    return ""

def match_photo(listing,candidates):
    if listing.get("image_link"):
        return None
    for candidate in candidates or ():
        if not isinstance(candidate,dict):continue
        image=str(candidate.get('image_link') or "")
        if not image.startswith("https://"):continue
        kind=evidence_match(listing,candidate)
        if kind:
            return {
                'image_link':image[:1500],
                'image_source_url':str(candidate.get('source_url') or "")[:500],
                'image_match':kind,
                'matched_title':str(candidate.get('product') or "")[:160]
            }
    return None
