const path = require('node:path');
const fs = require('node:fs');
const pkg = process.argv[2];
const dir = path.dirname(require.resolve(pkg + '/package.json', { paths: [process.env.DSH_INSTALL_DIR] }));
console.log('DIR=' + dir);
for (const name of fs.readdirSync(dir)) {
  const p = path.join(dir, name);
  try {
    const st = fs.lstatSync(p);
    console.log(name, 'dir=' + st.isDirectory(), 'file=' + st.isFile(), 'size=' + st.size);
  } catch (e) { console.log(name, 'STATERR', e.message); }
}
for (const name of ['package.json', 'client', 'index.ts']) {
  const p = path.join(dir, name);
  try {
    const st = fs.statSync(p);
    console.log('---', name, 'size', st.size);
    if (st.isFile()) console.log(fs.readFileSync(p, 'utf8').slice(0, 600));
  } catch (e) { console.log('---', name, 'ERR', e.message); }
}
