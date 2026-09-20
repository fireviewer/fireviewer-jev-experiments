"""Acquire publicly exposed originals for private incident analysis, with rights kept."""
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit
from acquire_satellite import fetch

ROOT=Path(__file__).resolve().parent
def main():
    photos=json.loads((ROOT/'discovery/flickr-photo-metadata.json').read_text())
    target=ROOT/'acquisition/flickr';target.mkdir(exist_ok=True)
    rows=[]
    for photo in photos:
        date=photo['stats']['data']['dateTaken']
        if not '2025-08-05' <= date[:10] <= '2025-08-09':continue
        image=photo['sizes']['data']['o']['data'];url='https:'+image['url']
        if urlsplit(url).hostname!='live.staticflickr.com':raise ValueError('Unexpected asset host')
        row={'id':'flickr-'+photo['id'],'provider':'Flickr','kind':'ground_image',
            'local_date':date[:10],'captured_at_literal':date,'timezone_status':'camera timezone unverified',
            'source_url':url,'source_page':'https://www.flickr.com/photos/larecettedujour/'+photo['id']+'/',
            'path':'acquisition/flickr/'+photo['id']+'.jpg',
            'license':'Flickr license 0; not a free license', 'rights':'private analysis only; no publication grant inferred',
            'attribution':'Veronica / larecettedujour', 'provenance_group':'flickr-album-72177720328180380',
            'observed_content_status':'not_reviewed','variant':'original',
            'width':image['width'],'height':image['height'],
            'published_at':dt.datetime.fromtimestamp(int(photo['stats']['data']['datePosted']),dt.timezone.utc).isoformat(),
            'capture_metadata_source':'public album modelExport photo-stats-models'}
        rows.append(fetch(row,maximum=12_000_000))
        (target/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
