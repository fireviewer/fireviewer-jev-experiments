"""Download the indexed Aude bulletins for the proposed daily campaign.

The website's index dates are preserved separately: they do not establish the
first publication time of each bulletin. Existing files are verified, not replaced.
"""
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
INDEX = 'https://www.aude.gouv.fr/Publications/Salle-de-Presse/Communiques-de-presse/Aout-2025/CP-Incendie-Departement-de-l-Aude'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href, self.parts, self.items = None, [], []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href, self.parts = dict(attrs).get('href'), []

    def handle_data(self, data):
        if self.href:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href:
            self.items.append((self.href, ' '.join(''.join(self.parts).split())))
            self.href = None


def main():
    index = ROOT / 'acquisition/official-index.html'
    parser = Links()
    parser.feed(index.read_text())
    folder = ROOT / 'acquisition/official'
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    for href, label in parser.items:
        cp = re.search(r'CP\s+(\d+)\s*-', label)
        date = re.search(r'\b(0?[5-9])\s+ao[uû]t\b', label, re.I)
        if not cp or not date or '.pdf' not in href.lower():
            continue
        number, day = int(cp[1]), int(date[1])
        hour = re.search(r'\b(\d{1,2})h(\d{2})?\b', label[date.end():])
        path = folder / f'2025-08-{day:02d}-cp-{number:02d}.pdf'
        parts = urlsplit(urljoin(INDEX, href))
        if parts.hostname != 'www.aude.gouv.fr' or parts.scheme != 'https':
            raise ValueError('Unexpected bulletin host')
        url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe='/%'), parts.query, ''))
        record = {'id': f'aude-cp-{number:02d}', 'provider':'official',
            'kind':'official_daily_report', 'local_date':f'2025-08-{day:02d}',
            'observed_time_local':f'{int(hour[1]):02d}:{hour[2] or "00"}' if hour else None,
            'timezone':'Europe/Paris', 'source_url':url, 'source_index':INDEX,
            'index_label':label, 'published_at':None,
            'publication_time_status':'first_publication_not_verified',
            'path':str(path.relative_to(ROOT)), 'status':'pending'}
        try:
            if not path.exists():
                request = urllib.request.Request(url, headers={'User-Agent':'FireViewer-Research/1.0'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    content = response.read(5_000_001)
                if not content.startswith(b'%PDF-') or len(content)>5_000_000:
                    raise ValueError('Not a bounded PDF')
                path.write_bytes(content)
            content = path.read_bytes()
            record.update(status='downloaded', sha256=hashlib.sha256(content).hexdigest(),
                bytes=len(content), acquired_at=datetime.now(timezone.utc).isoformat())
            if shutil.which('pdftotext'):
                text = path.with_suffix('.txt')
                subprocess.run(['pdftotext','-layout',str(path),str(text)],check=True,capture_output=True)
                record['text_path'] = str(text.relative_to(ROOT))
                record['text_sha256'] = hashlib.sha256(text.read_bytes()).hexdigest()
        except Exception as exc:
            record.update(status='failed', error_type=type(exc).__name__)
        records.append(record)
        temporary = folder / 'manifest.tmp'
        temporary.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
        temporary.replace(folder / 'manifest.json')
        print(json.dumps({k:record[k] for k in ('id','local_date','status')},ensure_ascii=False),flush=True)
    print(json.dumps({'bulletins':len(records),'downloaded':sum(r['status']=='downloaded' for r in records)}))


if __name__ == '__main__':
    main()
