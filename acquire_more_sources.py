"""Acquire public article evidence and its media; admission requires a separate review."""
import argparse
import datetime as dt
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import re
import socket
import time
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import httpx
from PIL import Image

def save(path, value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    args=p.parse_args();out=args.root/'acquisition/expanded';out.mkdir(parents=True,exist_ok=True)
    plan=json.loads(args.plan.read_text());manifest_path=out/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'pages':[],'media':[],'complete':False,'events':[]}
    manifest['complete']=False;manifest['planned_pages']=len(plan)
    def emit(kind,**data):
        event={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'type':kind,**data};manifest['events'].append(event)
        save(manifest_path,manifest);print(json.dumps(event,ensure_ascii=False),flush=True)
    known_pages={r['url'] for r in manifest['pages']};known_media={r['url'] for r in manifest['media']}
    def download(client,url,bound):
        for _ in range(6):
            parsed=urlsplit(url)
            if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):raise ValueError('invalid public URL')
            addresses=socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('non-public destination')
            with client.stream('GET',url) as r:
                if r.is_redirect:
                    url=urljoin(url,r.headers['location']);continue
                r.raise_for_status();chunks=bytearray()
                for chunk in r.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks)>bound:raise ValueError('declared size limit exceeded')
                return bytes(chunks),str(r.url),dict(r.headers)
        raise ValueError('redirect limit exceeded')
    with httpx.Client(timeout=35,follow_redirects=False,headers={'User-Agent':'FireViewer research collection (private evaluation)'}) as client:
      for spec in plan:
        url=spec['url']
        if url in known_pages:continue
        key=hashlib.sha256(url.encode()).hexdigest()[:20]
        try:
            raw,final,headers=download(client,url,8_000_000)
            soup=BeautifulSoup(raw,'html.parser');title=soup.find('h1')
            if any(x in raw.lower() for x in [b'cf-chl-',b'captcha-delivery.com']):raise ValueError('provider_challenge')
            (out/(key+'.html')).write_bytes(raw)
            body=soup.find('article') or soup.find('main') or soup
            texts='\n'.join(e.get_text(' ',strip=True) for e in body.select('h1,h2,p,figcaption,blockquote'))
            (out/(key+'.txt')).write_text(texts)
            ld=[]
            def walk(v):
                if isinstance(v,list):
                    for x in v:walk(x)
                elif isinstance(v,dict):
                    if v.get('@type') in ['NewsArticle','Article','VideoObject','ImageObject']:ld.append(v)
                    for x in v.values():
                        if isinstance(x,(dict,list)):walk(x)
            for tag in soup.select('script[type="application/ld+json"]'):
                try:walk(json.loads(tag.string or tag.get_text()))
                except (ValueError,TypeError):pass
            published=next((x.get('datePublished') or x.get('uploadDate') for x in ld if x.get('datePublished') or x.get('uploadDate')),None)
            page={**spec,'id':key,'status':'downloaded','final_url':final,'title':title.get_text(' ',strip=True) if title else None,'published_at':published,'path':str((out/(key+'.html')).relative_to(args.root)),'text_path':str((out/(key+'.txt')).relative_to(args.root)),'sha256':hashlib.sha256(raw).hexdigest(),'structured_data':ld,'bytes':len(raw),'acquired_at':dt.datetime.now(dt.timezone.utc).isoformat()}
            links=[]
            for f in body.select('figure'):
                caption=f.find('figcaption');caption=caption.get_text(' ',strip=True) if caption else f.get_text(' ',strip=True)
                for im in f.select('img'):
                    srcset=im.get('srcset') or im.get('data-srcset') or ''
                    entries=[]
                    for entry in srcset.split(','):
                        parts=entry.strip().rsplit(' ',1)
                        if len(parts)==2 and parts[1].endswith('w'):
                            try:entries.append((int(parts[1][:-1]),parts[0]))
                            except ValueError:pass
                    source=max(entries)[1] if entries else im.get('data-src') or im.get('src')
                    if source:links.append({'url':urljoin(final,source),'caption':caption,'alt':im.get('alt'),'discovery':'article_figure'})
            for item in ld:
                if item.get('@type') in ['Article','NewsArticle','VideoObject']:
                    values=item.get('image') or item.get('thumbnailUrl') or []
                    for value in values if isinstance(values,list) else [values]:
                        candidate=value if isinstance(value,str) else value.get('url') or value.get('contentUrl')
                        if candidate:links.append({'url':urljoin(final,candidate),'caption':item.get('caption') or item.get('description'),'discovery':'structured_article_image'})
                if item.get('@type')=='VideoObject':
                    page.setdefault('video_candidates',[]).append({k:item.get(k) for k in ['name','contentUrl','embedUrl','uploadDate','description','duration']})
                if item.get('@type')=='ImageObject' and (item.get('contentUrl') or item.get('url')):
                    links.append({'url':urljoin(final,item.get('contentUrl') or item['url']),'caption':item.get('caption') or item.get('description'),'credit':item.get('creditText') or item.get('copyrightNotice'),'discovery':'structured_image'})
            for frame in body.select('iframe'):
                src=frame.get('src') or frame.get('data-src')
                if src:page.setdefault('embeds',[]).append(urljoin(final,src))
            manifest['pages'].append(page);known_pages.add(url);emit('page_acquired',id=key,title=page['title'],images=len(links))
            for candidate in links:
                media_url=candidate['url']
                if media_url in known_media:continue
                known_media.add(media_url);mid=hashlib.sha256(media_url.encode()).hexdigest()[:20]
                item={**candidate,'id':'field-candidate-'+mid,'source_page':url,'page_id':key,'published_at':published,'status':'candidate','observed_at':None,'local_date':None,'date_status':'review_required_not_inferred_from_publication','selection_status':'not_reviewed','rights':'publicly_viewable_copyright_retained_private_evaluation_only'}
                try:
                    data,resolved,_=download(client,media_url,20_000_000)
                    im=Image.open(io.BytesIO(data));im.load()
                    ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(im.format)
                    if not ext:raise ValueError('unsupported image format')
                    file=out/(mid+ext);file.write_bytes(data)
                    # Hash serves duplicate triage only, never image-content admission.
                    grey=im.convert('L').resize((9,8));pixels=list(grey.getdata());bits=[pixels[y*9+x]>pixels[y*9+x+1] for y in range(8) for x in range(8)]
                    dhash=sum(int(bit)<<i for i,bit in enumerate(bits))
                    item.update(status='downloaded',path=str(file.relative_to(args.root)),resolved_url=resolved,width=im.width,height=im.height,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),dhash=f'{dhash:016x}',format=im.format)
                except Exception as e:item.update(status='failed',error_type=type(e).__name__,error=str(e)[:180])
                manifest['media'].append(item);emit('image_acquired',id=item['id'],status=item['status'],size=[item.get('width'),item.get('height')])
            time.sleep(.5)
        except Exception as e:
            manifest['pages'].append({**spec,'id':key,'status':'failed','error_type':type(e).__name__,'error':str(e)[:200]});emit('page_failed',id=key,error_type=type(e).__name__)
    manifest['complete']=True;emit('collection_wave_finished',pages=len(manifest['pages']),media=len(manifest['media']))

if __name__=='__main__':main()
