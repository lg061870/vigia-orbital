// Captures the website screens for the video (site served locally against a local API).
const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
await p.route('**/config.js',r=>r.fulfill({contentType:'text/javascript',body:'window.VIGIA_API="http://localhost:8000"'}));
const out=__dirname+'/public/site/';
await p.goto('http://localhost:8765/');await p.waitForTimeout(6000);await p.screenshot({path:out+'a.png'});
await p.click('#m-demo');await p.waitForTimeout(5000);await p.screenshot({path:out+'b.png'});
await p.click('#cards .card:nth-child(5)');await p.waitForTimeout(5000);await p.screenshot({path:out+'c.png'});
console.log(await p.textContent('#issued'));await b.close()})();
