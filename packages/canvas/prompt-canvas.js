/* Prompt canvas: direct exact-text editing with guarded autosave and recoverable drafts. */
const promptCanvasSessions=new Map();
function promptCanvasSession(i){
 let s=promptCanvasSessions.get(i.id);if(s)return s;
 let draft=null;try{draft=JSON.parse(sessionStorage.getItem('workspace-prompt-draft:'+i.id)||'null')}catch{}
 if(draft?.id!==i.id)draft=null;
 s={id:i.id,item:i,base:draft?.base||{body:i.body,revision:i.revision},body:draft?.body??i.body,
  pending:draft?.pending||null,busy:null,timer:null,ready:false,paused:!!draft,error:'',conflict:false,
  recovered:!!draft,changed:()=>{}};
 promptCanvasSessions.set(i.id,s);return s;
}
function promptCanvasDirty(s){return !!s.pending||s.body!==s.base.body}
function promptCanvasRemember(s){
 const ok=promptStorage('workspace-prompt-draft:'+s.id,promptCanvasDirty(s)?{id:s.id,body:s.body,base:s.base,pending:s.pending}:null);
 if(!ok){s.storageError='Draft recovery unavailable. Download your draft before leaving.'}
}
function promptCanvasUpdate(s){promptCanvasRemember(s);s.changed()}
function promptCanvasQueue(s,delay=900){
 clearTimeout(s.timer);if(!s.ready||s.paused||s.composing)return;
 s.timer=setTimeout(()=>promptCanvasSave(s),delay);
}
async function promptCanvasSave(s,explicit=false){
 clearTimeout(s.timer);
 if(s.busy){await s.busy;if(explicit&&promptCanvasDirty(s)&&!s.paused)return promptCanvasSave(s,true);return !promptCanvasDirty(s)}
 if(!s.ready||s.conflict||(!explicit&&s.paused))return false;
 if(!s.pending&&s.body===s.base.body){s.error='';s.paused=false;promptCanvasUpdate(s);return true}
 if(!s.body.trim()&&!s.pending){s.error='The prompt cannot be empty. Your draft is kept.';s.paused=true;promptCanvasUpdate(s);return false}
 if(!s.pending)s.pending={id:s.id,revision:s.base.revision,body:s.body,requestId:uid()};
 s.error='';s.paused=false;const request=s.pending;
 s.busy=(async()=>{
  try{
   const result=await api('/api/edit',request),saved=result.prompt;
   if(!saved)throw Error('Save receipt missing. Retry checks the same save.');
   Object.assign(s.item,{body:saved.body,revision:saved.revision,status:saved.status,approval:saved.approval});
   const current=find(s.id);if(current)Object.assign(current,s.item);
   s.base={body:saved.body,revision:saved.revision};s.pending=null;s.error='';s.recovered=false;
   return true;
  }catch(e){
   s.paused=true;
   if(e.httpStatus){s.pending=null;s.conflict=e.httpStatus===409;s.error=s.conflict?'A newer version was saved elsewhere. Your draft is kept. Compare before saving.':e.message+' Your draft is kept.'}
   else s.error='Save not confirmed. Your draft is kept. Retry checks the same save.';
   return false;
  }finally{s.busy=null;promptCanvasUpdate(s);if(!s.paused&&s.body!==s.base.body)promptCanvasQueue(s,250)}
 })();
 promptCanvasUpdate(s);return s.busy;
}
async function promptCanvasRefresh(s){
 try{
  const data=await api('/api/prompts/'+encodeURIComponent(s.id.split(':')[1])),p=data.prompt;
  if(!promptCanvasDirty(s)){s.base={body:p.body,revision:p.revision};s.body=p.body;Object.assign(s.item,p,{id:s.id});s.paused=false;s.recovered=false;s.error=''}
  else if(p.revision!==s.base.revision&&!s.pending){s.conflict=true;s.paused=true;s.error='A newer version was saved elsewhere. Your draft is kept. Compare before saving.'}
  else if(s.recovered){s.error='Recovered your unsaved draft. Review it, then resume saving.'}
  s.ready=true;
 }catch{s.ready=false;s.paused=true;s.error='Could not load the saved prompt. Your draft is kept; reconnect to resume.'}
 promptCanvasUpdate(s);
}
async function promptCanvasCompare(s,host){
 try{
  const latest=(await api('/api/prompts/'+encodeURIComponent(s.id.split(':')[1]))).prompt;
  host.replaceChildren();host.hidden=false;
  const box=el('details','prompt-conflict-compare');box.open=true;
  box.append(el('summary','','Saved version · Revision '+latest.revision),el('pre','',latest.body));
  const actions=el('div','prompt-inline-recovery');
  actions.append(button('Use saved version',()=>{
   if(promptCanvasDirty(s)&&!confirm('Discard this local draft and use the saved version?'))return;
   s.pending=null;s.base={body:latest.body,revision:latest.revision};s.body=latest.body;s.conflict=false;s.paused=false;s.error='';s.recovered=false;Object.assign(s.item,latest,{id:s.id});host.hidden=true;promptCanvasUpdate(s);
  }),button('Save my draft over this version',async()=>{
   if(!confirm('Save your draft over revision '+latest.revision+'? Both versions remain in history.'))return;
   s.base={body:latest.body,revision:latest.revision};s.pending=null;s.conflict=false;s.paused=false;s.ready=true;await promptCanvasSave(s,true);if(!s.error)host.hidden=true;
  }));
  box.append(actions);host.append(box);
 }catch(e){s.error='Could not load the newer version. '+e.message;promptCanvasUpdate(s)}
}
function renderPromptCanvas(){
 const i=find(opened);
 if(!i){view.replaceChildren(el('p','empty','Loading prompt…'));return}
 const s=promptCanvasSession(i),wrap=el('article','reader prompt-canvas'),bar=el('div','reader-actions prompt-canvas-actions');
 bar.append(button('← Back',goBack));const saved=el('span','prompt-save-status');saved.setAttribute('role','status');saved.setAttribute('aria-live','polite');
 bar.append(saved,button('Copy',()=>copyPrompt(i)),button('History',async()=>{
  historyBox.replaceChildren();historyBox.hidden=false;
  try{const rows=await api('/api/history/'+encodeURIComponent(i.id));historyBox.append(el('h2','','Version history'));
   for(const r of rows){const entry=el('details','history-entry');entry.append(el('summary','',r.created||r.at||'Earlier revision'));let body=r.body;if(!body&&r.before_data)body=JSON.parse(r.before_data).body;entry.append(el('pre','',body||''));historyBox.append(entry)}
   if(!rows.length)historyBox.append(el('p','','No earlier revisions.'));
  }catch(e){historyBox.append(el('p','',e.message))}
 }),button('Download',()=>download(i.title+'.md',s.body,'text/markdown')));
 const title=el('h1','',i.title),meta=el('p','prompt-canvas-meta');
 const area=el('textarea','prompt-inline-body');area.setAttribute('aria-label','Prompt');area.spellcheck=true;area.value=s.body;area.rows=12;area.placeholder='Write the prompt…';
 const error=el('div','prompt-inline-error');error.setAttribute('role','status');const message=el('p');const recovery=el('div','prompt-inline-recovery');
 const retry=button('Resume saving',async()=>{if(!s.ready)await promptCanvasRefresh(s);if(!s.conflict){s.paused=false;await promptCanvasSave(s,true)}});
 recovery.append(retry,button('Compare saved version',()=>promptCanvasCompare(s,compare)),button('Download draft',()=>download(i.title+'-draft.md',s.body,'text/markdown')));
 error.append(message,recovery);const compare=el('section','prompt-inline-comparison');compare.hidden=true;
 const historyBox=el('section','prompt-inline-history');historyBox.hidden=true;
 wrap.append(bar,title,meta,error,compare,area,historyBox);view.replaceChildren(wrap);
 const resize=()=>{if(!area.isConnected)return;area.style.height='auto';area.style.height=Math.max(320,area.scrollHeight+4)+'px'};
 s.changed=()=>{
  if(!wrap.isConnected)return;
  if(area.value!==s.body){area.value=s.body;resize()}
  saved.textContent=s.busy?'Saving…':s.error?'Not saved':!s.ready?'Loading…':promptCanvasDirty(s)?'Unsaved changes':'Saved';
  saved.dataset.state=s.busy?'saving':s.error?'error':promptCanvasDirty(s)?'dirty':'saved';
  meta.textContent=promptWordCount(s.body)+' words · Revision '+s.base.revision+' · '+(s.item.status==='approved'?'Wording approved':'Wording not approved');
  error.hidden=!s.error&&!s.storageError;message.textContent=[s.error,s.storageError].filter(Boolean).join(' ');
  retry.hidden=s.conflict;retry.disabled=!!s.busy;
 };
 area.addEventListener('input',()=>{s.body=area.value;promptCanvasUpdate(s);resize();if(!s.paused)promptCanvasQueue(s)});
 area.addEventListener('compositionstart',()=>{s.composing=true;clearTimeout(s.timer)});
 area.addEventListener('compositionend',()=>{s.composing=false;s.body=area.value;promptCanvasUpdate(s);promptCanvasQueue(s)});
 area.addEventListener('blur',()=>{if(!s.composing)promptCanvasQueue(s,100)});
 area.addEventListener('keydown',e=>{if(e.metaKey&&e.altKey&&e.key.startsWith('Arrow'))return;
  if(e.metaKey&&e.altKey&&e.key.startsWith('Arrow'))return;
  if((e.metaKey||e.ctrlKey)&&!e.altKey&&e.key==='Enter'){e.preventDefault();promptCanvasSave(s,true)}
  if(e.key==='Escape'){e.preventDefault();e.stopPropagation();title.tabIndex=-1;title.focus();promptCanvasQueue(s,100)}
 });
 s.changed();requestAnimationFrame(resize);promptCanvasRefresh(s);
}
editPrompt=function(i){if(mode!=='prompts'||opened!==i.id)navigate('prompts',i.id);document.querySelector('.prompt-inline-body')?.focus()};
copyPrompt=async function(i){
 const s=promptCanvasSessions.get(i.id);
 if(s&&promptCanvasDirty(s)){
  const ok=await promptCanvasSave(s,true);
  if(!ok||promptCanvasDirty(s))return toast('Resolve the unsaved draft before copying. Download draft keeps your current text.');
 }
 try{const p=(await api('/api/prompts/'+encodeURIComponent(i.id.split(':')[1]))).prompt;Object.assign(i,{body:p.body,revision:p.revision,status:p.status,approval:p.approval});if(await copy(p.body)){toast('Copied “'+i.title+'”')}}catch(e){toast('Could not check the saved prompt. '+e.message)}
};
window.addEventListener('beforeunload',e=>{if([...promptCanvasSessions.values()].some(promptCanvasDirty)){e.preventDefault();e.returnValue=''}});
