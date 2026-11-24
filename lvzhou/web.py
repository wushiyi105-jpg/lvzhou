"""Web：左边选简历和 JD，右边出对账，再点一下问改写。"""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import match, resume, store, suggest

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>履舟 · 简历对账</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b0f14;color:#c9d1d9;font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{padding:16px 24px;border-bottom:1px solid #21262d;display:flex;gap:12px;align-items:baseline}
h1{margin:0;font-size:18px;color:#e3b341}
.sub{color:#8b949e;font-size:13px}
main{display:grid;grid-template-columns:minmax(300px,360px) 1fr;min-height:calc(100vh - 60px)}
aside{border-right:1px solid #21262d;padding:16px}
section{padding:18px 24px}
h2{font-size:15px;margin:18px 0 8px}
textarea{width:100%;height:120px;background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:8px;padding:8px;font:13px/1.5 inherit;margin-bottom:6px}
input{width:100%;background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:8px;padding:6px 9px;margin-bottom:6px;font:13px inherit}
button{background:#9e6a03;color:#fff;border:0;border-radius:6px;padding:7px 12px;font:13px inherit;cursor:pointer}
button.ghost{background:#21262d;color:#c9d1d9}
button:disabled{opacity:.45}
.sel{padding:7px 9px;border-radius:6px;cursor:pointer;border:1px solid transparent}
.sel:hover{background:#161b22}
.sel.on{border-color:#9e6a03;background:#1c1a12}
.k{color:#8b949e;font-size:13px}
.ok{color:#7ee787}.mid{color:#e3b341}.bad{color:#ff7b72}
.card{border:1px solid #21262d;border-radius:8px;padding:12px;margin-bottom:10px}
pre{background:#161b22;border-radius:8px;padding:10px;overflow:auto;font-size:12.5px;margin:6px 0}
.tag{font-size:12px;border-radius:9px;padding:1px 7px;background:#1c2f3d;color:#79c0ff}
</style></head><body>
<header><h1>履舟</h1><span class="sub">简历和 JD 对账——本地看字面，模型只会改措辞，不许加事实</span></header>
<main>
<aside>
  <h2>简历</h2>
  <div id="resume-list"></div>
  <input id="r-name" placeholder="名字（可空）">
  <textarea id="r-body" placeholder="粘简历正文…"></textarea>
  <button id="r-add">存这份简历</button>
  <h2>JD</h2>
  <div id="jd-list"></div>
  <input id="j-title" placeholder="岗位名（可空）">
  <textarea id="j-body" placeholder="粘 JD 正文…"></textarea>
  <button id="j-add">存这份 JD</button>
</aside>
<section>
  <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px">
    <button id="run" class="ghost">对账</button>
    <button id="ask" disabled>问改写</button>
    <span class="k" id="status">左边选一份简历和一份 JD</span>
  </div>
  <div id="out"><p class="k">对账全在本地算：JD 要的技能、简历里在哪一段写过、经历里有没有佐证。</p></div>
</section>
</main>
<script>
const $ = s => document.querySelector(s);
const esc = s => String(s==null?'':s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let picked = {resume: null, jd: null};
let rows = {resumes: [], jds: []};

async function load(){
  const d = await (await fetch('/api/list')).json();
  rows = d;
  $('#resume-list').innerHTML = d.resumes.map(r =>
    `<div class="sel" data-kind="resume" data-id="${r.id}">${esc(r.name)}<div class="k">${esc(r.created_at)}</div></div>`
  ).join('') || '<p class="k">还没有</p>';
  $('#jd-list').innerHTML = d.jds.map(r =>
    `<div class="sel" data-kind="jd" data-id="${r.id}">${esc(r.title)}<div class="k">${esc(r.created_at)}</div></div>`
  ).join('') || '<p class="k">还没有</p>';
  document.querySelectorAll('.sel').forEach(el => el.onclick = () => {
    const kind = el.dataset.kind;
    picked[kind] = Number(el.dataset.id);
    document.querySelectorAll(`.sel[data-kind="${kind}"]`).forEach(x => x.classList.remove('on'));
    el.classList.add('on');
    $('#ask').disabled = !(picked.resume && picked.jd);
    $('#status').textContent = picked.resume && picked.jd ? '可以跑了' : '还差一个';
  });
}

function renderResult(d){
  const cls = {poor:'bad', fair:'mid', good:'ok', unknown:'k'}[d.level] || 'k';
  let html = `<h2>匹配度 <span class="${cls}">${d.score}</span>/100 · ${esc(d.why)}</h2>`;
  html += `<div class="card">` + d.rows.map(r => {
    const c = {strong:'ok', weak:'mid', none:'bad'}[r.level];
    return `<div style="display:flex;justify-content:space-between;gap:12px;padding:4px 0;border-bottom:1px solid #161b22">
      <span>${esc(r.skill)} <span class="tag">${esc(r.jd_word || '')}</span></span>
      <span class="${c}">${esc(r.status)}</span></div>
      ${r.resume_line ? `<div class="k">«${esc(r.resume_line)}»</div>` : ''}`;
  }).join('') + `</div>`;
  [['edu_gap','学历'],['year_gap','年限'],['english_gap','英语']].forEach(([k,label]) => {
    if(d[k]) html += `<p class="bad">! ${label}：${esc(d[k])}</p>`;
  });
  return html;
}

$('#run').onclick = async () => {
  if(!(picked.resume && picked.jd)) return;
  $('#status').textContent = '本地算…';
  const d = await (await fetch(`/api/match?resume=${picked.resume}&jd=${picked.jd}`)).json();
  $('#status').textContent = '';
  if(d.error){ $('#out').innerHTML = `<p class="bad">${esc(d.error)}</p>`; return; }
  $('#out').innerHTML = renderResult(d);
};

$('#ask').onclick = async () => {
  $('#ask').disabled = true;
  $('#status').textContent = '模型在改…十几秒';
  const d = await (await fetch(`/api/advice?resume=${picked.resume}&jd=${picked.jd}`)).json();
  $('#ask').disabled = false;
  $('#status').textContent = '';
  if(d.error){ $('#out').innerHTML += `<p class="bad">✗ ${esc(d.error)}</p>`; return; }
  let html = renderResult(d.match) + `<h2>改写</h2>`;
  html += (d.advice.rewrites || []).map((r,i) => `<div class="card">
    <b>${i+1}. ${esc(r.after)}</b>
    ${r.before ? `<div class="k">原句：${esc(r.before)}</div>` : ''}
    ${r.why ? `<div class="k">为什么：${esc(r.why)}</div>` : ''}
    ${(r.problems||[]).map(p=>`<div class="bad">! ${esc(p)}</div>`).join('')}
    ${(r.confirm||[]).map(p=>`<div class="mid">? ${esc(p)}</div>`).join('')}</div>`).join('');
  if((d.advice.must_add||[]).length){
    html += `<h2>要你自己补素材的</h2>` + d.advice.must_add.map(m =>
      `<div class="card">${esc(m.item)}<div class="k">${esc(m.note)}</div>
       ${(m.not_in_resume||[]).length ? `<div class="mid">简历里没写过：${esc(m.not_in_resume.join('、'))}</div>` : ''}</div>`).join('');
  }
  if(d.advice.summary) html += `<p>${esc(d.advice.summary)}</p>`;
  $('#out').innerHTML = html;
};

async function add(kind){
  const body = $(kind === 'resume' ? '#r-body' : '#j-body').value.trim();
  if(!body) return alert('先粘正文');
  const name = $(kind === 'resume' ? '#r-name' : '#j-title').value.trim();
  const r = await fetch('/api/' + (kind === 'resume' ? 'resume' : 'jd'), {method:'POST',
    body: JSON.stringify({name, title: name, body})});
  const d = await r.json();
  if(d.error) return alert(d.error);
  $(kind === 'resume' ? '#r-body' : '#j-body').value = '';
  load();
}
$('#r-add').onclick = () => add('resume');
$('#j-add').onclick = () => add('jd');
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    conn = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _ids(self, qs):
        try:
            return int((qs.get("resume") or ["0"])[0]), int((qs.get("jd") or ["0"])[0])
        except ValueError:
            return None, None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/list":
            self._json({"resumes": [{k: r[k] for k in ("id", "name", "created_at")}
                                    for r in store.list_resumes(self.conn)],
                        "jds": [{k: r[k] for k in ("id", "title", "created_at")}
                                for r in store.list_jds(self.conn)]})
            return
        if parsed.path == "/api/match":
            rid, jid = self._ids(qs)
            r = store.get_resume(self.conn, rid) if rid else None
            j = store.get_jd(self.conn, jid) if jid else None
            if not r or not j:
                self._json({"error": "简历或 JD 不存在"}, 404)
                return
            result = match.coverage(r["body"], j["body"])
            level, why = match.verdict(result)
            self._json({**result, "level": level, "why": why})
            return
        if parsed.path == "/api/advice":
            rid, jid = self._ids(qs)
            r = store.get_resume(self.conn, rid) if rid else None
            j = store.get_jd(self.conn, jid) if jid else None
            if not r or not j:
                self._json({"error": "简历或 JD 不存在"}, 404)
                return
            result = match.coverage(r["body"], j["body"])
            level, why = match.verdict(result)
            out = suggest.suggest(r["body"], j["body"], result, config={})
            if out["error"] and not out["rewrites"]:
                self._json({"error": out["error"]}, 502)
                return
            store.save_match(self.conn, rid, jid, result, out)
            self._json({"match": {**result, "level": level, "why": why}, "advice": out})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/api/resume", "/api/jd"):
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 4 * 1024 * 1024:
            self._json({"error": "内容太大了"}, 413)
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "请求体不是合法 JSON"}, 400)
            return
        text = (body.get("body") or "").strip()
        if not text:
            self._json({"error": "正文不能空"}, 400)
            return

        if parsed.path == "/api/resume":
            name = (body.get("name") or "").strip() or "未命名简历"
            rid = store.add_resume(self.conn, name[:60], text)
            s = resume.stats(text)
            self._json({"id": rid, "sections": s["sections"], "skills": s["skills"]})
            return
        if parsed.path == "/api/jd":
            title = (body.get("title") or "").strip() or text.splitlines()[0][:40]
            jid = store.add_jd(self.conn, title[:60], text)
            self._json({"id": jid, "requirements": match.requirements(text)})
            return
        self._json({"error": "not found"}, 404)


def make_server(conn, host: str = "127.0.0.1", port: int = 8774) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"conn": conn})
    return ThreadingHTTPServer((host, port), handler)


def serve(conn, host: str = "127.0.0.1", port: int = 8774):
    httpd = make_server(conn, host, port)
    print(f"履舟已起：http://{host}:{port}  （Ctrl+C 退出）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n再见。")
    finally:
        httpd.server_close()
