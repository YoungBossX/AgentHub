const {createRequire}=require('node:module');
const fs=require('node:fs');
const path=require('node:path');
const root='X:/Git_Clone/AgentHub';
const web=createRequire(root+'/apps/web/package.json');
let resolve=createRequire(web.resolve('eslint-config-next'));
for(const name of ['@next/eslint-plugin-next','fast-glob','micromatch'])resolve=createRequire(resolve.resolve(name));
const entry=resolve.resolve('braces');
const braces=resolve('braces');
const patterns=['{'.repeat(4500)+'a'+'}'.repeat(4500),'('.repeat(4500)+'a'+')'.repeat(4500)];
const results=[];
for(const method of ['compile','stringify','expand'])for(const [index,input] of patterns.entries()){
 const start=performance.now();
 try{braces[method](input);results.push({method,index,result:'returned',ms:performance.now()-start});}
 catch(error){results.push({method,index,result:'error',name:error.name,message:error.message,ms:performance.now()-start});}
}
const cases=['{a,b}','src/**/*.{ts,tsx}','a/{b,{c,d}}/e','{1..5}','file\\{name\\}','{foo,bar}/(x)','{broken','"{quoted}"','a/{01..03}', 'a,b','[{}]'];
const ordinary=cases.map(input=>({input,compile:braces.compile(input),expand:braces.expand(input),stringify:braces.stringify(input)}));
const report={version:require(path.join(path.dirname(entry),'package.json')).version,entry,results,ordinary};
fs.writeFileSync(path.join(__dirname,process.argv[2]||'braces-before.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({results,normalCases:ordinary.length}));
