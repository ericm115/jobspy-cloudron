import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from http.server import ThreadingHTTPServer

import app


class FakeFrame:
    def to_json(self, **kwargs):
        return '[{"site":"indeed","title":"Developer"}]'


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.server.api_key = "test-key-abcdefghijklmnopqrstuvwxyz123"
        sys.modules["jobspy"] = types.SimpleNamespace(scrape_jobs=lambda **kwargs: FakeFrame())
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        del sys.modules["jobspy"]

    def request(self, method, path, body=None, key=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Content-Type": "application/json"}
        if key is not None:
            headers["Authorization"] = "Bearer " + key
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_health_and_auth(self):
        self.assertEqual(self.request("GET", "/health"), (200, {"status": "ok"}))
        self.assertEqual(self.request("POST", "/scrape", '{}')[0], 401)
        self.assertEqual(self.request("POST", "/scrape", '{}', "wrong")[0], 401)
        self.assertEqual(self.request("POST", "/scrape", '{}', "é")[0], 401)

    def test_scrape_and_validation(self):
        key = self.server.api_key
        self.assertEqual(self.request("POST", "/scrape", '{"search_term":"developer"}', key),
                         (200, {"jobs": [{"site": "indeed", "title": "Developer"}]}))
        calls = []
        original = sys.modules["jobspy"].scrape_jobs
        sys.modules["jobspy"].scrape_jobs = lambda **kwargs: (calls.append(kwargs), FakeFrame())[1]
        try:
            self.assertEqual(self.request("POST", "/scrape", json.dumps({
                "search_term": "developer", "location": "Austin, TX", "results_wanted": 2,
                "hours_old": 72, "distance": 25, "fetch_description": True
            }), key)[0], 200)
            self.assertEqual(calls[0]["distance"], 25)
            self.assertIs(calls[0]["linkedin_fetch_description"], True)
            self.assertNotIn("fetch_description", calls[0])
            self.assertEqual(self.request("POST", "/scrape", '{"search_term":"developer"}', key)[0], 200)
            self.assertNotIn("linkedin_fetch_description", calls[1])
            self.assertEqual(self.request("POST", "/scrape", '{"search_term":"developer","fetch_description":false}', key)[0], 200)
            self.assertIs(calls[2]["linkedin_fetch_description"], False)
        finally:
            sys.modules["jobspy"].scrape_jobs = original
        for payload in ({}, {"search_term": "x", "results_wanted": 500},
                        {"search_term": "x", "results_wanted": True},
                        {"search_term": "x", "proxies": ["localhost"]},
                        {"search_term": "x", "site_name": ["google"]},
                        {"search_term": "x", "results_wanted": None},
                        {"search_term": "x", "distance": 0},
                        {"search_term": "x", "distance": 201},
                        {"search_term": "x", "distance": True},
                        {"search_term": "x", "distance": "25"},
                        {"search_term": "x", "fetch_description": "true"},
                        {"search_term": "x", "fetch_description": 1},
                        {"search_term": "x", "fetch_description": None}):
            with self.subTest(payload=payload):
                self.assertEqual(self.request("POST", "/scrape", json.dumps(payload), key)[0], 400)
        self.assertEqual(self.request("POST", "/scrape", "not-json", key)[0], 400)

    def test_missing_or_short_key_prevents_start(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "api-key")
            env = {**os.environ, "JOBSPY_KEY_PATH": path}
            command = [sys.executable, "-B", "app.py"]
            missing = subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(missing.returncode, 0)
            with open(path, "w", encoding="ascii") as key_file:
                key_file.write("weak")
            short = subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(short.returncode, 0)
            self.assertIn("api-key missing or too short", short.stderr)

    def test_busy(self):
        self.assertTrue(app.BUSY.acquire(False))
        try:
            self.assertEqual(self.request("POST", "/scrape", '{"search_term":"x"}', self.server.api_key)[0], 429)
        finally:
            app.BUSY.release()


if __name__ == "__main__":
    unittest.main()
