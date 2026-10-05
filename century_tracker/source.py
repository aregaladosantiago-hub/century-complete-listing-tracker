"""Century's national directory, embedded commerce items and map status feed."""
import collections
import concurrent.futures
import gzip
import hashlib
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup, SoupStrainer
from .engine import HealthError, price

BASE = 'https://www.centurycommunities.com'
DIRECTORY = BASE + '/api/search/findcommunities?brand=Century%20Complete&mapShown=true&seed=42'
MAP = BASE + '/api/maps/geojson?brand=CMP'
CONTRACTED = {'Pending','Reserved','Under Contract','Already Taken','Sold','Closed'}
KNOWN = CONTRACTED | {'SpecModel','Unreleased','Model','Unavailable','Available HomeSite','Available','Under Construction','Move-In Ready','Hidden'}


def fetch(url, headers=None):
    if urlparse(url).hostname != 'www.centurycommunities.com':
        raise HealthError('Unexpected source host')
    cmd = ['curl','--fail','--silent','--show-error','--location','--max-time','180','--retry','2','--retry-delay','2',url]
    for name,value in (headers or {}).items():
        cmd.extend(['-H',f'{name}: {value}'])
    result = subprocess.run(cmd, capture_output=True, check=True, timeout=560)
    return result.stdout


def directory(payload):
    cs=payload['communities']
    if payload.get('relaxedMatch') or payload['showLoadMore'] or len(cs)!=payload['total']:
        raise HealthError('Directory pagination/count mismatch')
    if len({c['communityId'] for c in cs}) != len(cs):
        raise HealthError('Duplicate community directory entries')
    if len(cs)<100 or any(c['company']!='Century Complete' for c in cs):
        raise HealthError('Implausible or mixed-brand directory')
    return cs


def map_rows(payload):
    if payload.get('Type')!='FeatureCollection':
        raise HealthError('Map schema changed')
    lots={};communities={}
    for feature in payload['Features']:
        p=feature['Properties']
        if p['Brand']!='CMP':
            raise HealthError('Map returned another brand')
        if p['Type']=='Community':
            communities[p['CommunityId']]=p['Name']
        if p['Type']!='Lot':
            continue
        if p['LotStatus'] not in KNOWN:
            raise HealthError(f"Unrecognized status: {p['LotStatus']}")
        sku=p['LotSku']
        if not sku or not sku.endswith('_CMP'):
            raise HealthError('Missing or invalid map home SKU')
        if sku in lots and any(lots[sku][k]!=p[k] for k in ('LotStatus','Price','IsPublished','AddressLine1','ViewDetailsUrl')):
            raise HealthError('Conflicting duplicate map features')
        lots[sku]=p
    if len(lots)<5000:
        raise HealthError('Implausibly small national map response')
    return lots,communities


def detail_availability(text, sku, expected_price):
    """Resolve a missing card purchase button using the same home's detail page."""
    soup=BeautifulSoup(text,'html.parser')
    products=soup.select('.product_detail_contain[data-template="ProductDetailCommercePage_Lot"]')
    if len(products)!=1 or products[0].get('data-product-id')!=sku:
        raise HealthError(f'Detail identity mismatch: {sku}')
    product=products[0]
    flags=[x.get_text(' ',strip=True).casefold() for x in product.select('.gallery_flags_icon,.lot-status-icon')]
    status=next((v for v in sorted(CONTRACTED) if v.casefold() in flags),None)
    buy=False
    for a in soup.select('.product_detail_contain a[href],nav.sticky_footer_contain a[href]'):
        if a.get_text(' ',strip=True)!='Buy Now':
            continue
        target=urlparse(urljoin(BASE,a['href']))
        if target.hostname!='www.centurycommunities.com' or parse_qs(target.query).get('sku')!=[sku]:
            raise HealthError(f'Detail purchase identity mismatch: {sku}')
        buy=True
    if status:
        if buy:
            raise HealthError(f'Conflicting detail availability: {sku}')
        return status
    if not buy:
        raise HealthError(f'Unrecognized detail availability: {sku}')
    displayed=product.select_one('.price')
    if displayed is None or expected_price is None or price(displayed.get_text(strip=True))!=expected_price:
        raise HealthError(f'Detail advertised price disagreement: {sku}')
    return 'Available'


def parse_community(c, text, lots, detail_loader=None):
    items={}
    for raw in re.findall(r'data-ga-onload-event="([^"]+)"',text):
        event=json.loads(html.unescape(raw))
        if event.get('ecommerce',{}).get('item_list_id')!='quick-move-in':
            continue
        for item in event['ecommerce']['items']:
            url=urljoin(BASE,item['location_id'])
            if item['item_brand']!='Century Complete' or not item['item_id'].endswith('_CMP'):
                raise HealthError('Mixed-brand commerce item')
            if url in items:
                raise HealthError('Duplicate commerce item URL')
            items[url]=item
    soup=BeautifulSoup(text,'html.parser',parse_only=SoupStrainer('li'))
    cards=soup.select('li.quick-move-in-card')
    if len(cards)!=len(items):
        raise HealthError(f"Card/item count mismatch: {c['name']}")
    # Zero is accepted only on an identifiable community page, never a generic error page.
    if not cards and not re.search(r'"@type"\s*:\s*"(?:Place|ProductGroup)"',text):
        raise HealthError(f"Unrecognized empty community page: {c['name']}")
    rows=[]
    for card in cards:
        link=card.select_one('h4 a')
        if link is None:
            raise HealthError('Missing home address link')
        url=urljoin(BASE,link['href']);item=items.pop(url)
        sku=item['item_id'];parts=sku.split('_')
        if len(parts)!=3:
            raise HealthError('Home SKU schema changed')
        address_text=link.get_text(' ',strip=True)
        match=re.fullmatch(r'(.*?)\s*\|\s*Lot\s+(.+)',address_text)
        if not match or match[2].strip().lower()!=parts[1].lower():
            raise HealthError('Address/lot mismatch')
        flags=[x.get_text(' ',strip=True) for x in card.select('.quick-icon')]
        status=next((v for v in sorted(CONTRACTED) if any(f.casefold()==v.casefold() for f in flags)),None)
        mapped=lots.get(sku)
        buy=any(a.get_text(' ',strip=True)=='Buy Now' for a in card.select('.button-groups a'))
        if mapped and mapped['LotStatus'] in CONTRACTED:
            if buy:
                raise HealthError(f'Conflicting card/map availability: {sku}')
            status=mapped['LotStatus']
        displayed=card.select_one('.starting-price .price')
        shown=displayed.get_text(strip=True) if displayed else ''
        card_price=None if shown in ('','Call for Available Homes') else price(shown)
        confirmed=False
        if not status and not buy:
            if detail_loader is None:
                raise HealthError(f'Unrecognized home availability: {sku}')
            status=detail_availability(detail_loader(sku,url),sku,card_price)
            confirmed=True
        status=status or 'Available'
        if status=='Available' and (card_price!=price(item['price']) or card_price!=price(card.get('data-price'))):
            raise HealthError(f'Advertised price disagreement: {sku}')
        rows.append(dict(home_key=sku,listing_id=sku,brand='CMP',community_id=parts[0],
                         address=match[1].strip(),lot=parts[1],community=item['item_category4'],
                         url=url,status=status,active=status=='Available',price_cents=card_price,
                         state=item['item_category'],market=item['item_category']+'/'+item['item_category2'],
                         source='community_card_detail_confirmed' if confirmed else 'community_card',directory_id=str(c['communityId'])))
    return rows


def collect(raw_dir, fixture=None):
    """Save compressed source evidence before validating the candidate snapshot."""
    raw_dir=Path(raw_dir);raw_dir.mkdir(parents=True,exist_ok=True)
    def obtain(name,url,headers=None):
        if fixture:
            path=Path(fixture)/name
            if name=='directory.json':path=Path(fixture)/'directory.json'
            elif name=='map.json':path=Path(fixture)/'geo.json'
            elif name.startswith('community-'):path=Path(fixture)/'pages'/name.replace('community-','')
            data=path.read_bytes()
        else:
            data=fetch(url,headers)
        (raw_dir/(name+'.gz')).write_bytes(gzip.compress(data,mtime=0))
        (raw_dir/(name+'.receipt.json')).write_text(json.dumps(dict(url=url,fetched_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))))
        return data
    initial=obtain('directory.json',DIRECTORY)
    cs=directory(json.loads(initial))
    # Discover the public map key from the website, rather than hard-coding it.
    first=obtain('community-'+str(cs[0]['communityId'])+'.html',urljoin(BASE,cs[0]['url']))
    key=re.search(r'data-map-key="([^"]+)"',first.decode())
    if not key:
        for c in cs[1:]:
            probe=obtain('community-'+str(c['communityId'])+'.html',urljoin(BASE,c['url']))
            key=re.search(r'data-map-key="([^"]+)"',probe.decode())
            if key:break
    if not key:
        raise HealthError('Public map configuration missing')
    lots,names=map_rows(json.loads(obtain('map.json',MAP,{'X-API-KEY':key[1]})))
    def one(c):
        name='community-'+str(c['communityId'])+'.html'
        cached=raw_dir/(name+'.gz')
        data=gzip.decompress(cached.read_bytes()) if cached.exists() else obtain(name,urljoin(BASE,c['url']))
        return parse_community(c,data.decode(),lots,
                               lambda sku,url: obtain('detail-'+sku+'.html',url).decode())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        groups=list(pool.map(one,cs))
    rows=[r for group in groups for r in group]
    keys={r['home_key'] for r in rows}
    for sku,p in lots.items():
        if sku in keys or p['LotStatus'] not in CONTRACTED:
            continue
        rows.append(dict(home_key=sku,listing_id=sku,brand='CMP',community_id=p['CommunityId'],
                         address=p['AddressLine1'] or '',lot=p['LotId'],community=names.get(p['CommunityId'],p['CommunityId']),
                         url=p['ViewDetailsUrl'] or '',status=p['LotStatus'],active=False,price_cents=price(p['Price']),
                         state=p['State'],market=p['State']+'/'+(p['MetroName'] or '').strip(),source='map',directory_id=''))
    if not fixture:
        final=directory(json.loads(obtain('directory-end.json',DIRECTORY)))
        if {c['communityId'] for c in final}!={c['communityId'] for c in cs}:
            raise HealthError('Directory changed during capture')
    # Preserve source fields used by the collector without daily image/marketing payloads.
    for archive in raw_dir.glob('community-*.html.gz'):
        text=gzip.decompress(archive.read_bytes()).decode()
        cards=BeautifulSoup(text,'html.parser',parse_only=SoupStrainer('li')).select('li.quick-move-in-card')
        evidence=dict(cards=[dict(attributes=dict(card.attrs),address=card.select_one('h4').get_text(' ',strip=True),
                                 flags=[x.get_text(' ',strip=True) for x in card.select('.quick-icon')],
                                 prices=[x.get_text(' ',strip=True) for x in card.select('.starting-price .price')],
                                 links=[dict(text=a.get_text(' ',strip=True),href=a.get('href')) for a in card.select('h4 a,.button-groups a')]) for card in cards],
                      commerce=[json.loads(html.unescape(raw)) for raw in re.findall(r'data-ga-onload-event="([^"]+)"',text)
                                if json.loads(html.unescape(raw)).get('ecommerce',{}).get('item_list_id')=='quick-move-in'])
        archive.with_name(archive.name.replace('.html.gz','.json.gz')).write_bytes(gzip.compress(json.dumps(evidence).encode(),mtime=0))
        archive.unlink()
    map_fields=('LotSku','LotId','CommunityId','Brand','LotStatus','IsPublished','IsModelHome','IsQuickMoveIn','Price','AddressLine1','City','State','PostalCode','ViewDetailsUrl','ModifiedDate')
    (raw_dir/'map.json.gz').write_bytes(gzip.compress(json.dumps([dict((k,p[k]) for k in map_fields) for p in lots.values()]).encode(),mtime=0))
    active=[r for r in rows if r['active']]
    if len(active)<300:
        raise HealthError('Implausibly small available inventory')
    coverage=dict(complete=True,communities=len(cs),community_ids=sorted(str(c['communityId']) for c in cs),
                  map_lots=len(lots),observed_active=len(active),cards=sum(map(len,groups)),
                  markets=dict(collections.Counter(r['market'] for r in active)),
                  community_counts={str(c['communityId']):len(g) for c,g in zip(cs,groups)},
                  source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw_dir.glob('*.gz'))})
    return sorted(rows,key=lambda r:r['home_key']),coverage
