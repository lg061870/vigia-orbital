// Renders the proof-first deck slides to PNG (images mapped from the copied assets to local files).
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const A=path.resolve('../artifact-files/8710134d-b755-4920-8dab-b4cbb6015c6e');const R=path.resolve('../deck2/project');
const MAP={'1e98fdfdcde7ba073005e3567b08c27f':'77fa9d99870b21674c7b8bc719e67f3c','38f12c179401a526fa440cfb8145ecd1':'0a7a8c403ec6bee39015459109945ffb','cf917e9053bd713ecad037e3ff6e8c2a':'076c42312be2072ede1558977e6f32c8','3daed2532b34e4b33d95d214195881ba':'56f162fd5affaacb4e7d9e876cb8fb04','4a2d04cbb2d7d75c16b6de4aa6b24014':'3adc56e356074cbebdc098541de844f8','61a4c651feb8ef35f6c6447b73345083':'60b04486b2058daf333305ae20445cd7','f4540399766b763176533d4b81e556c1':'96da25929b49a49b230087525ec1f653','d177f9026be8ac72f71572c89b5e8f3b':'e637c0df94c742021e378eae34574b07','1634db7a5459800d34553e644e5e56da':'35dafac49a2f27eb514227b02f50d91b','31017da3bb059d38ec6cd69df05d4f0a':'102123eff5ca69c09b93e69411b3b567','55a6eb58d7ecb01fd03b19bf2d50b842':'1fd49d2596efd39e62b09fe2cf38b23c','9c91eea9fe9168af7d79d5fce771b3aa':'6cc5c80248d952ae20453fc0b6e445d7'};
const order=['semana-demo','detalle-dia','valida','armonizacion','formula','a1-notebook','compruebalo','impacto','limites','pronostico-hoy'];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:2});
await p.route('**/_blob/*',r=>{const id=MAP[r.request().url().split('/').pop()];const f=id&&fs.readdirSync(A).find(x=>x.startsWith(id));if(!f){console.log('MISSING',r.request().url());return r.abort();}r.fulfill({path:path.join(A,f)});});
const css=fs.readFileSync(path.join(R,'deck.css'),'utf8');
for(let i=0;i<order.length;i++){const html=fs.readFileSync(path.join(R,'slides',order[i]+'.html'),'utf8');
await p.goto('http://localhost:8766/blank.html');
await p.setContent(`<!doctype html><html><head><meta charset="utf-8"><base href="http://localhost:8766/"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@500;600;700&family=Source+Sans+3:wght@400;600&display=swap"><style>*{box-sizing:border-box}body{margin:0}p,h1,h2,h3,ul,table{margin:0}section{position:relative;width:1920px;height:1080px;overflow:hidden;display:block}aside{display:none}th{text-align:left}.card.fragment{opacity:1!important;transform:none!important}${css}</style></head><body>${html}</body></html>`,{waitUntil:'networkidle'});
await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(400);
await p.screenshot({path:`public/slides3/p${i+1}.png`,clip:{x:0,y:0,width:1920,height:1080}});console.log('ok',i+1,order[i]);}
await b.close()})();
