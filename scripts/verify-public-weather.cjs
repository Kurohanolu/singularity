'use strict';
// Run the reviewed weather browser assertions against the real Pages frontend.
// Only the server setup and navigation path change; numerical/UI assertions do not.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),Module=require('node:module');
const filename=path.resolve('tests/v110-weather-browser.cjs');
let source=fs.readFileSync(filename,'utf8');
function replaceOnce(before,after){assert.equal(source.split(before).length,2,'Exact reviewed browser adapter anchor: '+before);source=source.replace(before,after);}
replaceOnce('const lab=await startLab()',"const lab={origin:'https://kurohanolu.github.io',close:async()=>{}}");
replaceOnce("page.goto(lab.origin+'/candidate/')","page.goto(lab.origin+'/singularity/')");
// Existing feedback mocks remain isolated. No report is submitted or stored.
const mod=new Module(filename,module);mod.filename=filename;mod.paths=Module._nodeModulePaths(path.dirname(filename));mod._compile(source,filename);
