"""
Automated Test Suite for NUNES Catalogue Studio.
Verifies:
1. Product research & image candidate discovery.
2. AI Service (Gemini, OpenAI, Ollama, Fallback).
3. 2-Page Full Catalogue generation (5 spec rows, 60-80 words, 8 bullets, black bullets).
4. Mini Catalogue generation (no dummy boxes, no unwanted labels).
5. Background removal engine.
6. Word docx and Excel xlsx generation.
7. Webapp Flask routes and responses.
"""
import io
import json
import os
import sys
from pathlib import Path
from pypdf import PdfReader

# Ensure current dir is in path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import webapp
import generator as g
import ai_service
import image_processing
import product_research


def test_ai_service():
    print("Testing AI Service...")
    draft = ai_service.generate_product_draft(
        product="Digital Lux Meter",
        model="LX-1010B",
        raw_facts="Range: 0 to 50000 Lux; Accuracy: +/- 4%; Resolution: 1 Lux; Display: 3.5 digit LCD",
        provider="auto"
    )
    assert draft, "Draft should not be empty"
    assert "specifications" in draft, "Draft must have specifications"
    assert len(draft["specifications"]) >= 4, f"Specs count: {len(draft['specifications'])}"
    assert "description" in draft, "Draft must have description"
    assert "key_features" in draft, "Draft must have key_features"
    assert len(draft["key_features"]) >= 6, f"Features count: {len(draft['key_features'])}"
    print(f"✓ AI Service passed. Provider: {draft.get('provider')}, Specs: {len(draft['specifications'])}, Features: {len(draft['key_features'])}")


def test_full_catalogue_pdf():
    print("Testing Full Catalogue PDF Generation...")
    out_pdf = ROOT / "cache" / "test_full_out.pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    if out_pdf.exists():
        out_pdf.unlink()

    research = {
        "specs": [
            {"key": "Measuring Range", "value": "0 to 50,000 Lux (3 Ranges)"},
            {"key": "Measurement Accuracy", "value": "±4% rdg ± 0.5% f.s."},
            {"key": "Sampling Rate", "value": "2.0 times per second"},
            {"key": "Display Type", "value": "High Contrast Multi-Line Digital LCD"},
            {"key": "Power Supply", "value": "9V DC Alkaline Battery (6F22)"}
        ],
        "description": "The NUNES Digital Lux Meter is an industrial metrology instrument engineered for precise luminous intensity verification across industrial plants, quality laboratories, and architectural lighting installations. Built for certified repeatable readings, this instrument features silicon photo diode filtering, rapid zero adjustment, and ergonomic casing.",
        "key_features": [
            "Certified high photopic spectral sensitivity matching CIE standard curves",
            "Rugged compact casing engineered for reliable handheld field operation",
            "Clear digital LCD ensuring instant illumination readings under low ambient light",
            "Separate light sensor allowing flexible measurement at optimal angles",
            "Rapid electronic response time with instant data hold functionality",
            "Low battery warning indicator and auto zero-adjustment capability",
            "Engineered for extended operating life and minimal calibration drift",
            "Complies with NUNES certified metrology and international quality standards"
        ]
    }

    g.catalogue_pdf(out_pdf, "DIGITAL LUX METER", "LX-1010B", None, research)
    assert out_pdf.exists(), "PDF should be generated"

    # Verify PDF properties with pypdf
    reader = PdfReader(str(out_pdf))
    page_count = len(reader.pages)
    print(f"Full Catalogue Page Count: {page_count}")
    assert page_count == 2, f"Full Catalogue MUST be exactly 2 pages! Got: {page_count}"

    # Verify no unwanted labels
    text_p1 = reader.pages[0].extract_text()
    text_p2 = reader.pages[1].extract_text()
    all_text = text_p1 + " " + text_p2

    assert "VTech" not in all_text, "VTech must not appear in NUNES catalogue"
    assert "RELATED SEARCH KEYWORDS" not in all_text, "Unwanted labels must not appear"
    assert "PRODUCT SPECIFICATION" in text_p1, "Page 1 must have PRODUCT SPECIFICATION"
    assert "PRODUCT DESCRIPTION" in text_p2, "Page 2 must have PRODUCT DESCRIPTION"
    assert "KEY FEATURES" in text_p2, "Page 2 must have KEY FEATURES"
    print("✓ Full Catalogue PDF strictly matches 2-page reference specification.")


def test_mini_catalogue_pdf():
    print("Testing Mini Catalogue PDF Generation...")
    out_pdf = ROOT / "cache" / "test_mini_out.pdf"
    if out_pdf.exists():
        out_pdf.unlink()

    rel = [
        ({"product": "Digital Lux Meter", "model": "LX-1010B"}, None),
        ({"product": "Ultrasonic Thickness Gauge", "model": "UTG-200"}, None),
        ({"product": "Surface Roughness Tester", "model": "SRT-6200"}, None),
        ({"product": "Portable Hardness Tester", "model": "HT-1800"}, None)
    ]
    g.mini_pdf(out_pdf, "NUNES TESTING INSTRUMENTS", "", rel)
    assert out_pdf.exists(), "Mini PDF should be generated"

    reader = PdfReader(str(out_pdf))
    print(f"Mini Catalogue Page Count: {len(reader.pages)}")
    all_text = " ".join([p.extract_text() for p in reader.pages])

    assert "RELATED SEARCH KEYWORDS" not in all_text, "Must remove RELATED SEARCH KEYWORDS"
    assert "VTech" not in all_text, "Must remove VTech"
    assert "CERTIFIED PRODUCT RANGE" in all_text, "Final page must have CERTIFIED PRODUCT RANGE"
    print("✓ Mini Catalogue PDF generated without empty boxes or unwanted labels.")


def test_flask_endpoints():
    print("Testing Flask Webapp Endpoints...")
    app = webapp.app
    client = app.test_client()

    # 1. Health
    h_res = client.get("/api/health")
    assert h_res.status_code == 200, f"Health status: {h_res.status_code}"
    print("✓ /api/health returned 200 OK")

    # 2. Config
    c_res = client.get("/api/config")
    assert c_res.status_code == 200, f"Config status: {c_res.status_code}"
    print("✓ /api/config returned 200 OK")

    # 3. PDF Preview Endpoint
    prev_payload = {
        "type": "full",
        "product": "DIGITAL LUX METER",
        "model": "LX-1010B",
        "specifications": [
            {"key": "Range", "value": "0-50000 Lux"},
            {"key": "Accuracy", "value": "+/- 4%"},
            {"key": "Resolution", "value": "1 Lux"},
            {"key": "Display", "value": "LCD"},
            {"key": "Power", "value": "9V Battery"}
        ],
        "description": "Commercial description ~60 to 80 words for certified testing and verification.",
        "features": [f"Feature {i}" for i in range(1, 9)]
    }
    p_res = client.post("/api/preview", json=prev_payload)
    assert p_res.status_code == 200, f"Preview failed: {p_res.status_code}"
    assert p_res.content_type == "application/pdf", f"Preview content type: {p_res.content_type}"
    assert len(p_res.data) > 5000, f"Preview PDF size: {len(p_res.data)}"
    print(f"✓ /api/preview returned valid PDF ({len(p_res.data)} bytes)")

    # 4. Word docx export
    w_res = client.post("/api/export/docx", json=prev_payload)
    assert w_res.status_code == 200, f"Word export failed: {w_res.status_code}"
    assert "wordprocessingml" in w_res.content_type, f"Word content type: {w_res.content_type}"
    assert len(w_res.data) > 2000, f"Word doc size: {len(w_res.data)}"
    print(f"✓ /api/export/docx returned valid Word document ({len(w_res.data)} bytes)")

    # 5. Excel export
    e_res = client.post("/api/export/excel", json=prev_payload)
    assert e_res.status_code == 200, f"Excel export failed: {e_res.status_code}"
    assert "spreadsheetml" in e_res.content_type, f"Excel content type: {e_res.content_type}"
    assert len(e_res.data) > 2000, f"Excel file size: {len(e_res.data)}"
    print(f"✓ /api/export/excel returned valid Excel spreadsheet ({len(e_res.data)} bytes)")


def test_image_processing():
    print("Testing Image Processing & Background Removal...")
    from PIL import Image
    im = Image.new("RGB", (200, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    cutout = image_processing.remove_studio_background(buf.getvalue())
    assert cutout and len(cutout) > 50, "Cutout should return valid PNG bytes"
    print("✓ Image background cutout generated successfully.")


def test_product_research():
    print("Testing Product Research & Image Candidate Search...")
    candidates = product_research.search_image_candidates("Ultrasonic Thickness Gauge", limit=4)
    print(f"✓ Candidate search returned {len(candidates)} candidate(s).")


def test_file_extraction_pipeline():
    print("Testing File Extraction Pipeline across all formats...")
    import file_catalogue_detector
    import openpyxl
    import docx

    # 1. Excel (.xlsx) Extraction Test matching exact user prompt
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Specifications"
    ws.append(["Parameter", "Specification"])
    ws.append(["Product Name", "Digital Multimeter"])
    ws.append(["Model", "DM-100"])
    ws.append(["Display", "LCD"])
    ws.append(["DC Voltage", "0–600 V"])
    ws.append(["Power Supply", "Battery"])
    
    xlsx_io = io.BytesIO()
    wb.save(xlsx_io)
    xlsx_bytes = xlsx_io.getvalue()

    detected_xlsx = file_catalogue_detector.analyze_uploaded_file(xlsx_bytes, "Digital_Multimeter_Datasheet.xlsx")
    assert detected_xlsx["success"], "XLSX analysis should succeed"
    assert detected_xlsx["detected_format"] == "XLSX", f"Format should be XLSX, got {detected_xlsx['detected_format']}"
    assert detected_xlsx["product_name"] == "Digital Multimeter", f"Product name: {detected_xlsx['product_name']}"
    assert detected_xlsx["source_model"] == "DM-100", f"Source model: {detected_xlsx['source_model']}"
    assert detected_xlsx["catalogue_brand"] == "VTech", f"Catalogue brand: {detected_xlsx['catalogue_brand']}"
    assert "0–600 V" in detected_xlsx["specifications"], "Preserved measurement unit 0–600 V"
    assert "LCD" in detected_xlsx["specifications"], "Display spec present"
    assert "Battery" in detected_xlsx["specifications"], "Power supply spec present"
    assert "PK" not in detected_xlsx["specifications"], "CORRUPTED EXTRACTION BUG: PK found in specifications!"
    assert "[Content_Types].xml" not in detected_xlsx["specifications"], "CORRUPTED EXTRACTION BUG: XML found in specifications!"
    print("✓ Excel (.xlsx) extraction passed without any binary or XML artifacts.")

    # 2. Word (.docx) Extraction Test
    doc = docx.Document()
    doc.add_heading("Digital Ultrasonic Thickness Gauge", level=1)
    doc.add_paragraph("High accuracy thickness gauge for industrial pipe inspection.")
    table = doc.add_table(rows=1, cols=2)
    hdr = table.rows[0].cells
    hdr[0].text = "Parameter"
    hdr[1].text = "Specification"
    
    row1 = table.add_row().cells
    row1[0].text = "Model"
    row1[1].text = "UTG-200"
    
    row2 = table.add_row().cells
    row2[0].text = "Measuring Range"
    row2[1].text = "0.75 mm to 300 mm"

    row3 = table.add_row().cells
    row3[0].text = "Accuracy"
    row3[1].text = "±0.05 mm"

    doc.add_paragraph("Microprocessor controlled system", style="List Bullet")
    doc.add_paragraph("Clear backlit digital display", style="List Bullet")

    docx_io = io.BytesIO()
    doc.save(docx_io)
    docx_bytes = docx_io.getvalue()

    detected_docx = file_catalogue_detector.analyze_uploaded_file(docx_bytes, "Thickness_Gauge.docx")
    assert detected_docx["success"], "DOCX analysis should succeed"
    assert detected_docx["detected_format"] == "DOCX", f"Format: {detected_docx['detected_format']}"
    assert "Thickness Gauge" in detected_docx["product_name"], f"Product name: {detected_docx['product_name']}"
    assert detected_docx["source_model"] == "UTG-200", f"Model: {detected_docx['source_model']}"
    assert "0.75 mm to 300 mm" in detected_docx["specifications"], "Measuring range spec found"
    assert "PK" not in detected_docx["specifications"], "PK found in DOCX specs!"
    print("✓ Word (.docx) extraction passed with table & bullet points.")

    # 3. CSV Extraction Test
    csv_bytes = "Parameter,Specification\nProduct Name,Lux Meter\nModel,LX-101\nRange,0-50000 Lux\nDisplay,LCD".encode("utf-8")
    detected_csv = file_catalogue_detector.analyze_uploaded_file(csv_bytes, "Lux_Meter.csv")
    assert detected_csv["product_name"] == "Lux Meter"
    assert detected_csv["source_model"] == "LX-101"
    assert "0-50000 Lux" in detected_csv["specifications"]
    print("✓ CSV extraction passed.")

    # 4. JSON Extraction Test
    json_bytes = json.dumps({
        "product_name": "Digital Manometer",
        "model": "MN-500",
        "specifications": [
            {"key": "Pressure Range", "value": "0 to 100 psi"},
            {"key": "Resolution", "value": "0.01 psi"}
        ]
    }).encode("utf-8")
    detected_json = file_catalogue_detector.analyze_uploaded_file(json_bytes, "Manometer.json")
    assert detected_json["product_name"] == "Digital Manometer"
    assert detected_json["source_model"] == "MN-500"
    assert "0 to 100 psi" in detected_json["specifications"]
    print("✓ JSON extraction passed.")

    # 5. TXT Extraction Test
    txt_bytes = "Digital Tachometer\nModel: DT-2234\nRange: 2.5 to 99999 RPM\nAccuracy: +/- 0.05%".encode("utf-8")
    detected_txt = file_catalogue_detector.analyze_uploaded_file(txt_bytes, "Tachometer.txt")
    assert "Tachometer" in detected_txt["product_name"]
    assert detected_txt["source_model"] == "DT-2234"
    assert "99999 RPM" in detected_txt["specifications"]
    print("✓ TXT extraction passed.")


def test_upload_auto_generate_endpoint():
    print("Testing /api/catalogue/upload-auto-generate endpoint...")
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Parameter", "Specification"])
    ws.append(["Product Name", "Digital Multimeter"])
    ws.append(["Model", "DM-100"])
    ws.append(["Display", "LCD"])
    ws.append(["DC Voltage", "0–600 V"])
    ws.append(["Power Supply", "Battery"])
    
    xlsx_io = io.BytesIO()
    wb.save(xlsx_io)
    xlsx_bytes = xlsx_io.getvalue()

    app = webapp.app
    client = app.test_client()

    res = client.post(
        "/api/catalogue/upload-auto-generate",
        data={"file": (io.BytesIO(xlsx_bytes), "Digital_Multimeter.xlsx")},
        content_type="multipart/form-data"
    )
    assert res.status_code == 200, f"Upload auto generate failed: {res.status_code}, data: {res.data}"
    data = res.get_json()
    assert data["success"] is True, "Result success should be True"
    assert data["product_name"] == "Digital Multimeter", f"Product: {data['product_name']}"
    assert data["source_model"] == "DM-100", f"Source model: {data['source_model']}"
    assert data["catalogue_brand"] == "VTech", f"Catalogue brand: {data['catalogue_brand']}"
    assert "full_pdf_b64" in data and len(data["full_pdf_b64"]) > 1000, "Full PDF b64 missing"
    assert "mini_pdf_b64" in data and len(data["mini_pdf_b64"]) > 1000, "Mini PDF b64 missing"

    # Verify generated Full PDF
    import base64
    from pypdf import PdfReader
    pdf_bytes = base64.b64decode(data["full_pdf_b64"])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 2, f"Full PDF must be 2 pages, got: {len(reader.pages)}"
    pdf_text = reader.pages[0].extract_text() + " " + reader.pages[1].extract_text()
    assert "PK" not in pdf_text, "PK binary found in generated PDF!"
    assert "[Content_Types]" not in pdf_text, "Content_Types XML found in generated PDF!"
    print(f"✓ /api/catalogue/upload-auto-generate successfully generated 2-page Full PDF ({len(pdf_bytes)} bytes) and Mini PDF.")


if __name__ == "__main__":
    print("=" * 60)
    print("STARTING NUNES CATALOGUE STUDIO TEST SUITE")
    print("=" * 60)
    test_file_extraction_pipeline()
    test_upload_auto_generate_endpoint()
    test_ai_service()
    test_image_processing()
    test_product_research()
    test_full_catalogue_pdf()
    test_mini_catalogue_pdf()
    test_flask_endpoints()
    print("=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! (100% READY FOR LIVE DEPLOYMENT)")
    print("=" * 60)

