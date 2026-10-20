"""Honest, deterministic preparation for NUNES two-page Full Catalogues.

Keep manufacturer-sourced information distinct from general instrument-type
context; no guessed numerical specification or filler features are created.
Only Full Catalogue uses these helpers. Mini remains unchanged.
"""
import re
from typing import Iterable, Tuple, List

_CONTEXT_FIELDS = frozenset({
    "instrument type", "test category", "typical operating context",
    "intended function", "measurement function", "application category",
    "technical configuration", "typical sample type", "method category",
    "detection medium", "analysis principle",
})
_UNVERIFIED_VALUES = (
    "verification required", "pending confirmation", "not specified",
    "exact-model datasheet", "product category identified",
    "product purpose as identified", "manufacturer model details",
    "not verified", "to be confirmed", "confirm for exact model",
    "model details require confirmation", "datasheet confirmation",
    "laboratory or industrial instrumentation", "not supplied",
)

def select_specs(items: Iterable[Tuple[str, str]], limit: int = 5) -> List[Tuple[str, str]]:
    """Prefer concrete supplied values over generic product-family context.

    Does not synthesize rows. Preserves source order within each class.
    Filters placeholders and duplicate parameter names. The original editor
    retains all values; only the printed reference table is limited to five.
    """
    seen = set()
    pairs = []
    for index, pair in enumerate(items or ()):
        try:
            key, value = pair
        except (ValueError, TypeError):
            continue
        key = re.sub(r"\s+", " ", str(key)).strip()
        value = re.sub(r"\s+", " ", str(value)).strip()
        norm = key.casefold()
        if not key or not value or norm in seen:
            continue
        if any(bad in value.casefold() for bad in _UNVERIFIED_VALUES):
            continue
        seen.add(norm)
        priority = 1 if norm in _CONTEXT_FIELDS else 0
        pairs.append((priority, index, (key, value)))
    pairs.sort(key=lambda entry: (entry[0], entry[1]))
    return [pair for _, _, pair in pairs[:max(1, limit)]]

def select_features(items, limit: int = 8):
    """Trim extras for the fixed reference format; never pad missing facts."""
    result = []
    seen = set()
    for item in items or ():
        text = re.sub(r"\s+", " ", str(item)).strip().lstrip("•-* ").strip()
        if not text or text.casefold() in seen:
            continue
        result.append(text)
        seen.add(text.casefold())
        if len(result) >= limit:
            break
    return result


# The Full Catalogue copy enhancer expands ONLY prose and user-supplied
# product-family feature wording. It never manufactures parameters, quantities,
# model-specific hardware, detection media, approvals or numeric performance.
_WORD_RE = re.compile(r"\b[\w][\w/-]*\b", re.UNICODE)
_MARKETPLACE_COPY = re.compile(
    r"(?i)(?:trader\s*[-–]\s*wholesaler|wholesaler\s*/\s*distributor|"
    r"\b(?:dealers?|suppliers?|manufacturers?)\s*(?:in|of|at best)|"
    r"\bat best price\b|\bget latest price\b|\bverified companies\b|"
    r"\balso get\b|\bfrom (?:india|our (?:company|catalogue))\b|"
    r"\bquote\s*now\b|\bfind here online\b|"
    r"\bof the leak detectors manufactured\b|"
    r"\b(?:we offer|we are engaged in trading)\b)"
)

_FAMILY_CONTEXT = {
    "leak": {
        "intro": (
            "Leak Detector Kit is an inspection product category used to investigate "
            "suspected leakage in compatible industrial or maintenance systems. "
            "An appropriate test can help personnel identify areas requiring "
            "closer examination, but the underlying detection technology varies "
            "between products. Different kits are intended for different "
            "inspection media and test conditions."
        ),
        "guidance": [
            ("The correct procedure depends on the inspected medium, operating "
             "conditions and the detection principle supplied with the selected kit."),
            ("Check the exact manufacturer instructions, sensitivity information, "
             "accessories and permitted applications before selecting a kit for the job.")
        ],
        "qualifiers": [
            "for checking suspected leakage during planned equipment inspections",
            "where the chosen detector technology matches the inspected medium",
            "including routine servicing and maintenance investigations",
            "with findings interpreted according to the relevant test method",
            "because detector technology and supported media vary by model",
            "with exact compatibility established from the selected model datasheet"
        ]
    },
    "multimeter": {
        "intro": (
            "A digital multimeter is an electrical measurement instrument used "
            "to examine supported circuit quantities during installation, "
            "maintenance and troubleshooting. The functions available depend "
            "on the exact model and its test leads, ratings and selected "
            "measurement modes. Results must be interpreted within the "
            "instrument's documented measurement limits."
        ),
        "guidance": [
            ("Before testing, confirm the electrical safety category and voltage "
             "rating for the measurement environment and the selected test procedure."),
            ("Measurement range, resolution, protection and additional functions "
             "must be verified from the exact manufacturer's documentation.")
        ],
        "qualifiers": [
            "for measurements supported by the selected instrument mode",
            "subject to the documented input ratings and safety category",
            "during routine electrical equipment inspections",
            "with suitable test leads and the manufacturer-defined procedure",
            "while respecting the measurement range for the selected model"
        ]
    },
    "stirrer": {
        "intro": (
            "A laboratory magnetic stirrer is used to mix compatible liquid "
            "samples through magnetic coupling to a stirring bar placed in "
            "the vessel. Depending on the selected model, stirring capacity "
            "and speed control may differ. Operators should match vessel "
            "size, sample properties and any heating requirements to "
            "the manufacturer's declared configuration."
        ),
        "guidance": [
            ("Before use, verify the supplied top-plate material, suitable "
             "sample volume, speed setting and electrical requirements."),
            ("Operating limits and accessory compatibility depend on the exact "
             "model; unsupported capacities or temperature ranges are not assumed.")
        ],
        "qualifiers": [
            "for compatible mixing tasks and laboratory sample preparation",
            "within the manufacturer's stated vessel and load limits",
            "with the selected sample vessel and stir bar",
            "where the documented operating settings are followed",
            "subject to the actual model's heating and stirring configuration"
        ]
    },
    "pyrogen": {
        "intro": (
            "A digital pyrogen telethermometer is a laboratory temperature "
            "measurement instrument used in suitable animal-monitoring and "
            "experimental observation procedures. It supports review of "
            "temperature changes when operated with the correct "
            "measurement configuration. The supported probe arrangement, "
            "readout functions and test methods depend on the model."
        ),
        "guidance": [
            ("The laboratory should verify the selected measurement probes, "
             "channel arrangement and temperature accuracy using a matching datasheet."),
            ("Testing procedures must follow the site's approved protocol; "
             "no pharmacopoeial compliance is assumed without explicit evidence.")
        ],
        "qualifiers": [
            "during compatible laboratory temperature observation procedures",
            "when suitable probes and documented procedures are used",
            "with measurement accuracy checked against the exact model datasheet",
            "under the approved research protocol",
            "subject to the supplied channel and probe arrangement"
        ]
    },
    "generic": {
        "intro": (
            "This instrument belongs to the laboratory and industrial testing "
            "equipment category identified in the product name. Its suitability "
            "depends on the operating method and the exact "
            "manufacturer-supplied configuration. Product-family descriptions "
            "can explain typical workflows, but they do not prove "
            "model-specific performance or included accessories."
        ),
        "guidance": [
            ("Select a configuration only after checking the intended application, "
             "required measurements and environmental operating conditions."),
            ("Confirm interfaces, accessories, performance limits and any claimed "
             "compliance against the exact-model technical documentation.")
        ],
        "qualifiers": [
            "for work compatible with the documented instrument purpose",
            "using the manufacturer's specified operating procedure",
            "subject to the selected model's measurement limits",
            "with suitable accessories and operating conditions",
            "as appropriate to the application verified for that model"
        ]
    }
}


def _family(product):
    name = str(product or "").casefold()
    if any(term in name for term in (
            "blood analy", "hematol", "cell dyn", "cell-dyn",
            "cbc analyzer", "blood counter")):
        return "hematology"
    if "leak detect" in name or "leakfinder" in name:
        return "leak"
    if "multimeter" in name or "multi meter" in name:
        return "multimeter"
    if "magnetic stirrer" in name:
        return "stirrer"
    if "pyrogen" in name and ("thermometer" in name or "telethermometer" in name):
        return "pyrogen"
    return "generic"


def word_count(value):
    return len(_WORD_RE.findall(str(value or "")))


def _unpublishable_excerpt(text):
    text = str(text or "").strip()
    if _MARKETPLACE_COPY.search(text):
        return True
    if re.search(r"(?i)(?:\bfor|\bof|\bthe|\band|\bto|\bwith|\bfrom|\bby)\s*$", text):
        return True
    if re.search(r"[;:,]\s*$", text):
        return True
    return False


def enrich_full_copy(product, description, features, model=""):
    """Expand short Full PDF prose by about 20-50 *supported context* words.

    Descriptions from supplier indexes, broken/truncated excerpts or multiple
    unrelated products are rewritten as general product-family commentary.
    Numbers and exact-model claims are retained ONLY if already explicitly
    supplied in the clean input. Existing full detailed copy is preserved.
    The PDF can still be generated with fewer than eight genuine features.
    """
    profile = _FAMILY_CONTEXT[_family(product)]
    original = re.sub(r"\s+", " ", str(description or "")).strip()
    before_words = word_count(original)
    bad = _unpublishable_excerpt(original)
    if bad or before_words < 12:
        intro = profile["intro"]
        full = intro
        for sentence in profile["guidance"]:
            full += " " + sentence
        revised = full
        description_changed = revised != original
    elif before_words < 90:
        # Add one or two general usage/selection sentences, selecting only
        # complete sentences and preventing duplicates on repeated requests.
        revised = original
        budget = min(50, max(25, 96 - before_words))
        additions = 0
        for sentence in profile["guidance"]:
            n = word_count(sentence)
            if n > budget - additions + 6:
                continue
            if sentence.casefold() in revised.casefold():
                continue
            revised += " " + sentence
            additions += n
            if additions >= 22:
                break
        description_changed = revised != original
    else:
        revised = original
        description_changed = False

    raw_features = select_features(
        features.splitlines() if isinstance(features, str) else features,
        limit=10
    )
    out_features = []
    feature_extra = 0
    # Explain category-level feature phrases WITHOUT asserting new sensors,
    # functions or measurements about the photographed SKU.
    for index, feature in enumerate(raw_features):
        updated = feature
        if word_count(feature) <= 13 and word_count(" ".join(raw_features)) < 105:
            suffix = profile["qualifiers"][index % len(profile["qualifiers"])]
            suffix_words = word_count(suffix)
            if (feature_extra + suffix_words <= 50
                    and word_count(feature) <= 13
                    and suffix.casefold() not in feature.casefold()):
                updated = feature.rstrip(" .;") + " - " + suffix
                feature_extra += suffix_words
        out_features.append(updated)
    return {
        "description": revised,
        "key_features": out_features,
        "description_before_words": before_words,
        "description_after_words": word_count(revised),
        "description_added_words": word_count(revised) - before_words,
        "features_before_words": word_count(" ".join(raw_features)),
        "features_after_words": word_count(" ".join(out_features)),
        "features_added_words": feature_extra,
        "source_rewritten": bool(bad),
        "note": (
            "Product-family context was used only for prose. "
            "No exact-model specifications, detection technologies, performance "
            "limits or accessory claims were inferred."
        )
    }


# Professional 70-100-word section extensions. The initial source-backed
# version is retained and reused so previously generated drafts do not lose
# any actual technical facts. These sentences are product-FAMILY context,
# never model-confirmed numerical claims.
_previous_enrich_full_copy = enrich_full_copy

_ADDITIONAL_DESCRIPTION = {
    "leak": [
        "Inspection work begins by identifying the type of system under examination and the medium that might escape; the selected detection method must be suitable for both.",
        "Operators should distinguish an indication of suspected leakage from confirmation of its location, following the relevant test procedure before recording a conclusion.",
        "Access to joints, connections and other suspected areas may affect the practical inspection sequence, while environmental conditions can influence the chosen method.",
        "For purchasing comparisons, request the exact model datasheet and verify supported media, measurement limits, accessories and instructions against the intended maintenance task."
    ],
    "multimeter": [
        "Before taking a reading, the user should identify the expected quantity and choose an instrument setting suitable for the circuit under examination.",
        "Electrical safety requires attention to the selected equipment category, rated input limits and condition of the test leads, as described by the manufacturer.",
        "When comparing models, buyers can review the documented measurement functions, display resolution, permitted environments and protection information rather than relying on a product-family name.",
        "A complete technical assessment also checks whether the chosen meter and its supplied accessories match the actual maintenance or laboratory procedure."
    ],
    "stirrer": [
        "Laboratory mixing requirements should be defined by sample volume, viscosity, vessel geometry and the desired mixing procedure before the instrument is selected.",
        "Stirring performance can depend on the sample and the chosen bar and vessel, so manufacturer limits should be considered rather than assumed from appearance.",
        "The operator should verify speed control, surface construction, permissible load and any heating provision from the exact model documentation.",
        "For comparison between products, record the intended sample conditions and confirm that each declared capability meets the laboratory workflow."
    ],
    "pyrogen": [
        "The intended laboratory protocol determines how temperature readings are collected, monitored and recorded during the observation period.",
        "Probe selection, suitable attachment, sample context and channel arrangement should be confirmed against the selected model and any applicable test procedure.",
        "Where regulatory or pharmacopoeial requirements apply, suitability cannot be inferred merely from the instrument name and needs independent evidence.",
        "Before purchase, laboratories can compare the documented measurement range, accuracy, interfaces and accessories with their established experimental methods."
    ],
    "generic": [
        "Before deciding whether this instrument is appropriate, the buyer should define the material, sample, system or quantity that the equipment is expected to examine.",
        "Operating methods and configuration options differ between manufacturers, so a catalogue-level product name should not be treated as evidence of a particular capability.",
        "A technical comparison should use explicitly documented limits, the measurement or test principle, required accessories and applicable operating conditions.",
        "Any remaining uncertainty should be resolved with a matching model datasheet or a written supplier specification rather than an assumed performance figure."
    ]
}

_FEATURE_DETAIL_LONG = {
    "leak": [
        "This is a usage category; the supported sensing technology must be established from the exact product documentation.",
        "Match the procedure to the inspected medium and environment before treating an indication as confirmed leakage.",
        "Suitable inspection locations and maintenance intervals depend on equipment access and the chosen operating procedure.",
        "A suspected location should be checked by the selected method and assessed using relevant manufacturer instructions.",
        "Sensor method, supplied components, sensitivity and operating conditions remain model-dependent without an authoritative datasheet."
    ],
    "multimeter": [
        "This describes the instrument family; manufacturer documentation determines which measurement modes and ranges are present.",
        "Safe operation requires an appropriate input rating, test-lead condition and method for the circuit under examination.",
        "Technicians should select supported functions for the task rather than assuming every multimeter provides identical options.",
        "Each indicated quantity must be interpreted within the documented measurement limits and protection category.",
        "Before selection, review exact-model information for accuracy, resolution, supplied leads and permitted operating environment."
    ],
    "stirrer": [
        "Mixing suitability depends on vessel geometry, liquid properties and the exact manufacturer-declared stirring capacity.",
        "Any operating procedure should respect the selected model's speed range and compatible stirring-bar arrangement.",
        "Laboratory sample preparation requires control of vessel placement and the documented load and surface limits.",
        "Performance comparisons should consider the intended sample rather than treating model-family descriptions as test results.",
        "Heating provision, supplied accessories and electrical requirements must be verified against the selected product configuration."
    ],
    "pyrogen": [
        "This describes the measurement purpose and does not independently establish a channel count or probe arrangement.",
        "Use the readout within the documented sensor range and the approved laboratory observation procedure.",
        "Temperature trends require suitable probes, consistent technique and model-specific measurement accuracy information.",
        "Laboratories should record observations according to their approved protocol and the instrument's stated capabilities.",
        "Compatibility with a specific test method requires model-level technical evidence rather than a general category name."
    ],
    "generic": [
        "The actual operating method and compatible work must be established from the selected model's documentation.",
        "Select the required setting or configuration according to the task and the manufacturer-described procedure.",
        "This application depends on the supported measurement or testing principle and appropriate operating conditions.",
        "Performance should be interpreted within declared limits rather than inferred from general catalogue terminology.",
        "Verify included accessories, interfaces, ratings and any claimed compliance before specifying the exact configuration."
    ]
}
_FEATURE_DETAIL_SHORT = [
    "Confirm the particular operating limits and intended procedure for the exact model.",
    "Compare this function with the relevant task and documented equipment configuration.",
    "Use the stated method only under appropriate conditions and inspection requirements.",
    "Check whether any necessary accessories are included with the selected configuration.",
    "Model-specific ratings and performance must come from a traceable technical source.",
    "Review manufacturer instructions before assuming this function suits another application.",
    "Document the applicable measurement or test conditions during a technical comparison.",
    "Do not infer additional internal components or performance from the product photograph."
]


def build_specification_notes(specs, product=""):
    """80-100 words explaining HOW to read actual source-supplied pairs.

    The note is separate from the parameter/value table and must never be
    reported as an additional verified instrument specification. Missing
    ratings and model attributes stay missing.
    """
    chosen = select_specs(specs or [], limit=5)
    if not chosen:
        return ""
    compact = [(key, value) for key, value in chosen
               if word_count(key) + word_count(value) <= 12][:2]
    if compact:
        claims = " and ".join(key + " as " + value for key, value in compact)
        intro = (
            "The supplied information lists " + claims + ". "
            "These are recorded source values, not independent test results."
        )
    else:
        intro = (
            "These technical entries reproduce the available source values "
            "and must not be interpreted as independent laboratory verification."
        )
    sentences = [
        "Read the stated parameters alongside the intended measurement method, sample conditions and actual instrument configuration.",
        "When comparing possible models, check whether each listed value applies to the specific variant and operating procedure.",
        "Any omitted capacity, accuracy, detection limit, electrical rating or accessory information must remain unconfirmed until supported by a source.",
        "Published test methods should be matched against the sample and the chosen equipment configuration.",
        "Confirm units and compatibility with a matching manufacturer datasheet before an order is placed.",
        "A product-family description alone does not establish a numerical performance figure."
    ]
    chunks = [intro]
    for line in sentences:
        n = word_count(" ".join(chunks))
        if n >= 78:
            break
        if n + word_count(line) <= 98:
            chunks.append(line)
    return " ".join(chunks)


_FAMILY_CONTEXT["hematology"] = {
    "intro": (
        "A blood analyzer is used within laboratory workflows to examine "
        "blood specimens under compatible testing procedures. The analytical "
        "technology, supported parameters, sample capacity and reporting "
        "functions depend on the selected model. A product-family description "
        "does not establish a specific instrument's diagnostic suitability "
        "or manufacturer-confirmed performance."
    ),
    "guidance": [
        "Before selecting the instrument, laboratories should review intended sample types, validated analytical methods, throughput needs and quality-control requirements.",
        "Reagent compatibility, maintenance procedures, data interfaces and applicable clinical claims must be checked against the actual supplier documentation."
    ],
    "qualifiers": [
        "according to the applicable laboratory procedure and sample type",
        "with supported test parameters established from the model datasheet",
        "under laboratory quality-control and routine maintenance procedures",
        "subject to the documented reagent and accessory requirements",
        "with validated analytical performance verified for the exact model"
    ]
}

# The descriptions below are PRODUCT-FAMILY workflow guidance only.
# They do NOT assert exact-model precision, throughput, capacity, feature
# availability, supplied accessories, approval or a real manufacturer's ID.
_FAMILY_FEATURE_CANDIDATES = {
    "leak": [
        "Inspection purpose: investigate suspected leakage using an appropriate test method",
        "Detection method selection depends on the inspected medium and accessible equipment",
        "Field use requires a procedure compatible with the selected kit and environment",
        "Leak indications must be assessed using the manufacturer's documented method",
        "Inspection planning can include joints, seals and accessible connection points",
        "The appropriate test approach differs across fluids, gases and other media",
        "Technicians should interpret results within the stated detection method limits",
        "Model-specific sensor, accessory and sensitivity details require source confirmation",
        "Routine maintenance checks should follow established equipment inspection procedures",
        "Product comparison considers the medium, environment and operator requirements"
    ],
    "multimeter": [
        "Instrument category supports electrical measurement workflows where compatible",
        "The selected model determines supported quantities, measurement ranges and modes",
        "Electrical safety category and voltage limits require exact-model confirmation",
        "Test-lead suitability matters for the circuit and the selected measurement",
        "Range selection should follow the instrument's specified operating method",
        "Technicians should check display resolution and accuracy against stated values",
        "Electrical troubleshooting requires an appropriate method and safe access",
        "Measurement readings should be interpreted within documented input limits",
        "Maintenance workflows may include comparison with known reference conditions",
        "Function and accessory options vary across digital multimeter model families"
    ],
    "stirrer": [
        "Magnetic stirring is a common method for compatible liquid sample mixing",
        "The mixing workflow depends on vessel geometry and sample properties",
        "An appropriately selected stir bar is part of a typical magnetic mixing method",
        "Speed and mixing-load limits must match the documented model configuration",
        "The stirring surface and permissible vessel types require product confirmation",
        "Heating capability is not assumed from a general magnetic stirrer title",
        "Laboratory operators should consider sample volume before instrument selection",
        "Stirring conditions are selected according to the applicable laboratory procedure",
        "Equipment comparisons depend on declared capacity and operating conditions",
        "Accessory compatibility and electrical requirements are model-dependent"
    ],
    "pyrogen": [
        "The instrument category relates to laboratory temperature-observation workflows",
        "Temperature measurements follow an approved test or research procedure",
        "Suitable measurement probes depend on the actual channel configuration",
        "Laboratory monitoring requires consistent application of the chosen protocol",
        "Supported probe arrangement must be confirmed from the selected model source",
        "Recorded temperature changes should be interpreted in experimental context",
        "Measurement accuracy and permitted ranges depend on the manufacturer datasheet",
        "Any specific pharmacopeial application requires independently supported evidence",
        "Channel count and data interfaces must not be inferred from the product title",
        "Operator training includes correct probe handling and measurement practice"
    ],
    "hematology": [
        "The product family is associated with laboratory blood-sample analysis workflows",
        "Actual hematology test parameters depend on the instrument configuration",
        "Sample preparation and handling must follow the compatible laboratory procedure",
        "Supported analysis methods require confirmation from the selected model source",
        "Laboratory operators should review the documented sample-type requirements",
        "Results must be assessed using validated laboratory quality-control procedures",
        "Reported test parameters and processing functions vary between instruments",
        "Maintenance needs and compatible reagents depend on the actual configuration",
        "Product comparison includes throughput, interfaces and documented measurement claims",
        "Any claimed regulatory or clinical suitability needs independent source evidence"
    ],
    "generic": [
        "Instrument family relates to its stated industrial or laboratory test purpose",
        "Suitable operating methods depend on the exact product configuration",
        "Technical selection begins with the measurement or sample requirement",
        "A compatible procedure must follow the documented equipment method",
        "Model variants can differ in controls, interfaces and available functions",
        "Required accessories should be checked against the actual supplier information",
        "Operating environment and workload affect model selection and suitability",
        "Measurements or test outcomes need interpretation within declared limitations",
        "Model-specific performance values require a matching technical datasheet",
        "Technical review should confirm the intended application and supplied setup"
    ],
}
_FAMILY_FEATURE_CANDIDATES["generic"] += [
    "Installation and upkeep requirements depend on manufacturer documentation",
    "Quality-control procedures should match the verified test configuration",
]


def _description_target(product, legacy_text):
    """Raise short source-based copy into 150–200 words, keeping sentences whole.

    A long user-supplied paragraph is left unchanged rather than silently
    deleting possibly verified statements. Idempotent on repeat generation.
    """
    base=re.sub(r"\s+"," ",str(legacy_text or "")).strip()
    family=_family(product)
    pool=list(_ADDITIONAL_DESCRIPTION.get(family, _ADDITIONAL_DESCRIPTION["generic"]))
    source=_FAMILY_CONTEXT.get(family,_FAMILY_CONTEXT["generic"])
    pool.extend(source["guidance"])
    pool.extend(_ADDITIONAL_DESCRIPTION["generic"])
    out=base
    for sentence in pool:
        if word_count(out)>=150:break
        sentence=sentence.strip()
        if not sentence or sentence.casefold() in out.casefold():continue
        if word_count(out)+word_count(sentence)>200:continue
        out=(out.rstrip(" .;")+". " if out else "")+sentence
    return out


def _feature_target(product, original_features):
    """Retain supplied facts and add *labelled category-level* useful lines.

    Missing manufacturer specifications are never presented as model-proven.
    Repeat calls are stable; no duplicated pseudo-features.
    """
    raw=select_features(original_features,limit=10)
    if len(raw)>=8:return raw[:10]
    family=_family(product)
    candidates=_FAMILY_FEATURE_CANDIDATES.get(
        family,_FAMILY_FEATURE_CANDIDATES["generic"])
    seen={re.sub(r"[^a-z0-9]+"," ",s.lower()).strip() for s in raw}
    for candidate in candidates:
        key=re.sub(r"[^a-z0-9]+"," ",candidate.lower()).strip()
        if key in seen:continue
        raw.append(candidate+" (product-family context)")
        seen.add(key)
        if len(raw)>=8:break
    return raw


def enrich_full_copy(product, description, features, model="", specs=None):
    """Generate a reviewable Full draft: 150–200 words, 8–10 feature lines.

    The text is either source-supplied or clearly product-family guidance.
    It is NOT proof of exact-model design or manufacturer verification.
    The source values, model and numeric technical parameters are unchanged.
    Works for single-product PDFs and every source-supported batch product.
    """
    if not str(product or "").strip():
        raise ValueError("A product name is required to prepare catalogue copy")
    # Preserve original source facts and the existing conservative
    # anti-marketplace cleaning, but never pad facts with fictional numbers.
    legacy=_previous_enrich_full_copy(product,description,features,model)
    text=_description_target(product,legacy["description"])
    source_features=list(legacy["key_features"])
    # For any feature-rich exact-model input, keep original wording; for sparse
    # data, make generic context explicit rather than posing as a specification.
    feature_lines=_feature_target(product,source_features)
    # De-duplicate on a second enrichment pass.
    original_lines=select_features(
        features.splitlines() if isinstance(features,str) else features,
        limit=10)
    notes=build_specification_notes(specs or [],product)
    result=dict(legacy)
    result.update(
        description=text,
        key_features=feature_lines,
        description_before_words=word_count(description),
        description_after_words=word_count(text),
        description_added_context_words=max(
            0,word_count(text)-word_count(legacy["description"])),
        description_added_words=word_count(text)-word_count(description),
        features_before_words=word_count(" ".join(original_lines)),
        features_after_words=word_count(" ".join(feature_lines)),
        features_added_context_words=max(0,
            word_count(" ".join(feature_lines))-
            word_count(" ".join(legacy["key_features"]))),
        features_added_words=word_count(" ".join(feature_lines))-
            word_count(" ".join(original_lines)),
        feature_line_count=len(feature_lines),
        target_description_words=[150,200],
        target_feature_lines=[8,10],
        description_in_target=150<=word_count(text)<=200,
        features_in_target=8<=len(feature_lines)<=10,
        specification_notes=notes,
        specification_notes_words=word_count(notes),
        specification_added_words=word_count(notes),
        technical_row_count=len(select_specs(specs or [],limit=5)),
        content_basis=(
            "Product-specific numeric specifications stay source supplied. "
            "Context-only feature lines are marked product-family context; "
            "the catalogue requires exact-model review before publication."
        ),
    )
    return result
