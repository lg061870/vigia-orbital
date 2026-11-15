const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1.5});
await p.route('**/config.js',r=>r.fulfill({contentType:'text/javascript',body:'window.VIGIA_API="http://localhost:8000"'}));
await p.route('**/*.tile.openstreetmap.org/**',r=>r.abort());
const out='/tmp/claude-0/-home-user-vigia-orbital/ecc28c1e-ee26-59f5-9a5d-da45e8713a7c/scratchpad/video/public/site/';
await p.goto('http://localhost:8765/');await p.waitForTimeout(2500);await p.addStyleTag({content:'.leaflet-interactive{fill-opacity:.8}'});await p.screenshot({path:out+'a.png'});
await p.click('#m-demo');await p.waitForTimeout(600);await p.screenshot({path:out+'b.png'});
// click Bagaces polygon via its tooltip-less layer: use leaflet internals
await p.evaluate(()=>{S.canton='CR504';render();});await p.waitForTimeout(400);await p.screenshot({path:out+'c.png'});
console.log(await p.textContent('#issued'));await b.close()})();
