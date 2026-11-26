const path = require('node:path');
const fs = require('node:fs');
const pkg = process.argv[2];
const dir = path.dirname(require.resolve(pkg + '/package.json', { paths: [process.env.DSH_INSTALL_DIR] }));
function walk(d, depth) {
  if (depth > 2) return;
  for (const name of fs.readdirSync(d)) {
    const p = path.join(d, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) { console.log('DIR ' + path.relative(dir, p)); walk(p, depth + 1); }
    else console.log('FILE ' + path.relative(dir, p) + ' ' + st.size);
  }
}
walk(path.join(dir, 'client'), 0);
