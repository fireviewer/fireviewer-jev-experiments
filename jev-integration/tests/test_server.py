import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.old_key = os.environ.pop('TYPESAFE_API_KEY', None)
        self.temp = tempfile.TemporaryDirectory()
        self.old_data = server.DATA
        server.DATA = Path(self.temp.name)
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.url = 'http://127.0.0.1:'+str(self.http.server_port)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join()
        server.DATA = self.old_data
        self.temp.cleanup()
        os.environ.pop('TYPESAFE_API_KEY', None)
        if self.old_key is not None: os.environ['TYPESAFE_API_KEY'] = self.old_key

    def request(self, route, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        with urlopen(Request(self.url+route, data, {'Content-Type':'application/json', **(headers or {})})) as response:
            return json.load(response)

    def test_key_memory_only_not_in_state_or_export(self):
        key = 'synthetic-secret-not-a-provider-key'
        result = self.request('/api/credentials', {'api_key':key})
        self.assertFalse(result['persisted'])
        self.assertTrue(self.request('/api/state')['typesafe_ready'])
        self.assertNotIn(key, json.dumps(self.request('/api/export')))
        self.assertEqual(list(server.DATA.iterdir()), [])
        self.request('/api/credentials', {'api_key':''})
        self.assertFalse(self.request('/api/state')['typesafe_ready'])

    def test_cross_origin_and_nonlocal_host_rejected(self):
        for headers in ({'Origin':'https://untrusted.example'}, {'Host':'untrusted.example'}):
            with self.assertRaises(HTTPError) as caught:
                self.request('/api/credentials', {'api_key':'test'}, headers)
            self.assertEqual(caught.exception.code,403)

    def test_header_injection_in_key_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/credentials', {'api_key':'test\r\nprivate'})
        self.assertEqual(caught.exception.code,400)
        self.assertNotIn('TYPESAFE_API_KEY',os.environ)

    def test_capture_traversal_is_not_a_file_read(self):
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/captures/../server.py')
        self.assertEqual(caught.exception.code,404)

    def test_component_catalog_and_missing_component_rejected(self):
        catalog = self.request('/api/components')
        self.assertEqual(len(catalog), 12)
        self.assertTrue(all(c['binding_status'] == 'export_adapter_only' for c in catalog))
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/run', {'mode':'offline_plan', 'cases':[{}]})
        self.assertEqual(caught.exception.code,400)


if __name__ == '__main__': unittest.main()
