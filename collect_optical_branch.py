"""Execute the existing FireViewer Sentinel-2 collector for each historical cutoff."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--sources-root',type=Path,required=True);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    for repo in ['fireviewer-contracts','fireviewer-evidence-ingestion']:
        sys.path.insert(0,str(args.sources_root/repo/'src'))
    from fireviewer_evidence_ingestion.mvp import satellite_corpus as module
    root=args.root/'acquisition/sentinel2-analysis';root.mkdir(parents=True,exist_ok=True)
    path=root/'manifest.json'
    manifest={'branch':'sentinel2_optical_change','processor':module.PROCESSOR_REVISION,'processor_source_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),'complete':False,'days':[]}
    def save():
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n');temp.replace(path)
    for day in range(5,10):
        date=f'2025-08-{day:02}'
        request=module.SatelliteCorpusRequest(incident_id='ribaute-corbieres-20250805',bbox=(2.4,42.9,3.0,43.3),event_started_at=dt.datetime(2025,8,5,14,15,tzinfo=dt.timezone.utc),evaluation_cutoff_at=dt.datetime(2025,8,day,21,59,59,tzinfo=dt.timezone.utc),maximum_pairs=4,maximum_window_pixels=4_000_000,maximum_output_bytes=1024**3)
        row={'date':date,'status':'running','request':request.model_dump(mode='json')};manifest['days'].append(row);save();print(json.dumps({'date':date,'status':'running'}),flush=True)
        try:
            result=module.collect(request,root/date)
            f=root/date/'result.json';f.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
            row.update(status=result['reason'],result_path=str(f.relative_to(args.root)),pair_count=len(result['pairs']),written_bytes=result['written_bytes'],sha256=hashlib.sha256(f.read_bytes()).hexdigest())
        except Exception as e:row.update(status='failed',error_type=type(e).__name__,error=str(e)[:400])
        save();print(json.dumps(row,default=str),flush=True)
    manifest['complete']=True;manifest['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat();save()

if __name__=='__main__':main()
