"""Live individual FV-01 / FV-02 controls on ALL daily source text.

They add advisory metadata without removing media or changing visual execution.
No baseline classifier or human labels are invented; quality scores stay absent.
"""
import json,hashlib,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent;DAILY=ROOT.parent
from lab_config import require_execute, credential
CFG=require_execute()
sys.path.insert(0,str(DAILY/'jev-integration'));import component_runner,components
sys.path.insert(0,str(ROOT));from freeze import digest
m=json.loads((ROOT/'manifest.json').read_text());ocr=json.loads((ROOT/'derived-text.json').read_text())
key=credential('TYPESAFE_API_KEY')
if key.startswith('TYPESAFE_API_KEY='):key=key.split('=',1)[1].strip().strip('"').strip("'")
folder=ROOT/'jev-intake';folder.mkdir(exist_ok=True)
summary={'corpus_sha256':m['corpus_sha256'],'status':'RUNNING','days':{},'quality_ranking':None,'reason':'No independent human labels; baseline has no equivalent semantic control. Each variant adds one advisory component.'}
for d in m['days']:
 summary['days'][d['date']]={}
 for cid in ['FV-01','FV-02']:
  records=[]
  for source in d['sources']:
   target=folder/(d['date']+'-'+cid+'-'+source['id']+'.json')
   if target.exists():result=json.loads(target.read_text())
   else:
    if source.get('text_path'):
     p=DAILY/(ocr[source['id']]['path'] if source['id'] in ocr else source['text_path']);text=p.read_text()
    else:text=source.get('caption') or source.get('alt') or ''
    semantic={'title':'','text':text,'caption':'','language':'fr','source_id':source['id']} if cid=='FV-01' else {'text':text,'author_alias':source.get('provider') or 'source officielle','provenance':source['source_url']}
    case={'case_id':source['id'],'group_id':source.get('independence_group') or source.get('parent_video_id') or source['id'],'component_id':cid,'changed_components':[cid],'data_use':'public_authorized','semantic_input':semantic,'fixture_kind':'real_evidence',
          'frozen_context':{'corpus_sha256':d['sources_sha256'],'vision_artifacts_sha256':digest({'boundary':'textual intake before necessary vision'}),'pipeline_config_sha256':digest({'component_revision':components.REVISION,'vision_not_filtered':True}),'prior_state_sha256':digest({'status':'backend_empty_no_initial_perimeter'}),'arrival_batch_sha256':digest({'source_id':source['id'],'text_sha256':hashlib.sha256(text.encode()).hexdigest()})}}
    result=component_runner.run([case],component_id=cid,execute=True,api_key=key,max_cost_usd=.01)
    result['input_case']=case
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
   records.extend(result['records'])
   summary['days'][d['date']][cid]={'completed':len(records),'total':len(d['sources']),'successful':sum(x['status']=='ok' for x in records),'cost_usd':sum(x.get('cost_usd',0) for x in records),'latency_ms':sum(x.get('latency_ms',0) for x in records),'vision_skipped':0}
   summary['updated_at']=datetime.now(timezone.utc).isoformat();(ROOT/'jev-intake-progress.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'day':d['date'],'component':cid,**summary['days'][d['date']][cid]}),flush=True)
summary['status']='FINISHED';(ROOT/'jev-intake-progress.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
