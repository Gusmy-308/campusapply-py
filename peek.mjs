#!/usr/bin/env node
// 附着模式下查看「真实 Chrome」当前页面 —— 给 Claude 当眼睛用
// 用法: node peek.mjs [--text | --html | --forms | --click "选择器或文本"] [--url <子串>]
const CDP = 'http://localhost:9222';

async function wsUrlFor(match) {
  const list = await (await fetch(`${CDP}/json/list`)).json();
  const pages = list.filter(t => t.type === 'page' && !t.url.startsWith('chrome://'));
  if (!pages.length) throw new Error('没有可用标签页');
  const t = match ? (pages.find(p => p.url.includes(match)) || pages[0]) : pages[0];
  return { ws: t.webSocketDebuggerUrl, info: t };
}

function connect(url) {
  return new Promise((res, rej) => {
    const s = new WebSocket(url);
    const timer = setTimeout(() => rej(new Error('WS 连接超时 10s')), 10000);
    s.onopen = () => { clearTimeout(timer); res(s); };
    s.onerror = e => { clearTimeout(timer); rej(new Error('WS 连接失败')); };
  });
}

let _id = 0;
const pending = new Map();
function send(s, method, params = {}, timeout = 15000) {
  const id = ++_id;
  return new Promise((res, rej) => {
    const timer = setTimeout(() => { pending.delete(id); rej(new Error(`${method} 超时`)); }, timeout);
    pending.set(id, { res, timer });
    s.send(JSON.stringify({ id, method, params }));
  });
}

const args = process.argv.slice(2);
const mode = args.find(a => a.startsWith('--')) || '--text';
const urlMatch = args.includes('--url') ? args[args.indexOf('--url') + 1] : 'jsbchina';
const clickTarget = args.includes('--click') ? args[args.indexOf('--click') + 1] : null;

const { ws, info } = await wsUrlFor(urlMatch);
const s = await connect(ws);

s.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) {
    const { res, timer } = pending.get(m.id);
    pending.delete(m.id); clearTimeout(timer);
    m.error ? res({ __error: m.error.message }) : res(m.result);
  }
};

await send(s, 'Runtime.enable');

const evalJs = async (expr) => {
  const r = await send(s, 'Runtime.evaluate', {
    expression: expr, returnByValue: true, awaitPromise: true,
  });
  if (r.__error) throw new Error(r.__error);
  return r.result?.value;
};

const out = { url: info.url, title: info.title };

if (clickTarget) {
  out.clickResult = await evalJs(`(() => {
    const sel = ${JSON.stringify(clickTarget)};
    let el = null;
    try { el = document.querySelector(sel); } catch (e) {}
    if (!el) {
      const all = [...document.querySelectorAll('a,button,li,div[role=button],span')];
      el = all.find(e => (e.innerText || '').trim().includes(sel) && (e.innerText || '').trim().length < 80);
    }
    if (!el) return '未找到: ' + sel;
    el.scrollIntoView({block:'center'});
    el.click();
    return '已点击: ' + (el.innerText || el.tagName).trim().slice(0, 60);
  })()`);
  await new Promise(r => setTimeout(r, 3000));
  out.urlAfter = await evalJs('location.href');
}

if (mode === '--text') {
  out.text = await evalJs(`document.body ? document.body.innerText.slice(0, 4000) : '(空)'`);
} else if (mode === '--forms') {
  out.fields = await evalJs(`(() => {
    const out = [];
    document.querySelectorAll('input,textarea,select').forEach((el, i) => {
      const lab = el.closest('div,td,li')?.innerText?.trim().slice(0,40) || '';
      out.push({ i, tag: el.tagName, type: el.type||'', name: el.name||'', ph: el.placeholder||'', readonly: el.readOnly||false, label: lab.replace(/\\n/g,' / ') });
    });
    return out;
  })()`);
  out.buttons = await evalJs(`[...document.querySelectorAll('button,a[role=button]')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,25)`);
} else if (mode === '--html') {
  out.html = await evalJs(`document.body ? document.body.innerHTML.slice(0, 6000) : '(空)'`);
}

console.log(JSON.stringify(out, null, 2));
s.close();
process.exit(0);
