/* 大肥鱼 · 记忆星河 — 零依赖 Canvas 伪 3D 星图 */
(() => {
  'use strict';

  const canvas = document.getElementById('sky');
  const ctx = canvas.getContext('2d');
  const loader = document.getElementById('loader');
  const subtitle = document.getElementById('subtitle');
  const search = document.getElementById('search');
  const chips = document.getElementById('chips');
  const panel = document.getElementById('panel');
  const panelBody = document.getElementById('panel-body');
  const closeBtn = document.getElementById('close');
  const resetBtn = document.getElementById('reset');
  const tooltip = document.getElementById('tooltip');

  const FOCAL = 1100;
  const KIND_COLORS = {
    capability: '#7cd8ff',
    user_preference: '#ffb3d1',
    user_fact: '#ffd28a',
    experience: '#b9a7ff',
    interest: '#7ef0c8',
    relationship: '#ff9f8a',
    boundary: '#c7d2e8',
    preference: '#ffc4a3',
    technical: '#8fb7ff',
    core: '#ffd28a',
    event: '#8aa0c6',
    tag: '#e8c58d',
    digest: '#b9a7ff',
  };
  const KIND_NAMES = {
    capability: '能力',
    user_preference: '偏好',
    user_fact: '关于主人',
    experience: '经历',
    interest: '兴趣',
    relationship: '关系',
    boundary: '边界',
    preference: '偏好',
    technical: '技术',
  };

  const state = {
    yaw: 0.42,
    pitch: -0.16,
    dist: 19,
    auto: true,
    dragging: false,
    moved: 0,
    lastX: 0,
    lastY: 0,
    hover: null,
    selected: null,
    kind: null,
    query: '',
    idleTimer: null,
  };

  let data = null;
  let nodes = [];
  let edges = [];
  let byId = new Map();
  let W = 0;
  let H = 0;
  let DPR = 1;
  let screenNodes = [];
  let dust = [];
  let lastTime = 0;

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const hash = (s) => {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  };
  const rand = (seed, salt = 0) => {
    const x = Math.sin(seed * 12.9898 + salt * 78.233) * 43758.5453;
    return x - Math.floor(x);
  };
  const colorOf = (n) => n.type === 'memory'
    ? (KIND_COLORS[n.kind] || '#7cd8ff')
    : (KIND_COLORS[n.type] || '#9fb3d6');

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.floor(W * DPR);
    canvas.height = Math.floor(H * DPR);
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  function makeDust() {
    dust = [];
    for (let i = 0; i < 280; i++) {
      dust.push({
        x: rand(i, 1),
        y: rand(i, 2),
        r: 0.4 + rand(i, 3) * 1.2,
        a: 0.12 + rand(i, 4) * 0.45,
        p: rand(i, 5) * Math.PI * 2,
      });
    }
  }

  function layout() {
    const mems = nodes.filter((n) => n.type === 'memory');
    const kinds = [...new Set(mems.map((n) => n.kind))];
    const centers = new Map();
    kinds.forEach((kind, i) => {
      const angle = (i / Math.max(1, kinds.length)) * Math.PI * 2 + 0.25;
      centers.set(kind, {
        x: Math.cos(angle) * 6.2,
        y: (rand(hash(kind), 8) - 0.5) * 2.6,
        z: Math.sin(angle) * 6.2,
      });
    });

    for (const n of mems) {
      const c = centers.get(n.kind) || { x: 0, y: 0, z: 0 };
      const s = hash(n.id);
      const r = 1.15 + rand(s, 1) * 1.5;
      const theta = rand(s, 2) * Math.PI * 2;
      const phi = Math.acos(2 * rand(s, 3) - 1);
      n.pos = {
        x: c.x + Math.sin(phi) * Math.cos(theta) * r,
        y: c.y + Math.cos(phi) * r * 0.8,
        z: c.z + Math.sin(phi) * Math.sin(theta) * r,
      };
    }

    const core = nodes.find((n) => n.type === 'core');
    if (core) core.pos = { x: 0, y: 0, z: 0 };

    // 标签星云：取相关记忆的平均位置，再稍微向外推
    const tags = nodes.filter((n) => n.type === 'tag');
    for (const t of tags) {
      const linked = mems.filter((m) => (m.tags || []).includes(t.label));
      if (!linked.length) { t.pos = { x: 0, y: 0, z: 0 }; continue; }
      let x = 0, y = 0, z = 0;
      for (const m of linked) { x += m.pos.x; y += m.pos.y; z += m.pos.z; }
      x /= linked.length; y /= linked.length; z /= linked.length;
      const len = Math.max(0.001, Math.hypot(x, y, z));
      t.pos = { x: x + (x / len) * 1.1, y: y + 0.5, z: z + (z / len) * 1.1 };
    }

    // 事件尘：挂在第一条来源记忆旁边
    const events = nodes.filter((n) => n.type === 'event');
    for (const e of events) {
      const incoming = edges.find((ed) => ed.type === 'source' && ed.target === e.id);
      const parent = incoming ? byId.get(incoming.source) : null;
      const base = parent && parent.pos ? parent.pos : { x: 0, y: 0, z: 0 };
      const s = hash(e.id);
      const a = rand(s, 1) * Math.PI * 2;
      const r = 0.4 + rand(s, 2) * 0.8;
      e.pos = {
        x: base.x + Math.cos(a) * r,
        y: base.y + (rand(s, 3) - 0.5) * 0.9,
        z: base.z + Math.sin(a) * r,
      };
    }

    // 日摘要：外圈时间带
    const digests = nodes.filter((n) => n.type === 'digest');
    digests.forEach((d, i) => {
      const a = (i / Math.max(1, digests.length)) * Math.PI * 2 - Math.PI / 2;
      d.pos = { x: Math.cos(a) * 9.2, y: 2.4, z: Math.sin(a) * 9.2 };
    });
  }

  function project(p) {
    const cy = Math.cos(state.yaw);
    const sy = Math.sin(state.yaw);
    let x = p.x * cy - p.z * sy;
    let z = p.x * sy + p.z * cy;
    const cp = Math.cos(state.pitch);
    const sp = Math.sin(state.pitch);
    const y = p.y * cp - z * sp;
    z = p.y * sp + z * cp;
    const zc = z + state.dist;
    const f = FOCAL / Math.max(2, zc);
    return { x: W / 2 + x * f, y: H / 2 - y * f, z: zc, s: f / 58 };
  }

  function visible(n) {
    if (n.type === 'core') return true;
    if (n.type === 'digest') return !state.kind && !state.query;
    if (n.type === 'tag') {
      if (state.query && !n.label.toLowerCase().includes(state.query)) return false;
      return !state.kind;
    }
    if (n.type === 'event') {
      if (state.kind || state.query) {
        const incoming = edges.filter((ed) => ed.type === 'source' && ed.target === n.id);
        return incoming.some((ed) => {
          const m = byId.get(ed.source);
          return m && visible(m);
        });
      }
      return true;
    }
    if (n.type === 'memory') {
      if (state.kind && n.kind !== state.kind) return false;
      if (state.query) {
        const hay = (n.body + ' ' + (n.tags || []).join(' ') + ' ' + n.kind).toLowerCase();
        if (!hay.includes(state.query)) return false;
      }
      return true;
    }
    return true;
  }

  function drawBackground(t) {
    const g = ctx.createRadialGradient(W * 0.5, H * 0.5, 40, W * 0.5, H * 0.5, Math.max(W, H) * 0.78);
    g.addColorStop(0, '#081126');
    g.addColorStop(0.45, '#050a16');
    g.addColorStop(1, '#02040a');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    const neb1 = ctx.createRadialGradient(W * 0.28, H * 0.38, 0, W * 0.28, H * 0.38, W * 0.42);
    neb1.addColorStop(0, 'rgba(38, 92, 160, .18)');
    neb1.addColorStop(1, 'rgba(38, 92, 160, 0)');
    ctx.fillStyle = neb1;
    ctx.fillRect(0, 0, W, H);

    const neb2 = ctx.createRadialGradient(W * 0.74, H * 0.62, 0, W * 0.74, H * 0.62, W * 0.38);
    neb2.addColorStop(0, 'rgba(105, 62, 160, .14)');
    neb2.addColorStop(1, 'rgba(105, 62, 160, 0)');
    ctx.fillStyle = neb2;
    ctx.fillRect(0, 0, W, H);

    for (const d of dust) {
      const tw = 0.75 + 0.25 * Math.sin(t * 0.0011 + d.p);
      ctx.globalAlpha = d.a * tw;
      ctx.fillStyle = '#d9e8ff';
      ctx.beginPath();
      ctx.arc(d.x * W, d.y * H, d.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function drawEdges() {
    const focus = state.hover || state.selected;
    for (const e of edges) {
      const a = byId.get(e.source);
      const b = byId.get(e.target);
      if (!a || !b || !a.pos || !b.pos || !visible(a) || !visible(b)) continue;
      const pa = project(a.pos);
      const pb = project(b.pos);
      const touched = focus && (e.source === focus.id || e.target === focus.id);
      let color = 'rgba(140, 165, 205, .12)';
      let width = 0.6;
      if (e.type === 'semantic') { color = 'rgba(92, 202, 255, .15)'; width = 0.7; }
      if (e.type === 'tag') { color = 'rgba(232, 197, 141, .10)'; width = 0.5; }
      if (touched) { color = 'rgba(124, 216, 255, .55)'; width = 1.4; }
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
    }
  }

  function drawNode(n, p, t) {
    const base = n.type === 'core' ? 10
      : n.type === 'memory' ? 2.6 + (n.importance || 3) * 0.9
        : n.type === 'tag' ? 4.2
          : n.type === 'digest' ? 3.2 : 1.15;
    const size = Math.max(0.6, base * clamp(p.s, 0.55, 1.7));
    const color = colorOf(n);
    const focus = state.hover === n || state.selected === n;
    const alpha = n.type === 'event' ? 0.58 : 0.95;
    const r = focus ? size * 1.5 : size;

    const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 4.2);
    glow.addColorStop(0, color + 'cc');
    glow.addColorStop(0.35, color + '44');
    glow.addColorStop(1, color + '00');
    ctx.globalAlpha = alpha * (n.type === 'event' ? 0.55 : 1);
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(p.x, p.y, r * 4.2, 0, Math.PI * 2);
    ctx.fill();

    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
    ctx.fill();

    if (n.type === 'core') {
      ctx.strokeStyle = 'rgba(255, 226, 170, .8)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r + 5 + Math.sin(t * 0.0018) * 1.2, 0, Math.PI * 2);
      ctx.stroke();
    }

    const showLabel = n.type === 'core' || n.type === 'digest'
      || (n.type === 'memory' && (n.importance >= 5 || focus))
      || (n.type === 'tag' && focus);
    if (showLabel) {
      ctx.globalAlpha = focus ? 1 : 0.72;
      ctx.fillStyle = n.type === 'core' ? '#ffe2aa' : '#c9d9f2';
      ctx.font = n.type === 'core' ? '600 12px "Microsoft YaHei", sans-serif' : '11px "Microsoft YaHei", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const text = n.type === 'core' ? '核心记忆' : n.label;
      ctx.fillText(text, p.x, p.y + r * 3.1 + 4);
    }
    ctx.globalAlpha = 1;
  }

  function draw(t) {
    drawBackground(t);
    drawEdges();

    screenNodes = [];
    const visibleNodes = nodes.filter(visible);
    for (const n of visibleNodes) {
      if (!n.pos) continue;
      const p = project(n.pos);
      screenNodes.push({ n, p });
    }
    screenNodes.sort((a, b) => b.p.z - a.p.z);
    for (const { n, p } of screenNodes) drawNode(n, p, t);

    if (state.auto && !state.dragging) state.yaw += 0.00045;
    requestAnimationFrame(draw);
  }

  function hitTest(x, y) {
    let best = null;
    let bestD = Infinity;
    for (const { n, p } of screenNodes) {
      if (n.type === 'event' && best) continue;
      const d = Math.hypot(p.x - x, p.y - y);
      const limit = n.type === 'core' ? 26 : n.type === 'memory' ? 15 : 12;
      if (d < limit && p.z < bestD) {
        best = n;
        bestD = p.z;
      }
    }
    return best;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function sourceEvents(n) {
    if (n.type !== 'memory') return [];
    return edges
      .filter((e) => e.type === 'source' && e.source === n.id)
      .map((e) => byId.get(e.target))
      .filter(Boolean);
  }

  function openPanel(n) {
    state.selected = n;
    panel.classList.add('open');
    const kindName = n.type === 'memory' ? (KIND_NAMES[n.kind] || n.kind) : n.type;
    const tags = (n.tags || []).map((x) => `<span class="tag">${escapeHtml(x)}</span>`).join('');
    const src = sourceEvents(n);
    const sources = src.length
      ? `<div class="sources"><b>来源事件</b><br>${src.slice(0, 3).map((e) => '· ' + escapeHtml(e.label)).join('<br>')}</div>`
      : '';
    const meta = n.type === 'memory'
      ? `<div class="meta">
          <span>重要度</span><b>${n.importance} / 5</b>
          <span>置信度</span><b>${Math.round((n.confidence || 0) * 100)}%</b>
          <span>时间</span><b>${escapeHtml((n.created_at || '').slice(0, 10))}</b>
        </div>`
      : n.type === 'event'
        ? `<div class="meta"><span>时间</span><b>${escapeHtml((n.occurred_at || '').slice(0, 16).replace('T', ' '))}</b></div>`
        : '';
    const canSpeak = (n.type === 'memory' || n.type === 'core' || n.type === 'digest') && n.body;
    panelBody.innerHTML = `
      <span class="kind">${escapeHtml(kindName)}</span>
      <h2>${escapeHtml(n.label)}</h2>
      <p class="body">${escapeHtml(n.body || n.label)}</p>
      ${tags ? `<div class="tags">${tags}</div>` : ''}
      ${meta}
      ${sources}
      ${canSpeak ? `<button class="speak" id="speak-btn" type="button">让大肥鱼读给我听</button>` : ''}
    `;
    const speakBtn = document.getElementById('speak-btn');
    if (speakBtn) {
      speakBtn.addEventListener('click', () => speak(n, speakBtn));
    }
  }

  async function speak(n, btn) {
    const text = (n.body || n.label || '').slice(0, 1200);
    if (!text) return;
    btn.disabled = true;
    btn.textContent = '正在生成…';
    try {
      const res = await fetch('http://127.0.0.1:9881/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, emotion: 'neutral' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'TTS failed');
      const audio = new Audio(data.url + '?t=' + Date.now());
      audio.onended = () => { btn.disabled = false; btn.textContent = '让大肥鱼读给我听'; };
      await audio.play();
      btn.textContent = '正在读…';
    } catch (err) {
      btn.disabled = false;
      btn.textContent = '朗读失败：' + String(err.message || err).slice(0, 40);
    }
  }

  function updateTooltip(n, x, y) {
    if (!n) {
      tooltip.classList.remove('on');
      return;
    }
    tooltip.textContent = n.type === 'memory'
      ? `${KIND_NAMES[n.kind] || n.kind} · ${n.label}`
      : n.label;
    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
    tooltip.classList.add('on');
  }

  function selectNode(n) {
    if (!n) return;
    openPanel(n);
  }

  function buildChips() {
    const kinds = [...new Set(nodes.filter((n) => n.type === 'memory').map((n) => n.kind))];
    chips.innerHTML = '<button class="chip on" data-kind="">全部</button>'
      + kinds.map((k) => `<button class="chip" data-kind="${escapeHtml(k)}">${escapeHtml(KIND_NAMES[k] || k)}</button>`).join('');
    chips.addEventListener('click', (ev) => {
      const btn = ev.target.closest('.chip');
      if (!btn) return;
      state.kind = btn.dataset.kind || null;
      [...chips.querySelectorAll('.chip')].forEach((c) => c.classList.toggle('on', c === btn));
    });
  }

  function bind() {
    canvas.addEventListener('pointerdown', (ev) => {
      state.dragging = true;
      state.moved = 0;
      state.lastX = ev.clientX;
      state.lastY = ev.clientY;
      state.auto = false;
      canvas.classList.add('dragging');
      canvas.setPointerCapture(ev.pointerId);
    });
    canvas.addEventListener('pointermove', (ev) => {
      if (state.dragging) {
        const dx = ev.clientX - state.lastX;
        const dy = ev.clientY - state.lastY;
        state.moved += Math.abs(dx) + Math.abs(dy);
        state.lastX = ev.clientX;
        state.lastY = ev.clientY;
        state.yaw += dx * 0.005;
        state.pitch = clamp(state.pitch + dy * 0.003, -1.2, 1.2);
        tooltip.classList.remove('on');
        return;
      }
      const n = hitTest(ev.clientX, ev.clientY);
      state.hover = n;
      updateTooltip(n, ev.clientX, ev.clientY);
    });
    canvas.addEventListener('pointerup', (ev) => {
      if (state.dragging && state.moved < 6) {
        selectNode(hitTest(ev.clientX, ev.clientY));
      }
      state.dragging = false;
      canvas.classList.remove('dragging');
      try { canvas.releasePointerCapture(ev.pointerId); } catch { /* ignore */ }
      clearTimeout(state.idleTimer);
      state.idleTimer = setTimeout(() => { state.auto = true; }, 6000);
    });
    canvas.addEventListener('pointerleave', () => {
      state.hover = null;
      tooltip.classList.remove('on');
    });
    canvas.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      state.dist = clamp(state.dist + ev.deltaY * 0.012, 8, 34);
    }, { passive: false });
    canvas.addEventListener('dblclick', () => reset());
    closeBtn.addEventListener('click', () => {
      panel.classList.remove('open');
      state.selected = null;
    });
    search.addEventListener('input', () => { state.query = search.value.trim().toLowerCase(); });
    resetBtn.addEventListener('click', reset);
    window.addEventListener('resize', resize);
  }

  function reset() {
    state.yaw = 0.42;
    state.pitch = -0.16;
    state.dist = 19;
    state.kind = null;
    state.query = '';
    state.auto = true;
    search.value = '';
    [...chips.querySelectorAll('.chip')].forEach((c, i) => c.classList.toggle('on', i === 0));
    panel.classList.remove('open');
    state.selected = null;
  }

  async function boot() {
    resize();
    makeDust();
    bind();
    try {
      if (window.__GALAXY__) {
        data = window.__GALAXY__;
      } else {
        const res = await fetch('galaxy.json', { cache: 'no-store' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        data = await res.json();
      }
      nodes = data.nodes || [];
      edges = data.edges || [];
      byId = new Map(nodes.map((n) => [n.id, n]));
      layout();
      buildChips();
      const m = data.meta || {};
      subtitle.textContent = `${m.memory_count || 0} 颗记忆星 · ${m.event_count || 0} 粒事件尘 · ${m.tag_count || 0} 个标签 · ${m.digest_count || 0} 份日摘要`;
      loader.classList.add('hide');
      requestAnimationFrame(draw);
    } catch (err) {
      loader.innerHTML = '读不到 galaxy.json<br><small style="opacity:.7">先在 D:\\大肥鱼 运行：python MemoryService/export_galaxy.py<br>然后用本地 HTTP 打开本页</small>';
      console.error(err);
    }
  }

  boot();
})();
