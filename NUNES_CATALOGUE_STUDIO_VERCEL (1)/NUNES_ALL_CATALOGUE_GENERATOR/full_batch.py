"""Bounded one-click multi-product Full Catalogue ZIP export.

Each Source Evidence item receives a TWO-page A4 PDF. Readable, exact-title
supplier information may be used only as a DRAFT awaiting human verification.
Where no technical data is available, create an explicitly marked photo/name
review draft instead of presenting fabricated model specifications.

VTech and VT are house catalogue identifiers, NOT manufacturer provenance.
"""
from __future__ import annotations
import base64
import binascii
import csv
import io
import json
import re
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

import generator as g
from catalogue_content import select_specs, select_features, enrich_full_copy
from mini_keywords import clean_term
from template_layout import CatalogueLayoutError, paragraph, _centered_title
from source_fact_extraction import public_product_page

MAX_BATCH=8
NAVY=colors.HexColor('#183C77')
MAGENTA=colors.HexColor('#EC168C')
MUTED=colors.HexColor('#425878')
HOUSE_BRAND='VTech'
HOUSE_MODEL='VT'

def _valid_source(url):
    try:
        url=urlsplit(str(url or ''))
        return (url.scheme=='https' and bool(url.hostname)
                and not url.username and not url.password
                and url.port in (None,443))
    except ValueError:
        return False

def _row(candidate):
    if not isinstance(candidate,dict):raise ValueError('Every batch item must be an object.')
    product=clean_term(candidate.get('product') or '')[:130]
    if len(product)<5:raise ValueError('Every batch item requires a readable source product name.')
    model=str(candidate.get('model') or '').strip()[:65]
    url=str(candidate.get('source_url') or '').strip()[:500]
    image=str(candidate.get('image_link') or '').strip()[:1500]
    if url and not _valid_source(url):url=''
    if image and not _valid_source(image):image=''
    raw=candidate.get('image_data')
    if raw and (not isinstance(raw,str) or len(raw)>1500000):
        raise ValueError('Batch image data exceeds the supported limit.')
    return {
        'product':product,'model':model,'source_url':url,
        'image_link':image,'image_data':raw or '',
        'source':str(candidate.get('source') or 'Public listing')[:100]
    }

def _work_source(record):
    """Bounded exact-source fetch only, never borrow another model's facts."""
    url=record['source_url']
    if not url:return {'description':'','specifications':''}
    try:return public_product_page(url,record['product'],record['model'])
    except Exception:return {'description':'','specifications':''}

def _download_photo(record,directory,number):
    raw=record.get('image_data')
    if raw:
        try:
            decoded=base64.b64decode(str(raw).split(',',1)[-1],validate=True)
            if len(decoded)>1050000:raise ValueError('image exceeds allowed size')
            path=directory/('batch_image_%02d.png'%number)
            with Image.open(io.BytesIO(decoded)) as picture:
                if picture.width*picture.height>12000000:
                    raise ValueError('image dimensions exceed allowed size')
                picture.convert('RGB').save(path,'PNG')
            return path
        except (OSError,ValueError,binascii.Error):
            return None
    url=record.get('image_link')
    if url:
        try:
            # Include the EXACT image URL in the cache key. Using only
            # short product names can silently reuse the wrong image.
            return g.download_image(url,
                'batch_%02d_%s'%(number,url),preserve_alpha=False)
        except Exception:
            return None
    return None

def _review_pdf(output,record,photo,source,reason):
    """Two-page professional NUNES draft; never a counterfeit datasheet."""
    title=record['product']
    c=canvas.Canvas(str(output),pagesize=A4,pageCompression=1)
    W,H=A4
    c.setTitle('DRAFT - NUNES Full Catalogue - '+title[:100])
    g.draw_header(c,g.FULL_HEADER,H-52*mm,50*mm)
    c.setStrokeColor(NAVY)
    c.line(14*mm,H-52*mm,W-14*mm,H-52*mm)
    _centered_title(c,title,H-63*mm,178*mm,13,3,NAVY,True)
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold',9.1)
    c.drawCentredString(W/2,H-83*mm,
        'Catalogue Brand: VTech  |  Catalogue Model: VT')
    g.draw_contained_image(c,photo,64*mm,H-158*mm,W-128*mm,62*mm)
    c.setFillColor(MAGENTA)
    c.setFont('Helvetica-Bold',12)
    c.drawString(12*mm,H-173*mm,'PRODUCT SPECIFICATION')
    c.setFillColor(colors.HexColor('#7F273F'))
    c.setFont('Helvetica-Bold',11)
    c.drawString(13*mm,H-187*mm,'DRAFT - TECHNICAL REVIEW REQUIRED')
    details=(
       'The named public listing and any available photograph are gathered '
       'for initial catalogue preparation. Exact performance, measurement '
       'range, accuracy, power, dimensions, compliance and manufacturer '
       'specifications have not been established from sufficient '
       'matching documentation. No missing specification has been invented. '
       'Replace this review draft after checking the correct manufacturer '
       'datasheet and the actual product model.'
    )
    block=paragraph(details,10.2,17,color=MUTED)
    _,height=block.wrap(W-29*mm,H)
    block.drawOn(c,14*mm,H-198*mm-height)
    c.setFont('Helvetica',9)
    c.setFillColor(MUTED)
    c.drawString(14*mm,44*mm,'Catalogue Identity: VTech / VT')
    source_host=urlsplit(record.get('source_url') or '').hostname or 'not provided'
    c.drawString(14*mm,35*mm,'Source host: '+source_host[:80])
    c.showPage()
    c.setFillColor(MAGENTA)
    c.setFont('Helvetica-Bold',12)
    c.drawString(11*mm,H-18*mm,'PRODUCT DESCRIPTION')
    # Even when exact-model specs are unavailable, make a useful *clearly
    # marked review draft* with 150-200 words and 8-10 product-family
    # guide lines; NEVER pass those context lines off as verified hardware.
    copy=enrich_full_copy(title,'',[],model=record.get('model') or '',specs=[])
    desc=copy['description']
    features=copy['key_features']
    chosen=None
    for body_size,leading,feat_size,feat_leading,gap in (
            (9.65,14.2,9.0,12.8,2.2),
            (9.2,13.2,8.7,12.0,1.7),
            (8.8,12.5,8.35,11.5,1.4)):
        para=paragraph(desc,body_size,leading,color=MUTED)
        _,height=para.wrap(W-28*mm,H)
        feature_rows=[]
        for bullet in features:
            feature_para=paragraph('• '+bullet,feat_size,feat_leading,color=MUTED)
            _,feature_h=feature_para.wrap(W-31*mm,H)
            feature_rows.append((feature_para,feature_h))
        body_bottom=H-31*mm-height
        features_start=body_bottom-20*mm
        lowest=features_start-sum(fh+gap*mm for _,fh in feature_rows)
        if lowest>=84*mm:
            chosen=(para,height,feature_rows,features_start,gap)
            break
    if chosen is None:
        raise CatalogueLayoutError(
            'Even the compact review draft cannot fit 150-200 words and '
            '8-10 conditional product-family notes above the NUNES footer.')
    para,height,feature_rows,features_start,gap=chosen
    para.drawOn(c,13*mm,H-31*mm-height)
    c.setFillColor(MAGENTA)
    c.setFont('Helvetica-Bold',11.5)
    c.drawString(12*mm,features_start+8*mm,'Key Features - DRAFT CATEGORY CONTEXT')
    y=features_start
    for item,feature_h in feature_rows:
        item.drawOn(c,15*mm,y-feature_h)
        y-=feature_h+gap*mm
    c.setFont('Helvetica-Bold',9.0)
    c.setFillColor(colors.HexColor('#8A3942'))
    c.drawString(14*mm,72*mm,'NOT FOR PUBLICATION - MISSING SOURCE SPECIFICATIONS')
    g.draw_footer(c,g.FULL_FOOTER,-1*mm,54*mm)
    c.showPage()
    c.save()

def build_zip(candidates):
    """Return (zip bytes, summary), with exactly one named PDF per input item."""
    if not isinstance(candidates,list) or not (1<=len(candidates)<=MAX_BATCH):
        raise ValueError('Select between 1 and 8 Source Evidence products.')
    records=[_row(x) for x in candidates]
    keys=set()
    for row in records:
        key=(row['product'].casefold(),row['source_url'])
        if key in keys:
            raise ValueError('Repeated Source Evidence item: '+row['product'])
        keys.add(key)
    with tempfile.TemporaryDirectory(prefix='nunes_full_batch_') as folder:
        directory=Path(folder)
        # Fetch photo and exact-source information in parallel, without
        # making the whole batch fail when one remote host rejects requests.
        photos={}
        sources={}
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures={}
            for number,record in enumerate(records,1):
                futures[executor.submit(_download_photo,record,directory,number)]=('photo',number)
                if record['source_url']:
                    futures[executor.submit(_work_source,record)]=('source',number)
            for job in as_completed(futures):
                kind,index=futures[job]
                try:value=job.result()
                except Exception:value=None
                if kind=='photo':photos[index]=value
                else:sources[index]=value or {}
        manifest=[]
        zip_content=io.BytesIO()
        with zipfile.ZipFile(zip_content,'w',compression=zipfile.ZIP_DEFLATED,
                             compresslevel=5) as result:
            for number,record in enumerate(records,1):
                photo=photos.get(number)
                source=sources.get(number,{})
                pairs=select_specs(
                    g.parse_specs(source.get('specifications','')),limit=5)
                real_desc=re.sub(r'\s+',' ',str(source.get('description') or '')).strip()
                file_name=('%02d_'%number)+g.safe_filename(
                    record['product'],'')[:75]+'.pdf'
                target=directory/file_name
                status='review_draft'
                failure='Source technical details need verification.'
                # Only display source-backed values in the full spec table;
                # never invent numeric specifications to fill missing rows.
                if photo and pairs and len(real_desc.split())>=12:
                    try:
                        draft_text=(
                           'Supplier-reported specification values below must '
                           'be verified for the exact product before use. '
                           'The catalogue is based on the linked source only.'
                        )
                        features=[k+': '+v for k,v in pairs]
                        content=enrich_full_copy(
                            record['product'],real_desc,features,
                            model='',specs=pairs)
                        research={
                            'specs':pairs,'description':content['description'],
                            'features':content['key_features'],
                            'technical_notes':content['specification_notes']
                        }
                        g.catalogue_pdf(target,record['product'],'',photo,research)
                        status='source_reported_draft'
                        failure=''
                    except (CatalogueLayoutError,OSError,ValueError) as exc:
                        failure='Full layout fallback: '+str(exc)[:130]
                if status=='review_draft':
                    _review_pdf(target,record,photo,source,failure)
                pages=len(PdfReader(str(target)).pages)
                if pages!=2:raise ValueError('Full batch PDF must contain exactly two pages')
                result.write(target,arcname=file_name)
                manifest.append({
                    'item':number,'product_name':record['product'],
                    'catalogue_brand':'VTech','catalogue_model':'VT',
                    'source_model':record['model'],
                    'source_url':record['source_url'],
                    'image_source_url':record['image_link'],
                    'photo_available':bool(photo and Path(photo).is_file()),
                    'source_spec_rows':len(pairs),
                    'source_description_available':bool(real_desc),
                    'status':status,
                    'pdf_filename':file_name,
                    'pages':pages,
                    'note':failure or 'Supplier-reported details require review before publishing.'
                })
            result.writestr('BATCH_REPORT.json',json.dumps(
                {'status':'drafts_for_review',
                 'catalogue_brand':'VTech','catalogue_model':'VT',
                 'item_count':len(manifest),'results':manifest},
                 indent=2,ensure_ascii=False))
            table=io.StringIO()
            writer=csv.DictWriter(table,fieldnames=list(manifest[0].keys()))
            writer.writeheader();writer.writerows(manifest)
            result.writestr('BATCH_REPORT.csv',table.getvalue())
        return zip_content.getvalue(),{
            'total':len(manifest),
            'source_reported_drafts':sum(r['status']=='source_reported_draft' for r in manifest),
            'review_drafts':sum(r['status']=='review_draft' for r in manifest),
            'photos':sum(r['photo_available'] for r in manifest),
            'results':manifest
        }
