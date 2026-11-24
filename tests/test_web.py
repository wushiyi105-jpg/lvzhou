import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from lvzhou import store, suggest, web

CV = "工作经历：\n- 用 SQL 取数\n项目经历：\n- 用 Python 处理 12 万条日志\n专业技能：\nSQL、Python"
JD = "数据分析师\n1. 掌握 SQL\n2. 了解机器学习"


class WebTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = store.connect(self.path)
        self.httpd = web.make_server(self.conn, port=0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.conn.close()
        os.unlink(self.path)

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def post(self, path, payload):
        req = urllib.request.Request(self.base + path,
                                     data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def seed(self):
        self.post("/api/resume", {"name": "罗晓", "body": CV})
        self.post("/api/jd", {"title": "数据分析师", "body": JD})

    def test_page(self):
        status, html = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("履舟", html)

    def test_list_empty(self):
        _, body = self.get("/api/list")
        self.assertEqual(json.loads(body), {"resumes": [], "jds": []})

    def test_add_resume(self):
        status, d = self.post("/api/resume", {"name": "罗晓", "body": CV})
        self.assertEqual(status, 200)
        self.assertIn("sql", d["skills"])

    def test_add_resume_empty(self):
        status, d = self.post("/api/resume", {"body": "  "})
        self.assertEqual(status, 400)

    def test_add_jd(self):
        status, d = self.post("/api/jd", {"title": "数据分析师", "body": JD})
        self.assertEqual(status, 200)
        self.assertTrue(d["requirements"])

    def test_match(self):
        self.seed()
        status, body = self.get("/api/match?resume=1&jd=1")
        self.assertEqual(status, 200)
        d = json.loads(body)
        self.assertIn("score", d)
        self.assertIn("level", d)

    def test_match_missing(self):
        self.assertEqual(self.get("/api/match?resume=1&jd=1")[0], 404)

    def test_match_bad_id(self):
        self.assertEqual(self.get("/api/match?resume=abc&jd=1")[0], 404)

    def test_advice(self):
        self.seed()
        reply = json.dumps({"rewrites": [{"before": "用 SQL 取数", "after": "独立用 SQL 取数"}],
                            "must_add": [], "summary": "缺机器学习"}, ensure_ascii=False)
        with patch.object(suggest.llm, "chat", return_value=reply):
            status, body = self.get("/api/advice?resume=1&jd=1")
        self.assertEqual(status, 200)
        d = json.loads(body)
        self.assertEqual(len(d["advice"]["rewrites"]), 1)
        self.assertIsNotNone(store.last_match(self.conn, 1, 1))

    def test_advice_model_down(self):
        self.seed()
        with patch.object(suggest.llm, "chat", side_effect=suggest.llm.LLMError("429")):
            status, _ = self.get("/api/advice?resume=1&jd=1")
        self.assertEqual(status, 502)

    def test_404(self):
        self.assertEqual(self.get("/nope")[0], 404)

    def test_post_404(self):
        self.assertEqual(self.post("/api/nope", {})[0], 404)

    def test_bad_json(self):
        req = urllib.request.Request(self.base + "/api/resume", data=b"not json",
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("应该报 400")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)


if __name__ == "__main__":
    unittest.main()
