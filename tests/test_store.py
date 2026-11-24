import tempfile
import unittest

from lvzhou import store


class StoreTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        import os

        os.close(fd)
        self.conn = store.connect(self.path)

    def tearDown(self):
        self.conn.close()
        import os

        os.unlink(self.path)

    def test_add_and_get(self):
        rid = store.add_resume(self.conn, "张三", "简历正文")
        self.assertEqual(store.get_resume(self.conn, rid)["name"], "张三")
        jid = store.add_jd(self.conn, "数据分析师", "要求：SQL")
        self.assertEqual(store.get_jd(self.conn, jid)["title"], "数据分析师")

    def test_lists(self):
        store.add_resume(self.conn, "A", "x")
        store.add_resume(self.conn, "B", "y")
        self.assertEqual(len(store.list_resumes(self.conn)), 2)
        self.assertEqual(store.list_jds(self.conn), [])

    def test_match_upsert(self):
        rid = store.add_resume(self.conn, "A", "x")
        jid = store.add_jd(self.conn, "B", "y")
        m1 = store.save_match(self.conn, rid, jid, {"score": 40}, {"rewrites": []})
        m2 = store.save_match(self.conn, rid, jid, {"score": 61}, {"rewrites": [1]})
        self.assertEqual(m1, m2)
        last = store.last_match(self.conn, rid, jid)
        self.assertEqual(last["result"]["score"], 61)
        self.assertEqual(last["advice"]["rewrites"], [1])

    def test_last_match_missing(self):
        self.assertIsNone(store.last_match(self.conn, 1, 1))

    def test_delete_resume_cascades(self):
        rid = store.add_resume(self.conn, "A", "x")
        jid = store.add_jd(self.conn, "B", "y")
        store.save_match(self.conn, rid, jid, {"score": 50}, {})
        store.delete_resume(self.conn, rid)
        self.assertIsNone(store.get_resume(self.conn, rid))
        self.assertIsNone(store.last_match(self.conn, rid, jid))

    def test_delete_jd_cascades(self):
        rid = store.add_resume(self.conn, "A", "x")
        jid = store.add_jd(self.conn, "B", "y")
        store.save_match(self.conn, rid, jid, {"score": 50}, {})
        store.delete_jd(self.conn, jid)
        self.assertIsNone(store.get_jd(self.conn, jid))
        self.assertIsNone(store.last_match(self.conn, rid, jid))

    def test_stats(self):
        rid = store.add_resume(self.conn, "A", "x")
        jid = store.add_jd(self.conn, "B", "y")
        store.save_match(self.conn, rid, jid, {"score": 72.5}, {})
        s = store.stats(self.conn)
        self.assertEqual(s["resumes"], 1)
        self.assertEqual(s["matches"], 1)
        self.assertEqual(s["best_score"], 72.5)

    def test_stats_empty(self):
        s = store.stats(self.conn)
        self.assertIsNone(s["best_score"])

    def test_stats_ignores_corrupt_result(self):
        rid = store.add_resume(self.conn, "A", "x")
        jid = store.add_jd(self.conn, "B", "y")
        store.save_match(self.conn, rid, jid, {"score": "很高"}, {})
        self.assertIsNone(store.stats(self.conn)["best_score"])


if __name__ == "__main__":
    unittest.main()
