"""One-component post-vision variants, matched to immutable daily model receipts."""
from pathlib import Path
import json,sys,time,hashlib,subprocess
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent;DAILY=ROOT.parent
from lab_config import require_execute, credential
CFG=require_execute()
sys.path.insert(0,str(DAILY/'jev-integration'));import components,component_runner
sys.path.insert(0,str(ROOT));from freeze import digest
m=json.loads((ROOT/'manifest.json').read_text());ocr=json.loads((ROOT/'derived-text.json').read_text())
key=credential('TYPESAFE_API_KEY')
if key.startswith('TYPESAFE_API_KEY='):key=key.split('=',1)[1].strip().strip('"').strip("'")
folder=ROOT/'jev-postvision';folder.mkdir(exist_ok=True)
SSH=str((DAILY/CFG['ssh_config']).resolve())
REMOTE=CFG['remote_dashboard']

def call(case):
 p=folder/(case['case_id']+'.json')
 if p.exists():return json.loads(p.read_text())
 existing=[json.loads(f.read_text()) for f in folder.glob('*.json')];spent=sum(x['result']['report']['measured_typesafe_cost_usd'] for x in existing)
 if spent+0.002688>.45:raise RuntimeError('campaign_semantic_budget_exhausted')
 result=component_runner.run([case],component_id=case['component_id'],execute=True,api_key=key,max_cost_usd=.01)
 record={'case':case,'result':result};p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');return record

def main():
 done=set()
 while datetime.now(timezone.utc)<datetime.fromisoformat(CFG['stop_at']):
  if not (ROOT/'visual-results.json').exists():time.sleep(10);continue
  visual=json.loads((ROOT/'visual-results.json').read_text())
  for day,v in zip(m['days'],visual['days']):
   identity=(day['date'],v['visual_artifacts_sha256'])
   if not v['all_sources_returned'] or identity in done:continue
   references=[];sources={s['id']:s for s in day['sources']}
   for s in day['sources']:
    if s.get('text_path'):references.append((s['id'],(DAILY/(ocr[s['id']]['path'] if s['id'] in ocr else s['text_path'])).read_text()))
   # Every report is retained, in bounded document groups. No silent truncation.
   groups=[''];groupids=[[]]
   for sid,txt in references:
    entry=sid+'\n'+txt+'\n'
    if len(groups[-1])+len(entry)>9500:groups.append('');groupids.append([])
    groups[-1]+=entry;groupids[-1].append(sid)
   results={'LOC-02':[],'LOC-04':[]}
   for item in v['items']:
    sid=item['input_id'];source=sources[sid]
    facts=item.get('fact_proposals',[])
    claims=[str(f.get('summary') or f.get('description') or f.get('text') or f.get('claim') or json.dumps(f,ensure_ascii=False)) for f in facts]
    labels=sorted({r['label'] for r in item.get('pixel_regions',[])})
    vision_text='Visual models proposed these labels: '+', '.join(labels)+'. These are predictions, not verified facts.' if labels else 'No visual model region is available for this input.'
    source_text=(DAILY/(ocr[sid]['path'] if sid in ocr else source['text_path'])).read_text() if source.get('text_path') else source.get('caption') or source.get('alt') or ''
    frozen={'corpus_sha256':day['sources_sha256'],'vision_artifacts_sha256':v['visual_artifacts_sha256'],'pipeline_config_sha256':digest({'image':visual['image'],'revision':components.REVISION}),'prior_state_sha256':digest({'previous_day':day['prior_day'],'state':'awaiting_spatial_initialization'}),'arrival_batch_sha256':digest({'sources':day['sources_sha256'],'ocr':ocr})}
    # LOC-02 judges model interpretations against ALL official documentary groups.
    if labels or claims:
     for index,ref in enumerate(groups):
      claim='\n'.join(claims) if claims else vision_text
      if len(claim)>10000:raise ValueError('claim grouping required; never truncate')
      cid='LOC-02';case={'case_id':day['date']+'-'+sid+'-loc02-'+str(index),'group_id':source.get('independence_group') or sid,'component_id':cid,'changed_components':[cid],'data_use':'public_authorized','fixture_kind':'real_evidence','frozen_context':frozen,'semantic_input':{'claim':claim,'source_text':source_text,'reference_text':ref,'computed_checks_text':'Same observation day only. Exact capture time and camera pose unknown. No geometric contradiction inferred. Source reports can discuss different sites/times within the day.','vision_observation_text':vision_text}}
      # Stay within the API byte limit by splitting reference documents if needed.
      try:components.prepare(case,cid)
      except ValueError:
       if len(groupids[index])>1:
        for refid,reftxt in references:
         if refid not in groupids[index]:continue
         c=json.loads(json.dumps(case));c['case_id']+='-'+refid;c['semantic_input']['reference_text']=refid+'\n'+reftxt;results[cid].append(call(c))
       else:raise
      else:results[cid].append(call(case))
    # LOC-04 checks each real proposal; no generated substitute claims.
    for index,claim in enumerate(claims):
     cid='LOC-04';case={'case_id':day['date']+'-'+sid+'-loc04-'+str(index),'group_id':source.get('independence_group') or sid,'component_id':cid,'changed_components':[cid],'data_use':'public_authorized','fixture_kind':'real_evidence','frozen_context':frozen,'semantic_input':{'claim':claim,'supporting_text':source_text+'\n'+vision_text,'provenance_text':source['source_url']+'; private draft; unverified model proposals; no autonomous publication'}};results[cid].append(call(case))
   document={'date':day['date'],'corpus_sha256':day['sources_sha256'],'vision_artifacts_sha256':v['visual_artifacts_sha256'],'image':visual['image'],'baseline':{'kind':'actual_v2_daily_receipts_without_jev','input_count':len(v['items']),'runs':v['runs'],'facts':sum(len(x.get('fact_proposals',[])) for x in v['items']),'pixel_regions':sum(len(x.get('pixel_regions',[])) for x in v['items']),'spatial_state':v['spatial_state']},'variants':{},'quality_winner':None,'full_pipeline_validated':False,'publication_enabled':False}
   for cid,records in results.items():
    clean=[r['result']['records'][0] for r in records];valid=[r for r in clean if r['status']=='ok'];document['variants'][cid]={'intervention':'one optional textual control added to the baseline daily dossier','changed_components':[cid],'shared_visual_artifacts_sha256':v['visual_artifacts_sha256'],'raw_observations_changed':False,'cases':len(clean),'successful':len(valid),'failed':len(clean)-len(valid),'latency_ms':sum(r.get('latency_ms',0) for r in clean),'cost_usd':sum(r.get('cost_usd',0) for r in clean),'records':clean}
   out=ROOT/(day['date']+'-comparison.json');out.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n');done.add(identity);print(json.dumps({'date':day['date'],'variants':{k:{a:x[a] for a in ('cases','successful','failed')} for k,x in document['variants'].items()}}),flush=True)
   # Publish component details separately; they cannot overwrite the baseline.
   subprocess.run(['scp','-q','-F',SSH,str(out),CFG['ssh_host']+':/home/ec2-user/'+out.name],check=True,capture_output=True,timeout=30)
   subprocess.run(['ssh','-F',SSH,CFG['ssh_host'],'sudo install -m0644 /home/ec2-user/'+out.name+' '+REMOTE+out.name],check=True,capture_output=True,timeout=30)
  if len(done)==len(m['days']):return
  time.sleep(15)
if __name__=='__main__':main()
