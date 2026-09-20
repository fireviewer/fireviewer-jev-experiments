"""Publish actual daily receipts and visual overlays; never manufacture a perimeter."""
from pathlib import Path
import json,time,subprocess,hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent;DAILY=ROOT.parent
from lab_config import require_execute, credential
from receipt_policy import complete_day
CFG=require_execute()
SSH=str((DAILY/CFG['ssh_config']).resolve())
REMOTE=CFG['remote_dashboard']
m=json.loads((ROOT/'manifest.json').read_text())
def update():
 progress=json.loads((ROOT/'progress.json').read_text()) if (ROOT/'progress.json').exists() else {}
 admitted={c.get('job_id') for d in progress.get('days',[]) for c in d.get('chunks',[]) if c.get('comparison_eligible') is True}
 out={'updated_at':datetime.now(timezone.utc).isoformat(),'corpus_sha256':m['corpus_sha256'],'image':progress.get('image'),'days':[],'full_pipeline_validated':False}
 for d in m['days']:
  row={'date':d['date'],'expected_sources':len(d['sources']),'items':[],'runs':[],'report_drafts':[],'optical_branch':d['optical_branch'],'spatial_state':{'status':'awaiting_spatial_initialization','perimeter':None,'area_ha':None},'source_context':{s['id']:{'path':s['path'],'source_url':s['source_url'],'sha256':s['sha256']} for s in d['sources']}}
  for p in sorted((ROOT/'jobs').glob(d['date']+'-*-result.private.json')):
   r=json.loads(p.read_text());v=r.get('output') or {}
   if r.get('id') not in admitted:continue
   if not isinstance(v,dict):continue
   row['items'].extend(v.get('items',[]));row['runs'].append({'job_id':r['id'],'status':r['status'],'output_status':v.get('status'),'execution_ms':r.get('executionTime'),'model_runs':v.get('model_runs',[]),'validation_errors':v.get('validation_errors',[])})
   if v.get('report_draft'):row['report_drafts'].append(v['report_draft'])
  row['visual_artifacts_sha256']=hashlib.sha256(json.dumps(row['items'],sort_keys=True).encode()).hexdigest()
  row['all_sources_returned']=complete_day([s['id'] for s in d['sources']], row['items'], row['runs'])
  comparison=ROOT/(d['date']+'-comparison.json')
  if comparison.exists():
   c=json.loads(comparison.read_text())
   if c['image']==out['image'] and c['vision_artifacts_sha256']==row['visual_artifacts_sha256']:
    row['comparison']={'path':comparison.name,'variants':{k:{a:v[a] for a in ('cases','successful','failed','cost_usd','latency_ms','raw_observations_changed')} for k,v in c['variants'].items()}}
  out['days'].append(row)
 target=ROOT/'visual-results.json';target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 subprocess.run(['scp','-q','-F',SSH,str(target),CFG['ssh_host']+':/home/ec2-user/fv-campaign-visual-results.next'],check=True,capture_output=True,timeout=25)
 subprocess.run(['ssh','-F',SSH,CFG['ssh_host'],'sudo install -m0644 /home/ec2-user/fv-campaign-visual-results.next '+REMOTE+'campaign-visual-results.json.next && sudo mv '+REMOTE+'campaign-visual-results.json.next '+REMOTE+'campaign-visual-results.json'],check=True,capture_output=True,timeout=25)
 print(json.dumps({'published_at':out['updated_at'],'returned_items':sum(len(d['items']) for d in out['days'])}),flush=True)
if __name__=='__main__':
 while datetime.now(timezone.utc)<datetime.fromisoformat(CFG['stop_at']):
  try:update()
  except Exception as e:print(type(e).__name__,flush=True)
  time.sleep(20)
