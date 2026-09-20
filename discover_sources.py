"""Broader discovery using the unchanged FireViewer ResearchBroker, with receipts.

This harness is acquisition only. It does not replace the agent planner or claim
that raw search results are eligible daily evidence. Limits are explicit.
"""
import argparse
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import secrets
import sys
import time

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=args.sources_root/'fireviewer-evidence-ingestion/src'
    sys.path.insert(0,str(source))
    from fireviewer_evidence_ingestion.research_broker import ResearchBroker
    planner=source/'fireviewer_evidence_ingestion/mvp/research/source_planner.py'
    tree=ast.parse(planner.read_text())
    policies=next(n.value for n in tree.body if isinstance(n,ast.AnnAssign) and getattr(n.target,'id',None)=='DEFAULT_SOURCE_POLICIES')
    domains=[ast.literal_eval(k) for k in policies.keys]
    domains+=['aude.gouv.fr','aude.fr','sdis11.fr','nasa.gov','commons.wikimedia.org','flickr.com',
        'securite-civile.interieur.gouv.fr','lagrasse.fr','mairie-ribaute.fr']
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    pages=out/'pages';pages.mkdir(exist_ok=True)
    events=out/'events.jsonl'
    def emit(kind,**fields):
        item={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'type':kind,**fields}
        with events.open('a') as f:f.write(json.dumps(item,ensure_ascii=False)+'\n')
        print(json.dumps(item,ensure_ascii=False),flush=True)
    class ReceiptBroker(ResearchBroker):
        last_response=None
        def _request(self,*a,**kw):
            r,b=super()._request(*a,**kw)
            self.last_response={'status':r.status_code,'sha256':hashlib.sha256(b).hexdigest(),
                'challenge':any(s in b.lower() for s in [b'challenge-form',b'bots use duckduckgo',b'anomaly.js'])}
            return r,b
    broker=ReceiptBroker(control_token=secrets.token_urlsafe(32))
    policy=broker._policy({'allowed_domains':domains,
        'search_templates':{'html.duckduckgo.com':'https://html.duckduckgo.com/html/?q={query}',
            'duckduckgo.com':'https://duckduckgo.com/html/?q={query}'},
        'max_fetch_bytes':8_000_000,'max_media_fetch_bytes':12_000_000,'timeout_seconds':20})
    plan=[]
    for day in range(5,10):
        date=f'2025-08-{day:02}'
        for query in [f'incendie Ribaute {day} août 2025 photo video drone fumée flammes',
                      f'incendie Corbières {day} août 2025 reportage témoignage',
                      f'incendie Aude {day} août 2025 point situation préfecture sdis mairie',
                      f'incendie Corbières {day} août 2025 carte périmètre satellite',
                      f'incendie Ribaute {day} août 2025 site:francetvinfo.fr',
                      f'incendie Aude {day} août 2025 site:sdis11.fr',
                      f'incendie Corbières {day} août 2025 site:commons.wikimedia.org']:
            plan.append({'target_date':date,'query':query})
    manifest={'collector':'unchanged ResearchBroker, reviewed lab harness',
        'configuration_change':'Allow official duckduckgo.com redirect-link origin as well as html.duckduckgo.com. Target domains and public-address checks remain enforced.',
        'collector_sha256':hashlib.sha256((source/'fireviewer_evidence_ingestion/research_broker.py').read_bytes()).hexdigest(),
        'limits':{'max_source_pages':200,'search_results_per_query':50,'page_bytes':8_000_000},
        'queries':[],'pages':[],'candidates':{},'media_candidates':[], 'complete':False}
    def save():
        temp=out/'manifest.tmp';temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');temp.replace(out/'manifest.json')
    for item in plan:
        broker.last_response=None
        try:
            result=broker.search({'arguments':{'domain':'html.duckduckgo.com','query':item['query'],'limit':50}},policy)
            response=broker.last_response or {}
            state='provider_challenge' if response.get('challenge') else 'results_found' if result['links'] else 'no_matching_result'
            row={**item,'status':state,'response':response,'result_count':len(result['links']), 'next_cursor':result.get('next_cursor')}
            if state!='provider_challenge':
                for link in result['links']:
                    candidate=manifest['candidates'].setdefault(link['url'],{'url':link['url'],'title':link['title'],'query_dates':[]})
                    if item['target_date'] not in candidate['query_dates']:candidate['query_dates'].append(item['target_date'])
        except Exception as e:row={**item,'status':'request_failed','error_type':type(e).__name__}
        manifest['queries'].append(row);save();emit('query_finished',**row);time.sleep(1)
    candidates=list(manifest['candidates'].values())
    manifest['not_fetched_due_to_limit']=max(0,len(candidates)-200)
    seen_media=set()
    for candidate in candidates[:200]:
        url=candidate['url'];key=hashlib.sha256(url.encode()).hexdigest()[:20]
        try:
            info,raw=broker._fetch_public_content(url=url,policy=policy)
            if (broker.last_response or {}).get('challenge'):raise ValueError('provider challenge')
            file=pages/(key+'.bin');file.write_bytes(raw)
            row={**candidate,'status':'downloaded','path':'pages/'+file.name,
                'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'content_type':info.get('content_type'),
                'metadata':info.get('metadata',{}),'daily_eligibility':'not_reviewed',
                'query_dates_are_not_capture_dates':True}
            for media in info.get('media_links',[]):
                if media in seen_media:continue
                seen_media.add(media)
                manifest['media_candidates'].append({'url':media,'source_page':url,'status':'candidate_not_downloaded','capture_date':None,'license_status':'not_reviewed'})
        except Exception as e:row={**candidate,'status':'fetch_failed','error_type':type(e).__name__}
        manifest['pages'].append(row);save();emit('page_finished',url=url,status=row['status']);time.sleep(.2)
    manifest['complete']=True;manifest['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat();save()
    emit('discovery_finished',queries=len(plan),pages=len(manifest['pages']),media_candidates=len(seen_media),limit_skipped=manifest['not_fetched_due_to_limit'])

if __name__=='__main__':main()
