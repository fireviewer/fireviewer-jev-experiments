"""Read pinned existing evaluation manifest using HTTP ranges, then selected media."""
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import zipfile
from huggingface_hub import HfFileSystem

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
MANIFEST = 'fire-pointing-lora-v1/corpus/wikimedia-candidates-v0.1.0/manifest.jsonl'

def main():
    inventory = json.loads((BASE/'cpu-scaleup/source-inspection/firewarning-train-bundles-v1/inventory.json').read_text())
    token = (BASE/'data/hftoken').read_text().strip()
    fs = HfFileSystem(token=token)
    target = ROOT/'acquisition/ground'
    target.mkdir(parents=True, exist_ok=True)
    archive = f"datasets/{inventory['repo']}@{inventory['revision']}/fire-pointing-lora-v1.zip"
    with fs.open(archive, 'rb', block_size=2*1024**2, cache_type='blockcache', cache_options={'maxblocks':4}) as handle:
        with zipfile.ZipFile(handle) as z:
            raw = z.read(MANIFEST)
            if hashlib.sha256(raw).hexdigest() != 'a4ebdb91d4d9af47d4304df92d973d1d77d5327105ca030506934f8eafcc7a70':
                raise ValueError('manifest differs from pinned source snapshot')
            rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
            rows = [r for r in rows if r['source_id']=='commons_corbieres_2025']
            (target/'candidates.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
            print('Candidate dates:',dict(collections.Counter(str(r.get('captured_at_literal'))[:10] for r in rows)),flush=True)
            selected = []
            for r in rows:
                date = str(r.get('captured_at_literal',''))[:10]
                if not '2025-08-05' <= date <= '2025-08-09': continue
                member = str(Path(MANIFEST).parent / r['image_relpath'])
                if z.getinfo(member).file_size > 12_000_000: raise ValueError('image exceeds bound')
                content = z.read(member)
                sha = hashlib.sha256(content).hexdigest()
                if sha != r['sha256']: raise ValueError('image SHA mismatch')
                name = sha+'.jpg'
                (target/name).write_bytes(content)
                row = dict(id=r['sample_id'], provider='Wikimedia Commons', kind='ground_image', local_date=date, captured_at_literal=r['captured_at_literal'], timezone_status='camera timezone unverified', source_url=r['source_asset']['description_url'], path='acquisition/ground/'+name, sha256=sha, bytes=len(content), status='downloaded', license=r['license'], attribution=r['source_asset'].get('artist'), license_url=r['source_asset'].get('license_url'), variant=r['source_asset'].get('variant'), provenance_group=r.get('split_group'), near_duplicate_of=r.get('near_duplicate_of'), original_record=r, observed_content_status='not_reviewed', acquired_at=dt.datetime.now(dt.timezone.utc).isoformat(), source_archive={'repo':inventory['repo'],'revision':inventory['revision'],'member':member})
                selected.append(row)
                (target/'manifest.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2)+'\n')
                print(date,r['sample_id'],len(content),flush=True)

if __name__=='__main__': main()
