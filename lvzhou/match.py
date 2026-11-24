"""JD 与简历的对账：要求抽出来，逐条看简历有没有、证不证得住。"""

from __future__ import annotations

import re

from . import resume, skills

DEGREE_RANK = {"大专": 1, "专科": 1, "本科": 2, "硕士": 3, "研究生": 3, "博士": 4}

REQ_LINE = re.compile(r"^\s*(?:[\d]+[.、)]|[-•·*])\s*(.{4,120})")
YEARS_REQ = re.compile(r"(\d+)\s*年(?:以上)?(?:相关|工作)?")


def lines_of(jd: str) -> list[str]:
    """把 JD 拆成一条条要求。标题行不算要求。"""
    out = []
    first = True
    for raw in (jd or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if first:
            # JD 第一行通常是岗位名（「AI 产品经理（应届/1 年以内）」），不是要求
            first = False
            if not any(w in s for w in skills.REQUIRE_WORDS):
                continue
        if s.endswith(("：", ":")) and len(s) <= 12:
            continue  # 「岗位职责：」「任职要求：」这类小标题
        m = REQ_LINE.match(s)
        if m:
            out.append(m.group(1).strip())
        elif len(s) <= 120 and (any(w in s for w in skills.REQUIRE_WORDS)
                                or skills.canonical(s)):
            out.append(s)
    return out


def requirements(jd: str) -> list[dict]:
    """每条要求带上它涉及的技能。"""
    rows = []
    for line in lines_of(jd):
        rows.append({
            "text": line[:120],
            "skills": skills.canonical(line),
            "must": any(w in line for w in ("必须", "要求", "至少", "以上")),
        })
    return rows


def degree_of(jd: str) -> str | None:
    for d in ("博士", "硕士", "研究生", "本科", "大专", "专科"):
        if re.search(rf"({d})(?:及)?(?:以上)?", jd or ""):
            return d
    return None


def years_of(jd: str) -> int | None:
    """只认「N 年以上 / N 年经验」这种硬要求，`1 年以内`是上限不是门槛。"""
    for m in YEARS_REQ.finditer(jd or ""):
        tail = (jd or "")[m.end():m.end() + 4]
        if any(w in tail for w in ("以内", "以下", "之内", "左右")):
            continue
        return int(m.group(1))
    return None


_CET_WORDS = {4: "四级", 6: "六级", 8: "八级"}


def cet_of(text: str) -> int | None:
    """CET 等级：CET-4 / CET4 / 四级 → 4。雅思托福不折算，交给模型说。"""
    s = (text or "").upper()
    for level in (8, 6, 4):
        if re.search(rf"CET[- ]?{level}(?![0-9])", s) or _CET_WORDS[level] in (text or ""):
            return level
    return None


def coverage(resume_text: str, jd: str) -> dict:
    """JD 要的技能，简历里各自是什么状态。"""
    jd_skills = skills.canonical(jd)
    rows = []
    for name in jd_skills:
        ev = resume.evidence(resume_text, name)
        rows.append({
            "skill": name,
            "status": {"strong": "有，而且在经历里用过",
                       "weak": "只在技能栏写了，经历里没体现",
                       "none": "简历里没有"}[ev],
            "level": ev,
            "jd_word": skills.hits_of(name, jd),
            "resume_line": (resume.evidence_lines(resume_text, name) or [""])[0],
        })

    missing = [r["skill"] for r in rows if r["level"] == "none"]
    weak = [r["skill"] for r in rows if r["level"] == "weak"]
    strong = [r["skill"] for r in rows if r["level"] == "strong"]

    # 分数只用来排序，不当结论：硬技能覆盖占七成，证据强度占三成
    cover = (len(strong) + 0.5 * len(weak)) / len(rows) if rows else 0.0
    score = round(100 * (0.7 * cover + 0.3 * (len(strong) / len(rows) if rows else 0)), 1)

    edu_gap = None
    jd_degree = degree_of(jd)
    if jd_degree:
        mine = [d for d in DEGREE_RANK if d in (resume_text or "")]
        level = max((DEGREE_RANK[d] for d in mine), default=0)
        if level < DEGREE_RANK[jd_degree]:
            edu_gap = f"JD 要 {jd_degree}，简历里没看到对得上的学历"

    year_gap = None
    jd_years = years_of(jd)
    if jd_years:
        mine = resume.stats(resume_text)["years"]
        if mine is None:
            year_gap = f"JD 要 {jd_years} 年经验，简历里没写工作年限"
        elif mine + 0.01 < jd_years:
            year_gap = f"JD 要 {jd_years} 年，简历里写的是 {mine:g} 年"

    english_gap = None
    want_cet = cet_of(jd)
    if want_cet:
        got = cet_of(resume_text)
        if got is None:
            english_gap = f"JD 要 CET-{want_cet}，简历里没写英语等级"
        elif got < want_cet:
            english_gap = f"JD 要 CET-{want_cet}，简历里是 CET-{got}"

    return {
        "score": score,
        "rows": rows,
        "strong": strong,
        "weak": weak,
        "missing": missing,
        "edu_gap": edu_gap,
        "year_gap": year_gap,
        "english_gap": english_gap,
        "jd_skill_count": len(jd_skills),
    }


def verdict(result: dict) -> tuple[str, str]:
    """一句话判断，不给虚假希望。"""
    n = result["jd_skill_count"]
    if not n:
        return "unknown", "JD 里没认出可对账的技能词，只能靠人看"
    missing, weak = result["missing"], result["weak"]
    if len(missing) >= 2 or (missing and result["score"] < 50):
        return "poor", f"{len(missing)}/{n} 个要求技能简历里完全没有，{len(weak)} 个只在技能栏"
    if len(weak) >= max(2, n // 2):
        return "fair", f"技能大多只写在技能栏，{len(weak)}/{n} 个经历里没有佐证"
    if missing or weak:
        return "fair", f"{len(result['strong'])}/{n} 个有经历佐证，还有 {len(missing) + len(weak)} 个要补"
    return "good", f"{len(result['strong'])}/{n} 个要求技能都有实际经历佐证"


def render(result: dict) -> str:
    level, why = verdict(result)
    lines = [f"匹配度 {result['score']}/100 · {why}"]
    for r in result["rows"]:
        mark = {"strong": "有", "weak": "弱", "none": "缺"}[r["level"]]
        lines.append(f"  {mark} {r['skill']:<8}{r['status']}")
        if r["resume_line"]:
            lines.append(f"      «{r['resume_line']}»")
    if result["edu_gap"]:
        lines.append(f"  ! {result['edu_gap']}")
    if result["year_gap"]:
        lines.append(f"  ! {result['year_gap']}")
    if result.get("english_gap"):
        lines.append(f"  ! {result['english_gap']}")
    return "\n".join(lines)
