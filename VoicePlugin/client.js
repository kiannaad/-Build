window.__ModuleLoader__.load({
  id: 'dsh-voice-read',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const { useCallback, useEffect, useMemo, useRef, useState } = React;

    const API = 'http://127.0.0.1:9881';
    const AUTO_KEY = 'dafeiyu.voice.auto';
    const STARTED_AT = Date.now();
    const EMPTY = { nodes: { values: () => [] } };

    function useAutoRead() {
      const [on, setOn] = useState(() => {
        try { return localStorage.getItem(AUTO_KEY) === '1'; } catch { return false; }
      });
      useEffect(() => {
        const sync = () => {
          try { setOn(localStorage.getItem(AUTO_KEY) === '1'); } catch { /* ignore */ }
        };
        window.addEventListener('dafeiyu:voice-auto', sync);
        return () => window.removeEventListener('dafeiyu:voice-auto', sync);
      }, []);
      return on;
    }

    function assistantText(blocks) {
      if (!Array.isArray(blocks)) return '';
      return blocks
        .filter((b) => b && b.kind === 'text' && typeof b.text === 'string')
        .map((b) => b.text)
        .join('\n')
        .replace(/[ \t]+/g, ' ')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
    }

    function findNode(snapshot, messageId) {
      if (!snapshot || !snapshot.nodes) return undefined;
      for (const node of snapshot.nodes.values()) {
        if (node && node.kind === 'assistant-step'
          && node.data && node.data.finalNode
          && node.data.finalNode.messageId === messageId) return node;
      }
      return undefined;
    }

    function latestAssistantId(snapshot) {
      if (!snapshot || !snapshot.nodes) return undefined;
      let best;
      let bestSeq = -1;
      for (const node of snapshot.nodes.values()) {
        if (!node || node.kind !== 'assistant-step' || !node.data || !node.data.finalNode) continue;
        const id = node.data.finalNode.messageId;
        if (id === undefined) continue;
        const seq = typeof node.anchorSeq === 'number' ? node.anchorSeq : -1;
        if (seq > bestSeq) { bestSeq = seq; best = id; }
      }
      return best;
    }

    function VoiceAction({ messageId, useChat }) {
      const chat = typeof useChat === 'function' ? useChat : (selector) => selector(EMPTY);
      const text = chat((snapshot) => {
        const node = findNode(snapshot, messageId);
        return node ? assistantText(node.data.blocks) : '';
      });
      const messageTime = chat((snapshot) => {
        const node = findNode(snapshot, messageId);
        return node && typeof node.data.time === 'number' ? node.data.time : 0;
      });
      const latestId = chat((snapshot) => latestAssistantId(snapshot));
      const autoOn = useAutoRead();
      const [state, setState] = useState('idle');
      const [detail, setDetail] = useState('');
      const audioRef = useRef(null);
      const autoDone = useRef(false);

      useEffect(() => () => {
        if (audioRef.current) {
          try { audioRef.current.pause(); } catch { /* ignore */ }
          audioRef.current = null;
        }
      }, []);

      const speak = useCallback(async () => {
        if (!text || state === 'loading') return;
        if (audioRef.current) {
          try { audioRef.current.pause(); } catch { /* ignore */ }
          audioRef.current = null;
        }
        setState('loading');
        setDetail('');
        try {
          const res = await fetch(`${API}/speak`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, emotion: 'neutral' }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.message || `HTTP ${res.status}`);
          const audio = new Audio(`${data.url}?t=${Date.now()}`);
          audioRef.current = audio;
          audio.onended = () => setState('idle');
          audio.onerror = () => { setState('error'); setDetail('音频加载失败'); };
          await audio.play();
          setState('playing');
        } catch (error) {
          setState('error');
          setDetail(String(error && error.message ? error.message : error));
          window.setTimeout(() => setState('idle'), 2500);
        }
      }, [text, state]);

      // 只自动读“插件启动之后新到的最后一条”，历史消息不自动播。
      useEffect(() => {
        if (!autoOn || autoDone.current) return;
        if (!text || latestId !== messageId) return;
        if (!messageTime || messageTime < STARTED_AT) return;
        autoDone.current = true;
        speak();
      }, [autoOn, text, latestId, messageId, messageTime, speak]);

      const label = state === 'loading' ? '生成语音中'
        : state === 'playing' ? '停止朗读'
          : state === 'error' ? (detail || '朗读失败')
            : '朗读这条回复';
      const icon = state === 'loading' ? '…' : state === 'playing' ? '⏹' : state === 'error' ? '!' : '🔊';

      return h('button', {
        type: 'button',
        title: label,
        'aria-label': label,
        disabled: !text || state === 'loading',
        onClick: () => {
          if (state === 'playing' && audioRef.current) {
            try { audioRef.current.pause(); } catch { /* ignore */ }
            audioRef.current = null;
            setState('idle');
            return;
          }
          speak();
        },
        style: {
          width: 22,
          height: 22,
          padding: 0,
          border: 0,
          borderRadius: 6,
          background: 'transparent',
          color: state === 'error' ? 'var(--dsw-alias-state-error, #d44)' : 'var(--dsw-alias-text-secondary, #666)',
          cursor: text ? 'pointer' : 'default',
          opacity: text ? 1 : 0.4,
          fontSize: 13,
          lineHeight: '22px',
          textAlign: 'center',
        },
      }, icon);
    }

    const VOICE_CSS = `
      .dafeiyu-voice-view {
        height: 100%; overflow: auto; padding: 18px 16px 90px;
        background: radial-gradient(circle at 50% 0%, rgba(90, 120, 180, .12), transparent 52%);
      }
      .dafeiyu-voice-head {
        position: sticky; top: 0; z-index: 2; display: flex; align-items: baseline;
        gap: 8px; padding: 2px 2px 12px; backdrop-filter: blur(10px);
      }
      .dafeiyu-voice-head b { font-size: 14px; }
      .dafeiyu-voice-head span { color: var(--dsw-alias-text-secondary, #7e8ca6); font-size: 11px; }
      .dafeiyu-voice-list { display: flex; flex-direction: column; gap: 12px; max-width: 720px; margin: 0 auto; }
      .dafeiyu-voice-row { display: flex; gap: 9px; align-items: flex-start; }
      .dafeiyu-voice-avatar {
        width: 26px; height: 26px; flex: 0 0 26px; border-radius: 50%;
        display: grid; place-items: center; font-size: 11px;
        color: #ffe2aa; background: rgba(255, 210, 150, .12);
        border: 1px solid rgba(255, 210, 150, .22);
      }
      .dafeiyu-voice-bubble {
        min-width: 190px; max-width: min(72%, 480px); padding: 9px 12px 8px;
        border: 1px solid rgba(125, 160, 220, .22); border-radius: 4px 16px 16px 16px;
        background: linear-gradient(135deg, rgba(30, 45, 75, .92), rgba(12, 20, 38, .96));
        box-shadow: 0 10px 30px rgba(0, 0, 0, .25);
      }
      .dafeiyu-voice-main { display: flex; align-items: center; gap: 9px; }
      .dafeiyu-voice-play {
        width: 30px; height: 30px; flex: 0 0 30px; border-radius: 50%;
        border: 1px solid rgba(140, 200, 255, .35); background: rgba(100, 170, 255, .14);
        color: #cfeaff; cursor: pointer; font-size: 12px; line-height: 28px; text-align: center;
      }
      .dafeiyu-voice-play:disabled { opacity: .55; cursor: wait; }
      .dafeiyu-voice-wave { display: flex; align-items: center; gap: 2px; height: 26px; flex: 1; min-width: 70px; }
      .dafeiyu-voice-wave i {
        width: 2px; border-radius: 2px; background: rgba(150, 205, 255, .55);
        height: var(--h); transform-origin: center;
      }
      .dafeiyu-voice-bubble.is-playing .dafeiyu-voice-wave i { animation: dafeiyu-wave .9s ease-in-out infinite alternate; animation-delay: var(--d); }
      @keyframes dafeiyu-wave { from { transform: scaleY(.55); opacity: .5; } to { transform: scaleY(1.25); opacity: 1; } }
      .dafeiyu-voice-time { color: var(--dsw-alias-text-secondary, #7e8ca6); font-size: 10px; white-space: nowrap; }
      .dafeiyu-voice-meta { display: flex; justify-content: space-between; gap: 8px; margin-top: 7px; }
      .dafeiyu-voice-text-btn {
        border: 0; background: transparent; color: var(--dsw-alias-text-secondary, #8a9bb8);
        font-size: 10px; cursor: pointer; padding: 0;
      }
      .dafeiyu-voice-text-btn:hover { color: var(--dsw-alias-text-primary, #dce8ff); }
      .dafeiyu-voice-transcript {
        margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(125, 160, 220, .16);
        color: var(--dsw-alias-text-secondary, #a9b7cb); font-size: 12px; line-height: 1.65;
        white-space: pre-wrap; max-height: 240px; overflow: auto;
      }
      .dafeiyu-voice-empty { color: var(--dsw-alias-text-secondary, #7e8ca6); font-size: 12px; padding: 24px 4px; }
      .dafeiyu-voice-user {
        align-self: flex-end; max-width: min(72%, 480px); padding: 8px 11px;
        border-radius: 14px 4px 14px 14px; background: rgba(90, 120, 180, .14);
        border: 1px solid rgba(125, 160, 220, .16); color: #b9c9df; font-size: 12px;
        white-space: pre-wrap;
      }
    `;

    function ensureVoiceStyles() {
      if (document.getElementById('dafeiyu-voice-style')) return;
      const style = document.createElement('style');
      style.id = 'dafeiyu-voice-style';
      style.textContent = VOICE_CSS;
      document.head.appendChild(style);
    }

    function speechText(text) {
      return String(text || '')
        .replace(/```[\s\S]*?```/g, ' 代码段 ')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/^[#>*_\-\s]+/gm, '')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 1200);
    }

    function formatClock(ms) {
      if (!ms) return '';
      try {
        return new Date(ms).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      } catch { return ''; }
    }

    const WAVE = [5, 11, 7, 16, 9, 13, 6, 18, 10, 14, 7, 12, 5, 15, 8, 11, 6, 13, 9, 16, 7, 12, 5, 10];

    function VoiceBubble({ text, time, index }) {
      const [state, setState] = useState('idle');
      const [open, setOpen] = useState(false);
      const [duration, setDuration] = useState(0);
      const [progress, setProgress] = useState(0);
      const [detail, setDetail] = useState('');
      const audioRef = useRef(null);

      useEffect(() => () => {
        if (audioRef.current) {
          try { audioRef.current.pause(); } catch { /* ignore */ }
          audioRef.current = null;
        }
      }, []);

      const play = useCallback(async () => {
        if (!text || state === 'loading') return;
        if (state === 'playing' && audioRef.current) {
          audioRef.current.pause();
          setState('paused');
          return;
        }
        if (state === 'paused' && audioRef.current) {
          try { await audioRef.current.play(); setState('playing'); } catch { /* ignore */ }
          return;
        }
        if (audioRef.current) {
          try { audioRef.current.pause(); } catch { /* ignore */ }
          audioRef.current = null;
        }
        setState('loading');
        setDetail('');
        try {
          const res = await fetch(`${API}/speak`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: speechText(text), emotion: 'neutral' }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.message || `HTTP ${res.status}`);
          const audio = new Audio(`${data.url}?t=${Date.now()}`);
          audioRef.current = audio;
          audio.onloadedmetadata = () => setDuration(Number.isFinite(audio.duration) ? audio.duration : 0);
          audio.ontimeupdate = () => setProgress(audio.duration ? audio.currentTime / audio.duration : 0);
          audio.onended = () => { setState('idle'); setProgress(0); };
          audio.onerror = () => { setState('error'); setDetail('音频加载失败'); };
          await audio.play();
          setState('playing');
        } catch (error) {
          setState('error');
          const message = String(error && error.message ? error.message : error);
          setDetail(/Failed to fetch|NetworkError/i.test(message)
            ? '语音桥没启动：运行 start-all.ps1'
            : message.slice(0, 60));
          window.setTimeout(() => setState('idle'), 3000);
        }
      }, [text, state]);

      const seconds = duration > 0 ? Math.max(1, Math.round(duration)) : 0;
      const label = state === 'loading' ? '生成中' : state === 'playing' ? '播放中' : state === 'paused' ? '已暂停' : state === 'error' ? '失败' : '语音';

      return h('div', { className: 'dafeiyu-voice-row' },
        h('div', { className: 'dafeiyu-voice-avatar' }, '鱼'),
        h('div', {
          className: `dafeiyu-voice-bubble${state === 'playing' ? ' is-playing' : ''}`,
          style: { '--bubble-index': index },
        },
        h('div', { className: 'dafeiyu-voice-main' },
          h('button', {
            type: 'button', className: 'dafeiyu-voice-play', disabled: !text || state === 'loading',
            title: state === 'playing' ? '暂停' : '播放语音',
            'aria-label': state === 'playing' ? '暂停' : '播放语音',
            onClick: play,
          }, state === 'loading' ? '…' : state === 'playing' ? '❚❚' : '▶'),
          h('div', { className: 'dafeiyu-voice-wave', 'aria-hidden': 'true' },
            WAVE.map((height, i) => h('i', {
              key: i,
              style: { '--h': `${height}px`, '--d': `${(i % 6) * .08}s`, opacity: progress ? .35 + progress * .65 : 1 },
            }))),
          h('span', { className: 'dafeiyu-voice-time' }, seconds ? `${seconds}"` : label),
        ),
        h('div', { className: 'dafeiyu-voice-meta' },
          h('button', {
            type: 'button', className: 'dafeiyu-voice-text-btn',
            onClick: () => setOpen(!open),
          }, open ? '收起文字' : '生成文字'),
          h('span', { className: 'dafeiyu-voice-time' }, formatClock(time)),
        ),
        detail ? h('div', { className: 'dafeiyu-voice-time', style: { marginTop: 4 } }, detail) : null,
        open ? h('div', { className: 'dafeiyu-voice-transcript' }, text) : null,
        ),
      );
    }

    function VoiceView({ useChat }) {
      ensureVoiceStyles();
      const chat = typeof useChat === 'function' ? useChat : (selector) => selector(EMPTY);
      const snapshot = chat((value) => value);
      const items = useMemo(() => {
        if (!snapshot || !snapshot.nodes) return [];
        const out = [];
        for (const node of snapshot.nodes.values()) {
          if (!node || node.kind !== 'assistant-step' || !node.data) continue;
          const text = assistantText(node.data.blocks);
          if (!text) continue;
          out.push({
            key: node.key || `${node.anchorSeq || 0}-${out.length}`,
            text,
            time: typeof node.data.time === 'number' ? node.data.time : 0,
          });
        }
        out.sort((a, b) => (a.time || 0) - (b.time || 0));
        return out;
      }, [snapshot]);
      const listRef = useRef(null);
      useEffect(() => {
        const el = listRef.current;
        if (el) el.scrollTop = el.scrollHeight;
      }, [items.length]);
      return h('div', { className: 'dafeiyu-voice-view', ref: listRef },
        h('div', { className: 'dafeiyu-voice-head' },
          h('b', null, '语音对话'),
          h('span', null, '点气泡播放 · 文字默认收起'),
        ),
        items.length === 0
          ? h('div', { className: 'dafeiyu-voice-empty' }, '还没有可朗读的回复。先在对话里聊两句，再回来切到「语音」。')
          : h('div', { className: 'dafeiyu-voice-list' },
            items.map((item, index) => h(VoiceBubble, { key: item.key, text: item.text, time: item.time, index })),
          ),
      );
    }

    function parseVoiceSegments(text) {
      const out = [];
      // 单行 Markdown 引用定义：渲染不可见，语音正文藏在 title 里。
      // [dfy-voice-1]: # "tender|我在呢。"
      const re = /^[ \t]*\[dfy-voice-(\d+)\]:[ \t]*#[ \t]*"([a-z_]+)\|([^"]+)"[ \t]*$/gmi;
      let match;
      while ((match = re.exec(String(text || ''))) !== null) {
        const body = String(match[3] || '').trim();
        if (body) out.push({ emotion: match[2] || 'neutral', text: body });
      }
      return out;
    }

    function VoiceTurnBubbles({ turn, useChat }) {
      ensureVoiceStyles();
      const turnNo = turn && typeof turn === 'object' ? turn.turn : turn;
      const chat = typeof useChat === 'function' ? useChat : (selector) => selector(EMPTY);
      const snapshot = chat((value) => value);
      const source = useMemo(() => {
        if (!snapshot || !snapshot.locations || typeof snapshot.locations.getTurn !== 'function') {
          return { text: '', time: 0 };
        }
        const keys = snapshot.locations.getTurn(turnNo);
        let text = '';
        let time = 0;
        for (const key of keys) {
          const node = snapshot.nodes.get(key);
          if (!node || node.kind !== 'assistant-step' || !node.data) continue;
          const candidate = assistantText(node.data.blocks);
          if (candidate) {
            text = candidate;
            time = typeof node.data.time === 'number' ? node.data.time : time;
          }
        }
        return { text, time };
      }, [snapshot, turnNo]);
      const latestTurn = useMemo(() => {
        const order = snapshot && snapshot.timeline && snapshot.timeline.turnOrder;
        return Array.isArray(order) && order.length ? order[order.length - 1] : undefined;
      }, [snapshot]);
      const segments = useMemo(() => {
        const explicit = parseVoiceSegments(source.text);
        if (explicit.length) return explicit;
        // 兜底：最新一条短回复自动生成气泡，避免模型漏写协议。
        if (!latestTurn || turnNo !== latestTurn) return [];
        if (!source.text || source.text.length > 220) return [];
        if (/```|^\s*\|/.test(source.text)) return [];
        return [{ emotion: 'neutral', text: source.text }];
      }, [source.text, source.time, turnNo, latestTurn]);
      if (!segments.length) return null;
      return h('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 8, width: '100%', margin: '4px 0 6px' },
      }, segments.map((segment, index) => h(VoiceBubble, {
        key: index,
        text: segment.text,
        time: source.time,
        index,
      })));
    }

    function AutoToggle() {
      const on = useAutoRead();
      const toggle = () => {
        const next = !on;
        try { localStorage.setItem(AUTO_KEY, next ? '1' : '0'); } catch { /* ignore */ }
        window.dispatchEvent(new Event('dafeiyu:voice-auto'));
      };
      return h('button', {
        type: 'button',
        title: on ? '关闭自动朗读' : '开启自动朗读：新回复自动播报',
        'aria-pressed': on,
        onClick: toggle,
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          height: 26,
          padding: '0 9px',
          border: '1px solid var(--dsw-alias-border-secondary, rgba(127,127,127,.28))',
          borderRadius: 999,
          background: on ? 'var(--dsw-alias-bg-secondary, rgba(127,127,127,.12))' : 'transparent',
          color: 'var(--dsw-alias-text-secondary, #666)',
          cursor: 'pointer',
          fontSize: 12,
          lineHeight: '24px',
          whiteSpace: 'nowrap',
        },
      }, on ? '🔊 自动朗读' : '🔇 自动朗读');
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('conversation.chat.assistant-actions', () => ctx.slots.register({
          name: 'conversation.chat.assistant-actions',
          id: 'voice-read',
          order: 20,
        }, VoiceAction));
        ctx.slots.inject('conversation.chat.turnTail', () => ctx.slots.register({
          name: 'conversation.chat.turnTail',
          id: 'voice-bubbles',
          order: 30,
        }, VoiceTurnBubbles));
        ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
          name: 'conversation.composer.dock',
          id: 'voice-auto',
          order: 10,
        }, AutoToggle));
        ctx.slots.inject('conversation.view', () => ctx.slots.register({
          name: 'conversation.view',
          id: 'voice',
          order: 1,
          label: () => '语音',
        }, VoiceView));
      },
    };
  },
});
