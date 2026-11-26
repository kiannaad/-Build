const path = require('node:path');
const fs = require('node:fs');
const pkg = process.argv[2];
const dir = path.dirname(require.resolve(pkg + '/package.json', { paths: [process.env.DSH_INSTALL_DIR] }));
const terms = ['chat.node', 'conversation.chat', 'assistant', 'audio', 'uiConversation.on', 'assistant/message'];
for (const rel of ['src/client/contract/slots.ts', 'src/client/apply.ts', 'src/client/index.ts']) {
  const p = path.join(dir, rel);
  if (!fs.existsSync(p)) continue;
  const text = fs.readFileSync(p, 'utf8');
  console.log('## ' + rel);
  for (const term of terms) {
    let idx = -1, n = 0;
    while ((idx = text.indexOf(term, idx + 1)) !== -1 && n < 6) {
      n++;
      const line = text.slice(0, idx).split('\n').length;
      console.log(term + ' L' + line + ': ' + text.slice(Math.max(0, idx - 120), idx + 180).replace(/\s+/g, ' '));
    }
  }
}
