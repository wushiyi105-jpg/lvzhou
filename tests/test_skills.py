import unittest

from lvzhou import skills


class CanonicalTest(unittest.TestCase):
    def test_english_lowercase(self):
        self.assertIn("python", skills.canonical("熟练使用 Python3 写脚本"))

    def test_chinese_synonym(self):
        self.assertIn("数据分析", skills.canonical("做过数据清洗和商业分析"))

    def test_sql_alias(self):
        self.assertIn("sql", skills.canonical("会用 MySQL 和 PostgreSQL"))

    def test_no_false_hit_on_pmp(self):
        # pm 只有两个字母，pmp 里不该命中产品经理
        self.assertNotIn("产品经理", skills.canonical("考过 PMP 证书"))
        self.assertIn("项目管理", skills.canonical("考过 PMP 证书"))

    def test_pm_standalone_hits(self):
        self.assertIn("产品经理", skills.canonical("做过 2 年 PM"))

    def test_fullwidth(self):
        self.assertIn("需求分析", skills.canonical("（需求分析）"))

    def test_empty(self):
        self.assertEqual(skills.canonical(""), [])

    def test_hits_of_returns_alias(self):
        self.assertEqual(skills.hits_of("python", "熟悉 Python3"), "python3")

    def test_hits_of_none(self):
        self.assertIsNone(skills.hits_of("python", "只会 Excel"))

    def test_unknown_name(self):
        self.assertIsNone(skills.hits_of("不存在的技能", "随便一段"))


if __name__ == "__main__":
    unittest.main()
