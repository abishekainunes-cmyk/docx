"""Best-effort discovery of publicly indexed IndiaMART product listings.

This module does not bypass a login or scrape authenticated IndiaMART pages.
It never makes up products, specifications, vendors, or images. A third-party
result must be explicitly reviewed by the operator before use in a PDF.
"""
import html
import re
from urllib.parse import urlsplit

_STOP = {'the','for','with','and','from','of','to','in','a','an','on','use','best','price',
         'india','indiamart','near','me','sell','buy','contact','supplier','manufacturer'}
_PRICE = re.compile(r'(?:₹|Rs\.?\s*|INR\s*)([\d,]{3,12})(?:\s*/\s*\w+)?', re.I)

def _tokens(s):
    return set(x.rstrip('s') for x in re.findall(r'[a-z0-9]+', str(s).casefold())
               if len(x)>2 and x not in _STOP)

def _indiamart_url(url):
    try:
        p=urlsplit(str(url))
        host=(p.hostname or '').lower()
        return p.scheme=='https' and (host=='indiamart.com' or host.endswith('.indiamart.com'))
    except ValueError:
        return False

def _name(raw):
    title=html.unescape(re.sub(r'<[^>]+>','',str(raw or '')))
    for marker in (' | IndiaMART',' - IndiaMART',' at Best Price',' in India',' Get Best Price'):
        if marker.lower() in title.lower():
            title=title[:title.lower().find(marker.lower())]
    return re.sub(r'\s+',' ',title).strip(' -|')[:150]

def _family(name, query):
    title=name.casefold()
    if 'karl fischer' in title:return 'Karl Fischer Titrators'
    if 'potentiometric' in title:return 'Potentiometric Titrators'
    if 'ph meter' in title or 'ph tester' in title:return 'pH Meters'
    if 'titrator' in title or 'titration' in title:return 'Laboratory Titrators'
    t=re.findall(r'[\w-]+',name)
    return (' '.join(t[:3]) if len(t)>2 else name)[:65] or query

def _listing_page_image(source_url, product):
    """Return a real product image from its OWN IndiaMART listing metadata.

    No generic category photos, image hallucinations or unverified image links.
    This supplements indexed image search when listing results lack images.
    """
    if not _indiamart_url(source_url):
        return ""
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        res=requests.get(source_url,timeout=(2,3),allow_redirects=False,
                         headers={"User-Agent":"Mozilla/5.0 (compatible; NUNESCatalogue/1.0)"})
        if res.status_code!=200 or "text/html" not in res.headers.get("Content-Type","").lower():
            return ""
        if len(res.content)>650_000:
            return ""
        soup=BeautifulSoup(res.content,"html.parser")
        name=str((soup.title.string if soup.title and soup.title.string else "") or "")
        words=_tokens(product)
        if words and len(words & _tokens(name))<max(1,min(2,len(words))):
            return ""
        for key,prop in (("property","og:image"),("name","twitter:image")):
            tag=soup.find("meta",attrs={key:prop})
            candidate=str(tag.get("content") or "") if tag else ""
            if not candidate:
                continue
            url=urljoin(source_url,candidate)
            parsed=urlsplit(url)
            host=(parsed.hostname or "").lower()
            if (parsed.scheme=="https" and
                (host=="imimg.com" or host.endswith(".imimg.com") or
                 host=="indiamart.com" or host.endswith(".indiamart.com"))):
                return url[:1500]
    except Exception:
        pass
    return ""


def _is_actual_product_listing(name, url):
    """Exclude marketplace directory/category results from mini product cards."""
    title=str(name or '').casefold()
    path=urlsplit(str(url or '')).path.casefold()
    if any(x in path for x in ('/impcat/', '/search.mp', '/city/', '/directory/')):
        return False
    directory_words=('latest price', 'manufacturers', 'wholesalers',
                     'distributors', 'business directory', 'traders',
                     'suppliers in ', 'dealers in ', 'price list',
                     'get best price', ' in mumbai', ' in delhi',
                     ' at ₹', 'at rs.', 'per piece |', 'latest price,')
    if any(x in title for x in directory_words):
        return False
    return bool(name and len(name)>6)


def public_indiamart_products(query, limit=16):
    """Return search-backed listings; never a count of all IndiaMART products."""
    query=str(query or '').strip()[:120]
    if not query:return []
    tokens=_tokens(query)
    if not tokens:return []
    try:
        from ddgs import DDGS
        ddgs=DDGS(timeout=7)
        results=list(ddgs.text('site:indiamart.com '+query+' product',max_results=min(limit*2,30)))
    except Exception:
        return []
    out=[];seen=set()
    for row in results:
        url=str(row.get('href') or row.get('url') or '')
        if not _indiamart_url(url):continue
        name=_name(row.get('title'))
        name_tokens=_tokens(name)
        overlap=len(name_tokens & tokens)
        if not _is_actual_product_listing(name,url) or overlap<max(1,min(2,len(tokens))):continue
        if len(name)<7 or name.casefold() in seen:continue
        seen.add(name.casefold())
        body=re.sub(r'\s+',' ',html.unescape(str(row.get('body') or '')))[:800]
        price_match=_PRICE.search(body+' '+str(row.get('title') or ''))
        out.append({'product':name,'model':'','specifications':'',
                    'image_link':'','price':('₹'+price_match.group(1) if price_match else ''),
                    'supplier':'','location':'','source':'IndiaMART search',
                    'source_url':url,'category':_family(name,query),
                    'source_note':body[:190]})
        if len(out)>=limit:break
    # Matching image results may carry the exact indexed listing URL. Never attach
    # images merely because a product category is similar.
    if out:
        try:
            from ddgs import DDGS
            images=list(DDGS(timeout=6).images('site:indiamart.com '+query,max_results=25,safesearch='moderate'))
            for image in images:
                page=str(image.get('url') or '')
                candidate=str(image.get('image') or '')
                if not _indiamart_url(page) or not candidate.startswith('https://'):continue
                img_title=_tokens(image.get('title') or '')
                for product in out:
                    if product['image_link']:continue
                    prod_tokens=_tokens(product['product'])
                    if (page.split('?',1)[0].rstrip('/')==product['source_url'].split('?',1)[0].rstrip('/')
                        and len(img_title & prod_tokens)>=max(1,min(2,len(prod_tokens)))):
                        product['image_link']=candidate
                        break
        except Exception:
            pass
        # Metadata from the exact matching listing is safer than random category
        # image search. Bound work to the first five image-less listings.
        checked=0
        for product in out:
            if product.get('image_link') or checked>=5:
                continue
            checked+=1
            product['image_link']=_listing_page_image(product['source_url'],product['product'])
    return out

def categorize(products):
    groups={}
    for p in products:
        name=str(p.get('category') or p.get('product') or 'Other')
        groups.setdefault(name,[]).append(p)
    cats=[]
    for name,group in groups.items():
        group.sort(key=lambda p:(not bool(p.get('image_link')),p.get('product','').casefold()))
        cats.append({'name':name,'count':len(group),'products':group})
    cats.sort(key=lambda c:(-c['count'],c['name'].casefold()))
    return cats
