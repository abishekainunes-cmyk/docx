"""Evidence-first preparation for browser-driven NUNES catalogue batches.

The live Vercel server uses bounded public HTTPS research. Optional Playwright
captures are performed on the user's Windows computer and may be imported as
JSON. Captures do not authenticate to or bypass IndiaMART.
"""
import re
from urllib.parse import urlsplit
from product_discovery import _tokens
from source_fact_extraction import extract_pairs, public_product_page

_WORDS = re.compile(r"\b[\w][\w/-]*\b", re.UNICODE)

def is_indiamart_listing(url):
    try:
        u=urlsplit(str(url or ""))
        h=(u.hostname or "").lower()
        return (u.scheme=="https" and u.username is None and u.password is None
                and u.port in (None,443)
                and (h=="indiamart.com" or h.endswith(".indiamart.com"))
                and ("/proddetail/" in u.path or "/product/" in u.path))
    except ValueError:
        return False

def words(text):
    return len(_WORDS.findall(str(text or "")))

def parsed_spec_lines(value, limit=28):
    pairs=extract_pairs(str(value or "")[:8000],limit=limit)
    return "\n".join(key+": "+val for key,val in pairs)

def normalize_scraped(item, product):
    """Accept only identifiable, exact-product user-imported Playwright output."""
    if not isinstance(item,dict):return None
    source=str(item.get("source_url") or "")[:500].strip()
    title=str(item.get("product") or "").strip()[:170]
    if not is_indiamart_listing(source) or not title:
        return None
    q=_tokens(product)
    t=_tokens(title)
    if not q or len(q&t)<max(1,min(2,len(q))):
        return None
    return {
        "product":title,"source_url":source,
        "description":re.sub(r"\s+"," ",str(item.get("description") or ""))[:2600].strip(),
        "specifications":parsed_spec_lines(item.get("specifications") or ""),
        "image_link":str(item.get("image_link") or "")[:1500],
        "model":str(item.get("model") or "")[:120],
        "capture_method":"windows_playwright_public_page",
    }

def matching_image(product, model, source_url, candidates):
    """Do not use a category-only image as an exact product photograph."""
    from mini_photo_match import match_photo
    item={"product":product,"model":model,"source_url":source_url}
    if not candidates:
        return {"image_link":"","image_match":"unavailable"}
    matched=match_photo(item,candidates)
    if matched:
        return {"image_link":matched["image_link"],
                "image_match":matched["image_match"]}
    return {"image_link":"","image_match":"unavailable"}

def prepare_item(product, model="", listing_url="", imported=None,
                 allow_gemini=True, external_research=True):
    product=str(product or "").strip()[:170]
    model=str(model or "").strip()[:100]
    url=str(listing_url or "").strip()[:500]
    if not product:
        raise ValueError("Product name required")
    if url and not is_indiamart_listing(url):
        raise ValueError("Supply a public HTTPS IndiaMART product-detail URL")
    scraped=normalize_scraped(imported,product)
    if scraped and url and scraped["source_url"].split("?")[0]!=url.split("?")[0]:
        raise ValueError("Imported Playwright capture URL differs from the named source")
    if scraped:
        base=scraped
        source_method="windows_playwright_public_page"
    elif external_research:
        from product_research import research_product
        result=research_product(product,model,listing_url=url)
        sources=result.get("sources") or []
        known=url or next((str(s.get("url") or "") for s in sources
                           if is_indiamart_listing(s.get("url"))),"")
        base={
            "product":product,"model":model,"source_url":known,
            "description":str(result.get("description") or "")[:2600],
            "specifications":parsed_spec_lines(result.get("specifications") or ""),
            "image_link":str(result.get("image_link") or ""),
        }
        # For a supplied exact URL, give public page parsing a second chance
        # if indexed snippets failed; never replace a known value with a guess.
        if url and (not base["specifications"] or words(base["description"])<45):
            exact=public_product_page(url,product,model)
            if exact["specifications"] and not base["specifications"]:
                base["specifications"]=parsed_spec_lines(exact["specifications"])
            if exact["description"] and words(exact["description"])>words(base["description"]):
                base["description"]=str(exact["description"])[:2600]
        image_match="source_listing_image" if base["image_link"] and known else ""
        if not base["image_link"]:
            selected=matching_image(
                product,model,known,result.get("image_candidates") or [])
            base["image_link"]=selected["image_link"]
            image_match=selected["image_match"]
        base["image_match"]=image_match or "unavailable"
        source_method=str(result.get("retrieval_method") or "public_page_research")
    else:
        base={"product":product,"model":model,"source_url":url,"description":"",
              "specifications":"","image_link":"","image_match":"unavailable"}
        source_method="no_research_test"

    specs=parsed_spec_lines(base["specifications"])
    # An entered model must be the exact model shown in the imported/public
    # source. Never silently switch from the requested product variant.
    if model and base.get("model") and (
            model.casefold()!=str(base["model"]).strip().casefold()):
        raise ValueError(
            "The source model differs from the requested model; select a matching IndiaMART product page.")
    # Confirm the original source model, NOT the house-catalogue 'VT' label.
    source_model=base.get("model") or model
    for key,value in extract_pairs(specs):
        if key.casefold() in ("model","model number","model no"):
            if model and value.casefold()!=model.casefold():
                # Exact-model conflict: no numerical claims from a different model.
                specs=""
                break
            source_model=value[:100]
            break

    description=base.get("description") or ""
    original_words=words(description)
    source_used=source_method
    ai_failure=""
    # Gemini is optional and invoked only for sparse or truncated source text.
    # NEVER promote AI-proposed technical specifications to source facts.
    from draft_fallback import make_draft
    payload={"product":product,"model":source_model,
             "source_description":description,
             "source_specifications":specs,
             "specifications":specs,
             "source_url":base.get("source_url") or ""}
    fallback=make_draft(payload)
    if allow_gemini and original_words<100:
        try:
            import gemini_direct
            if gemini_direct.is_configured():
                ai=gemini_direct.generate(payload)
                candidate=str(ai.get("description") or "").strip()
                if words(candidate)>=100:
                    description=candidate[:4300]
                    fallback["key_features"]=ai.get("key_features") or fallback.get("key_features")
                    source_used="gemini_expanded_unverified_copy"
            else:
                ai_failure="Gemini key not configured"
        except Exception as exc:
            # Return a usable deterministic draft; never call it Gemini.
            ai_failure=type(exc).__name__
    if words(description)<100:
        description=fallback.get("description") or description
        source_used=source_method+"_plus_source_based_draft"
    from catalogue_content import enrich_full_copy,select_specs,select_features
    evidence=select_specs(extract_pairs(specs),limit=5)
    features=select_features(fallback.get("key_features") or [],limit=8)
    expanded=enrich_full_copy(product,description,features,model=source_model,
                               specs=evidence)
    description=expanded["description"]
    features=expanded["key_features"]
    # Preserve exactly what the real source supports and mark other text.
    return {
        "product":product,"catalogue_brand":"VTech","catalogue_model":"VT",
        "source_model":source_model,"source_url":base.get("source_url") or "",
        "source_method":source_method,"copy_method":source_used,
        "source_description_words":original_words,
        "description_words":words(description),
        "description":description[:4900],
        "features":features[:8],
        "specifications":"\n".join(k+": "+v for k,v in evidence),
        "specification_count":len(evidence),
        "image_link":base.get("image_link") or "",
        "image_match":base.get("image_match") or ("imported_exact_page" if scraped else "unavailable"),
        "playwright_imported":bool(scraped),
        "full_ready":bool(evidence and (base.get("image_link"))),
        "mini_ready":True,
        "gemini_issue":ai_failure,
        "verification_status":"supplier_claimed_review_required",
        "warning":"Exact source technical fields are unverified supplier claims; Gemini drafts only descriptive copy.",
    }
