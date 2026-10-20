"""One-click, cloud-only Full + Mini Catalogue bundle for NUNES Studio.

Given up to eight real source-evidence records, produce independent two-page
Full PDF drafts, one combined Mini PDF and a transparent source/provenance
report. These are source-dependent drafts, never manufacturer certification.
Missing exact-model facts remain unverified instead of being invented.
"""
from __future__ import annotations
import csv
import io
import json
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import generator as g
from full_batch import build_zip, _row, MAX_BATCH
from mini_photo_match import match_photo
from product_discovery import public_indiamart_products, _is_actual_product_listing

def _product_key(record):
    return (str(record.get('product') or '').casefold().strip(),
            str(record.get('source_url') or '').split('?',1)[0].rstrip('/').casefold())

def discover_public_products(query):
    """Discover actual indexed titles and exact-photo candidates, up to eight.

    Never turn unrelated generic Source Evidence pictures into new products.
    Selected photos remain linked to their original URLs and provenance.
    """
    query=str(query or '').strip()[:120]
    if len(query)<4:
        raise ValueError('Enter a product or category name of at least four characters.')
    names=[]
    try:
        names=public_indiamart_products(query,limit=MAX_BATCH)
    except Exception:
        names=[]
    pictures=[]
    try:
        from product_research import image_candidates
        pictures=image_candidates(query,limit=MAX_BATCH)
    except Exception:
        pictures=[]
    rows=[]
    seen=set()
    # Exact source listing products get preference over broad image titles.
    for listing in names:
        if not isinstance(listing,dict):
            continue
        if not _is_actual_product_listing(listing.get('product'),listing.get('source_url')):
            continue
        candidate=dict(listing)
        if not candidate.get('image_link'):
            matched=match_photo(candidate,pictures)
            if matched:
                candidate.update(matched)
        key=_product_key(candidate)
        if key not in seen:
            seen.add(key)
            rows.append(candidate)
        if len(rows)>=MAX_BATCH:
            break
    # Add real named public image-result products only when fewer than 8 actual
    # listings exist. Every picture stays associated with its own source page.
    for photo in pictures:
        if len(rows)>=MAX_BATCH:
            break
        if not isinstance(photo,dict) or not photo.get('image_link'):
            continue
        if not _is_actual_product_listing(photo.get('product'),photo.get('source_url')):
            continue
        candidate={
            'product':photo.get('product'),'model':'',
            'image_link':photo.get('image_link'),
            'source_url':photo.get('source_url'),
            'source':photo.get('source') or 'Public image result'
        }
        key=_product_key(candidate)
        if key not in seen:
            seen.add(key)
            rows.append(candidate)
    return rows[:MAX_BATCH]

def _mini_photo(record,index):
    raw=record.get('image_data')
    if raw:
        from full_batch import _download_photo
        return _download_photo(record,Path(tempfile.gettempdir()),100+index)
    url=record.get('image_link')
    if not url:
        return None
    try:
        return g.download_image(url,
             'cloud_mini_'+str(url),preserve_alpha=True)
    except Exception:
        return None

def build_cloud_bundle(query,products=None,save_drive=False):
    """Return ZIP bytes + summary for 1-8 independent source product records."""
    supplied=products is not None
    if supplied:
        if not isinstance(products,list) or not(1<=len(products)<=MAX_BATCH):
            raise ValueError('Select between one and eight source products.')
        records=[_row(x) for x in products]
    else:
        records=[_row(x) for x in discover_public_products(query)]
    if not records:
        raise ValueError(
            'No matching public product listings or images were retrieved. '
            'Enter an exact model, or select a genuine Source Evidence photo.')
    seen=set()
    for record in records:
        key=_product_key(record)
        if key in seen:
            raise ValueError('Duplicate source product: '+record['product'])
        seen.add(key)
    # Existing Full renderer guarantees one two-page A4 PDF per real item.
    full_zip,full_summary=build_zip(records)

    # Mini renderer receives the SAME list of product names, never an invented
    # card, and downloads each matching URL only. Missing images print as names.
    photos=[None]*len(records)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(_mini_photo,row,idx):idx
                 for idx,row in enumerate(records)}
        for future in as_completed(futures):
            try:photos[futures[future]]=future.result()
            except Exception:pass
    # Keep photo / source name order stable; the Mini renderer visually
    # prioritizes images and still lists EVERY selected name on last sheet.
    from image_processing import prepare_mini_product_image
    for index,photo in enumerate(photos):
        if photo is None:
            continue
        try:
            photos[index],_=prepare_mini_product_image(photo)
        except Exception:
            photos[index]=photo
    mini_pictured=sum(bool(p and Path(p).is_file()) for p in photos)
    with tempfile.TemporaryDirectory(prefix='nunes_cloud_bundle_') as dirname:
        mini_path=Path(dirname)/'NUNES_VTech_VT_Mini_Catalogue.pdf'
        g.mini_pdf(mini_path,records[0]['product'],'',
                   list(zip(records,photos)),keywords=None)
        from pypdf import PdfReader
        pages=len(PdfReader(str(mini_path)).pages)
        if pages<1:
            raise ValueError('Mini Catalogue PDF has no pages.')
        report={
            'status':'generated_drafts_pending_source_review',
            'catalogue_brand':'VTech',
            'catalogue_model':'VT',
            'query':str(query or '')[:120],
            'discovery':'selected_source_evidence' if supplied else 'public_indexed_search',
            'product_count':len(records),
            'full_pdf_count':full_summary['total'],
            'mini_pdf_count':1,
            'mini_pages':pages,
            'mini_photographed_products':mini_pictured,
            'mini_names_only_products':len(records)-mini_pictured,
            'review_draft_count':full_summary['review_drafts'],
            'source_reported_draft_count':full_summary['source_reported_drafts'],
            'original_product_names_retained':True,
            'missing_specifications_are_not_invented':True,
            'items':full_summary['results'],
            'notice':('VTech/VT are house catalogue designations, NOT claims that '
                      'Review the matching source-model evidence before publication.')
        }
        if save_drive:
            try:
                from drive_storage import configured as drive_configured, save_pdf
                if drive_configured():
                    try:
                        mini_drive_url = save_pdf(mini_path, mini_path.name, kind='mini', allow_server_token=True)
                        report['mini_drive_link'] = mini_drive_url
                    except Exception:
                        pass
                    with zipfile.ZipFile(io.BytesIO(full_zip),'r') as source:
                        for item in full_summary['results']:
                            pdf_name = item.get('filename')
                            if pdf_name and pdf_name in source.namelist():
                                pdf_bytes = source.read(pdf_name)
                                p_temp = Path(dirname) / pdf_name
                                p_temp.write_bytes(pdf_bytes)
                                try:
                                    full_drive_url = save_pdf(p_temp, pdf_name, kind='full', allow_server_token=True)
                                    item['drive_link'] = full_drive_url
                                except Exception:
                                    pass
            except Exception:
                pass
        file=io.BytesIO()
        with zipfile.ZipFile(file,'w',compression=zipfile.ZIP_DEFLATED,
                             compresslevel=5) as output:
            with zipfile.ZipFile(io.BytesIO(full_zip),'r') as source:
                for name in source.namelist():
                    if name.endswith('.pdf'):
                        output.writestr('Full_Catalogues/'+name,source.read(name))
            output.write(mini_path,arcname='Mini_Catalogue/'+mini_path.name)
            output.writestr('BATCH_REPORT.json',json.dumps(
                report,indent=2,ensure_ascii=False))
            text=io.StringIO()
            fields=list(full_summary['results'][0].keys())
            writer=csv.DictWriter(text,fieldnames=fields)
            writer.writeheader()
            writer.writerows(full_summary['results'])
            output.writestr('BATCH_REPORT.csv',text.getvalue())
            output.writestr('READ_ME.txt',
                'NUNES Catalogue Studio - Full + Mini Export\n\n'
                'Full_Catalogues/: one two-page A4 PDF per selected source item.\n'
                'Mini_Catalogue/: combined image-first product catalogue.\n'
                'BATCH_REPORT: item counts, original source links and review status.\n\n'
                'Items with missing exact-model technical evidence are NOT approved '
                'manufacturer datasheets. Verify before distribution.\n'
                'VTech / VT are internal catalogue designations.\n')
        return file.getvalue(),report
