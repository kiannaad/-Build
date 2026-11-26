const path = require('node:path');
const fs = require('node:fs');
const nm = path.resolve(process.env.DSH_INSTALL_DIR, '../..', '@deepseek-ai');
console.log('NM=' + nm);
for (const name of fs.readdirSync(nm)) {
  if (/client|ui|chat|conversation|session/.test(name)) console.log(name);
}
