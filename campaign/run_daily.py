"""Run immutable daily evidence through the actual deployed V2 worker.

Every admitted item runs. Technical windows are merged by day. Provider failures
and absent georeferencing remain explicit, never a fabricated successful replay.
"""
from datetime import datetime,timezone,timedelta
import hashlib,json,os,subprocess,sys,time,tomllib
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent;DAILY=ROOT.parent
from lab_config import require_execute, credential
CFG=require_execute()
sys.path.insert(0,str(ROOT));from freeze import digest
MANIFEST=json.loads((ROOT/'manifest.json').read_text())
ENDPOINT=json.loads((DAILY/CFG['endpoint_receipt']).read_text())
STOP=datetime.fromisoformat(ENDPOINT['stop_at'])
if STOP != datetime.fromisoformat(CFG['stop_at']):
 raise SystemExit('Endpoint and campaign spending deadlines must agree')
API_KEY=credential('RUNPOD_API_KEY')
HEADERS={'Authorization':'Bearer '+API_KEY,'Content-Type':'application/json','User-Agent':'FireViewer-Lab/1.0'}
AWS=[CFG['aws_cli'],'--profile',CFG['aws_profile'],'--region',CFG['aws_region']]
SSH=str((DAILY/CFG['ssh_config']).resolve())
REMOTE=CFG['remote_dashboard']
STATE=ROOT/'progress.json'

def now():return datetime.now(timezone.utc)
def write(path,data,private=False):
 path.parent.mkdir(exist_ok=True,parents=True);tmp=path.with_suffix(path.suffix+'.next')
 with open(tmp,'w',opener=lambda p,f:os.open(p,f,0o600 if private else 0o644)) as out:out.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 tmp.replace(path)
def api(suffix,payload=None):
 req=Request('https://api.runpod.ai/v2/'+ENDPOINT['id']+'/'+suffix,headers=HEADERS,data=json.dumps(payload).encode() if payload is not None else None)
 with urlopen(req,timeout=45) as r:return json.load(r)
def worker_identity(worker_id):
 with urlopen(Request('https://api.runpod.io/v2/serverless/'+ENDPOINT['id']+'/workers',headers=HEADERS),timeout=30) as response:
  data=json.load(response)
 rows=data if isinstance(data,list) else data.get('workers',data.get('items',[]))
 return next(({'id':x['id'],'image':x.get('image'),'version':x.get('version'),'gpu':x.get('gpuTypeId')} for x in rows if x.get('id')==worker_id),None)
def publish(state):
 state['updated_at']=now().isoformat();state['stop_at']=json.loads((DAILY/CFG['endpoint_receipt']).read_text())['stop_at'];write(STATE,state)
 try:
  subprocess.run(['scp','-q','-F',SSH,str(STATE),CFG['ssh_host']+':/home/ec2-user/fv-campaign-progress.json.next'],check=True,capture_output=True,timeout=15)
  subprocess.run(['ssh','-F',SSH,CFG['ssh_host'],'sudo install -m 0644 /home/ec2-user/fv-campaign-progress.json.next '+REMOTE+'campaign-progress.json.next && sudo mv '+REMOTE+'campaign-progress.json.next '+REMOTE+'campaign-progress.json'],check=True,capture_output=True,timeout=15)
 except (OSError,subprocess.SubprocessError):pass
 print(json.dumps({'at':state['updated_at'],'state':state['status'],'current':state.get('current')}),flush=True)

def build_payload(day,chunk,index):
 items=[];sources={s['id']:s for s in day['sources']}
 for sid in chunk['source_ids']:
  s=sources[sid];image=s['pipeline_branch']=='ground_visual'
  item={'input_id':sid,'media_type':'image' if image else 'article',
    'provenance':{'source_key':sid,'source_reference_url':s['source_url'],
      'license_identifier':s.get('license') or s.get('rights') or 'rights_unverified_private_analysis',
      'attribution':s.get('attribution') or s.get('provider') or 'source attributed in corpus',
      'trust':'unverified' if image else 'institutional','source_kind':'press' if image else 'authority',
      'source_confidence':'lead' if image else 'A+','publication_policy':'private_analysis_only'}}
  file=DAILY/s['path'];assert hashlib.sha256(file.read_bytes()).hexdigest()==s['sha256']
  if image:
   key='s3://'+CFG['artifact_bucket']+'/inputs/daily/'+s['sha256']+file.suffix
   subprocess.run(AWS+['s3','cp',str(file),key,'--sse','AES256','--only-show-errors'],check=True,capture_output=True,timeout=60)
   item['working_file_url']=subprocess.run(AWS+['s3','presign',key,'--expires-in','3600'],check=True,capture_output=True,text=True,timeout=30).stdout.strip()
  else:
   text=(DAILY/s['text_path']).read_text();assert hashlib.sha256((DAILY/s['text_path']).read_bytes()).hexdigest()==s['text_receipt']['sha256'];item['article_text']=text
   if not text.strip():
    ocr=json.loads((ROOT/'derived-text.json').read_text())[sid]
    assert ocr['parent_pdf_sha256']==s['sha256']
    data=(DAILY/ocr['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==ocr['sha256']
    item['article_text']=data.decode()
    item['provenance']['attribution']+=' · machine OCR, transcription unverified'
   assert item['article_text'].strip(), 'empty report must be prepared, never silently omitted'
  items.append(item)
 start=datetime.fromisoformat(day['date']).replace(tzinfo=ZoneInfo('Europe/Paris'))
 return {'schema_version':'2.0','batch_id':f"daily-{day['date']}-{index:02d}-r5",'batch_type':'external_media','priority':'scheduled',
  'analysis_window':{'analysis_id':'daily-'+day['date'],'fire_id':'FR-11-99991','episode_id':'lab-ribaute-20250805',
    'window_start_at':start.isoformat(),'window_end_at':(start+timedelta(days=1)).isoformat(),'local_date':day['date'],'timezone':'Europe/Paris'},'items':items}

def new_state():
 return {'campaign_id':MANIFEST['campaign_id'],'corpus_sha256':MANIFEST['corpus_sha256'],'image':ENDPOINT['image'],
  'status':'READY','scope':'Daily V2 worker processing of all admitted ground media and official reports; existing optical branch retained. Daily spatial fusion pending admissible initial perimeter.',
  'full_pipeline_validated':False,'publication_enabled':False,'source_total':MANIFEST['all_admitted_dated_sources'],'completed_sources':0,'stop_at':ENDPOINT['stop_at'],
  'days':[{'date':d['date'],'counts':d['source_counts'],'status':'PENDING','chunks':[],'jev':{},'spatial_state':'NEEDS_ADMISSIBLE_INITIAL_STATE','optical_status':d['optical_branch']['status']} for d in MANIFEST['days']]}

def main():
 state=json.loads(STATE.read_text()) if STATE.exists() else new_state()
 assert state['corpus_sha256']==MANIFEST['corpus_sha256'];assert state['image']==ENDPOINT['image'],'image changed: create a distinct run'
 state['status']='RUNNING';publish(state)
 for day,display in zip(MANIFEST['days'],state['days']):
  for i,chunk in enumerate(day['chunks']):
   receipt=ROOT/'jobs'/f"{day['date']}-{i:02d}.json";result=receipt.with_name(receipt.stem+'-result.private.json')
   if result.exists():
    saved=json.loads(result.read_text())
    if saved.get('status')=='COMPLETED' and i<len(display['chunks']) and display['chunks'][i].get('comparison_eligible') is True:
     continue
    state['status']='PAUSED_EXISTING_UNSUCCESSFUL_RECEIPT';publish(state);return
   remaining=(datetime.fromisoformat(json.loads((DAILY/CFG['endpoint_receipt']).read_text())['stop_at'])-now()).total_seconds()
   if remaining<180:state['status']='PAUSED_AT_SPENDING_DEADLINE';publish(state);return
   if len(display['chunks'])<=i:display['chunks'].append({'index':i,'branch':chunk['branch'],'source_count':len(chunk['source_ids']),'state':'PREPARING'})
   row=display['chunks'][i];display['status']='RUNNING';state['current']={'date':day['date'],'chunk':i+1,'chunks':len(day['chunks']),'branch':chunk['branch']};publish(state)
   if not receipt.exists():
    payload=build_payload(day,chunk,i)
    # Exact source hashes are recorded; signed transport URLs never enter receipts/UI.
    job=api('run',{'input':payload,'policy':{'executionTimeout':min(900000,int((remaining-60)*1000)),'ttl':min(1800000,int(remaining*1000))}})
    identity=json.loads(json.dumps(payload))
    for item in identity['items']:
     if 'working_file_url' in item:item['working_file_url']='sha256:'+next(s['sha256'] for s in day['sources'] if s['id']==item['input_id'])
    write(receipt,{'id':job['id'],'submitted_at':now().isoformat(),'source_ids':chunk['source_ids'],'day_sha256':day['sources_sha256'],'effective_input_sha256':digest(identity),'input_without_signed_urls':identity,'image':ENDPOINT['image']})
   job=json.loads(receipt.read_text());row['job_id']=job['id']
   while True:
    if now() >= STOP:
     api('cancel/'+job['id'],{})
     state['status']='PAUSED_AT_SPENDING_DEADLINE';publish(state);return
    try:r=api('status/'+job['id'])
    except (OSError,ValueError) as exc:
     row['status_error']=type(exc).__name__;publish(state);time.sleep(15);continue
    row['state']=r['status'];row['execution_ms']=r.get('executionTime');row['delay_ms']=r.get('delayTime')
    if r.get('workerId') and not row.get('actual_worker'):
     row['actual_worker']=worker_identity(r['workerId'])
    publish(state)
    if r['status'] in {'COMPLETED','FAILED','TIMED_OUT','CANCELLED'}:break
    time.sleep(15)
   write(result,r,True)
   if not row.get('actual_worker') or row['actual_worker'].get('image')!=ENDPOINT['image']:
    row['comparison_eligible']=False;state['status']='PAUSED_WORKER_IMAGE_MISMATCH';publish(state);return
   row['comparison_eligible']=True
   out=r.get('output') or {};row['pipeline_status']=out.get('status','no_output') if isinstance(out,dict) else 'invalid_output'
   if isinstance(out,dict):
    row['model_runs']=[{k:x.get(k) for k in ('model_role','model_id','status','error_code','inference_ms','peak_vram_bytes')} for x in out.get('model_runs',[])]
    row['items_returned']=len(out.get('items',[]));row['candidate_errors']=[{'candidate_id':x.get('candidate_id'),'error_code':x.get('error_code'),'diagnostic':(x.get('output_payload') or {}).get('diagnostic')} for x in out.get('candidate_runs',[]) if x.get('status')=='failed']
   state['completed_sources']+=len(chunk['source_ids']);publish(state)
   if r['status']!='COMPLETED':state['status']='PAUSED_PROVIDER_FAILURE';publish(state);return
  display['status']='PROCESSED' if all(c.get('pipeline_status')=='succeeded' for c in display['chunks']) else 'PROCESSED_WITH_ERRORS'
  publish(state)
 state['status']='WORKER_PASSES_FINISHED';state['current']=None;publish(state)
if __name__=='__main__':
 try:main()
 except Exception as exc:
  s=json.loads(STATE.read_text()) if STATE.exists() else new_state();s['status']='PAUSED_RUNTIME_ERROR';s['error_type']=type(exc).__name__;publish(s);raise
