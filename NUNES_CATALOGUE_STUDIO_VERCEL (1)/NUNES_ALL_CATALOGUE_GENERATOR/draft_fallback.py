"""Reliable reference-length NUNES catalogue draft for AI/credit outages.

Copy is separated into two evidentiary tiers:
* explicit model/vendor parameters (user supplied or exact-product listing)
* product-type principles / *typical* use cases (NOT claims about an exact model).

Do not invent instrument performance, electrodes, supplied accessories,
range, automation, accuracy, materials or model-specific features. Public
supplier excerpts are unverified; advertising snippets are never catalogue
prose. This module is deterministic and never claims Gemini generation.
"""
from __future__ import annotations
import re
from source_fact_extraction import extract_pairs

TARGET_DESCRIPTION_WORDS=(150,200)
REFERENCE_FEATURES=10
REFERENCE_APPLICATIONS=6
_WORDS=re.compile(r"\b[\w][\w/-]*\b",re.UNICODE)
_ADS=re.compile(
    r"(?i)(?:at best price|best price|get (?:latest )?price|price list|"
    r"manufacturer(?:s)?[,]?\s*(?:exporters|suppliers|traders)|"
    r"also get|verified compan(?:y|ies)|latest price|visit our website|"
    r"order online|find here online|contact supplier|shipping|"
    r"request (?:a )?(?:callback|quote)|compare prices|"
    r"corporation at best|₹|\brs\.\s*\d|"
    r"\bid\s*:?\s*\d{7,}|supplier directory|"
    r"for wholesale|seller rating|add to cart|"
    r"indiamart\.com|tradeindia\.com|"
    r"get info of suppliers|dealers[, ]+traders|"
    r"trader\s*[-–]\s*wholesaler|wholesaler\s*/\s*distributor|"
    r"trader\s*[-–]\s*manufacturer|find here online)"
)

def clean(value,limit=500):
    return re.sub(r"\s+"," ",str(value or "")).strip(" •*;-")[:limit]

def _unique(items, limit):
    seen=set()
    result=[]
    for item in items:
        item=clean(item,180)
        if not item or _ADS.search(item):
            continue
        key=item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result)>=limit:
            break
    return result

def _as_lines(raw, limit=20):
    if isinstance(raw,(tuple,list)):
        raw_lines=[str(x) for x in raw]
    else:
        raw_lines=str(raw or "").splitlines()
    return _unique((re.sub(r"^\s*[-*•]\s*","",line) for line in raw_lines),limit)

def _type_profile(product):
    name=product.casefold()
    if "pyrogen" in name and ("telethermometer" in name or
                              "tele thermometer" in name or
                              "tele-thermometer" in name):
        return {
            "type":"digital pyrogen telethermometer",
            "function":(
                "is a laboratory temperature-measuring instrument intended "
                "for monitoring experimental animals during compatible "
                "pyrogen testing and physiological research. Digital "
                "temperature observations help laboratory personnel follow "
                "temperature changes over a defined observation period, "
                "where an appropriate probe and test procedure are used."),
            "use":(
                "This product category is used in animal-temperature "
                "monitoring workflows, including pharmacological and "
                "preclinical studies. Digital readout and temperature "
                "probe monitoring are associated with this instrument "
                "type; the number of channels, probe configuration, "
                "range, accuracy, data-recording software and approved "
                "pharmacopoeial procedures vary by manufacturer and "
                "model and require confirmation."),
            "features":[
                "Digital temperature-monitoring instrument for laboratory use",
                "Temperature observation during appropriate pyrogen tests",
                "Probe-based measurement approach described for the instrument type",
                "Monitoring of temperature changes during test intervals",
                "Use in compatible laboratory-animal research procedures",
                "Designed for temperature-measurement workflows",
                "Applicable to experimental temperature studies",
                "Model-dependent channel and probe options require confirmation"],
            "applications":[
                "Pyrogen testing in suitably equipped laboratories",
                "Temperature monitoring in preclinical research",
                "Laboratory-animal temperature observations",
                "Pharmacology and physiological research",
                "Temperature studies under approved test protocols",
                "Research involving controlled thermal measurements"],
            "context_specs":[
                ("Instrument Type","Digital laboratory telethermometer"),
                ("Measurement Function","Temperature monitoring"),
                ("Typical Sample Context","Laboratory animals"),
                ("Typical Test Application","Pyrogen testing"),
                ("Measurement Approach","Temperature probe monitoring")],
            "context_source":"https://orchidscientific.com/product/pyrogen-test-digital-telethermometer/"
        }
    if "potentiometric" in name and ("titrator" in name or "titrat" in name):
        return {
            "type":"potentiometric titration apparatus",
            "function":(
                "is a laboratory instrument for potentiometric titration, a "
                "chemical-analysis method that follows changes in electrical "
                "potential while a titrant is introduced. This approach helps "
                "evaluate titration progress and identify an endpoint using "
                "an electrochemical measurement rather than relying solely on "
                "a visual colour indicator."),
            "use":(
                "The apparatus is intended for analytical titration methods "
                "where an electrical-potential endpoint is appropriate. "
                "Electrodes, titrants, operating conditions and method "
                "compatibility must be selected and verified for the "
                "particular sample and laboratory procedure."),
            "features":[
                "Potentiometric titration measurement principle",
                "Evaluation of electrical-potential changes during titration",
                "Electrochemical endpoint determination method",
                "Digital laboratory apparatus format" if "digital" in name else
                    "Laboratory titration apparatus",
                "Instrument type intended for analytical chemistry",
                "Liquid-sample titration workflow",
                "Potential-based rather than colour-only endpoint assessment"],
            "applications":[
                "Potentiometric titration in analytical laboratories",
                "Chemical analysis of compatible liquid samples",
                "Quality-control titration procedures",
                "Laboratory analytical-method development",
                "Research involving electrochemical titration",
                "Education and training in titration techniques"],
            "context_specs":[
                ("Instrument Type","Potentiometric titration apparatus"),
                ("Analysis Principle","Electrical potential during titration"),
                ("Measurement Function","Electrochemical titration endpoint detection"),
                ("Typical Sample Type","Compatible laboratory liquid samples"),
                ("Method Category","Analytical potentiometric titration")],
            "context_source":"" }
    if "magnetic stirrer" in name:
        return {
            "type":"laboratory magnetic stirrer",
            "function":(
                "uses magnetic stirring principles to mix compatible liquid "
                "samples in laboratory vessels. A rotating magnetic field "
                "drives a suitable stir bar within the sample, allowing "
                "the liquid to be mixed without a mechanical impeller "
                "passing through the vessel."),
            "use":(
                "It is intended for laboratory sample-preparation and "
                "mixing workflows. The number of operating positions, "
                "stirring capacity, speed range, plate material and "
                "heating capability depend on the exact model and must "
                "be checked against its technical data."),
            "features":[
                "Magnetic stirring principle for laboratory liquids",
                "Contact-free drive of a suitable magnetic stir bar",
                "Liquid mixing in compatible laboratory vessels",
                "Laboratory sample preparation and agitation",
                "Stirring without a shaft entering the sample",
                "Mixing applications in analytical work"],
            "applications":[
                "Chemical and analytical laboratories",
                "Laboratory liquid-sample preparation",
                "Pharmaceutical laboratory mixing",
                "Educational and research laboratories",
                "Routine laboratory solution mixing",
                "Industrial quality-control sample preparation"],
            "context_specs":[
                ("Instrument Type","Laboratory magnetic stirrer"),
                ("Mixing Principle","Magnetic stirring"),
                ("Typical Sample Type","Compatible laboratory liquid solutions"),
                ("Intended Function","Laboratory liquid mixing")],
            "context_source":"" }
    if "multimeter" in name:
        return {
            "type":"electrical multimeter",
            "function":(
                "is a measuring instrument used to assess electrical "
                "quantities during testing and troubleshooting. "
                "A multimeter combines several measurement functions "
                "in one instrument, allowing a technician to check "
                "conditions appropriate to its stated measurement modes."),
            "use":(
                "It supports electrical inspection and diagnostic work "
                "where the instrument's specified measurement functions "
                "are suitable. The available modes, accuracy, category "
                "rating, probe configuration and operating limits "
                "must be checked for the exact model."),
            "features":[
                "Combined electrical measurement instrument",
                "Electrical inspection and testing format",
                "Use for troubleshooting appropriate electrical circuits",
                "Multiple measurement functions subject to model datasheet",
                "Portable electrical test instrument category"],
            "applications":[
                "Electrical maintenance and diagnostics",
                "Electrical laboratory testing",
                "Industrial electrical inspection",
                "Equipment servicing and troubleshooting",
                "Technical education and training",
                "Routine electrical measurement work"],
            "context_specs":[
                ("Instrument Type","Electrical multimeter"),
                ("Measurement Function","Electrical quantity measurement"),
                ("Test Category","Electrical testing and inspection"),
                ("Typical Operating Context","Electrical troubleshooting")],
            "context_source":"" }
    if "leak detector" in name or "leak detection" in name:
        return {
            "type":"leak detection instrument",
            "function":(
                "is an inspection instrument intended to locate "
                "or indicate leaks in systems compatible with the "
                "detection technique used. Leak testing helps "
                "maintenance and quality personnel investigate "
                "suspected loss of containment or unwanted release."),
            "use":(
                "The applicable medium, detection method, sensitivity "
                "and operating conditions vary substantially between "
                "gas, liquid, refrigerant and acoustic leak detectors. "
                "Confirm the actual technology and its limitations "
                "before using the equipment on a particular system."),
            "features":[
                "Leak inspection instrument category",
                "Support for compatible leak detection procedures",
                "Inspection and maintenance application",
                "Identification of suspected leakage locations subject to method",
                "Product-specific sensor method requires confirmation"],
            "applications":[
                "Routine equipment inspection",
                "Maintenance leak investigations",
                "Quality-control leak checks",
                "Commissioning checks where compatible",
                "Troubleshooting suspected losses",
                "Applicable industrial or laboratory inspections"],
            "context_specs":[
                ("Instrument Type","Leak detector"),
                ("Intended Function","Leak location or indication"),
                ("Inspection Category","Maintenance and quality-control leak checks"),
                ("Detection Medium","Confirm for exact model")],
            "context_source":"" }
    if "analy" in name:
        typ="analytical laboratory instrument"
    elif "tester" in name or "testing apparatus" in name:
        typ="laboratory and industrial testing instrument"
    elif "meter" in name:
        typ="measurement instrument"
    else:
        typ="laboratory or industrial instrumentation product"
    return {
        "type":typ,
        "function":(
            "is an instrument identified for the measurement, "
            "analytical or testing purpose stated in its product "
            "name. It is presented here to help buyers review "
            "the product identity and the technical information "
            "available for the selected configuration."),
        "use":(
            "It may be considered for work matching its documented "
            "purpose and required performance. Before purchasing, "
            "confirm the exact model, measurement principle, "
            "included accessories, installation requirements "
            "and compatible applications from an authoritative "
            "datasheet or supplier specification."),
        "features":[
            "Instrument category aligned with the stated product purpose",
            "Suitable tasks depend on the documented measurement or test method",
            "Exact-model technical limits require datasheet confirmation"],
        "applications":[],
        "context_specs":[
            ("Instrument Type",typ),
            ("Intended Function","Product purpose as identified in the product name"),
            ("Application Category","Laboratory or industrial instrumentation"),
            ("Technical Configuration","Exact-model datasheet confirmation required")],
        "context_source":"" }

def _conflicting_model(text, selected):
    if not selected:
        return False
    ids=re.findall(r"\bmodel\s*(?:number|no\.?)?\s*:?\s*([A-Za-z0-9_-]{3,35})",
                   str(text),re.I)
    return any(v.casefold()!=selected.casefold() and bool(re.search(r"\d",v))
               for v in ids)

def _source_sentences(raw,selected_model):
    # Public listings frequently concatenate multiple search results and ads.
    # Use only product-specific prose with no marketing, model conflict or URLs.
    sentences=[]
    for piece in re.split(r"(?<=[.!?])\s+",clean(raw,2600)):
        piece=piece.strip(" .;")
        if (len(piece)<45 or _ADS.search(piece) or "http" in piece.casefold()
                or _conflicting_model(piece,selected_model)):
            continue
        if len(_WORDS.findall(piece))>60:
            continue
        if re.search(r"\b(?:products?|suppliers?|manufacturers?)\s+(?:price|online|in india)\b",piece,re.I):
            continue
        sentences.append(piece+".")
    return _unique(sentences,2)

def _feature_from_fact(key,value,product):
    field=key.casefold().strip()
    if field in ("brand","model","model number","model no","manufacturer",
                 "country of origin"):
        return ""
    if field in ("number of positions","stirring positions"):
        return (value+" stirring positions" if "stirrer" in product.casefold()
                else value+" positions")
    if field=="speed range":
        return "Variable speed range: "+value
    if field in ("top plate","top plate material"):
        return value+" top plate"
    if field in ("body","body material"):
        return value+" body construction"
    if field=="power supply":
        return value+" power supply"
    if field in ("heating","heating plate") and ("without" in value.casefold() or "no hot" in value.casefold()):
        return "Without a hot plate or heating function"
    if field=="speed control":
        return value+" speed regulation"
    return key+": "+value

def make_draft(payload):
    if not isinstance(payload,dict):
        raise ValueError("Product data must be an object.")
    name=clean(payload.get("product"),180)
    if not name:
        raise ValueError("Product name required.")
    model=clean(payload.get("model"),100)
    profile=_type_profile(name)
    source_url=clean(payload.get("source_url"),500)
    operator=str(payload.get("specifications") or "")[:4500]
    source=str(payload.get("source_specifications") or "")[:4500]
    source_description=str(payload.get("source_description") or "")[:2600]
    if _conflicting_model(source,model):
        source=""  # Do not borrow any details from a known wrong-model sheet.
    inline=re.sub(r"[;|]\s*(?=[A-Za-z][A-Za-z /()]{2,50}\s*:)",
                  "\n",source_description)
    if _conflicting_model(inline,model) or _ADS.search(inline):
        inline=""
    technical=[]
    seen=set()
    for raw,basis in ((operator,"user_supplied"),(source,"supplier_claimed"),
                      (inline,"supplier_claimed")):
        for key,value in extract_pairs(raw,limit=30):
            if (model and key.casefold() in ("model","model number","model no")
                    and value.casefold()!=model.casefold()):
                continue
            if key.casefold() in seen:
                continue
            seen.add(key.casefold())
            technical.append({
                "parameter":key, "value":value,
                "verification_status":basis,
                "source_url":source_url if basis=="supplier_claimed" else ""
            })
            if len(technical)>=25:
                break
    if model and not any(v["parameter"].casefold() in ("model","model number","model no")
                         for v in technical):
        technical.insert(0,{"parameter":"Model","value":model,
                            "verification_status":"user_supplied","source_url":""})
    # All product categories need useful non-numeric technical context, even
    # when web research does not return a datasheet. Never invent an accuracy,
    # channel count, speed, capacity, power requirement or other model value.
    if not profile.get("context_specs"):
        profile["context_specs"]=[
            ("Instrument Type",profile.get("type") or "Industrial instrument"),
            ("Intended Function","Product category identified by the product name"),
            ("Technical Configuration","Manufacturer model details require confirmation")]
    # Useful category-level parameters belong in the specification table,
    # but must never be mistaken for exact-model numerical performance.
    # The source names the family/application, not this operator's SKU.
    for parameter,value in profile.get("context_specs",[]):
        if parameter.casefold() in seen:
            continue
        technical.append({
            "parameter":parameter,"value":value,
            "verification_status":"product_type_context_not_model_verified",
            "source_url":profile.get("context_source","")})
        seen.add(parameter.casefold())
    details={v["parameter"].casefold():v["value"] for v in technical}
    brand=details.get("brand") or details.get("manufacturer") or ""
    country=details.get("country of origin") or ""
    factual=[(v["parameter"],v["value"]) for v in technical
             if v["verification_status"] != "product_type_context_not_model_verified"
             and v["parameter"].casefold() not in
             ("brand","model","model number","model no","manufacturer","country of origin")]
    features=_as_lines(payload.get("key_features") or payload.get("features"),10)
    features += [_feature_from_fact(key,value,name) for key,value in factual]
    # Product-type principles are typical functional characteristics; never
    # present them as manufacturer-confirmed model-specific features.
    features+=profile["features"]
    features=_unique(features,REFERENCE_FEATURES)
    applications=_as_lines(payload.get("applications"),REFERENCE_APPLICATIONS)
    applications=_unique(applications+profile["applications"],REFERENCE_APPLICATIONS)
    intro=name+" "+profile["function"]
    sourced=_source_sentences(source_description,model)
    if sourced:
        # Introduce a clean matching page statement, not an index advertisement.
        intro+=" "+sourced[0]
    supplier_lines=[]
    if model:
        supplier_lines.append("model "+model)
    if brand:
        supplier_lines.append("brand "+brand)
    if country:
        supplier_lines.append("country of origin listed as "+country)
    if supplier_lines:
        opener="The available product information identifies "+", ".join(supplier_lines)+"."
    else:
        opener="The current public information identifies the requested product type but supplies limited model-specific technical data."
    if factual:
        claims=" Source-stated values include "+", ".join(
            key.casefold()+" "+value for key,value in factual[:3])+"."
    else:
        claims=""
    close=(" Confirm performance limits, supplied accessories, electrical "
           "requirements and the final configuration from the exact-model "
           "datasheet before publishing or placing an order.")
    second=opener+" "+profile["use"]+claims+close
    # Keep the reference's two full paragraphs; no repeated shopping copy.
    # If product data is sparse, be useful about the method and qualification,
    # rather than inventing 10 exact-model specifications.
    description=intro.strip()+"\n\n"+second.strip()
    specs_str="\n".join(x["parameter"]+": "+x["value"] for x in technical)
    return {
        "product_name":name,"model":model,
        "product_type":profile["type"],
        "description":description[:2300],
        "description_word_count":len(_WORDS.findall(description)),
        "description_target_words":list(TARGET_DESCRIPTION_WORDS),
        "summary":clean(intro,450),
        "mini_caption":name,
        "key_features":features,
        "technical_specifications":technical,
        "applications":applications,
        "applications_basis":"product_type_typical_not_model_verified",
        "category_specifications_basis":"product_type_context_not_model_verified",
        "keywords":[name]+([model] if model else []),
        "verified_specifications":specs_str,
        "provider":"template",
        "model_used":"Evidence-based catalogue writer (not AI)",
        "verification_status":"operator_review_required",
        "note":("Full reference-style content from explicit supplier facts plus "
                "general instrument-type principles. Typical applications "
                "require suitability confirmation; model specifications are not fabricated.")
    }
