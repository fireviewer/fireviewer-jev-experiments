import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const root=new URL('../../.local/browser-captures/',import.meta.url);await mkdir(root,{recursive:true});
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1080}}),errors=[],posted=[];
 page.setDefaultTimeout(20000);page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().endsWith('/api/run'))posted.push(r.postDataJSON());});
 await page.goto('http://127.0.0.1:8765/');
 await page.waitForFunction(()=>document.querySelectorAll('.component-grid button').length===12);
 await page.getByRole('button',{name:/LOC-02 Contradictions textuelles/}).click();
 assert.equal(await page.getByLabel('Brique évaluée').inputValue(),'LOC-02');
 await page.getByRole('button',{name:'Charger un exemple synthétique'}).click();
 await page.getByRole('button',{name:'Préparer l’essai',exact:true}).click();
 await page.waitForFunction(()=>document.body.textContent.includes('Préparation hors ligne terminée'));
 assert.equal(posted.length,1);assert.equal(posted[0].component_id,'LOC-02');assert.equal(posted[0].mode,'offline_plan');
 const state=await (await page.request.get('http://127.0.0.1:8765/api/state')).json();
 assert.equal(state.result.report.component_id,'LOC-02');assert.equal(state.result.report.successful_requests,0);
 assert.equal(state.result.report.full_pipeline_executed,false);assert.equal(state.result.records[0].status,'planned');
 const invalid=await page.request.post('http://127.0.0.1:8765/api/run',{data:{mode:'offline_plan',cases:posted[0].cases}});assert.equal(invalid.status(),400);
 await page.screenshot({path:new URL('jev-components-desktop.png',root).pathname,fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:new URL('jev-components-mobile.png',root).pathname,fullPage:true});

 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);
 const receipt={at:new Date().toISOString(),status:'PASS',scope:'local published Jev contracts and browser UI',model_calls:0,run_id:state.run_id,checks:['12 components selectable','LOC-02 only in submitted payload','offline plan makes no model call','missing component rejected with HTTP 400','full pipeline not claimed','desktop/mobile no overflow','no page errors'],limitations:['synthetic UI fixture only','no Jev inference or full pipeline qualification']};
 await writeFile(new URL('jev-components-verification.json',root),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
}finally{await browser.close();}
