import json
import os
import tempfile
import unittest
from unittest.mock import patch

from lvzhou import cli, store, suggest

ROOT = os.path.dirname(os.path.dirname(__file__))
CV = os.path.join(ROOT, "samples", "简历-罗晓.txt")
JD = os.path.join(ROOT, "samples", "JD-AI产品经理.txt")


class CliTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    def tearDown(self):
        os.unlink(self.path)

    def run_cli(self, argv):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["--db", self.path] + argv)
        return code, buf.getvalue()

    def seed(self):
        self.run_cli(["resume", CV, "--name", "罗晓"])
        self.run_cli(["jd", JD, "--title", "AI产品经理"])

    def test_add_resume(self):
        code, out = self.run_cli(["resume", CV, "--name", "罗晓"])
        self.assertEqual(code, 0)
        self.assertTrue("工作经历" in out or "work" in out, out)

    def test_add_resume_empty_file(self):
        empty = self.path + ".txt"
        open(empty, "w", encoding="utf-8").close()
        try:
            self.assertEqual(self.run_cli(["resume", empty])[0], 1)
        finally:
            os.unlink(empty)

    def test_add_jd_lists_requirements(self):
        code, out = self.run_cli(["jd", JD])
        self.assertEqual(code, 0)
        self.assertIn("抽出", out)
        self.assertIn("SQL", out)

    def test_list(self):
        code, out = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("简历", out)
        self.assertIn("JD", out)

    def test_match(self):
        self.seed()
        code, out = self.run_cli(["match", "1", "1"])
        self.assertEqual(code, 0)
        self.assertIn("匹配度", out)

    def test_match_json(self):
        self.seed()
        code, out = self.run_cli(["match", "1", "1", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out[out.index("{"):])
        self.assertIn("score", data)

    def test_match_out_file(self):
        self.seed()
        out_path = self.path + ".md"
        try:
            code, _ = self.run_cli(["match", "1", "1", "--out", out_path])
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as f:
                self.assertIn("匹配度", f.read())
        finally:
            os.unlink(out_path)

    def test_match_missing(self):
        self.assertEqual(self.run_cli(["match", "9", "1"])[0], 1)

    def test_advice(self):
        self.seed()
        reply = json.dumps({"rewrites": [{"before": "用 Excel 做用户反馈分类",
                                          "after": "用 Excel 分类 340 条用户反馈", "why": "动词前置"}],
                            "must_add": [], "summary": "缺大模型经验"}, ensure_ascii=False)
        with patch.object(suggest.llm, "chat", return_value=reply):
            code, out = self.run_cli(["advice", "1", "1"])
        self.assertEqual(code, 0)
        self.assertIn("动词前置", out)
        self.assertIn("已存下", out)
        conn = store.connect(self.path)
        try:
            self.assertIsNotNone(store.last_match(conn, 1, 1))
        finally:
            conn.close()

    def test_advice_model_down(self):
        self.seed()
        with patch.object(suggest.llm, "chat", side_effect=suggest.llm.LLMError("连不上")):
            code, out = self.run_cli(["advice", "1", "1"])
        self.assertEqual(code, 0)
        self.assertIn("连不上", out)

    def test_show(self):
        self.seed()
        self.assertEqual(self.run_cli(["show", "1", "1"])[0], 1)
        reply = json.dumps({"rewrites": [], "must_add": [], "summary": "还行"}, ensure_ascii=False)
        with patch.object(suggest.llm, "chat", return_value=reply):
            self.run_cli(["advice", "1", "1"])
        code, out = self.run_cli(["show", "1", "1"])
        self.assertEqual(code, 0)
        self.assertIn("上次对账", out)

    def test_rm(self):
        self.seed()
        code, out = self.run_cli(["rm", "resume", "1"])
        self.assertEqual(code, 0)
        self.assertIn("已删除", out)
        self.assertEqual(self.run_cli(["rm", "jd", "1"])[0], 0)

    def test_rm_missing(self):
        self.assertEqual(self.run_cli(["rm", "jd", "5"])[0], 1)

    def test_stats(self):
        code, out = self.run_cli(["stats"])
        self.assertEqual(code, 0)
        self.assertIn("resumes", out)


if __name__ == "__main__":
    unittest.main()
