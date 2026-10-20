"""Plain product-name keywords for Mini Catalogue PDFs.

The printed keyword text contains ONLY selected product names: no search
qualifiers, guessed specifications, added models or advertising phrases.
The original source listing names remain unchanged in the other section.
"""
from __future__ import annotations
import html
import re
from typing import Iterable

MAX_TERMS=180
_MODEL_CODE=re.compile(
    r"(?i)\b(?:[a-z]{1,8}[-/]?\d+[a-z0-9/-]*|\d+[a-z]{1,8}[a-z0-9/-]*)\b"
)
_MEASURE_WITH_UNIT=re.compile(
    r"(?i)^\d+(?:kg|g|mm|cm|m|ml|l|rpm|hz|khz|mhz|v|kv|w|kw|ma|a|mpa|bar)$"
)

def _strip_model_code(match):
    code=match.group(0)
    # Keep real name/specification words such as '3D', '200kg' and '40kHz'.
    if len(code)<4 or _MEASURE_WITH_UNIT.fullmatch(code):
        return code
    return ' '
_MODEL_LABEL=re.compile(
    r"(?i)\b(?:model(?:\s+(?:no|number))?|series|type\s+no)\s*"
    r"[:#=\-\s]+\s*([A-Za-z0-9][A-Za-z0-9/+\-.]{1,35})"
)

def clean_term(value):
    raw=html.unescape(re.sub(r"\s+"," ",str(value or ""))).strip()
    raw=re.sub(r"(?i)\s*\|\s*(?:IndiaMART|best price|buy online).*$","",raw)
    raw=re.sub(r"(?i)\s+(?:at|for)\s+(?:Rs\.?|INR|₹)\s*[\d,]+.*$","",raw)
    raw=re.sub(r"[<>{}\[\]\\\n\r]","",raw).strip(" \t,;.-")
    return raw[:145].strip()

def product_name_only(value, model=""):
    """Remove explicit model designators and codes, preserving category nouns.

    'Digital Multimeter UT161E' -> 'Digital Multimeter'
    'Analyzer - Model CS1000' -> 'Analyzer'
    Don't remove ordinary words like '3D', 'pH', 'AC', 'DC' or '200 kg'.
    """
    raw=clean_term(value)
    if not raw:return ""
    if model:
        raw=re.sub(r"(?i)(?<![A-Za-z0-9])"+re.escape(str(model).strip())+
                   r"(?![A-Za-z0-9])"," ",raw)
    raw=_MODEL_LABEL.sub(" ",raw)
    raw=_MODEL_CODE.sub(_strip_model_code,raw)
    raw=re.sub(r"\s+(?:-\s*)?(?:model|series)\s*$","",raw,flags=re.I)
    raw=re.sub(r"\s+"," ",raw).strip(" \t,;.-/|")
    # Keep a readable name, never an empty string from aggressive stripping.
    return raw or clean_term(value)

def generate_search_keywords(focus:str,selected_names:Iterable[str],
                             manual=None,limit=MAX_TERMS):
    """Return UNIQUE plain product names, not derived search phrases."""
    out=[]
    seen=set()
    for name in [focus,*list(selected_names or [])]:
        text=product_name_only(name)
        key=text.casefold()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
        if len(out)>=max(1,min(int(limit),MAX_TERMS)):
            break
    # Free-form manual content is deliberately ignored: it could reintroduce
    # model names, marketing terms or unsupported 'search keywords'.
    return out
