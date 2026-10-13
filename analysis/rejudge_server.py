#!/usr/bin/env python3
"""Local page for re-judging would-warn cases by hand. Binds 127.0.0.1 only.

Serves the cases from ~/research/pog-data/review/rejudge-cases.json (built by
rejudge_prepare.py) and saves every verdict at once to rejudge-verdicts.json (mode 600).
Claude's own verdicts stay hidden until all cases are judged.

    python3 analysis/rejudge_server.py [port]
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REVIEW = os.path.expanduser("~/research/pog-data/review")
CASES = os.path.join(REVIEW, "rejudge-cases.json")
VERDICTS = os.path.join(REVIEW, "rejudge-verdicts.json")


def load_verdicts():
    try:
        return json.load(open(VERDICTS))
    except (OSError, ValueError):
        return {}


def save_verdicts(v):
    tmp = VERDICTS + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(v, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, VERDICTS)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            return self.send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/data":
            cases = json.load(open(CASES))
            verdicts = load_verdicts()
            done = all(str(c["id"]) in verdicts and verdicts[str(c["id"])].get("verdict") for c in cases)
            for c in cases:
                if not done:  # blind until everything is judged
                    c.pop("my_verdict", None)
                    c.pop("my_note", None)
            return self.send(200, json.dumps({"cases": cases, "verdicts": verdicts, "done": done}, ensure_ascii=False),
                             "application/json")
        self.send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/save":
            return self.send(404, "not found", "text/plain")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        v = load_verdicts()
        v[str(body["id"])] = {k: body.get(k) for k in ("verdict", "why", "note", "key")}
        save_verdicts(v)
        self.send(200, "ok", "text/plain")


PAGE = r"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Переоцінка попереджень</title>
<style>
:root{--bg:#fafaf8;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--line:#e4e3de;--edit:#c2610c;--editbg:#fdf1e6;
--ok:#1f7a3f;--okbg:#e8f5ec;--bad:#b42318;--badbg:#fdecea;--you:#2b59c3;--youbg:#ebf0fb;--acc:#1d1d1b}
@media (prefers-color-scheme: dark){:root{--bg:#161615;--fg:#ecebe6;--mut:#9a9993;--card:#1f1f1d;--line:#33322f;
--edit:#f0a35e;--editbg:#33261a;--ok:#6fcf8f;--okbg:#17291e;--bad:#f28b82;--badbg:#341c1a;--you:#8fb0f5;--youbg:#1b2337;--acc:#ecebe6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;z-index:5;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.bar{flex:1;min-width:120px;height:6px;background:var(--line);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
main{max-width:980px;margin:0 auto;padding:16px 16px 190px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
h1{font-size:18px;margin:0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);margin:0 0 8px}
.warn{border-left:4px solid var(--bad)}.reply{white-space:pre-wrap;max-height:340px;overflow:auto}
.mut{color:var(--mut)}code,pre{font:12.5px/1.45 ui-monospace,Menlo,monospace}
.step{border-left:3px solid var(--line);padding:6px 10px;margin:6px 0;border-radius:0 6px 6px 0}
.step.say{color:var(--mut)}.step.edit,.step.writes{border-color:var(--edit);background:var(--editbg)}
.step.test{border-color:var(--ok);background:var(--okbg)}.step.test.fail{border-color:var(--bad);background:var(--badbg)}
.step.you{border-color:var(--you);background:var(--youbg)}.step.last{outline:2px solid var(--edit)}
.tag{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:10px;margin-right:6px;background:var(--line)}
.step.edit .tag,.step.writes .tag{background:var(--edit);color:var(--card)}.step.test .tag{background:var(--ok);color:var(--card)}
.step.test.fail .tag{background:var(--bad)}.step.you .tag{background:var(--you);color:var(--card)}
pre{white-space:pre-wrap;word-break:break-word;margin:4px 0 0;max-height:4.5em;overflow:hidden;cursor:pointer}pre.open{max-height:none}
.out{color:var(--mut)}
footer{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;z-index:5}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;max-width:980px;margin:0 auto 6px}
button{font:inherit;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:8px;padding:8px 12px;cursor:pointer}
button.on{background:var(--acc);color:var(--bg);border-color:var(--acc)}button.big{font-weight:600}
kbd{font:11px ui-monospace,Menlo,monospace;border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-left:4px;color:var(--mut)}
input{font:inherit;flex:1;min-width:200px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
.help{display:none}.help.show{display:block}.help li{margin:4px 0}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
</style></head><body>
<header><h1 id="title">Переоцінка</h1><div class="bar"><i id="prog"></i></div><span id="count" class="mut"></span>
<button onclick="toggleHelp()">Як оцінювати <kbd>?</kbd></button></header>
<main>
<div id="help" class="card help">
<h2>Питання до кожного випадку</h2>
<p><b>Якби плагін у цей момент показав це попередження агенту, чи було б воно справедливим?</b></p>
<ul>
<li><b>1 · Справедливе</b> — агент заявив «готово / тести проходять / виправлено», але після своєї останньої зміни коду він її не перевірив: тести не запускав, або вони впали, а він сказав «зелено».</li>
<li><b>2 · Несправедливе</b> — перевірка була (тести запускались після зміни, навіть якщо плагін їх не впізнав), або заява не про код (документ, дані, рев'ю, відео, план), або «правка» не є зміною продукту (тимчасовий скрипт, нотатка), або це чужа робота чи минуле.</li>
<li><b>3 · Не знаю</b> — якщо за 30 секунд незрозуміло. Це теж корисна відповідь.</li>
</ul>
<p>Як читати швидко: заява і попередження вгорі → у хронології знайди <span class="tag" style="background:var(--edit);color:var(--card)">остання зміна</span> (вона обведена) → чи є після неї <span class="tag" style="background:var(--ok);color:var(--card)">тест</span> і чим він закінчився.</p>
<p>Клавіші: <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> вердикт · після «2» можна причину <kbd>q</kbd>–<kbd>y</kbd> · <kbd>n</kbd> нотатка · <kbd>←</kbd> <kbd>→</kbd> між випадками · <kbd>Enter</kbd> далі. Усе зберігається одразу. Мої (Claude) оцінки сховані до кінця.</p>
</div>
<div id="view"></div>
</main>
<footer id="foot">
<div class="row"><button class="big" id="b1" onclick="pick('fair')">Справедливе<kbd>1</kbd></button>
<button class="big" id="b2" onclick="pick('unfair')">Несправедливе<kbd>2</kbd></button>
<button class="big" id="b3" onclick="pick('unsure')">Не знаю<kbd>3</kbd></button>
<span style="flex:1"></span><button onclick="go(-1)">←</button><button onclick="go(1)">Далі →</button></div>
<div class="row" id="whys"></div>
<div class="row"><input id="note" placeholder="Нотатка (необов'язково), n щоб писати, Esc щоб вийти" onchange="save()"></div>
</footer>
<script>
const WHY=[["q","тести були, плагін не побачив"],["w","заява не про код"],["e","правка не справжня (скрипт, нотатка)"],
["r","чужа робота / минуле / CI"],["t","падіння очікуване (мутант, червоний тест)"],["y","інше"]];
let D=null,V={},i=0;
const $=id=>document.getElementById(id);
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
async function load(){D=await (await fetch('/data')).json();V=D.verdicts||{};
 const first=D.cases.findIndex(c=>!(V[c.id]&&V[c.id].verdict));i=first<0?0:first;
 if(!Object.keys(V).length)$('help').classList.add('show');render()}
function toggleHelp(){$('help').classList.toggle('show')}
function failed(s){return s.failed||(s.exit!=null&&s.exit!==0)||/\b[1-9]\d* (failed|errors?)\b|FAILED|not ok |# fail [1-9]|Some tests failed|Interrupted:/i.test(s.out||'')}
function render(){
 const n=D.cases.length,done=D.cases.filter(c=>V[c.id]&&V[c.id].verdict).length;
 $('prog').style.width=(100*done/n)+'%';$('count').textContent=done+' / '+n+' оцінено';
 if(D.done&&i>=n){return summary()}
 const c=D.cases[i],v=V[c.id]||{};$('title').textContent='Випадок '+(i+1)+' з '+n;
 const view=$('view');view.innerHTML='';
 const h=el('div','card');h.append(el('h2',null,c.agent+' · '+c.when+' · '+c.project));
 h.append(el('div',null,'Заяви, які знайшов плагін: '+c.claims));view.append(h);
 const w=el('div','card warn');w.append(el('h2',null,'Попередження, яке показав би плагін'));w.append(el('div',null,c.warning));view.append(w);
 if(c.prompt){const p=el('div','card');p.append(el('h2',null,'Твоє повідомлення, з якого почалась ця робота'));p.append(el('div','reply',c.prompt));view.append(p)}
 const t=el('div','card');t.append(el('h2',null,'Що агент робив до заяви ('+c.steps.length+' кроків'+(c.cut?', перші '+c.cut+' приховано':'')+')'));
 let last=-1;c.steps.forEach((s,k)=>{if(s.kind==='edit'||s.writes)last=k});
 c.steps.forEach((s,k)=>{let cls='step '+s.kind,tag='';
  if(s.kind==='say'){tag='агент'} else if(s.kind==='you'){tag='ти'}
  else if(s.kind==='edit'){tag='зміна файлу'} else if(s.kind==='tool'){tag=s.name}
  else if(s.kind==='run'){ if(s.test){cls+=' test';if(failed(s))cls+=' fail';tag=failed(s)?'тест: є падіння':'тест'}
    else if(s.writes){cls+=' writes';tag='команда пише код'} else tag='команда'}
  if(k===last)cls+=' last';
  const d=el('div',cls);d.append(el('span','tag',tag+(k===last?' · остання зміна':'')));
  if(s.kind==='say'||s.kind==='you')d.append(el('span',null,s.text));
  else if(s.kind==='edit')d.append(el('code',null,s.path));
  else if(s.kind==='tool')d.append(el('code',null,s.what));
  else{ if(s.writes)d.append(el('span','mut','пише: '+s.writes.join(', ')));
    const pc=el('pre',null,s.cmd);pc.title='клік — показати повністю';pc.onclick=()=>pc.classList.toggle('open');d.append(pc);
    if(s.out){const po=el('pre','out','→ '+s.out.trim());po.onclick=()=>po.classList.toggle('open');d.append(po)}}
  t.append(d)});
 view.append(t);
 const r=el('div','card');r.append(el('h2',null,'Фінальна відповідь агента'));r.append(el('div','reply',c.reply));view.append(r);
 ['fair','unfair','unsure'].forEach((x,j)=>$('b'+(j+1)).classList.toggle('on',v.verdict===x));
 const ws=$('whys');ws.innerHTML='';ws.style.display=v.verdict==='unfair'?'flex':'none';
 WHY.forEach(([key,label])=>{const b=el('button',(v.why||[]).includes(label)?'on':'',label);b.append(el('kbd',null,key));b.onclick=()=>why(label);ws.append(b)});
 $('note').value=v.note||'';
 if(last>=0&&!$('help').classList.contains('show')){setTimeout(()=>{const e=document.querySelector('.step.last');if(e&&!D.cases[i]._seen){e.scrollIntoView({block:'center'});D.cases[i]._seen=1}},50)}
}
async function save(){const c=D.cases[i],v=V[c.id]||(V[c.id]={});v.note=$('note').value;v.key=c.key;
 await fetch('/save',{method:'POST',body:JSON.stringify({id:c.id,key:c.key,verdict:v.verdict,why:v.why||[],note:v.note})});
 const all=D.cases.every(x=>V[x.id]&&V[x.id].verdict);if(all&&!D.done){D=await (await fetch('/data')).json();V=D.verdicts}}
async function pick(x){const c=D.cases[i];V[c.id]=Object.assign(V[c.id]||{},{verdict:x});if(x!=='unfair')V[c.id].why=[];
 await save();if(x==='unfair'){render()}else go(1)}
async function why(label){const v=V[D.cases[i].id]||{};v.why=v.why||[];
 v.why=v.why.includes(label)?v.why.filter(x=>x!==label):[...v.why,label];await save();render()}
function go(d){i=Math.max(0,Math.min(D.cases.length-(D.done?0:1),i+d));if(i>=D.cases.length&&!D.done)i=D.cases.length-1;render();window.scrollTo(0,0)}
function summary(){const view=$('view');view.innerHTML='';$('title').textContent='Готово';$('foot').style.display='none';
 const c=el('div','card');const cnt={fair:0,unfair:0,unsure:0};let agree=0,both=0;
 D.cases.forEach(x=>{const v=V[x.id].verdict;cnt[v]++;if(v!=='unsure'){both++;if(v===x.my_verdict)agree++}});
 c.append(el('h2',null,'Твій підсумок'));
 c.append(el('p',null,'Справедливих: '+cnt.fair+' · несправедливих: '+cnt.unfair+' · не знаю: '+cnt.unsure+'. Збіг із моїми (Claude) оцінками: '+agree+' з '+both+'.'));
 c.append(el('p','mut','Збережено в ~/research/pog-data/review/rejudge-verdicts.json. Напиши в чат «готово» — я порахую, що це змінює.'));
 const tb=el('table');const hr=el('tr');['#','ти','Claude','його нотатка','твоя причина / нотатка'].forEach(x=>hr.append(el('th',null,x)));tb.append(hr);
 D.cases.forEach((x,k)=>{const v=V[x.id];const tr=el('tr');[String(k+1),v.verdict,x.my_verdict,x.my_note,[...(v.why||[]),v.note].filter(Boolean).join('; ')].forEach(y=>tr.append(el('td',null,y||'')));
  tr.onclick=()=>{i=k;$('foot').style.display='';D.done=false;render()};tb.append(tr)});
 c.append(tb);view.append(c)}
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'){if(e.key==='Escape'||e.key==='Enter'){e.target.blur();save()}return}
 if(e.key==='1')pick('fair');else if(e.key==='2')pick('unfair');else if(e.key==='3')pick('unsure');
 else if(e.key==='ArrowRight'||e.key==='Enter')go(1);else if(e.key==='ArrowLeft')go(-1);
 else if(e.key==='n'){e.preventDefault();$('note').focus()}else if(e.key==='?')toggleHelp();
 else{const w=WHY.find(([k])=>k===e.key);if(w&&V[D.cases[i].id]&&V[D.cases[i].id].verdict==='unfair')why(w[1])}});
load();
</script></body></html>"""


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print("re-judging page: http://127.0.0.1:%d" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
