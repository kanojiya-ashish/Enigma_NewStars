const fs = require('fs');
const path = require('path');
const root = path.join(__dirname, 'frontend', 'src');
const files = [];
function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const stat = fs.statSync(full);
    if (stat.isDirectory()) walk(full);
    else if (/\.(ts|tsx)$/.test(name) && !name.endsWith('.d.ts')) files.push(full);
  }
}
walk(root);
const importRe = /(?:import|export)\s+(?:[^'";]*?\sfrom\s+)?['"]([^'"]+)['"]/g;
const candidates = ['', '.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.tsx'];
const resolveLocal = (from, spec) => {
  const base = path.resolve(path.dirname(from), spec);
  for (const suffix of candidates) {
    const target = base + suffix;
    if (fs.existsSync(target) && fs.statSync(target).isFile()) return target;
  }
  return null;
};
let failures = 0;
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  let match;
  while ((match = importRe.exec(text))) {
    const spec = match[1];
    if (!spec.startsWith('.')) continue;
    if (!resolveLocal(file, spec)) {
      failures++;
      console.error(`Missing local import: ${path.relative(root, file)} -> ${spec}`);
    }
  }
}
const app = fs.readFileSync(path.join(root, 'App.tsx'), 'utf8');
const pageMatches = [...app.matchAll(/case '([^']+)':/g)].map(m => m[1]);
if (!pageMatches.includes('route')) {
  failures++;
  console.error('App.tsx is missing route page case.');
}

const login = fs.readFileSync(path.join(root, 'pages', 'LoginPage.tsx'), 'utf8');
for (const role of ['ORGANIZATION','RECEIVER','RECYCLER','LOGISTICS','DRIVER']) {
  if (!login.includes(`role: '${role}'`)) { failures++; console.error(`LoginPage is missing visible demo role: ${role}`); }
}
if (!login.includes('Platform Admin') || !login.includes('showInternal')) { failures++; console.error('LoginPage is missing protected internal admin access.'); }
const routePage = fs.readFileSync(path.join(root, 'pages', 'RoutePage.tsx'), 'utf8');
if (routePage.includes('routeRefresh')) { failures++; console.error('RoutePage contains stale/undefined routeRefresh reference.'); }
const api = fs.readFileSync(path.join(root, 'api.ts'), 'utf8');
if (api.includes('localStorage')) { failures++; console.error('api.ts must use per-tab sessionStorage, not localStorage.'); }
if (!api.includes('access_token')) { failures++; console.error('api.ts is missing access_token handling.'); }

console.log(`Frontend structure: ${failures === 0 ? 'PASS' : 'FAIL'} (${files.length} source files scanned)`);
process.exit(failures ? 1 : 0);
