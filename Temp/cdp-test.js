const fs = require('node:fs');

const wsUrl = process.argv[2];
const shotPath = process.argv[3];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ws = new WebSocket(wsUrl);
let seq = 0;
const pending = new Map();

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
  }
};

const open = new Promise((resolve, reject) => {
  ws.onopen = resolve;
  ws.onerror = reject;
});

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const res = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (res.exceptionDetails) throw new Error(res.exceptionDetails.text || 'evaluate failed');
  return res.result.value;
}

(async () => {
  await open;
  await send('Runtime.enable');
  await send('Page.enable');
  await sleep(1800);

  const initial = await evaluate(`({
    subtitle: document.getElementById('subtitle').textContent,
    nodes: window.__GALAXY_DEBUG__.nodes.length,
    edges: window.__GALAXY_DEBUG__.edges.length,
    loaderHidden: document.getElementById('loader').classList.contains('hide')
  })`);
  console.log('INITIAL', JSON.stringify(initial));

  const selected = await evaluate(`(() => {
    const d = window.__GALAXY_DEBUG__;
    const m = d.nodes.find(n => n.type === 'memory' && n.importance >= 5);
    d.selectNode(m);
    return { id: m.id, label: m.label };
  })()`);
  await sleep(900);
  const detail = await evaluate(`({
    open: document.getElementById('panel').classList.contains('open'),
    heading: (document.querySelector('#panel-body h2') || {}).textContent,
    body: (document.querySelector('#panel-body .body') || {}).textContent.slice(0, 80),
    links: document.querySelectorAll('#panel-body [data-node]').length,
    selected: window.__GALAXY_DEBUG__.state.selected && window.__GALAXY_DEBUG__.state.selected.type,
    target: !!window.__GALAXY_DEBUG__.state.target
  })`);
  console.log('DETAIL', JSON.stringify({ selected, detail }));

  const tagResult = await evaluate(`(() => {
    const d = window.__GALAXY_DEBUG__;
    const t = d.nodes.find(n => n.type === 'tag');
    d.selectNode(t);
    return { label: t.label };
  })()`);
  await sleep(600);
  const tagPanel = await evaluate(`({
    heading: (document.querySelector('#panel-body h2') || {}).textContent,
    links: document.querySelectorAll('#panel-body [data-node]').length,
    body: (document.querySelector('#panel-body .body') || {}).textContent
  })`);
  console.log('TAG', JSON.stringify({ tagResult, tagPanel }));

  const linkClick = await evaluate(`(() => {
    const a = document.querySelector('#panel-body [data-node]');
    if (!a) return { clicked: false };
    const id = a.getAttribute('data-node');
    a.click();
    return { clicked: true, id };
  })()`);
  await sleep(500);
  const afterLink = await evaluate(`({
    heading: (document.querySelector('#panel-body h2') || {}).textContent,
    selected: window.__GALAXY_DEBUG__.state.selected && window.__GALAXY_DEBUG__.state.selected.id
  })`);
  console.log('LINK', JSON.stringify({ linkClick, afterLink }));

  const filter = await evaluate(`(() => {
    const d = window.__GALAXY_DEBUG__;
    const s = document.getElementById('search');
    s.value = '声音';
    s.dispatchEvent(new Event('input', { bubbles: true }));
    return {
      query: d.state.query,
      visible: d.nodes.filter(n => d.visible(n)).length,
      total: d.nodes.length
    };
  })()`);
  console.log('FILTER', JSON.stringify(filter));

  await evaluate(`(() => {
    const s = document.getElementById('search');
    s.value = '';
    s.dispatchEvent(new Event('input', { bubbles: true }));
    const d = window.__GALAXY_DEBUG__;
    d.selectNode(d.nodes.find(n => n.type === 'memory' && n.importance >= 5));
  })()`);
  await sleep(700);
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(shotPath, Buffer.from(shot.data, 'base64'));
  console.log('SHOT', shotPath, fs.statSync(shotPath).size);

  ws.close();
})().catch((err) => {
  console.error('FAIL', err.stack || err);
  process.exitCode = 1;
  try { ws.close(); } catch { /* ignore */ }
});
