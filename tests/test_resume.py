import unittest

from lvzhou import resume

CV = """张三

求职意向：产品经理 / 数据分析

教育背景：
某大学  统计学  本科  2019 - 2023

工作经历：
某公司  数据分析实习生  2023.07 - 2023.12
- 用 SQL 取数，写了 40 条查询
- 做了 3 份周报

项目经历：
用户流失分析  2023.03 - 2023.06
- 用 Python 处理 12 万条日志
- 输出 18 页报告

专业技能：
SQL、Python、Tableau
英语 CET-6
"""


class SplitTest(unittest.TestCase):
    def test_sections_recognized(self):
        secs = resume.split_sections(CV)
        self.assertIn("edu", secs)
        self.assertIn("work", secs)
        self.assertIn("project", secs)
        self.assertIn("skill", secs)

    def test_intent_separated(self):
        secs = resume.split_sections(CV)
        self.assertIn("intent", secs)
        self.assertNotIn("产品经理", "\n".join(secs.get("skill", [])))

    def test_bracket_header(self):
        secs = resume.split_sections("【项目经历】\n做了个东西")
        self.assertEqual(secs["project"], ["做了个东西"])

    def test_bullet_number_stripped(self):
        secs = resume.split_sections("工作经历：\n1. 做了 a\n2、做了 b")
        self.assertEqual(secs["work"], ["做了 a", "做了 b"])

    def test_unknown_lines_to_other(self):
        secs = resume.split_sections("随便一行\n专业技能：\nSQL")
        self.assertIn("随便一行", secs["other"])


class EvidenceTest(unittest.TestCase):
    def test_strong_when_in_work(self):
        self.assertEqual(resume.evidence(CV, "sql"), "strong")

    def test_strong_when_in_project(self):
        self.assertEqual(resume.evidence(CV, "python"), "strong")

    def test_weak_when_only_skill_section(self):
        self.assertEqual(resume.evidence("专业技能：\nTableau", "tableau"), "weak")

    def test_none(self):
        self.assertEqual(resume.evidence(CV, "大模型"), "none")

    def test_intent_is_not_evidence(self):
        text = "求职意向：数据分析\n\n专业技能：\nExcel"
        self.assertEqual(resume.evidence(text, "数据分析"), "none")

    def test_evidence_lines_prefer_work(self):
        lines = resume.evidence_lines(CV, "sql")
        self.assertTrue(lines[0].startswith("- 用 SQL"))

    def test_evidence_lines_limit(self):
        text = "\n".join(["- 用 python 做事"] * 5)
        self.assertEqual(len(resume.evidence_lines(text, "python", limit=2)), 2)


class NumbersTest(unittest.TestCase):
    def test_metric_with_unit(self):
        self.assertIn("12 万条", resume.numbers("处理 12 万条日志"))

    def test_percent(self):
        self.assertIn("40%", resume.numbers("提升了 40%"))

    def test_plain_year_not_metric(self):
        # 2023 这种年份不算可被模型滥用的业绩数字
        self.assertEqual(resume.numbers("2023.07 - 2023.12"), [])

    def test_multiple(self):
        got = resume.numbers("服务 300 万人，做了 5 次迭代")
        self.assertEqual(got, ["300 万人", "5 次"])


class StatsTest(unittest.TestCase):
    def test_basic(self):
        s = resume.stats(CV)
        self.assertEqual(s["sections"], ["edu", "intent", "other", "project", "skill", "work"])
        self.assertIn("sql", s["skills"])
        self.assertIn("sql", s["strong_skills"])
        self.assertNotIn("tableau", s["strong_skills"])

    def test_years_missing(self):
        self.assertIsNone(resume.stats(CV)["years"])

    def test_years_parsed(self):
        self.assertEqual(resume.stats("3 年工作经验")["years"], 3.0)

    def test_prompt_keeps_sections(self):
        text = resume.sections_for_prompt(CV)
        self.assertIn("【工作经历】", text)
        self.assertIn("【技能栏】", text)

    def test_prompt_truncates(self):
        text = "项目经历：\n" + "\n".join(f"- 第{i}行" for i in range(30))
        out = resume.sections_for_prompt(text, limit_per_section=5)
        self.assertIn("还有 25 行", out)


if __name__ == "__main__":
    unittest.main()
