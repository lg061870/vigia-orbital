const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const A=path.resolve('artifact-files/8710134d-b755-4920-8dab-b4cbb6015c6e');
const slides={1:'pronostico-hoy',2:'semana-demo',3:'detalle-dia',6:'armonizacion',7:'formula',8:'a3-coeficientes',9:'valida',10:'impacto',12:'a1-notebook'};
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:2});
await p.route('**/_blob/*',r=>{const id=r.request().url().split('/').pop();const f=fs.readdirSync(A).find(x=>x.startsWith(id));if(!f){console.log('MISSING',id);return r.abort();}r.fulfill({path:path.join(A,f)});});
const css=fs.readFileSync(path.join(A,'project/deck.css'),'utf8');
for(const [n,id] of Object.entries(slides)){const html=fs.readFileSync(path.join(A,'project/slides',id+'.html'),'utf8');
await p.goto('http://localhost:8766/blank.html');
await p.setContent(`<!doctype html><html><head><meta charset="utf-8"><base href="http://localhost:8766/"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@500;600;700&family=Source+Sans+3:wght@400;600&display=swap"><style>*{box-sizing:border-box}body{margin:0}p,h1,h2,h3,ul,table{margin:0}section{position:relative;width:1920px;height:1080px;overflow:hidden;display:block}aside{display:none}th{text-align:left}.card.fragment{opacity:1!important;transform:none!important}${css}</style></head><body>${html}</body></html>`,{waitUntil:'networkidle'});
await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(400);
await p.screenshot({path:`video/public/slides/s${n}.png`,clip:{x:0,y:0,width:1920,height:1080}});console.log('ok',n,id);}
await b.close()})();
