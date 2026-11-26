const path = require('node:path');
const fs = require('node:fs');
const pkg = process.argv[2];
const dir = path.dirname(require.resolve(pkg + '/package.json', { paths: [process.env.DSH_INSTALL_DIR] }));
const terms = ['conversation.chat.node', 'conversation.composer.dock', 'assistant/message', 'uiConversation', 'events.register', 'sessionProjections', 'shell.overlay'];
function walk(d, depth) {
  if (depth > 3) return;
  for (const name of fs.readdirSync(d)) {
    const p = path.join(d, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p, depth + 1);
    else if (st.size < 1024 * 1024 && /\.(ts|tsx|js|mjs)$/.test(name)) {
      const text = fs.readFileSync(p, 'utf8');
      const hits = [];
      for (const term of terms) {
        let idx = text.indexOf(term);
        while (idx !== -1 && hits.length < 30) {
          const line = text.slice(0, idx).split('\n').length;
          const start = Math.max(0, idx - 90);
          hits.push(term + ' L' + line + ': ' + text.slice(start, idx + term.length + 120).replace(/\s+/g, ' '));
          idx = text.indexOf(term, idx + 1);
        }
      }
      if (hits.length) {
        console.log('### ' + path.relative(dir, p));
        for (const h of hits.slice(0, 8)) console.log(h);
      }
    }
  }
}
walk(path.join(dir, 'src'), 0);
