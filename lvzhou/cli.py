"""命令行入口。"""

from __future__ import annotations

import argparse
import json
import os

from . import match, resume, store, suggest

_OPENED: list = []


def _open(args):
    conn = store.connect(args.db)
    _OPENED.append(conn)
    return conn


def _read(path: str) -> str:
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def _cfg(args):
    if args.api_key or args.base_url or args.model:
        cfg = {}
        if args.api_key:
            cfg["api_key"] = args.api_key
        if args.base_url:
            cfg["base_url"] = args.base_url
        if args.model:
            cfg["model"] = args.model
        return cfg
    return None


def cmd_add_resume(args) -> int:
    conn = _open(args)
    body = _read(args.file)
    if not body.strip():
        print(f"✗ {args.file} 是空的")
        return 1
    name = args.name or os.path.splitext(os.path.basename(args.file))[0]
    rid = store.add_resume(conn, name, body)
    s = resume.stats(body)
    print(f"· 简历 [{rid}] {name} —— {s['lines']} 行，认出的段落：{'、'.join(s['sections'])}")
    print(f"  技能 {len(s['skills'])} 个，其中在经历里有佐证的 {len(s['strong_skills'])} 个")
    return 0


def cmd_add_jd(args) -> int:
    conn = _open(args)
    body = _read(args.file)
    if not body.strip():
        print(f"✗ {args.file} 是空的")
        return 1
    title = args.title or body.splitlines()[0][:40]
    jid = store.add_jd(conn, title, body)
    reqs = match.requirements(body)
    print(f"· JD [{jid}] {title} —— 抽出 {len(reqs)} 条要求")
    for r in reqs:
        extra = f"（{'、'.join(r['skills'])}）" if r["skills"] else ""
        print(f"  · {r['text'][:60]}{extra}")
    return 0


def cmd_list(args) -> int:
    conn = _open(args)
    print("简历：")
    rows = store.list_resumes(conn)
    for r in rows:
        print(f"  [{r['id']}] {r['name']} · {r['created_at']}")
    if not rows:
        print("  还没有")
    print("JD：")
    rows = store.list_jds(conn)
    for r in rows:
        print(f"  [{r['id']}] {r['title']} · {r['created_at']}")
    if not rows:
        print("  还没有")
    return 0


def cmd_match(args) -> int:
    conn = _open(args)
    r = store.get_resume(conn, args.resume)
    j = store.get_jd(conn, args.jd)
    if not r:
        print(f"✗ 没有 id={args.resume} 的简历")
        return 1
    if not j:
        print(f"✗ 没有 id={args.jd} 的 JD")
        return 1
    result = match.coverage(r["body"], j["body"])
    print(f"=== {r['name']} → {j['title']} ===")
    print(match.render(result))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.out:
        level, why = match.verdict(result)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(f"# {r['name']} → {j['title']}\n\n")
            f.write(f"匹配度 {result['score']}/100（{level}）：{why}\n\n```\n")
            f.write(match.render(result) + "\n```\n")
        print(f"\n已写到 {args.out}")
    return 0


def cmd_advice(args) -> int:
    conn = _open(args)
    r = store.get_resume(conn, args.resume)
    j = store.get_jd(conn, args.jd)
    if not r or not j:
        print("✗ 简历或 JD 不存在")
        return 1
    result = match.coverage(r["body"], j["body"])
    print(match.render(result))
    print("\n问模型改简历…（十几秒）", flush=True)
    out = suggest.suggest(r["body"], j["body"], result, config=_cfg(args))
    print("\n" + suggest.render(out))
    if not out["error"]:
        store.save_match(conn, args.resume, args.jd, result, out)
        print(f"\n· 已存下这次对账（{len(out['rewrites'])} 条改写）")
    if args.json:
        print(json.dumps({"match": result, "advice": out}, ensure_ascii=False, indent=2))
    return 0


def cmd_show(args) -> int:
    conn = _open(args)
    m = store.last_match(conn, args.resume, args.jd)
    if not m:
        print("这对简历和 JD 还没对过账。先跑 match 或 advice。")
        return 1
    print(f"=== 上次对账 {m['created_at']} ===")
    print(match.render(m["result"]))
    if m["advice"]:
        print()
        print(suggest.render(m["advice"]))
    return 0


def cmd_rm(args) -> int:
    conn = _open(args)
    if args.what == "resume":
        if not store.get_resume(conn, args.id):
            print(f"✗ 没有 id={args.id} 的简历")
            return 1
        store.delete_resume(conn, args.id)
    else:
        if not store.get_jd(conn, args.id):
            print(f"✗ 没有 id={args.id} 的 JD")
            return 1
        store.delete_jd(conn, args.id)
    print(f"· [{args.id}] {args.what} 已删除（连带对账记录）")
    return 0


def cmd_stats(args) -> int:
    conn = _open(args)
    print("统计：", store.stats(conn))
    return 0


def cmd_serve(args) -> int:
    from . import web

    conn = _open(args)
    web.serve(conn, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lvzhou", description="简历和 JD 对账，改写只准改措辞。")
    p.add_argument("--db", default="data/lvzhou.db")
    p.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    p.add_argument("--api-key")
    p.add_argument("--base-url")
    p.add_argument("--model")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("resume", help="加一份简历")
    a.add_argument("file")
    a.add_argument("--name")
    a.set_defaults(func=cmd_add_resume)

    b = sub.add_parser("jd", help="加一份 JD")
    b.add_argument("file")
    b.add_argument("--title")
    b.set_defaults(func=cmd_add_jd)

    sub.add_parser("list", help="简历和 JD 列表").set_defaults(func=cmd_list)

    m = sub.add_parser("match", help="本地对账，不调模型")
    m.add_argument("resume", type=int)
    m.add_argument("jd", type=int)
    m.add_argument("--json", action="store_true")
    m.add_argument("--out")
    m.set_defaults(func=cmd_match)

    ad = sub.add_parser("advice", help="对账 + 让模型改写")
    ad.add_argument("resume", type=int)
    ad.add_argument("jd", type=int)
    ad.add_argument("--json", action="store_true")
    ad.set_defaults(func=cmd_advice)

    sh = sub.add_parser("show", help="看上次对账结果")
    sh.add_argument("resume", type=int)
    sh.add_argument("jd", type=int)
    sh.set_defaults(func=cmd_show)

    rm = sub.add_parser("rm", help="删简历或 JD")
    rm.add_argument("what", choices=["resume", "jd"])
    rm.add_argument("id", type=int)
    rm.set_defaults(func=cmd_rm)

    sub.add_parser("stats", help="统计").set_defaults(func=cmd_stats)

    sv = sub.add_parser("serve", help="起 Web")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8774)
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    finally:
        while _OPENED:
            try:
                _OPENED.pop().close()
            except Exception:  # noqa: BLE001
                pass
