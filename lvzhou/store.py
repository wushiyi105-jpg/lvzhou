"""简历和 JD 都存下来，对账结果一起存。

同一份简历投不同岗位，是常见用法，所以简历单独一张表、JD 单独一张表，对账记录关联两者。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    jd_id INTEGER NOT NULL,
    result TEXT NOT NULL DEFAULT '{}',
    advice TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_match_pair ON matches(resume_id, jd_id);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(path: str = "data/lvzhou.db") -> sqlite3.Connection:
    import os

    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_resume(conn, name: str, body: str) -> int:
    with _LOCK:
        cur = conn.execute("INSERT INTO resumes(name, body, created_at) VALUES (?,?,?)",
                           (name, body, now()))
        conn.commit()
        return cur.lastrowid


def add_jd(conn, title: str, body: str) -> int:
    with _LOCK:
        cur = conn.execute("INSERT INTO jds(title, body, created_at) VALUES (?,?,?)",
                           (title, body, now()))
        conn.commit()
        return cur.lastrowid


def get_resume(conn, rid: int) -> dict | None:
    row = conn.execute("SELECT * FROM resumes WHERE id=?", (rid,)).fetchone()
    return dict(row) if row else None


def get_jd(conn, jid: int) -> dict | None:
    row = conn.execute("SELECT * FROM jds WHERE id=?", (jid,)).fetchone()
    return dict(row) if row else None


def list_resumes(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM resumes ORDER BY id").fetchall()]


def list_jds(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM jds ORDER BY id").fetchall()]


def save_match(conn, resume_id: int, jd_id: int, result: dict, advice: dict) -> int:
    """同一对简历+JD 只留最新一次对账，投递前重跑是常事。"""
    with _LOCK:
        old = conn.execute("SELECT id FROM matches WHERE resume_id=? AND jd_id=?",
                           (resume_id, jd_id)).fetchone()
        payload = (json.dumps(result, ensure_ascii=False),
                   json.dumps(advice, ensure_ascii=False), now())
        if old:
            conn.execute("UPDATE matches SET result=?, advice=?, created_at=? WHERE id=?",
                         payload + (old["id"],))
            conn.commit()
            return old["id"]
        cur = conn.execute(
            "INSERT INTO matches(resume_id, jd_id, result, advice, created_at) VALUES (?,?,?,?,?)",
            (resume_id, jd_id) + payload)
        conn.commit()
        return cur.lastrowid


def last_match(conn, resume_id: int, jd_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM matches WHERE resume_id=? AND jd_id=?",
                       (resume_id, jd_id)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["result"] = json.loads(d["result"] or "{}")
    d["advice"] = json.loads(d["advice"] or "{}")
    return d


def delete_resume(conn, rid: int) -> None:
    with _LOCK:
        conn.execute("DELETE FROM matches WHERE resume_id=?", (rid,))
        conn.execute("DELETE FROM resumes WHERE id=?", (rid,))
        conn.commit()


def delete_jd(conn, jid: int) -> None:
    with _LOCK:
        conn.execute("DELETE FROM matches WHERE jd_id=?", (jid,))
        conn.execute("DELETE FROM jds WHERE id=?", (jid,))
        conn.commit()


def stats(conn) -> dict:
    resumes = conn.execute("SELECT COUNT(*) n FROM resumes").fetchone()["n"]
    jds = conn.execute("SELECT COUNT(*) n FROM jds").fetchone()["n"]
    rows = conn.execute("SELECT result FROM matches").fetchall()
    scores = []
    for r in rows:
        try:
            value = json.loads(r["result"] or "{}").get("score")
        except ValueError:
            continue
        if isinstance(value, (int, float)):
            scores.append(float(value))
    return {"resumes": resumes, "jds": jds, "matches": len(rows),
            "best_score": max(scores) if scores else None}
