const path = require('node:path');
const fs = require('node:fs');
const pkg = process.argv[2];
const dir = path.dirname(require.resolve(pkg + '/package.json', { paths: [process.env.DSH_INSTALL_DIR] }));
const term = 'assistant-actions';
function walk(d) {
  for (const name of fs.readdirSync(d)) {
    const p = path.join(d, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p);
    else if (st.size < 1024 * 1024 && /\.(ts|tsx)$/.test(name)) {
      const text = fs.readFileSync(p, 'utf8');
      let idx = -1, n = 0;
      while ((idx = text.indexOf(term, idx + 1)) !== -1 && n < 8) {
        n++;
        const line = text.slice(0, idx).split('\n').length;
        console.log('## ' + path.relative(dir, p) + ' L' + line);
        console.log(text.split('\n').slice(line - 6, line + 16).join('\n'));
      }
    }
  }
}
walk(path.join(dir, 'src'));
