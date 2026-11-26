import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

/* 大肥鱼 · 记忆星河 — 自定义 Three.js + Bloom 实验版 */

const stage = document.getElementById('stage');
const loader = document.getElementById('loader');
const subtitle = document.getElementById('subtitle');
const search = document.getElementById('search');
const chips = document.getElementById('chips');
const panel = document.getElementById('panel');
const panelBody = document.getElementById('panel-body');
const closeBtn = document.getElementById('close');
const resetBtn = document.getElementById('reset');
const labelLayer = document.getElementById('labels');
if (new URLSearchParams(window.location.search).has('embed')) {
  document.body.classList.add('embed');
}

const KIND_COLORS = {
  capability: '#7cd8ff', user_preference: '#ffb3d1', user_fact: '#ffd28a',
  experience: '#b9a7ff', interest: '#7ef0c8', relationship: '#ff9f8a',
  boundary: '#c7d2e8', preference: '#ffc4a3', technical: '#8fb7ff',
  core: '#ffd28a', event: '#8aa0c6', tag: '#e8c58d', digest: '#b9a7ff',
};
const KIND_NAMES = {
  capability: '能力', user_preference: '偏好', user_fact: '关于主人',
  experience: '经历', interest: '兴趣', relationship: '关系',
  boundary: '边界', preference: '偏好', technical: '技术',
};

const state = {
  selected: null, hover: null, kind: null, query: '',
};

let data = null;
let nodes = [];
let edges = [];
let byId = new Map();
let scene = null;
let camera = null;
let renderer = null;
let composer = null;
let controls = null;
let bloom = null;
let galaxyGroup = null;
let nodeGroup = null;
let lineGroup = null;
let clock = null;
let nodeSprites = [];
let labelEntries = [];
let camTween = null;
let startX = 0;
let startY = 0;
let moved = 0;
let dragging = false;
let hoverNode = null;
let hoverTip = null;

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const colorOf = (n) => n.type === 'memory'
  ? (KIND_COLORS[n.kind] || '#7cd8ff')
  : (KIND_COLORS[n.type] || '#9fb3d6');
const idOf = (x) => (x && typeof x === 'object') ? x.id : x;
const seeded = (id, salt = 0) => {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) { h ^= id.charCodeAt(i); h = Math.imul(h, 16777619); }
  const x = Math.sin((h >>> 0) * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
};

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

function radialTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.18, 'rgba(255,255,255,.95)');
  g.addColorStop(0.42, 'rgba(255,255,255,.42)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function placeNodes() {
  const mems = nodes.filter((n) => n.type === 'memory');
  const kinds = [...new Set(mems.map((n) => n.kind))];
  const centers = new Map();
  kinds.forEach((kind, i) => {
    const a = (i / Math.max(1, kinds.length)) * Math.PI * 2 + 0.2;
    centers.set(kind, {
      x: Math.cos(a) * 210,
      y: Math.sin(i * 1.7) * 55,
      z: Math.sin(a) * 210,
    });
  });

  for (const n of mems) {
    const c = centers.get(n.kind) || { x: 0, y: 0, z: 0 };
    const r = 32 + seeded(n.id, 1) * 38;
    const theta = seeded(n.id, 2) * Math.PI * 2;
    const phi = Math.acos(2 * seeded(n.id, 3) - 1);
    n.pos = {
      x: c.x + Math.sin(phi) * Math.cos(theta) * r,
      y: c.y + Math.cos(phi) * r * 0.7,
      z: c.z + Math.sin(phi) * Math.sin(theta) * r,
    };
  }

  const core = nodes.find((n) => n.type === 'core');
  if (core) core.pos = { x: 0, y: 0, z: 0 };

  for (const t of nodes.filter((n) => n.type === 'tag')) {
    const linked = mems.filter((m) => (m.tags || []).includes(t.label));
    if (!linked.length) { t.pos = { x: 0, y: 30, z: 0 }; continue; }
    let x = 0, y = 0, z = 0;
    for (const m of linked) { x += m.pos.x; y += m.pos.y; z += m.pos.z; }
    x /= linked.length; y /= linked.length; z /= linked.length;
    const len = Math.max(0.001, Math.hypot(x, y, z));
    t.pos = { x: x + (x / len) * 22, y: y + 35, z: z + (z / len) * 22 };
  }

  for (const e of nodes.filter((n) => n.type === 'event')) {
    const incoming = edges.find((ed) => ed.type === 'source' && idOf(ed.target) === e.id);
    const parent = incoming ? byId.get(idOf(incoming.source)) : null;
    const base = parent && parent.pos ? parent.pos : { x: 0, y: 0, z: 0 };
    const a = seeded(e.id, 1) * Math.PI * 2;
    const r = 10 + seeded(e.id, 2) * 18;
    e.pos = {
      x: base.x + Math.cos(a) * r,
      y: base.y + (seeded(e.id, 3) - 0.5) * 28,
      z: base.z + Math.sin(a) * r,
    };
  }

  nodes.filter((n) => n.type === 'digest').forEach((d, i, arr) => {
    const a = (i / Math.max(1, arr.length)) * Math.PI * 2 - Math.PI / 2;
    d.pos = { x: Math.cos(a) * 360, y: 70, z: Math.sin(a) * 360 };
  });
}

function buildGalaxy() {
  const N = 22000;
  const positions = new Float32Array(N * 3);
  const colors = new Float32Array(N * 3);
  const palette = [
    [1.0, 0.93, 0.82], [1.0, 0.67, 0.84], [0.62, 0.82, 1.0],
    [0.80, 0.68, 1.0], [1.0, 0.82, 0.58], [0.92, 0.96, 1.0],
  ];
  for (let i = 0; i < N; i++) {
    let x, y, z, c;
    if (i < 3800) {
      const r = Math.pow(Math.random(), 2.2) * 135;
      const a = Math.random() * Math.PI * 2;
      x = Math.cos(a) * r;
      y = (Math.random() - 0.5) * (55 - r * 0.18);
      z = Math.sin(a) * r;
      c = Math.random() < 0.45 ? palette[4] : palette[0];
    } else if (i < 19800) {
      const r = 80 + Math.pow(Math.random(), 0.66) * 820;
      const arm = (i % 2) * Math.PI;
      const a = arm + r * 0.0062 + (Math.random() - 0.5) * 0.36;
      x = Math.cos(a) * r;
      z = Math.sin(a) * r;
      y = (Math.random() - 0.5) * (26 + 70 * (1 - r / 1000));
      c = palette[Math.floor(Math.random() * palette.length)];
    } else {
      const a = Math.random() * Math.PI * 2;
      const p = Math.acos(2 * Math.random() - 1);
      const r = 500 + Math.random() * 850;
      x = Math.sin(p) * Math.cos(a) * r;
      y = Math.cos(p) * r * 0.55;
      z = Math.sin(p) * Math.sin(a) * r;
      c = palette[5];
    }
    positions[i * 3] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;
    const b = 0.55 + Math.random() * 0.45;
    colors[i * 3] = c[0] * b;
    colors[i * 3 + 1] = c[1] * b;
    colors[i * 3 + 2] = c[2] * b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const mat = new THREE.PointsMaterial({
    size: 1.9,
    map: radialTexture(),
    vertexColors: true,
    transparent: true,
    opacity: 0.7,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
    alphaTest: 0.01,
  });
  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;
  galaxyGroup = new THREE.Group();
  galaxyGroup.add(points);

  // 星云
  const nebulaTex = radialTexture();
  const nebulaSpecs = [
    [0, 0, 0, 560, 0xffd2a0, 0.32],
    [-190, 10, 130, 380, 0xff8dc4, 0.24],
    [210, -20, -120, 420, 0x7cc8ff, 0.22],
    [-320, 40, 220, 320, 0xb494ff, 0.18],
    [360, -30, 260, 360, 0xffa8cc, 0.16],
  ];
  for (const [x, y, z, size, color, op] of nebulaSpecs) {
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: nebulaTex, color, transparent: true, opacity: op * 0.42,
      depthWrite: false, blending: THREE.AdditiveBlending,
    }));
    sprite.position.set(x, y, z);
    sprite.scale.set(size, size, 1);
    galaxyGroup.add(sprite);
  }
  scene.add(galaxyGroup);
}

function buildNodes() {
  nodeGroup = new THREE.Group();
  scene.add(nodeGroup);
  const tex = radialTexture();
  for (const n of nodes) {
    if (!n.pos) continue;
    const baseSize = n.type === 'core' ? 82
      : n.type === 'memory' ? 18 + (n.importance || 3) * 8
        : n.type === 'tag' ? 30
          : n.type === 'digest' ? 24 : 7;
    const size = baseSize * 0.5;
    const mat = new THREE.SpriteMaterial({
      map: tex,
      color: new THREE.Color(colorOf(n)),
      transparent: true,
      opacity: n.type === 'event' ? 0.5 : 0.9,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const sprite = new THREE.Sprite(mat);
    sprite.position.set(n.pos.x, n.pos.y, n.pos.z);
    sprite.scale.set(size, size, 1);
    sprite.userData.node = n;
    n.sprite = sprite;
    nodeGroup.add(sprite);
    if (n.type !== 'event') nodeSprites.push(sprite);
  }
}

function buildEdges() {
  const positions = [];
  const colors = [];
  for (const e of edges) {
    const a = byId.get(idOf(e.source));
    const b = byId.get(idOf(e.target));
    if (!a || !b || !a.pos || !b.pos) continue;
    positions.push(a.pos.x, a.pos.y, a.pos.z, b.pos.x, b.pos.y, b.pos.z);
    let c = [0.45, 0.55, 0.7];
    if (e.type === 'semantic') c = [0.35, 0.78, 1.0];
    else if (e.type === 'tag') c = [0.9, 0.72, 0.42];
    colors.push(...c, ...c);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  const mat = new THREE.LineBasicMaterial({
    vertexColors: true, transparent: true, opacity: 0.3,
    depthWrite: false, blending: THREE.AdditiveBlending,
  });
  lineGroup = new THREE.LineSegments(geo, mat);
  scene.add(lineGroup);
}

function buildLabels() {
  labelEntries = nodes
    .filter((n) => n.type === 'core' || n.type === 'digest' || n.type === 'memory')
    .map((n) => {
      const el = document.createElement('div');
      el.className = `graph-label ${n.type}`;
      el.textContent = n.type === 'core' ? '核心记忆'
        : n.type === 'digest' ? n.day : n.label.slice(0, 20);
      labelLayer.appendChild(el);
      return { n, el };
    });
}

function updateLabels() {
  if (!camera) return;
  for (const { n, el } of labelEntries) {
    const show = (n.type === 'core' || state.selected === n)
      && visible(n) && !(state.selected && n.type === 'core');
    if (!show || !n.pos) { el.style.display = 'none'; continue; }
    const v = new THREE.Vector3(n.pos.x, n.pos.y, n.pos.z).project(camera);
    if (v.z < -1 || v.z > 1) { el.style.display = 'none'; continue; }
    const x = (v.x * 0.5 + 0.5) * window.innerWidth;
    const y = (-v.y * 0.5 + 0.5) * window.innerHeight;
    if (x < -80 || y < -40 || x > window.innerWidth + 80 || y > window.innerHeight + 40) {
      el.style.display = 'none'; continue;
    }
    el.style.display = 'block';
    const dy = n.type === 'core' ? 24 : n.type === 'digest' ? -16 : 18;
    el.style.transform = `translate(-50%, -50%) translate(${x}px, ${y + dy}px)`;
    el.classList.toggle('selected', state.selected === n);
  }
}

function updateVisibility() {
  for (const s of nodeSprites) {
    const n = s.userData.node;
    s.visible = visible(n);
    s.material.opacity = n.type === 'event' ? 0.5 : 0.9;
    if (state.selected) {
      if (n.id === state.selected.id) s.material.opacity = 1;
      else if (s.material.opacity < 0.7) s.material.opacity *= 0.35;
    }
  }
  if (lineGroup) lineGroup.material.opacity = state.selected ? 0.12 : 0.3;
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

function sourceEvents(n) {
  if (n.type !== 'memory') return [];
  return edges.filter((e) => e.type === 'source' && idOf(e.source) === n.id)
    .map((e) => byId.get(idOf(e.target))).filter(Boolean);
}

function linkList(list, label) {
  if (!list.length) return '';
  return `<div class="sources"><b>${esc(label)} ${list.length}</b><br>${list.slice(0, 8).map((x) =>
    `<button class="link" type="button" data-node="${esc(x.id)}">· ${esc(x.label)}</button>`).join('')}</div>`;
}

function openPanel(n) {
  panel.classList.add('open');
  const kindName = n.type === 'memory' ? (KIND_NAMES[n.kind] || n.kind) : n.type;
  const tags = (n.tags || []).map((x) => `<span class="tag">${esc(x)}</span>`).join('');
  const src = sourceEvents(n);
  const sources = src.length
    ? `<div class="sources"><b>来源事件 ${src.length}</b><br>${src.slice(0, 5).map((e) =>
      `<button class="link" type="button" data-node="${esc(e.id)}">· ${esc(e.label)}</button>`).join('')}</div>`
    : '';
  const related = relatedNodes(n);
  const relatedBlock = linkList(related, n.type === 'tag' ? '相关记忆' : '关联记忆');
  const meta = n.type === 'memory'
    ? `<div class="meta"><span>重要度</span><b>${n.importance} / 5</b>
       <span>置信度</span><b>${Math.round((n.confidence || 0) * 100)}%</b>
       <span>时间</span><b>${esc((n.created_at || '').slice(0, 10))}</b></div>`
    : n.type === 'event'
      ? `<div class="meta"><span>时间</span><b>${esc((n.occurred_at || '').slice(0, 16).replace('T', ' '))}</b></div>`
      : '';
  const bodyText = n.type === 'tag'
    ? `和「${n.label}」有关的记忆 ${related.length} 条。点下面的记忆就能跳过去。`
    : (n.body || n.label);
  const canSpeak = (n.type === 'memory' || n.type === 'core' || n.type === 'digest') && n.body;
  panelBody.innerHTML = `
    <span class="kind">${esc(kindName)}</span>
    <h2>${esc(n.label)}</h2>
    <p class="body">${esc(bodyText)}</p>
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

function selectNode(n) {
  state.selected = n;
  if (!n) {
    state.selected = null;
    panel.classList.remove('open');
    controls.autoRotate = true;
    updateVisibility();
    return;
  }
  openPanel(n);
  controls.autoRotate = false;
  const p = new THREE.Vector3(n.pos.x, n.pos.y, n.pos.z);
  const dir = new THREE.Vector3().subVectors(camera.position, controls.target).normalize();
  const dest = p.clone().add(dir.multiplyScalar(760));
  camTween = {
    from: camera.position.clone(),
    to: dest,
    lookFrom: controls.target.clone(),
    lookTo: p,
    t: 0,
  };
  updateVisibility();
}

function buildChips() {
  const kinds = [...new Set(nodes.filter((n) => n.type === 'memory').map((n) => n.kind))];
  chips.innerHTML = '<button class="chip on" data-kind="">全部</button>'
    + kinds.map((k) => `<button class="chip" data-kind="${esc(k)}">${esc(KIND_NAMES[k] || k)}</button>`).join('');
  chips.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.chip');
    if (!btn) return;
    state.kind = btn.dataset.kind || null;
    [...chips.querySelectorAll('.chip')].forEach((c) => c.classList.toggle('on', c === btn));
    updateVisibility();
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
    camera.position.set(0, 390, 1180);
    controls.target.set(0, 0, 0);
    camTween = null;
    controls.autoRotate = true;
    updateVisibility();
  });
  search.addEventListener('input', () => {
    state.query = search.value.trim().toLowerCase();
    updateVisibility();
    selectNode(null);
  });
  renderer.domElement.addEventListener('pointerdown', (ev) => {
    dragging = true; moved = 0; startX = ev.clientX; startY = ev.clientY;
    if (hoverTip) hoverTip.classList.remove('on');
  });
  renderer.domElement.addEventListener('pointermove', (ev) => {
    if (dragging) {
      moved += Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY);
      startX = ev.clientX; startY = ev.clientY;
      if (hoverTip) hoverTip.classList.remove('on');
      return;
    }
    const n = nodeAt(ev);
    if (n !== hoverNode) showHover(n, ev);
    else if (n && hoverTip) {
      hoverTip.style.left = Math.min(window.innerWidth - 290, ev.clientX + 14) + 'px';
      hoverTip.style.top = Math.min(window.innerHeight - 120, ev.clientY + 14) + 'px';
    }
  });
  renderer.domElement.addEventListener('pointerup', (ev) => {
    if (moved < 6) pick(ev);
    dragging = false;
  });
  renderer.domElement.addEventListener('pointerleave', () => showHover(null, null));
  window.addEventListener('resize', resize);
}

function nodeAt(ev) {
  const rect = renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(
    ((ev.clientX - rect.left) / rect.width) * 2 - 1,
    -((ev.clientY - rect.top) / rect.height) * 2 + 1,
  );
  const ray = new THREE.Raycaster();
  ray.params.Sprite = { threshold: 0.1 };
  ray.setFromCamera(mouse, camera);
  const hits = ray.intersectObjects(nodeSprites.filter((s) => s.visible), false);
  return hits.length ? hits[0].object.userData.node : null;
}

function ensureHoverTip() {
  if (hoverTip) return hoverTip;
  hoverTip = document.createElement('div');
  hoverTip.className = 'hover-tip';
  document.body.appendChild(hoverTip);
  return hoverTip;
}

function showHover(n, ev) {
  const tip = ensureHoverTip();
  if (!n) {
    hoverNode = null;
    tip.classList.remove('on');
    renderer.domElement.style.cursor = '';
    return;
  }
  hoverNode = n;
  const kind = n.type === 'memory' ? (KIND_NAMES[n.kind] || n.kind)
    : n.type === 'core' ? '核心'
      : n.type === 'event' ? '事件'
        : n.type === 'tag' ? '标签'
          : n.type === 'digest' ? '日摘要' : n.type;
  const body = (n.body || n.label || '').replace(/\s+/g, ' ').slice(0, 120);
  tip.innerHTML = `<div class="hover-kind">${esc(kind)}</div>
    <div class="hover-title">${esc(n.label)}</div>
    <div class="hover-body">${esc(body)}</div>`;
  tip.style.left = Math.min(window.innerWidth - 290, ev.clientX + 14) + 'px';
  tip.style.top = Math.min(window.innerHeight - 120, ev.clientY + 14) + 'px';
  tip.classList.add('on');
  renderer.domElement.style.cursor = 'pointer';
}

function pick(ev) {
  const n = nodeAt(ev);
  if (n) selectNode(n);
  else selectNode(null);
}

function resize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  composer.setSize(w, h);
  bloom.setSize(w, h);
}

function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();
  if (galaxyGroup) galaxyGroup.rotation.y = t * 0.012;
  if (camTween) {
    camTween.t = Math.min(1, camTween.t + 0.03);
    const k = 1 - Math.pow(1 - camTween.t, 3);
    camera.position.lerpVectors(camTween.from, camTween.to, k);
    controls.target.lerpVectors(camTween.lookFrom, camTween.lookTo, k);
    if (camTween.t >= 1) camTween = null;
  }
  controls.update();
  composer.render();
  updateLabels();
}

async function boot() {
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

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x03050c);
    camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 5000);
    camera.position.set(0, 390, 1180);
    renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.85;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    stage.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.22;
    controls.minDistance = 260;
    controls.maxDistance = 2600;

    buildGalaxy();
    buildNodes();
    buildEdges();
    buildLabels();
    updateVisibility();

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.28, 0.34, 0.5);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());

    clock = new THREE.Clock();
    buildChips();
    bindUi();
    const m = data.meta || {};
    subtitle.textContent = `${m.memory_count || 0} 颗记忆星 · ${m.event_count || 0} 粒事件尘 · ${m.tag_count || 0} 个标签 · bloom 实验版`;
    window.__GALAXY_DEBUG__ = { scene, camera, renderer, composer, controls, nodes, edges, selectNode, state };
    loader.classList.add('hide');
    animate();
  } catch (err) {
    loader.innerHTML = '启动失败<br><small style="opacity:.7">' + esc(err.message || err) + '</small>';
    console.error(err);
  }
}

boot();
