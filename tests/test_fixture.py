import json
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class FixtureContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = Path(__file__).resolve().parents[1] / 'fixture' / 'server.py'
        cls.process = subprocess.Popen(
            [sys.executable, '-u', str(script), '--host', '127.0.0.1', '--port', '0'],
            stdout=subprocess.PIPE, text=True,
        )
        cls.addClassCleanup(cls.process.stdout.close)
        cls.addClassCleanup(cls.process.wait, 5)
        cls.addClassCleanup(cls.process.kill)
        cls.base = 'http://127.0.0.1:' + cls.process.stdout.readline().strip()
        if cls.process.poll() is not None or cls.base.endswith(':'):
            raise RuntimeError('Fixture did not announce a listening port')

    def chat(self, **kwargs):
        payload = {'model': 'ops-fixture', 'messages': [{'role': 'user', 'content': 'Hello'}]}
        payload.update(kwargs)
        return urlopen(Request(self.base + '/v1/chat/completions', json.dumps(payload).encode(),
                               {'Content-Type': 'application/json'}), timeout=3)

    def test_json_and_error(self):
        with self.chat() as response:
            self.assertEqual(json.load(response)['choices'][0]['message']['content'], 'ops fixture')
        with self.assertRaises(HTTPError) as exception:
            self.chat(model='missing')
        self.assertEqual(exception.exception.code, 404)
        exception.exception.close()

    def test_stream_and_metrics(self):
        with self.chat(stream=True) as response:
            self.assertEqual(response.headers.get_content_type(), 'text/event-stream')
            self.assertIn(b'data: [DONE]', response.read())
        with urlopen(self.base + '/metrics', timeout=3) as response:
            self.assertIn(b'ops_fixture_requests_total', response.read())

    def test_worker_json_object(self):
        with self.chat(response_format={'type': 'json_object'}) as response:
            message = json.load(response)['choices'][0]['message']['content']
        self.assertEqual(json.loads(message)['tool'], 'record_request')
