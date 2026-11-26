/* 大肥鱼 · 记忆星河 — 3d-force-graph / ThreeJS 版 */
(() => {
  'use strict';

  const graphEl = document.getElementById('graph');
  const loader = document.getElementById('loader');
  const subtitle = document.getElementById('subtitle');
  const search = document.getElementById('search');
  const chips = document.getElementById('chips');
  const panel = document.getElementById('panel');
  const panelBody = document.getElementById('panel-body');
  const closeBtn = document.getElementById('close');
  const resetBtn = document.getElementById('reset');

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
    selected: null,
    neighbors: new Set(),
    hover: null,
    kind: null,
    query: '',
  };

  let Graph = null;
  let data = null;
  let nodes = [];
  let edges = [];
  let byId = new Map();
  let labelEntries = [];
  const labelLayer = document.getElementById('labels');
  const seeded = (id, salt = 0) => {
    let h = 2166136261;
    for (let i = 0; i < id.length; i++) {
      h ^= id.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    const x = Math.sin((h >>> 0) * 12.9898 + salt * 78.233) * 43758.5453;
    return x - Math.floor(x);
  };

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const escapeHtml = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const colorOf = (n) => n.type === 'memory'
    ? (KIND_COLORS[n.kind] || '#7cd8ff')
    : (KIND_COLORS[n.type] || '#9fb3d6');
  const idOf = (x) => (x && typeof x === 'object') ? x.id : x;

  function visible(n) {
    if (n.type === 'core') return true;
    if (n.type === 'digest') return !state.kind && !state.query;
    if (n.type === 'tag') {
      if (state.query && !n.label.toLowerCase().includes(state.query)) return false;
      if (state.kind) return false;
      return edges.some((e) => e.type === 'tag' && idOf(e.target) === n.id
        && visible(byId.get(idOf(e.source))));
    }
    if (n.type === 'event') {
      if (!state.kind && !state.query) return true;
      return edges.some((e) => e.type === 'source' && idOf(e.target) === n.id
        && visible(byId.get(idOf(e.source))));
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

  function nodeVal(n) {
    if (n.type === 'core') return 32;
    if (n.type === 'memory') return 2 + (n.importance || 3) * 1.25;
    if (n.type === 'tag') return 5.5;
    if (n.type === 'digest') return 5;
    return 0.8;
  }

  function nodeColor(n) {
    if (state.selected && n.id !== state.selected.id && n.type !== 'core'
      && !state.neighbors.has(n.id)) return '#26344d';
    return colorOf(n);
  }

  function nodeLabel(n) {
    const kind = n.type === 'memory' ? (KIND_NAMES[n.kind] || n.kind) : n.type;
    return `<div style="max-width:260px;white-space:normal;line-height:1.5">
      <div style="color:${colorOf(n)};font-size:10px;letter-spacing:.04em">${escapeHtml(kind)}</div>
      <div>${escapeHtml(n.label || n.id)}</div>
    </div>`;
  }

  function linkColor(l) {
    const s = idOf(l.source);
    const t = idOf(l.target);
    if (state.selected && s !== state.selected.id && t !== state.selected.id) return 'rgba(90,110,145,.10)';
    if (l.type === 'semantic') return 'rgba(92,202,255,.38)';
    if (l.type === 'tag') return 'rgba(232,197,141,.18)';
    return 'rgba(140,165,205,.22)';
  }

  function linkWidth(l) {
    if (state.selected && idOf(l.source) !== state.selected.id && idOf(l.target) !== state.selected.id) return 0.25;
    return l.type === 'semantic' ? 0.8 : 0.45;
  }

  function refreshStyle() {
    if (!Graph) return;
    Graph.nodeColor(nodeColor).linkColor(linkColor).linkWidth(linkWidth);
    Graph.refresh();
  }

  function placeNodes() {
    const mems = nodes.filter((n) => n.type === 'memory');
    const kinds = [...new Set(mems.map((n) => n.kind))];
    const centers = new Map();
    kinds.forEach((kind, i) => {
      const a = (i / Math.max(1, kinds.length)) * Math.PI * 2 + 0.2;
      centers.set(kind, {
        x: Math.cos(a) * 120,
        y: Math.sin(i * 1.7) * 26,
        z: Math.sin(a) * 120,
      });
    });

    for (const n of mems) {
      const c = centers.get(n.kind) || { x: 0, y: 0, z: 0 };
      const r = 22 + seeded(n.id, 1) * 22;
      const theta = seeded(n.id, 2) * Math.PI * 2;
      const phi = Math.acos(2 * seeded(n.id, 3) - 1);
      n.fx = c.x + Math.sin(phi) * Math.cos(theta) * r;
      n.fy = c.y + Math.cos(phi) * r * 0.7;
      n.fz = c.z + Math.sin(phi) * Math.sin(theta) * r;
      n.x = n.fx; n.y = n.fy; n.z = n.fz;
    }

    const core = nodes.find((n) => n.type === 'core');
    if (core) { core.fx = 0; core.fy = 0; core.fz = 0; core.x = 0; core.y = 0; core.z = 0; }

    for (const t of nodes.filter((n) => n.type === 'tag')) {
      const linked = mems.filter((m) => (m.tags || []).includes(t.label));
      if (!linked.length) { t.fx = 0; t.fy = 20; t.fz = 0; continue; }
      let x = 0, y = 0, z = 0;
      for (const m of linked) { x += m.x; y += m.y; z += m.z; }
      x /= linked.length; y /= linked.length; z /= linked.length;
      const len = Math.max(0.001, Math.hypot(x, y, z));
      t.fx = x + (x / len) * 14;
      t.fy = y + 22;
      t.fz = z + (z / len) * 14;
      t.x = t.fx; t.y = t.fy; t.z = t.fz;
    }

    for (const e of nodes.filter((n) => n.type === 'event')) {
      const incoming = edges.find((ed) => ed.type === 'source' && idOf(ed.target) === e.id);
      const parent = incoming ? byId.get(idOf(incoming.source)) : null;
      const base = parent && parent.x != null ? parent : { x: 0, y: 0, z: 0 };
      const a = seeded(e.id, 1) * Math.PI * 2;
      const r = 6 + seeded(e.id, 2) * 12;
      e.fx = base.x + Math.cos(a) * r;
      e.fy = base.y + (seeded(e.id, 3) - 0.5) * 18;
      e.fz = base.z + Math.sin(a) * r;
      e.x = e.fx; e.y = e.fy; e.z = e.fz;
    }

    const digests = nodes.filter((n) => n.type === 'digest');
    digests.forEach((d, i) => {
      const a = (i / Math.max(1, digests.length)) * Math.PI * 2 - Math.PI / 2;
      d.fx = Math.cos(a) * 215;
      d.fy = 55;
      d.fz = Math.sin(a) * 215;
      d.x = d.fx; d.y = d.fy; d.z = d.fz;
    });
  }

  function buildGraph() {
    Graph = ForceGraph3D({ controlType: 'orbit' })(graphEl)
      .backgroundColor('#04060f')
      .showNavInfo(false)
      .nodeRelSize(2.4)
      .nodeVal(nodeVal)
      .nodeColor(nodeColor)
      .nodeOpacity(0.95)
      .nodeResolution(12)
      .nodeLabel(nodeLabel)
      .linkColor(linkColor)
      .linkWidth(linkWidth)
      .linkOpacity(0.6)
      .linkResolution(6)
      .linkDirectionalParticles((l) => l.type === 'semantic' ? 2 : 0)
      .linkDirectionalParticleWidth(1.2)
      .linkDirectionalParticleSpeed(0.004)
      .onNodeClick((node) => selectNode(node))
      .onNodeHover((node) => { state.hover = node || null; })
      .onBackgroundClick(() => selectNode(null))
      .enableNodeDrag(false)
      .warmupTicks(0)
      .cooldownTicks(0);

    setTimeout(() => fitCamera(700), 500);
    Graph.controls().autoRotate = true;
    Graph.controls().autoRotateSpeed = 0.35;
    Graph.controls().enableDamping = true;
  }

  function fitCamera(duration = 800) {
    if (!Graph) return;
    if (typeof Graph.zoomToFit === 'function') {
      Graph.zoomToFit(duration, 70, (n) => n.type === 'memory' || n.type === 'core' || n.type === 'tag');
      return;
    }
    const list = nodes.filter((n) => visible(n) && n.x != null);
    if (!list.length) return;
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    for (const n of list) {
      minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
      minZ = Math.min(minZ, n.z); maxZ = Math.max(maxZ, n.z);
    }
    const center = { x: (minX + maxX) / 2, y: (minY + maxY) / 2, z: (minZ + maxZ) / 2 };
    let radius = 1;
    for (const n of list) {
      radius = Math.max(radius, Math.hypot(n.x - center.x, n.y - center.y, n.z - center.z));
    }
    const distance = Math.max(150, radius * 1.8);
    Graph.cameraPosition({
      x: center.x,
      y: center.y + radius * 0.28,
      z: center.z + distance,
    }, center, duration);
  }

  function applyFilters() {
    const ns = nodes.filter(visible);
    const keep = new Set(ns.map((n) => n.id));
    const ls = edges.filter((e) => keep.has(idOf(e.source)) && keep.has(idOf(e.target)));
    Graph.graphData({ nodes: ns, links: ls });
    refreshStyle();
  }

  function sourceEvents(n) {
    if (n.type !== 'memory') return [];
    return edges
      .filter((e) => e.type === 'source' && idOf(e.source) === n.id)
      .map((e) => byId.get(idOf(e.target)))
      .filter(Boolean);
  }

  function relatedNodes(n) {
    if (n.type === 'tag') {
      return edges.filter((e) => e.type === 'tag' && idOf(e.target) === n.id)
        .map((e) => byId.get(idOf(e.source))).filter(Boolean);
    }
    if (n.type === 'event') {
      const incoming = edges.find((e) => e.type === 'source' && idOf(e.target) === n.id);
      return incoming ? [byId.get(idOf(incoming.source))].filter(Boolean) : [];
    }
    return [];
  }

  function linkList(list, label) {
    if (!list.length) return '';
    return `<div class="sources"><b>${escapeHtml(label)} ${list.length}</b><br>${list.slice(0, 8).map((x) =>
      `<button class="link" type="button" data-node="${escapeHtml(x.id)}">· ${escapeHtml(x.label)}</button>`).join('')}</div>`;
  }

  function openPanel(n) {
    panel.classList.add('open');
    const kindName = n.type === 'memory' ? (KIND_NAMES[n.kind] || n.kind) : n.type;
    const tags = (n.tags || []).map((x) => `<span class="tag">${escapeHtml(x)}</span>`).join('');
    const src = sourceEvents(n);
    const sources = src.length
      ? `<div class="sources"><b>来源事件 ${src.length}</b><br>${src.slice(0, 5).map((e) =>
        `<button class="link" type="button" data-node="${escapeHtml(e.id)}">· ${escapeHtml(e.label)}</button>`).join('')}</div>`
      : '';
    const related = relatedNodes(n);
    const relatedBlock = linkList(related, n.type === 'tag' ? '相关记忆' : '关联记忆');
    const meta = n.type === 'memory'
      ? `<div class="meta">
          <span>重要度</span><b>${n.importance} / 5</b>
          <span>置信度</span><b>${Math.round((n.confidence || 0) * 100)}%</b>
          <span>时间</span><b>${escapeHtml((n.created_at || '').slice(0, 10))}</b>
        </div>`
      : n.type === 'event'
        ? `<div class="meta"><span>时间</span><b>${escapeHtml((n.occurred_at || '').slice(0, 16).replace('T', ' '))}</b></div>`
        : '';
    const bodyText = n.type === 'tag'
      ? `和「${n.label}」有关的记忆 ${related.length} 条。点下面的记忆就能跳过去。`
      : (n.body || n.label);
    const canSpeak = (n.type === 'memory' || n.type === 'core' || n.type === 'digest') && n.body;
    panelBody.innerHTML = `
      <span class="kind">${escapeHtml(kindName)}</span>
      <h2>${escapeHtml(n.label)}</h2>
      <p class="body">${escapeHtml(bodyText)}</p>
      ${tags ? `<div class="tags">${tags}</div>` : ''}
      ${meta}
      ${relatedBlock}
      ${sources}
      ${canSpeak ? `<button class="speak" id="speak-btn" type="button">让大肥鱼读给我听</button>` : ''}
    `;
    panelBody.querySelectorAll('[data-node]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const next = byId.get(btn.dataset.node);
        if (next) selectNode(next);
      });
    });
    const speakBtn = document.getElementById('speak-btn');
    if (speakBtn) speakBtn.addEventListener('click', () => speak(n, speakBtn));
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
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.message || 'TTS failed');
      const audio = new Audio(payload.url + '?t=' + Date.now());
      audio.onended = () => { btn.disabled = false; btn.textContent = '让大肥鱼读给我听'; };
      await audio.play();
      btn.textContent = '正在读…';
    } catch (err) {
      btn.disabled = false;
      btn.textContent = '朗读失败：' + String(err.message || err).slice(0, 40);
    }
  }

  function focusCamera(n) {
    if (!Graph || !n) return;
    const len = Math.hypot(n.x || 0, n.y || 0, n.z || 0);
    const distance = 250;
    if (len < 15) {
      Graph.cameraPosition({ x: 0, y: 60, z: 220 }, n, 1000);
    } else {
      const ratio = 1 + distance / len;
      Graph.cameraPosition({
        x: (n.x || 0) * ratio,
        y: (n.y || 0) * ratio,
        z: (n.z || 0) * ratio,
      }, n, 1000);
    }
    Graph.controls().autoRotate = false;
  }

  function selectNode(n) {
    if (!Graph) return;
    if (!n) {
      state.selected = null;
      state.neighbors.clear();
      panel.classList.remove('open');
      Graph.controls().autoRotate = true;
      refreshStyle();
      return;
    }
    state.selected = n;
    state.neighbors = new Set();
    for (const e of edges) {
      if (idOf(e.source) === n.id) state.neighbors.add(idOf(e.target));
      else if (idOf(e.target) === n.id) state.neighbors.add(idOf(e.source));
    }
    openPanel(n);
    focusCamera(n);
    refreshStyle();
  }

  function ensureLabels() {
    labelLayer.innerHTML = '';
    labelEntries = nodes
      .filter((n) => n.type === 'core' || n.type === 'digest' || n.type === 'memory')
      .map((n) => {
        const el = document.createElement('div');
        el.className = `graph-label ${n.type}`;
        el.textContent = n.type === 'core' ? '核心记忆'
          : n.type === 'digest' ? n.day
            : n.label.slice(0, 20);
        labelLayer.appendChild(el);
        return { n, el };
      });
    requestAnimationFrame(updateLabels);
  }

  function updateLabels() {
    if (!Graph) {
      requestAnimationFrame(updateLabels);
      return;
    }
    for (const { n, el } of labelEntries) {
      const show = (n.type === 'core' || n.type === 'digest'
        || state.selected === n) && visible(n)
        && !(state.selected && n.type === 'core');
      if (!show || n.x == null) {
        el.style.display = 'none';
        continue;
      }
      let p = null;
      try { p = Graph.graph2ScreenCoords(n.x, n.y, n.z); } catch { /* ignore */ }
      if (!p || p.x < -80 || p.y < -40 || p.x > window.innerWidth + 80 || p.y > window.innerHeight + 40) {
        el.style.display = 'none';
        continue;
      }
      el.style.display = 'block';
      const dy = n.type === 'core' ? 20 : n.type === 'digest' ? -14 : 16;
      el.style.transform = `translate(-50%, -50%) translate(${p.x}px, ${p.y + dy}px)`;
      el.classList.toggle('selected', state.selected === n);
    }
    requestAnimationFrame(updateLabels);
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
      applyFilters();
      selectNode(null);
    });
  }

  function bindUi() {
    closeBtn.addEventListener('click', () => selectNode(null));
    resetBtn.addEventListener('click', () => {
      state.kind = null;
      state.query = '';
      search.value = '';
      [...chips.querySelectorAll('.chip')].forEach((c, i) => c.classList.toggle('on', i === 0));
      selectNode(null);
      applyFilters();
      setTimeout(() => fitCamera(800), 250);
      Graph.controls().autoRotate = true;
    });
    search.addEventListener('input', () => {
      state.query = search.value.trim().toLowerCase();
      applyFilters();
      selectNode(null);
    });
  }

  async function boot() {
    if (typeof ForceGraph3D !== 'function') {
      loader.textContent = '3d-force-graph 没加载出来';
      return;
    }
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
      placeNodes();
      buildGraph();
      Graph.graphData({ nodes, links: edges });
      ensureLabels();
      buildChips();
      bindUi();
      const m = data.meta || {};
      subtitle.textContent = `${m.memory_count || 0} 颗记忆星 · ${m.event_count || 0} 粒事件尘 · ${m.tag_count || 0} 个标签 · ${m.digest_count || 0} 份日摘要`;
      window.__GALAXY_DEBUG__ = { Graph, state, nodes, edges, selectNode, applyFilters, visible };
      loader.classList.add('hide');
    } catch (err) {
      loader.innerHTML = '读不到 galaxy.json<br><small style="opacity:.7">先在 D:\\大肥鱼 运行：python MemoryService/export_galaxy.py<br>然后用本地 HTTP 打开本页</small>';
      console.error(err);
    }
  }

  boot();
})();
