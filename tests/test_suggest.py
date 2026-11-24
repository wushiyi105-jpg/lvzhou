import json
import unittest
from unittest.mock import patch

from lvzhou import match, suggest

RESUME = """工作经历：
- 用 SQL 取数，写了 40 条查询
- 用 Excel 整理 340 条反馈
项目经历：
- 用 Python 处理 12 万条日志
"""

JD = """数据分析师
1. 掌握 SQL，能做数据分析
2. 熟悉 Tableau
3. 3 年以上经验
"""


def fake(reply):
    def _chat(messages, config=None, **kwargs):
        return reply
    return _chat


def run(reply):
    result = match.coverage(RESUME, JD)
    with patch.object(suggest.llm, "chat", fake(reply)):
        return suggest.suggest(RESUME, JD, result, config={"api_key": "x"})


class CheckRewriteTest(unittest.TestCase):
    def setUp(self):
        self.have = {"sql", "excel", "python"}
        self.jd = {"sql", "数据分析", "tableau"}

    def test_clean_rewrite(self):
        blocked, confirm = suggest.check_rewrite(
            {"before": "用 SQL 取数，写了 40 条查询",
             "after": "独立编写 40 条 SQL 查询支撑业务取数"}, RESUME, self.have, self.jd)
        self.assertEqual(blocked, [])
        self.assertEqual(confirm, [])

    def test_new_number_blocked(self):
        blocked, _ = suggest.check_rewrite(
            {"before": "写了 40 条查询", "after": "写了 40 条查询，覆盖 300 万用户"},
            RESUME, self.have, self.jd)
        self.assertTrue(any("数字" in b for b in blocked))

    def test_new_skill_not_in_jd_blocked(self):
        # 词表里的技能才能被认出来；词表外的东西（比如 Hadoop）这套规则看不见，是已知局限
        blocked, _ = suggest.check_rewrite(
            {"before": "用 Excel 整理反馈", "after": "用 Excel 和机器学习整理反馈"},
            RESUME, self.have, self.jd)
        self.assertTrue(any("机器学习" in b for b in blocked))

    def test_jd_skill_goes_to_confirm(self):
        blocked, confirm = suggest.check_rewrite(
            {"before": "用 Excel 整理反馈", "after": "用 Excel 做数据分析"},
            RESUME, self.have, self.jd)
        self.assertTrue(any("数据分析" in c for c in confirm))
        self.assertEqual(blocked, [])

    def test_missing_before_is_blocked(self):
        blocked, _ = suggest.check_rewrite({"before": "", "after": "带团队"}, RESUME, self.have, self.jd)
        self.assertTrue(any("原句" in b for b in blocked))

    def test_number_in_before_is_ok(self):
        blocked, _ = suggest.check_rewrite(
            {"before": "处理了 40 条", "after": "处理 40 条"}, RESUME, self.have, self.jd)
        self.assertEqual(blocked, [])


class SuggestTest(unittest.TestCase):
    def test_normal(self):
        reply = json.dumps({"rewrites": [
            {"before": "用 SQL 取数，写了 40 条查询", "after": "编写 40 条 SQL 查询支撑取数", "why": "动词前置"},
        ], "must_add": [{"item": "Tableau", "note": "需要你自己补作品"}],
            "summary": "缺可视化经验"}, ensure_ascii=False)
        out = run(reply)
        self.assertEqual(len(out["rewrites"]), 1)
        self.assertEqual(out["rewrites"][0]["problems"], [])
        self.assertEqual(out["fabricated"], 0)
        self.assertTrue(out["must_add"][0]["not_in_resume"])

    def test_fabrication_counted(self):
        reply = json.dumps({"rewrites": [
            {"before": "写了 40 条查询", "after": "写了 40 条查询，服务 300 万用户"},
        ]}, ensure_ascii=False)
        out = run(reply)
        self.assertEqual(out["fabricated"], 1)
        self.assertTrue(out["rewrites"][0]["problems"])

    def test_max_six(self):
        rows = [{"before": "用 SQL 取数", "after": f"用 SQL 取数 v{i}"} for i in range(9)]
        out = run(json.dumps({"rewrites": rows}, ensure_ascii=False))
        self.assertEqual(len(out["rewrites"]), suggest.MAX_REWRITES)

    def test_blank_after_skipped(self):
        out = run(json.dumps({"rewrites": [{"before": "a", "after": "  "},
                                          {"before": "用 SQL 取数", "after": "用 SQL 取数"}]},
                             ensure_ascii=False))
        self.assertEqual(len(out["rewrites"]), 1)

    def test_model_down(self):
        with patch.object(suggest.llm, "chat", side_effect=suggest.llm.LLMError("429")):
            result = match.coverage(RESUME, JD)
            out = suggest.suggest(RESUME, JD, result, config={"api_key": "x"})
        self.assertEqual(out["rewrites"], [])
        self.assertIn("429", out["error"])

    def test_bad_json(self):
        out = run("我觉得你的简历挺好的")
        self.assertEqual(out["rewrites"], [])
        self.assertTrue(out["error"])

    def test_system_says_no_fabrication(self):
        self.assertIn("编造", suggest.SYSTEM)
        self.assertIn("数字", suggest.SYSTEM)

    def test_prompt_includes_jd_and_resume(self):
        payload, have = suggest.rewrite_prompt(RESUME, JD, match.coverage(RESUME, JD))
        self.assertIn("Tableau", payload)
        self.assertIn("SQL", payload)
        self.assertEqual(have, {"sql", "excel", "python"})

    def test_render(self):
        out = {"rewrites": [{"before": "a", "after": "b", "why": "c", "problems": ["凭空加了数字：300 万"],
                             "confirm": []}], "must_add": [{"item": "Tableau", "note": "",
                                                            "not_in_resume": ["tableau"]}],
               "summary": "s", "error": "", "fabricated": 1}
        text = suggest.render(out)
        self.assertIn("凭空加了数字", text)
        self.assertIn("1 条改写", text)
        self.assertIn("Tableau", text)

    def test_render_error(self):
        self.assertIn("✗", suggest.render({"rewrites": [], "must_add": [], "summary": "",
                                           "error": "连不上", "fabricated": 0}))


if __name__ == "__main__":
    unittest.main()
