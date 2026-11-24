import unittest

from lvzhou import match

RESUME = """张三

求职意向：数据分析

工作经历：
某公司  数据实习生  2023.07 - 2023.12
- 用 SQL 取数，写了 40 条查询

项目经历：
用户流失分析
- 用 Python 处理 12 万条日志

专业技能：
SQL、Python、Tableau
英语 CET-4
学历：本科
"""

JD = """数据分析师

任职要求：
1. 本科及以上学历
2. 掌握 SQL，能独立取数
3. 熟悉 Tableau 做可视化
4. 了解机器学习基础
5. 英语 CET-6 以上
6. 3 年以上相关经验
"""


class RequirementsTest(unittest.TestCase):
    def test_numbered_lines(self):
        reqs = match.requirements(JD)
        self.assertTrue(any("SQL" in r["text"] for r in reqs))

    def test_title_skipped(self):
        reqs = match.requirements(JD)
        self.assertFalse(any(r["text"] == "数据分析师" for r in reqs))

    def test_section_header_skipped(self):
        reqs = match.requirements("岗位职责：\n1. 负责报表")
        self.assertFalse(any("岗位职责" in r["text"] for r in reqs))

    def test_skills_attached(self):
        reqs = match.requirements(JD)
        sql = [r for r in reqs if "SQL" in r["text"]][0]
        self.assertIn("sql", sql["skills"])

    def test_bullet_lines(self):
        reqs = match.requirements("数据分析师\n- 熟练使用 Excel\n• 会写 Python")
        self.assertEqual(len(reqs), 2)

    def test_plain_first_line_is_title(self):
        reqs = match.requirements("AI 产品经理（应届）\n1. 掌握 SQL")
        self.assertEqual([r["text"] for r in reqs], ["掌握 SQL"])


class RequirementDetailTest(unittest.TestCase):
    def test_degree(self):
        self.assertEqual(match.degree_of(JD), "本科")

    def test_degree_missing(self):
        self.assertIsNone(match.degree_of("负责写代码"))

    def test_years(self):
        self.assertEqual(match.years_of(JD), 3)

    def test_years_within_is_not_a_bar(self):
        # 「1 年以内」是上限，不是门槛
        self.assertIsNone(match.years_of("应届或 1 年以内经验"))
        self.assertIsNone(match.years_of("3 年以下经验"))

    def test_cet(self):
        self.assertEqual(match.cet_of("英语 CET-6"), 6)
        self.assertEqual(match.cet_of("CET4 通过"), 4)
        self.assertEqual(match.cet_of("英语六级"), 6)
        self.assertIsNone(match.cet_of("英语流利"))


class CoverageTest(unittest.TestCase):
    def setUp(self):
        self.result = match.coverage(RESUME, JD)

    def test_strong_and_weak(self):
        rows = {r["skill"]: r["level"] for r in self.result["rows"]}
        self.assertEqual(rows["sql"], "strong")
        self.assertEqual(rows["tableau"], "weak")

    def test_missing(self):
        self.assertIn("机器学习", self.result["missing"])

    def test_score_between(self):
        self.assertGreater(self.result["score"], 0)
        self.assertLess(self.result["score"], 100)

    def test_english_gap(self):
        self.assertIn("CET-6", self.result["english_gap"])

    def test_year_gap(self):
        self.assertIn("3 年", self.result["year_gap"])

    def test_no_gap_when_matching(self):
        r = match.coverage("本科\n英语 CET-6\n5 年工作经验", "本科 CET-6 5 年以上经验")
        self.assertIsNone(r["english_gap"])
        self.assertIsNone(r["year_gap"])

    def test_empty_jd(self):
        r = match.coverage(RESUME, "我们招人，来聊聊")
        self.assertEqual(r["jd_skill_count"], 0)
        self.assertEqual(match.verdict(r)[0], "unknown")

    def test_verdict_poor(self):
        self.assertEqual(match.verdict(self.result)[0], "poor")

    def test_verdict_good(self):
        r = match.coverage("项目经历：\n- 用 Python 和 SQL 做过报表",
                           "要求：Python、SQL")
        self.assertEqual(match.verdict(r)[0], "good")

    def test_verdict_fair_when_only_skill_section(self):
        r = match.coverage("专业技能：\nPython、SQL", "要求：Python、SQL")
        self.assertEqual(match.verdict(r)[0], "fair")

    def test_render_contains_marks(self):
        text = match.render(self.result)
        self.assertIn("匹配度", text)
        self.assertIn("有", text)
        self.assertIn("缺", text)


if __name__ == "__main__":
    unittest.main()
