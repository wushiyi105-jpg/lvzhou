"""简历：切段、看技能到底写在哪一段。

只写在「技能」那一栏的技能，和写在「项目经历」里的技能，说服力不是一回事。
这个区别本地就能算出来，不用麻烦模型。
"""

from __future__ import annotations

import re

from . import skills

SECTION_WORDS = {
    "work": ("工作经历", "工作经验", "实习经历", "实习经验", "职业经历"),
    "project": ("项目经历", "项目经验", "项目"),
    "skill": ("专业技能", "技能", "技术栈", "能力"),
    "edu": ("教育经历", "教育背景", "学历"),
    "award": ("获奖", "荣誉", "证书", "资格证书"),
    "self": ("自我评价", "个人总结", "自我描述"),
}

HEADER = re.compile(r"^[#*•\-\s]*([\u4e00-\u9fa5A-Za-z ]{2,10})[：:]\s*$")
NUM_DOT = re.compile(r"^\d+[.、)]\s*")


def _section_of(line: str) -> str | None:
    stripped = line.strip().strip("#*").strip()
    head = stripped.split("：")[0].split(":")[0].strip()
    if 1 <= len(head) <= 8:
        for key, words in SECTION_WORDS.items():
            if head in words or any(head == w for w in words):
                return key
    # 也认 "【专业技能】" 这种写法
    m = re.fullmatch(r"【([^】]{2,10})】", stripped)
    if m:
        for key, words in SECTION_WORDS.items():
            if m.group(1).strip() in words:
                return key
    return None


def split_sections(text: str) -> dict[str, list[str]]:
    """按小标题切段，认不出的行归到 other。"""
    out: dict[str, list[str]] = {"other": []}
    current = "other"
    for line in (text or "").splitlines():
        raw = line.rstrip()
        if not raw.strip():
            continue
        # 求职意向写「AI 产品经理 / 数据分析」，那不是技能证据，单独放一段
        if raw.strip().startswith(("求职意向", "应聘岗位", "目标岗位")):
            out.setdefault("intent", []).append(raw.strip())
            continue
        sec = _section_of(raw)
        if sec:
            current = sec
            out.setdefault(current, [])
            continue
        out.setdefault(current, []).append(NUM_DOT.sub("", raw.strip()))
    return out


def section_text(text: str, name: str) -> str:
    return "\n".join(split_sections(text).get(name, []))


def evidence(text: str, skill: str) -> str:
    """这个技能的证据强度：strong（经历里真的用过）/ weak（只写在技能栏）/ none。

    求职意向不算证据——那只说明你想做什么，不说明你做过。
    """
    secs = split_sections(text)
    if skills.hits_of(skill, "\n".join(secs.get("work", []) + secs.get("project", []))):
        return "strong"
    body = "\n".join(v and "\n".join(v) or "" for k, v in secs.items() if k != "intent")
    if skills.hits_of(skill, body):
        return "weak"
    return "none"


def evidence_lines(text: str, skill: str, limit: int = 3) -> list[str]:
    """把这个技能的原文出处捞出来，先给经历段，再给技能栏。

    顺序很重要：只写在「求职意向」里的技能，拿求职意向那行当证据会误导人。
    """
    secs = split_sections(text)
    order = ("work", "project", "skill", "award", "edu", "self", "other")
    out: list[str] = []
    for key in order:
        for line in secs.get(key) or []:
            s = line.strip()
            if s and skills.hits_of(skill, s):
                out.append(s[:120])
            if len(out) >= limit:
                return out
    return out


METRIC = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:%|％|万[条份人单]?|亿[人条]?|千[人条]?"
    r"|人|次|个|单|篇|家|台|小时|天|年|倍|条|份|张|页|位|轮))"
)


def numbers(text: str) -> list[str]:
    """简历里出现的所有数字性表述。模型改写时不许出现超出这个集合的新数字。"""
    return [m.group(1).strip() for m in METRIC.finditer(text or "")]


def stats(text: str) -> dict:
    secs = split_sections(text)
    hit = skills.canonical(text)
    return {
        "chars": len(text or ""),
        "lines": len([x for x in (text or "").splitlines() if x.strip()]),
        "sections": sorted(k for k, v in secs.items() if v),
        "skills": hit,
        "strong_skills": [s for s in hit if evidence(text, s) == "strong"],
        "years": _years(text),
    }


def _years(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*年(?:以上)?(?:工作|相关|经验)", text or "")
    return float(m.group(1)) if m else None


def sections_for_prompt(text: str, limit_per_section: int = 12) -> str:
    """给模型的简历正文：保留段落结构，太长就截。"""
    secs = split_sections(text)
    label = {"work": "工作经历", "project": "项目经历", "skill": "技能栏",
             "edu": "教育", "award": "证书获奖", "self": "自我评价",
             "intent": "求职意向", "other": "其他"}
    parts = []
    for key in ("intent", "work", "project", "skill", "edu", "award", "self", "other"):
        lines = secs.get(key) or []
        if not lines:
            continue
        parts.append(f"【{label[key]}】")
        parts.extend("  " + line[:160] for line in lines[:limit_per_section])
        if len(lines) > limit_per_section:
            parts.append(f"  （还有 {len(lines) - limit_per_section} 行，略）")
    return "\n".join(parts)
