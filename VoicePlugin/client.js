window.__ModuleLoader__.load({
  id: 'dsh-voice-read',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const { useCallback, useEffect, useRef, useState } = React;

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
        ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
          name: 'conversation.composer.dock',
          id: 'voice-auto',
          order: 10,
        }, AutoToggle));
      },
    };
  },
});
