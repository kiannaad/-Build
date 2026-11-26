const path = require('node:path');
const fs = require('node:fs');
const pkg = process.argv[2];
const dir = path.dirname(require.resolve(pkg + '/package.json', { paths: [process.env.DSH_INSTALL_DIR] }));
console.log(dir);
for (const f of fs.readdirSync(path.join(dir, 'src')).slice(0, 120)) console.log('  ' + f);
