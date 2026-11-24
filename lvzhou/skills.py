"""技能词表：中英文别名、大小写、常见写法。

匹配靠的是「同一个东西的不同叫法」，不是关键词堆叠。
写 Python 简历的人可能写 Python、python3、Py；写 JD 的人可能写「Python 开发经验」。
"""

from __future__ import annotations

# 规范名 → 各种写法。匹配时把文本压平（小写、去空格标点）再找。
SKILLS = {
    "python": ["python", "py3", "python3"],
    "sql": ["sql", "mysql", "postgresql", "postgres", "sqlserver", "oracle"],
    "excel": ["excel", "vlookup", "power query", "数据透视", "透视表"],
    "tableau": ["tableau"],
    "power bi": ["powerbi", "power bi", "power-bi"],
    "数据分析": ["数据分析", "数据挖掘", "数据洞察", "商业分析", "数据清洗", "数据处理", "ba"],
    "用户研究": ["用户研究", "用户调研", "可用性测试", "深访", "焦点小组"],
    "需求分析": ["需求分析", "需求管理", "需求梳理", "需求评审"],
    "原型": ["原型", "axure", "figma", "墨刀", "sketch", "交互设计"],
    "产品经理": ["产品经理", "产品策划", "产品设计", "产品实习", "产品助理", "产品岗", "pm"],
    "项目管理": ["项目管理", "项目推进", "进度管理", "敏捷", "scrum", "pmp"],
    "运营": ["运营", "内容运营", "活动运营", "用户运营"],
    "机器学习": ["机器学习", "machine learning", "ml", "深度学习", "dl"],
    "大模型": ["大模型", "llm", "gpt", "transformer", "rag", "prompt", "aigc"],
    "爬虫": ["爬虫", "scrapy", "requests", "抓取"],
    "git": ["git", "github", "gitlab", "版本管理"],
    "英语": ["英语", "english", "cet-4", "cet4", "cet-6", "cet6", "雅思", "托福", "ielts", "toefl"],
    "保险": ["保险", "核保", "理赔", "精算", "寿险", "健康险"],
    "财务": ["财务", "会计", "报表", "预算", "成本核算"],
    "销售": ["销售", "商务拓展", "bd", "客户开发"],
    "客服": ["客服", "客诉", "工单", "售后"],
    "写作": ["写作", "文案", "编辑", "内容创作", "新媒体"],
    "视频剪辑": ["视频剪辑", "剪映", "premiere", "pr", "final cut"],
}

# JD 里「要求」的动词，抽需求时当锚点
REQUIRE_WORDS = ("熟悉", "掌握", "精通", "熟练", "了解", "具备", "要求", "优先", "有", "能够", "会")

# 学历要求
DEGREES = ("博士", "硕士", "研究生", "本科", "大专", "专科")


import re

_SHORT = re.compile(r"[a-z0-9+#]+")


def _contains(text: str, alias: str) -> bool:
    """短别名（2 个字符以内，比如 pm、ml）要求独立词边界，否则 pmp 会命中 pm。"""
    flat_alias = _flatten(alias)
    if not flat_alias:
        return False
    if len(flat_alias) <= 2 and _SHORT.fullmatch(flat_alias):
        return re.search(rf"(?<![a-z0-9]){re.escape(flat_alias)}(?![a-z0-9])",
                         str(text).lower()) is not None
    return flat_alias in _flatten(text)


def canonical(text: str) -> list[str]:
    """一段文字里命中的所有规范技能名。"""
    hits = []
    for name, aliases in SKILLS.items():
        if any(_contains(text, a) for a in aliases):
            hits.append(name)
    return hits


def _flatten(text: str) -> str:
    s = str(text or "").lower()
    for ch in " \t\r\n，。、；：（）()【】[]「」\"'·-—_/|":
        s = s.replace(ch, "")
    return s


def hits_of(name: str, text: str) -> str | None:
    """这个技能在这段文字里是以哪个写法出现的（用来给用户看原词）。

    命中多个写法时取最长的那个——「Python3」比「Python」更贴原文。
    """
    found = [a for a in SKILLS.get(name, []) if _contains(text, a)]
    return max(found, key=len) if found else None


def all_names() -> list[str]:
    return list(SKILLS)
