/** Always starts an isolated, fabricated demo. Never target live records. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm,mkdir,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=resolve(fileURLToPath(new URL('..',import.meta.url)));
const runtime=await mkdtemp(join(tmpdir(),'workspace-browser-'));
const child=spawn(process.env.PYTHON||'python3',[join(root,'server.py'),'--demo','--data',join(runtime,'data'),'--port','0'],{cwd:root});
let browser,log='';child.stderr.on('data',b=>log+=b);
try{
 const port=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('Startup timed out '+log)),15000);child.stdout.on('data',b=>{const m=String(b).match(/127\.0\.0\.1:(\d+)/);if(m){clearTimeout(timeout);resolve(Number(m[1]))}});child.on('exit',code=>{clearTimeout(timeout);reject(Error('Server exited '+code+' '+log))})});
 browser=await chromium.launch({headless:true,...(process.env.BROWSER_CHANNEL?{channel:process.env.BROWSER_CHANNEL}:{})});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{window.copied=[];Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>window.copied.push(text)}})});
 await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>typeof catalogReady!=='undefined'&&catalogReady);
 const surfaces=['home','decisions','work','tasks','updates','company','design','prompts','skills','files','bookmarks','canvas','contexts','culture','principles','insights'];
 for(const mode of surfaces){await page.evaluate(m=>navigate(m),mode);await page.waitForTimeout(80);assert.ok((await page.locator('#view').innerText()).trim(),mode+' is empty')}
 await page.evaluate(()=>navigate('prompts'));await page.locator('.item-row').first().focus();await page.keyboard.press('1');await page.waitForFunction(()=>window.copied.length===1);await page.waitForFunction(()=>document.querySelector('#toast').textContent.startsWith('Copied'));
 assert.equal(await page.evaluate(()=>mode),'prompts');assert.equal(await page.evaluate(()=>window.copied.length),1);
 assert.equal(await page.evaluate(()=>window.copied[0]),await page.evaluate(()=>items.find(i=>i.id==='prompts:demo-1').body));
 await page.keyboard.press('Alt+1');assert.equal(await page.evaluate(()=>mode),'home');assert.equal(await page.evaluate(()=>window.copied.length),1);
 await page.evaluate(()=>navigate('prompts'));await page.locator('input[placeholder="Search prompts"]').fill('Plan a small');await page.locator('.item-row').focus();await page.keyboard.press('2');await page.waitForFunction(()=>window.copied.length===2);assert.equal(await page.evaluate(()=>window.copied.length),2);
 await page.locator('input[placeholder="Search prompts"]').focus();await page.keyboard.press('1');assert.equal(await page.evaluate(()=>window.copied.length),2);
 await page.evaluate(()=>navigate('tasks'));
 let lost=false;await page.route('**/api/edit',async route=>{if(!lost){lost=true;await route.fetch();await route.abort('failed')}else await route.continue()});
 await page.getByRole('button',{name:'New task',exact:true}).click();await page.locator('#edit-form [name="title"]').fill('A recoverable demo task');await page.locator('#save-edit').click();await page.waitForFunction(()=>!document.querySelector('#editor').open);
 await page.unroute('**/api/edit');assert.equal(await page.evaluate(()=>items.filter(i=>i.title==='A recoverable demo task').length),1);
 await page.reload();await page.waitForFunction(()=>catalogReady);assert.equal(await page.evaluate(()=>items.filter(i=>i.title==='A recoverable demo task').length),1);
 await page.evaluate(()=>navigate('prompts','prompts:demo-1'));await page.waitForFunction(()=>promptCanvasSessions.get('prompts:demo-1')?.ready);
 await page.getByRole('textbox',{name:'Prompt',exact:true}).fill('A revised fabricated review prompt.');await page.keyboard.press('Meta+Enter');await page.waitForFunction(()=>promptCanvasSessions.get('prompts:demo-1')?.base.body==='A revised fabricated review prompt.');
 await page.reload();await page.waitForFunction(()=>catalogReady);assert.equal(await page.getByRole('textbox',{name:'Prompt',exact:true}).inputValue(),'A revised fabricated review prompt.');
 await page.evaluate(()=>navigate('prompts'));await page.getByRole('button',{name:'New prompt',exact:true}).click();await page.locator('#edit-form [name="title"]').fill('A new demo prompt');await page.locator('#edit-form [name="body"]').fill('Review the fabricated demo evidence.');await page.locator('#save-edit').click();await page.waitForFunction(()=>!document.querySelector('#editor').open);assert.equal(await page.evaluate(()=>items.filter(i=>i.title==='A new demo prompt').length),1);
 await page.evaluate(()=>navigate('insights'));await page.getByRole('button',{name:'Use a skill',exact:true}).click();
 await page.locator('#edit-form [name=task]').fill('Review the fabricated Apollo prototype');await page.locator('#edit-form [name=client]').fill('Demo browser');await page.locator('#save-edit').click();
 await page.getByRole('button',{name:'Read instructions',exact:true}).click();await page.getByRole('button',{name:'Report applied',exact:true}).click();
 await page.getByRole('button',{name:'Return result',exact:true}).click();await page.locator('#edit-form [name=artifact]').fill('artifact-demo-review');await page.locator('#save-edit').click();
 await page.getByRole('button',{name:'Accept',exact:true}).click();await page.getByText('Accepted',{exact:true}).waitFor();
 await page.reload();await page.waitForFunction(()=>catalogReady);await page.getByText('Accepted',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Skills',exact:true}).last().click();await page.locator('.skill-insights-table').waitFor();assert.equal(await page.locator('.skill-insights-table tbody td').nth(1).innerText(),'1');
 const timings=await page.evaluate(async()=>{const times=[];for(let n=0;n<30;n++){const t=performance.now();await navigate(n%2?'home':'prompts');times.push(performance.now()-t)}return times.sort((a,b)=>a-b)});assert.ok(timings[28]<120,'Warm navigation is unexpectedly slow');
 await context.setOffline(true);await page.evaluate(async()=>{state.notes.push({id:'offline-draft',title:'Recovered draft',body:'Fabricated unsaved content'});try{await persist()}catch{}});assert.ok(await page.evaluate(()=>localStorage.getItem('workspace-unsaved-draft').includes('offline-draft')));await context.setOffline(false);
 await page.reload();await page.waitForFunction(()=>catalogReady);assert.ok(await page.evaluate(()=>failedDraft?.notes.some(n=>n.id==='offline-draft')));
 const screenshots=process.env.WORKSPACE_SCREENSHOTS;if(screenshots)await mkdir(screenshots,{recursive:true});
 for(const [width,theme]of [[1440,'light'],[390,'light'],[1440,'dark']]){await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme:theme});for(const surface of ['home','prompts','files','company','skills','insights']){await page.evaluate(m=>navigate(m),surface);await page.waitForTimeout(100);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),surface+' horizontal overflow');if(screenshots)await page.screenshot({path:join(screenshots,`${surface}-${width}-${theme}.png`)})}}
 assert.deepEqual(errors,[]);const report={surfaces:surfaces.length,responsiveViews:18,keyboard:'pass',copy:'exact',lostResponse:'one task',offlineDraft:'recovered',promptEditing:'persisted',promptCreation:'pass',skillRun:'prepared through reviewed, persisted',navigationP95ms:timings[28],errors};console.log(JSON.stringify(report,null,2));if(screenshots)await writeFile(join(screenshots,'browser-results.json'),JSON.stringify(report,null,2));
}finally{await browser?.close();child.kill('SIGTERM');if(child.exitCode===null)await new Promise(r=>child.once('exit',r));await rm(runtime,{recursive:true,force:true})}
