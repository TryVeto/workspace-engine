/* Prompt-specific editing: exact text, durable tab draft, revision-checked save. */
let promptDraftKey=null, promptPending=null;
function promptWordCount(s){return (s.trim().match(/\S+/g)||[]).length}
function promptMeta(i){
 const n=el('p','prompt-meta',promptWordCount(i.body)+' words · Revision '+i.revision+' · '+(i.status==='approved'?'Wording approved':'Wording not approved'));
 n.append(el('span','',' · Performance not evaluated'));
 return n;
}
async function copyPrompt(i){
 try{
  const data=await api('/api/prompts/'+encodeURIComponent(i.id.split(':')[1]));
  const p=data.prompt;
  Object.assign(i,{body:p.body,revision:p.revision,status:p.status,approval:p.approval});
  if(opened===i.id&&!$('#editor').open){renderReader();focusContent()}
  if(await copy(p.body))toast('Copied “'+i.title+'”');
 }catch(e){toast('Could not check the saved prompt. '+e.message)}
}
function promptStorage(key,value){
 try{if(value===null)sessionStorage.removeItem(key);else sessionStorage.setItem(key,JSON.stringify(value));return true}
 catch{return false}
}
function editPrompt(i){
 const key='workspace-prompt-draft:'+i.id;let draft=null;
 try{draft=JSON.parse(sessionStorage.getItem(key)||'null')}catch{}
 if(draft&&draft.id!==i.id)draft=null;
 const base=draft?.base||{body:i.body,revision:i.revision};
 let pending=draft?.pending||null;
 editDialog('Edit '+i.title,form=>{
  form.append(el('p','prompt-editor-help','⌘ Enter saves · Escape cancels · Changes keep earlier versions'));
  const area=field(form,'Prompt','body',draft?.body??i.body,'textarea');area.spellcheck=true;
  const meter=el('p','prompt-meter');meter.id='prompt-meter';meter.setAttribute('aria-live','polite');form.append(meter);
  const comparison=el('details','prompt-comparison');comparison.append(el('summary','','Compare with saved version'),el('pre','',i.body));form.append(comparison);
  const actions=el('div','prompt-draft-actions');
  actions.append(button('Download draft',()=>download(i.title+'-draft.md',area.value,'text/markdown')));
  if(draft)actions.append(button('Use saved version',()=>{
   if(!confirm('Discard the recovered draft and use the saved version?'))return;
   area.value=i.body;base.body=i.body;base.revision=i.revision;pending=null;promptPending=null;changed();
  }));
  form.append(actions);
  function changed(){
   const count=promptWordCount(area.value),delta=count-promptWordCount(base.body);
   meter.textContent=count+' words · '+(delta>0?'+':'')+delta+' from saved · '+area.value.length+' characters';
   dirty=area.value!==base.body;promptPending=pending;
   const ok=promptStorage(key,{id:i.id,body:area.value,base,pending});
   if(!ok)$('#edit-error').textContent='Draft recovery is unavailable. Download the draft before leaving.';
  }
  area.addEventListener('input',()=>{changed()});
  queueMicrotask(()=>{
   changed();area.setSelectionRange(0,0);area.scrollTop=0;
   if(draft)$('#edit-error').textContent=base.revision===i.revision?'Recovered your unsaved draft.':'Recovered draft is based on an older revision. Download it and compare before saving.';
  });
 },async()=>{
  const area=$('#edit-form').elements.body;
  if(!area.value.trim())throw Error('The prompt cannot be empty.');
  if(!pending&&area.value===base.body){promptStorage(key,null);return}
  // Retain the exact request across an uncertain response, including after reload.
  if(!pending)pending={id:i.id,revision:base.revision,body:area.value,requestId:uid()};
  promptPending=pending;
  promptStorage(key,{id:i.id,body:area.value,base,pending});
  const submitted=pending.body;
  let result;
  try{result=await api('/api/edit',pending)}
  catch(e){if(e.httpStatus){pending=null;promptPending=null;promptStorage(key,{id:i.id,body:area.value,base,pending:null});throw Error(e.message+' Your draft is kept. Reload and compare before replacing newer work.')}throw Error(e.message+' Your draft is kept. Retry checks the same save.')}
  pending=null;promptPending=null;
  const saved=result.prompt;
  if(!saved)throw Error('Save receipt missing. Download your draft before reloading.');
  Object.assign(i,{body:saved.body,revision:saved.revision,status:saved.status,approval:saved.approval});
  base.body=saved.body;base.revision=saved.revision;
  if(area.value!==submitted){
   promptStorage(key,{id:i.id,body:area.value,base,pending:null});
   throw Error('Earlier save confirmed. Your newer draft is still open; save it next.');
  }
  promptStorage(key,null);promptDraftKey=null;render();toast('Prompt saved · Revision '+saved.revision);
 });
 promptDraftKey=key;$('#editor').classList.add('prompt-editor');
}
document.querySelector('#editor').addEventListener('close',()=>{
 if(promptDraftKey&&!promptPending)promptStorage(promptDraftKey,null);
 promptDraftKey=null;$('#editor').classList.remove('prompt-editor');
});


function newPrompt(){
 const requestId=uid(),id=uid().replaceAll('-','').slice(0,12);
 editDialog('New prompt',form=>{field(form,'Title','title','').maxLength=80;field(form,'Prompt','body','','textarea');},async()=>{
  const fields=$('#edit-form').elements,title=fields.title.value.trim(),body=fields.body.value;
  if(!title||!body.trim())throw Error('Add a title and prompt.');
  const used=new Set(items.filter(i=>i.mode==='prompts').map(i=>i.key));
  const key=[...'1234567890'].find(k=>!used.has(k))||'';
  const result=await api('/api/prompts',{requestId,prompt:{id,title,body,group:'core',key}});
  await refresh();navigate('prompts','prompts:'+result.prompt.id);
 },'Create prompt');
}
