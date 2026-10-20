"""Vercel-compatible on-demand interface for the original NUNES PDF engine."""
import os, json, csv, io, re, tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response
from functools import lru_cache

ROOT=Path(__file__).resolve().parent
# On Vercel only /tmp is writable; preserve bundled reference templates.
if os.environ.get('VERCEL'):
    from shutil import copy2
    temp=Path('/tmp/nunes_catalogue')
    temp.mkdir(exist_ok=True)
    for d in ('Catalogue','Mini Catalogue','cache','logs'):(temp/d).mkdir(exist_ok=True)
    # Original generator resolves paths from its own module; override them after import.
import generator as g
if os.environ.get('VERCEL'):
    g.CAT_DIR=temp/'Catalogue';g.MINI_DIR=temp/'Mini Catalogue';g.CACHE_DIR=temp/'cache';g.LOG_DIR=temp/'logs';g.DB_PATH=temp/'progress.sqlite3'
    # File output directories are passed directly to the generator.

app=Flask(__name__,static_folder='static',static_url_path='/static')
app.config['MAX_CONTENT_LENGTH']=2_000_000

def auth():
    expected=os.environ.get('NUNES_ADMIN_PASSWORD','')
    supplied=request.headers.get('X-Nunes-Key','')
    return bool(expected) and __import__('hmac').compare_digest(supplied,expected)

def denied():return jsonify(error='Unauthorized. Set NUNES_ADMIN_PASSWORD in Vercel settings and enter it in the website.'),401

@app.get('/')
def home():return app.send_static_file('index.html')

@app.get('/api/health')
def health():return jsonify(status='ok',service='NUNES Catalogue Generator',sheet_id_configured=bool(g.SETTINGS.get('spreadsheet_id')),google_credentials_configured=bool(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')),password_configured=bool(os.environ.get('NUNES_ADMIN_PASSWORD')))

@lru_cache(maxsize=1)
def credentials():
    raw=os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON','')
    if not raw:return None
    import gspread
    from google.oauth2.service_account import Credentials
    info=json.loads(raw)
    c=Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    return gspread.authorize(c)

def fetch_products(query='',limit=60):
    """Query a bounded range; avoids reading >100k rows into serverless memory."""
    q=query.strip().casefold(); sid=g.SETTINGS['spreadsheet_id'];sheet=g.SETTINGS['sheet_name']
    gc=credentials()
    if gc:
        ws=gc.open_by_key(sid).worksheet(sheet)
        # Google Sheets API values endpoint; scans the configured columns.
        data=ws.get('D2:G'+str(min(ws.row_count,150000)),value_render_option='FORMATTED_VALUE')
    else:
        url=f'https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid=0'
        r=g.SESSION.get(url,timeout=25);r.raise_for_status()
        if '<html' in r.text[:300].lower():raise ValueError('Sheet not accessible: add GOOGLE_SERVICE_ACCOUNT_JSON and share the sheet with its service-account email.')
        data=[x[3:7] for x in csv.reader(io.StringIO(r.text))][1:]
    found=[];seen=set()
    for i,v in enumerate(data,2):
        v=list(v)+['']*max(0,4-len(v))
        image,name,model,specs=v[:4]
        if not name or (q and q not in (name+' '+model+' '+specs).casefold()):continue
        key=(name.casefold().strip(),model.casefold().strip())
        if key in seen:continue
        seen.add(key)
        found.append(dict(row=i,product=name,model=model,specifications=specs,image_link=image))
        if len(found)>=limit:break
    return found

@app.get('/api/products')
def products():
    if not auth():return denied()
    query=request.args.get('q','')[:120]
    if not query.strip():return jsonify(products=[],message='Type a product or model to search')
    try:return jsonify(products=fetch_products(query,40))
    except Exception as e:return jsonify(error=f'Google Sheet read failed: {str(e)[:280]}'),503

@app.post('/api/generate')
def generate():
    if not auth():return denied()
    payload=request.get_json(silent=True) or {}
    product=str(payload.get('product','')).strip()[:180]
    model=str(payload.get('model','')).strip()[:120]
    specs=str(payload.get('specifications','')).strip()[:3000]
    imageurl=str(payload.get('image_link','')).strip()[:1500]
    kind=str(payload.get('type','full'))
    if not product:return jsonify(error='Product name is required'),400
    if kind not in ('full','mini'):return jsonify(error='Invalid PDF type'),400
    # On-demand generation avoids slow external research within Vercel execution limits.
    research={'specs':g.parse_specs(specs),'description':f'{product} catalogue. Verify technical details against the manufacturer specification before purchase.', 'features':[], 'applications':[], 'sources':[]}
    try:
        out=Path(tempfile.mkstemp(prefix='nunes_',suffix='.pdf')[1])
        if kind=='full':
            # Only use the supplied product image, never substitute a different model's image.
            photo=g.download_image(imageurl,g.product_key(product,model)[:18]) if imageurl.startswith('https://') else None
            g.catalogue_pdf(out,product,model,photo,research)
        else:
            rel=payload.get('related',[])
            if not isinstance(rel,list):rel=[]
            related=[({'product':str(x.get('product',''))[:180], 'model':str(x.get('model',''))[:120]},None) for x in rel[:10] if isinstance(x,dict) and x.get('product')]
            g.mini_pdf(out,product,model,related)
        response=send_file(out,mimetype='application/pdf',as_attachment=True,download_name=g.safe_filename(product,model)+('_mini' if kind=='mini' else '')+'.pdf')
        return response
    except Exception as e:return jsonify(error=f'PDF generation failed: {str(e)[:300]}'),500

@app.get('/api/config')
def config():
    if not auth():return denied()
    return jsonify(company=g.SETTINGS['company_name'],sheet=g.SETTINGS['sheet_name'],sheet_id=g.SETTINGS['spreadsheet_id'],mode='on-demand',batch_backend='not configured')

if __name__=='__main__':app.run(debug=True,port=8788)
