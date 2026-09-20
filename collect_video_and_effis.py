"""Bounded public acquisitions, kept separate from admitted observations."""
import argparse, datetime as dt, hashlib, json
from pathlib import Path
import httpx

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args();root=args.root
out=root/'acquisition/video';out.mkdir(parents=True,exist_ok=True)
url='https://video.euronews.com/mp4/FHD/21/77/06/05/FHD_PYR_2177065_20250807102227.mp4'
with httpx.Client(timeout=45,follow_redirects=False) as client:
    dest=out/'euronews-20250807.mp4'
    if not dest.exists():
        with client.stream('GET',url) as res:
            res.raise_for_status();size=0
            with dest.with_suffix('.part').open('wb') as f:
                for data in res.iter_bytes():
                    size+=len(data)
                    if size>250_000_000:raise ValueError('video exceeds 250 MB bound')
                    f.write(data)
        dest.with_suffix('.part').replace(dest)
    row={'id':'euronews-nocomment-20250807','kind':'ground_video_candidate','pipeline_branch':'ground_visual',
        'source_url':'https://fr.euronews.com/video/2025/08/07/france-le-plus-grand-incendie-depuis-des-decennies-brule-16-000-hectares-dans-laude',
        'media_url':url,'path':str(dest.relative_to(root)),'bytes':dest.stat().st_size,
        'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'published_at':'2025-08-07T13:09:38+02:00',
        'observed_at':None,'selection_status':'scene_review_required','rights':'copyright_retained_private_evaluation_only',
        'note':'No day inferred from upload. Frames from the same video remain one source lineage.'}
    (out/'manifest.json').write_text(json.dumps([row],ensure_ascii=False,indent=2));print('video acquired',row['bytes'],flush=True)
    out=root/'acquisition/effis';out.mkdir(exist_ok=True)
    receipts=[]
    for layer in ['all.hs.query','viirs.hs.query','modis.ba.poly.2025']:
        params={'SERVICE':'WMS','VERSION':'1.1.1','REQUEST':'GetFeatureInfo','LAYERS':layer,'QUERY_LAYERS':layer,
            'STYLES':'','SRS':'EPSG:4326','BBOX':'2.4,42.9,3.0,43.3','WIDTH':1,'HEIGHT':1,'X':0,'Y':0,
            'FORMAT':'image/png','INFO_FORMAT':'application/vnd.ogc.gml','FEATURE_COUNT':10000,
            'TIME':'2025-08-05/2025-08-09'}
        try:
            res=client.get('https://maps.effis.emergency.copernicus.eu/effis',params=params);res.raise_for_status()
            dest=out/(layer+'-area-query.gml');dest.write_bytes(res.content)
            receipts.append({'layer':layer,'query_url':str(res.url),'status':res.status_code,'path':str(dest.relative_to(root)),
                'bytes':len(res.content),'sha256':hashlib.sha256(res.content).hexdigest(),'at':dt.datetime.now(dt.timezone.utc).isoformat()})
        except Exception as e:receipts.append({'layer':layer,'error_type':type(e).__name__})
        print('EFFIS',receipts[-1],flush=True)
    (out/'area-query-receipts.json').write_text(json.dumps(receipts,indent=2))
