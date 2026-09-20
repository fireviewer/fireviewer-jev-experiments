"""Acquire bounded public browse assets; never mislabel them as analysis-ready bands."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent

def fetch(row, maximum=5_000_000):
    path = ROOT / row['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists():
            raw = path.read_bytes()
        else:
            with urllib.request.urlopen(urllib.request.Request(row['source_url'], headers={'User-Agent': 'FireViewer-research/1.0'}), timeout=35) as response:
                raw = response.read(maximum + 1)
            if len(raw) > maximum:
                raise ValueError('asset exceeds download bound')
            if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8')):
                raise ValueError('response is not a PNG/JPEG')
            path.write_bytes(raw)
        row.update(status='downloaded', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    except Exception as exc:
        row.update(status='failed', error=type(exc).__name__ + ': ' + str(exc)[:120])
    row['acquired_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    print(row['id'], row['status'], flush=True)
    return row

def main():
    records = []
    output = ROOT / 'acquisition/satellite-manifest.json'
    def add(row):
        records.append(fetch(row))
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
    for day in range(5, 10):
        date = f'2025-08-{day:02d}'
        for layer, label in [('MODIS_Terra_CorrectedReflectance_TrueColor','terra-rgb'), ('VIIRS_NOAA20_Thermal_Anomalies_375m_All','viirs-thermal')]:
            query = urllib.parse.urlencode(dict(SERVICE='WMS', VERSION='1.1.1', REQUEST='GetMap', SRS='EPSG:4326', BBOX='2.4,42.9,3.0,43.3', WIDTH=1000, HEIGHT=667, TIME=date, LAYERS=layer, FORMAT='image/png', TRANSPARENT='TRUE'))
            add(dict(id=f'nasa-{label}-{date}', provider='NASA', kind='satellite_browse', local_date=date, time_basis='UTC daily composite; not a Europe/Paris observation timestamp', source_url='https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?'+query, path=f'acquisition/nasa/{date}-{label}.png', layer=layer, bbox=[2.4,42.9,3.0,43.3], bbox_role='discovery_only', analysis_ready=False, quality='not_yet_reviewed', attribution='NASA EOSDIS GIBS'))
    catalogue = json.loads((ROOT/'acquisition/copernicus/catalogue.json').read_text())
    for feature in catalogue['features']:
        asset = feature['assets']['thumbnail']
        add(dict(id=feature['id'], provider='Copernicus', kind='satellite_quicklook', local_date=feature['properties']['datetime'][:10], observed_at=feature['properties']['datetime'], source_url=asset['href'], path=f"acquisition/copernicus/{feature['id']}.jpg", analysis_ready=False, quality='343px tile overview; not spectral bands', attribution='Copernicus Sentinel data 2025 / CDSE', raw_assets_status='catalogued_not_downloaded'))

if __name__ == '__main__': main()
