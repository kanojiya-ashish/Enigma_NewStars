const fs = require('fs');
const path = require('path');
const ts = require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js');
const root = path.join(__dirname, 'frontend', 'src');
function walk(dir) { const out=[]; for(const name of fs.readdirSync(dir)){ const p=path.join(dir,name); const st=fs.statSync(p); if(st.isDirectory()) out.push(...walk(p)); else if(/\.(ts|tsx)$/.test(name) && !name.endsWith('.d.ts')) out.push(p);} return out; }
let failed=0; const files=walk(root);
for(const file of files){ const source=fs.readFileSync(file,'utf8'); const result=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.ESNext},reportDiagnostics:true,fileName:file}); const diagnostics=(result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error); if(diagnostics.length){ failed++; console.error('\n'+file); for(const d of diagnostics) console.error(ts.flattenDiagnosticMessageText(d.messageText,'\n')); }}
console.log(`Frontend syntax/transpile: ${files.length-failed}/${files.length} files PASS`);
process.exit(failed?1:0);
