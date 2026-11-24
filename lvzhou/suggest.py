"""让模型改简历。它能改措辞，不能加事实。

这是整个项目里我最在意的一条线：AI 改简历最容易做的事，就是替你编一段经历。
「主导千万级项目」「服务 300 万用户」——它不知道，但写出来很好看。

所以改完的每一句都要过两道核：
- 句子里出现的技能，必须是原句里就有、或者简历里别处已经写过
- 句子里出现的数字（万/亿/%/人/次…），必须在简历原文里出现过

过不了的句子不是删掉，而是标出来——我要让人看见模型编了什么，而不是偷偷擦干净。
"""

from __future__ import annotations

import re

from . import match, resume, skills, llm

SYSTEM = """你是简历编辑，不是职业顾问。

能做的：
- 把原句改得更具体、更有动作、更少形容词
- 调整语序、合并啰嗦的句子、把「负责」换成真的动词
- 指出哪条 JD 要求简历里没体现，让人自己去补

绝对不能做的：
- 编造任何没有的经历、项目、公司、时间、成果
- 添加原句里没有的数字（人数、金额、百分比、增长倍数）
- 添加简历里没写过的技能、工具、证书
- 替人写「我擅长 xx」，除非简历原文有这个依据

硬规则：改写的每一句都要能追溯到原句。追溯不到就不写，宁可少给一条。
如果某条 JD 要求简历里确实没有，写进 must_add，说清「需要你自己提供素材」，不要替他编。

只输出 JSON：
{"rewrites": [{"before": "原句", "after": "改后", "why": "为什么这么改"}],
 "must_add": [{"item": "JD 要但简历没有的", "note": "要你自己补什么素材"}],
 "summary": "两句话以内，说这份简历最大的一个问题"}"""

MAX_REWRITES = 6


def rewrite_prompt(resume_text: str, jd_text: str, result: dict) -> tuple[str, set[str]]:
    """拼提示词，同时返回「简历里已经有的技能」集合，给核验用。"""
    have = set(skills.canonical(resume_text))
    lines = [f"- {r['skill']}：{r['status']}" +
             (f"（原句：{r['resume_line'][:80]}）" if r["resume_line"] else "")
             for r in result["rows"]]
    user = ("【简历正文】\n" + resume.sections_for_prompt(resume_text) +
            "\n\n【目标 JD】\n" + jd_text.strip()[:2000] +
            "\n\n【本地对账结果】\n" + "\n".join(lines) +
            f"\n\n匹配度 {result['score']}/100。按边界改写，输出 JSON。")
    return user, have


def find_new_skills(text: str, allowed: set[str]) -> list[str]:
    """句子里冒出简历里没有的技能词。"""
    return [s for s in skills.canonical(text) if s not in allowed]


def find_new_numbers(text: str, resume_text: str) -> list[str]:
    got = set(resume.numbers(resume_text))
    return [n for n in resume.numbers(text) if n not in got]


def check_rewrite(rewrite: dict, resume_text: str, have_skills: set[str],
                  jd_skills: set[str] | None = None) -> tuple[list[str], list[str]]:
    """核一句话。返回 (不能用的, 要你自己确认的)。

    「不能用的」= 编了数字、编了简历里没有也没在 JD 出现的技能。
    「要确认的」= 用上了 JD 要、但简历没写过的技能词——这类可能是它把你的旧经历
    重新命名了，也可能是替你许愿，得由你自己判断。
    """
    after = str(rewrite.get("after") or "")
    before = str(rewrite.get("before") or "")
    blocked, confirm = [], []
    allowed = set(have_skills) | set(skills.canonical(before))
    for s in skills.canonical(after):
        if s in allowed:
            continue
        if jd_skills and s in jd_skills:
            confirm.append(f"把 JD 要求的「{s}」写进去了，确认你真做过再留")
        else:
            blocked.append(f"凭空加了技能：{s}")
    new_numbers = find_new_numbers(after, resume_text + " " + before)
    if new_numbers:
        blocked.append("凭空加了数字：" + "、".join(new_numbers))
    if not before.strip():
        blocked.append("没写原句，改了什么都对不上")
    return blocked, confirm


def _as_text(row) -> str:
    if isinstance(row, dict):
        for key in ("item", "text", "value", "skill"):
            if row.get(key):
                return str(row[key]).strip()
        return ""
    return str(row or "").strip()


def suggest(resume_text: str, jd_text: str, result: dict, config=None,
            max_tokens: int = 8000) -> dict:
    """返回 {rewrites, must_add, summary, error}。失败不抛。"""
    user, have = rewrite_prompt(resume_text, jd_text, result)
    try:
        raw = llm.chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            config=config, temperature=0.3, max_tokens=max_tokens,
        )
        data = llm.extract_json(raw)
        if not isinstance(data, dict):
            raise llm.LLMError("返回不是对象")
    except llm.LLMError as e:
        return {"rewrites": [], "must_add": [], "summary": "", "error": str(e),
                "fabricated": 0}

    rewrites = []
    jd_skills = set(skills.canonical(jd_text))
    for row in data.get("rewrites") or []:
        if not isinstance(row, dict):
            continue
        before = str(row.get("before") or "").strip()
        after = str(row.get("after") or "").strip()
        if not after:
            continue
        blocked, confirm = check_rewrite({"before": before, "after": after},
                                         resume_text, have, jd_skills)
        rewrites.append({
            "before": before[:200],
            "after": after[:300],
            "why": str(row.get("why") or "").strip()[:120],
            "problems": blocked,
            "confirm": confirm,
        })

    must_add = []
    for row in data.get("must_add") or []:
        item = _as_text(row)
        if not item:
            continue
        note = str(row.get("note") or "").strip() if isinstance(row, dict) else ""
        # 它推荐补充的项里如果藏着简历没写过的技能，也标出来——那是让你去学/去编的暗示
        fake = find_new_skills(item, have)
        must_add.append({"item": item[:120], "note": note[:120],
                         "not_in_resume": fake})

    summary = str(data.get("summary") or "").strip()
    return {
        "rewrites": rewrites[:MAX_REWRITES],
        "must_add": must_add,
        "summary": summary[:200],
        "error": "",
        "fabricated": sum(1 for r in rewrites if r["problems"]),
    }


def render(out: dict) -> str:
    if out.get("error") and not out.get("rewrites"):
        return f"✗ 模型没给改写：{out['error']}"
    lines = ["=== 改写 ==="]
    for i, r in enumerate(out["rewrites"], 1):
        lines.append(f"{i}. {r['after']}")
        if r["before"]:
            lines.append(f"   原句：{r['before']}")
        if r["why"]:
            lines.append(f"   为什么：{r['why']}")
        for p in r["problems"]:
            lines.append(f"   ! {p}")
        for p in r.get("confirm") or []:
            lines.append(f"   ? {p}")
    if out.get("must_add"):
        lines.append("")
        lines.append("=== 需要你自己补素材的 ===")
        for m in out["must_add"]:
            lines.append(f"  · {m['item']}" + (f" — {m['note']}" if m["note"] else ""))
            if m["not_in_resume"]:
                lines.append(f"    ! 简历里没写过：{'、'.join(m['not_in_resume'])}")
    if out.get("summary"):
        lines.append("")
        lines.append(out["summary"])
    if out.get("fabricated"):
        lines.append("")
        lines.append(f"! {out['fabricated']} 条改写出现了简历里没有的内容，别直接用")
    return "\n".join(lines)
