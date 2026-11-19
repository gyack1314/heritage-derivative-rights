"""Exercise the local recipient source contract using real loopback HTTP."""
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class RecipientSourceTests(unittest.TestCase):
    def test_receive_then_drop_query_duplicate_and_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            child = subprocess.Popen(
                [sys.executable, str(ROOT / 'tools/recipient.py'), '--state',
                 str(Path(temp) / 'receipts.sqlite3'), '--port', '0', '--drop-first-response'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                port = json.loads(child.stdout.readline())['port']
                url = f'http://127.0.0.1:{port}/deliveries'
                body = 'synthetic recipient payload'
                item = dict(id='delivery-local-1', enterprise='E1',
                            content_sha256=hashlib.sha256(body.encode()).hexdigest(), body=body)
                request = Request(url, data=json.dumps(item).encode(),
                                  headers={'Content-Type': 'application/json'}, method='POST')
                with self.assertRaises((http.client.RemoteDisconnected, URLError)):
                    urlopen(request, timeout=5)
                with urlopen(url + '/' + item['id'], timeout=5) as response:
                    receipt = json.load(response)
                self.assertEqual(receipt['content_sha256'], item['content_sha256'])
                with urlopen(request, timeout=5) as response:
                    self.assertTrue(json.load(response)['accepted'])
                item['body'] = 'different bytes'
                item['content_sha256'] = hashlib.sha256(item['body'].encode()).hexdigest()
                conflict = Request(url, data=json.dumps(item).encode(), method='POST')
                with self.assertRaises(HTTPError) as error:
                    urlopen(conflict, timeout=5)
                self.assertEqual(error.exception.code, 409)
            finally:
                child.terminate()
                child.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
