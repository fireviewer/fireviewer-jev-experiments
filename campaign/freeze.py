"""Freeze all admitted daily sources, including difficult cases; no day-size cap."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
ROOT=Path(__file__).resolve().parent
DAILY=ROOT.parent

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def checked(path,expected=None):
 p=DAILY/path;h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected:assert h==expected,path
 return {'path':path,'sha256':h,'bytes':p.stat().st_size}

def main():
 inventory=json.loads((DAILY/'inventory.json').read_text());days=[]
 for day in inventory['days']:
  date=day['date'];sources=[]
  for source in inventory['sources']:
   if source.get('local_date')!=date or source.get('role')=='excluded_candidate':continue
   if source.get('pipeline_branch') not in {'ground_visual','reports_text'}:continue
   assert source.get('file_verified'),source['id']
   row=dict(source);row['file_receipt']=checked(source['path'],source['sha256'])
   if source.get('text_path'):row['text_receipt']=checked(source['text_path'])
   sources.append(row)
  ground=[s['id'] for s in sources if s['pipeline_branch']=='ground_visual']
  reports=[s['id'] for s in sources if s['pipeline_branch']=='reports_text']
  # Technical windows preserve every item; all windows contribute to the same day.
  chunks=[{'branch':branch,'source_ids':ids[i:i+size]} for branch,ids,size in [('ground_visual',ground,4),('reports_text',reports,4)] for i in range(0,len(ids),size)]
  optical=next(x for x in inventory['branches']['sentinel2_optical_change']['days'] if x['date']==date)
  d={'date':date,'sources':sources,'sources_sha256':digest(sources),'chunks':chunks,
     'source_counts':{'ground_visual':len(ground),'official_reports':len(reports)},
     'optical_branch':{**optical,'result_receipt':checked(optical['result_path'],optical['sha256'])},
     'browse_only_ids':[s['id'] for s in inventory['sources'] if s.get('local_date')==date and s.get('role')=='display_preview'],
     'thermal_branch':inventory['branches']['thermal_activity'],
     'prior_day':days[-1]['date'] if days else None,'prior_state_policy':'canonical previous-day state, or explicit unavailable; never future observations',
     'availability_limitation':'Retrospective observation-day grouping. Exact historical publication/capture times are not verified for all sources.'}
  days.append(d)
 manifest={'schema':'fv-daily-campaign-1','campaign_id':'ribaute-20250805-09-bonsai2-jev-20260920','created_at':datetime.now(timezone.utc).isoformat(),
   'days':days,'all_admitted_dated_sources':sum(len(x['sources']) for x in days),'no_daily_source_cap':True,
   'excluded_unresolved_day_ids':[s['id'] for s in inventory['sources'] if s.get('role')=='visual_candidate_day_unresolved'],
   'comparison':'same visual execution reused; one textual advisory component added at a time, baseline without Jev',
   'quality_ground_truth':'No independent daily perimeter or human semantic labels supplied; no accuracy winner may be claimed.',
   'publication_enabled':False}
 manifest['corpus_sha256']=digest(manifest['days'])
 target=ROOT/'manifest.json'
 if target.exists():assert json.loads(target.read_text())['corpus_sha256']==manifest['corpus_sha256'],'immutable corpus changed'
 else:target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'days':[(d['date'],d['source_counts'],len(d['chunks'])) for d in days],'total':manifest['all_admitted_dated_sources'],'sha256':manifest['corpus_sha256']}))
if __name__=='__main__':main()
