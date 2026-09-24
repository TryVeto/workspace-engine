let hq={company:[],decisions:[],updates:[],revision:0},hqFilter='open',hqConnected=false,hqPending=false,hqPollTimer,committedState=null,failedDraft=null,catalogReady=false;
const hqModes=['home','decisions','updates','company'];
function hqItems(){return [...hq.company.map(r=>({id:'company:'+r.id,mode:'company',title:r.title,description:r.status==='current'?'Current · '+r.source:'Draft · '+(r.source||'Source needed'),body:r.body,record:r})),...hq.decisions.map(r=>({id:'decisions:'+r.id,mode:'decisions',title:r.title,description:r.status==='open'?'Waiting for you · '+r.actor:r.answer,body:[r.body,r.recommendation,...r.options,r.answer,r.reason].join('\n\n'),record:r})),...hq.updates.map(r=>({id:'updates:'+r.id,mode:'updates',title:r.title,description:r.actor+' · '+({working:'Working',waiting:'Waiting',returned:'Returned',paused:'Paused'}[r.status]||r.status),body:[r.body,r.checks,r.nextAction].join('\n\n'),record:r}))]}
function hqRecord(){return find(opened)?.record}
function hqTime(s){if(!s)return 'Not set';return new Date(s).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})}
function hqBadge(){const b=$('#side-nav [data-mode="decisions"]');if(b){b.querySelector('.nav-count')?.remove();const count=hq.decisions.filter(x=>x.status==='open').length;if(count){const badge=el('span','nav-count',count);badge.title=count+' decision'+(count===1?'':'s')+' waiting';badge.setAttribute('aria-label',badge.title);b.insertBefore(badge,b.querySelector('.nav-key'))}}}
function hqShell(title,description,action){const wrap=el('div','library hq-page'),head=el('div','library-head'),intro=el('div');intro.append(el('h1','',title));if(description)intro.append(el('p','',description));head.append(intro);if(action)head.append(action);wrap.append(head);view.replaceChildren(wrap);return wrap}
function hqRow(i,label){const row=el('div','item-row hq-row');row.dataset.item=i.id;row.tabIndex=selected===i.id?0:-1;row.setAttribute('aria-label',i.title);row.classList.toggle('selected',selected===i.id);row.onfocus=()=>selectRow(row,false);row.onkeydown=e=>{if(e.metaKey&&e.altKey&&e.key.startsWith('Arrow'))return;if((e.key==='Enter'||e.key==='ArrowRight')&&e.target===row){e.preventDefault();navigate(i.mode,i.id)}};const b=button('',()=>navigate(i.mode,i.id),'open-item');b.append(el('strong','',i.title));const description=i.mode==='company'?'':i.mode==='decisions'?i.record.actor:i.description;if(description)b.append(el('p','',description));row.append(icon(i.mode),b);if(label)row.append(el('span','hq-row-label',label));return row}
function hqSection(wrap,title,link,action){const section=el('section','hq-section'),head=el('div','hq-section-head');head.append(el('h2','',title));if(link)head.append(button(link,action));section.append(head);wrap.append(section);return section}
function hqRef(ref,label){const b=button(label||ref,()=>{const i=find(ref);if(i)navigate(i.mode,ref);else toast(catalogReady?'Source unavailable.':'Sources are still loading.');},'hq-source-link');return b}
function openDesignGroup(group){designNavigate(group)}
function renderHome(){
 const waiting=hq.decisions.filter(r=>r.status==='open'),active=state.work.filter(w=>w.status!=='done');
 const wrap=hqShell('Home',waiting.length?waiting.length+' decision'+(waiting.length===1?'':'s')+' waiting for you.':'',button('New work',()=>editWork(null),'primary'));
 const grid=el('div','hq-home-grid'),main=el('div','hq-home-main'),aside=el('aside','hq-home-aside');grid.append(main,aside);wrap.append(grid);
 const decisions=hqSection(main,'Your decisions','View all',()=>navigate('decisions'));
 if(!waiting.length)decisions.append(el('p','hq-empty','Nothing is waiting for your decision.'));
 for(const r of waiting.slice(0,5)){const i=find('decisions:'+r.id);decisions.append(hqRow(i,r.due?'Due '+r.due:'Review'))}
 const work=hqSection(main,'Current work','View all',()=>navigate('work'));
 if(!active.length)work.append(el('p','hq-empty','No active work.'));
 for(const w of active.slice(0,5))work.append(hqRow(find('work:'+w.id),statusLabel(w.status)));
 const updates=hqSection(main,'Latest updates','View all',()=>navigate('updates'));
 if(!hq.updates.length)updates.append(el('p','hq-empty','No updates yet.'));
 for(const r of hq.updates.slice(0,4))updates.append(hqRow(find('updates:'+r.id),hqTime(r.createdAt)));
 const goal=hq.company.find(r=>r.id==='goal'),direction=hqSection(aside,'Company goal','Open',()=>navigate('company','company:goal'));
 direction.append(el('p','hq-goal',goal?.body?.split(/\n\s*\n/)[0]||'No goal set.'));direction.append(el('p','muted hq-provenance',goal?.body?(goal.status==='current'?'Current':'Draft'):''));
 const links=hqSection(aside,'Company references');
 for(const [label,fn] of [['Strategy',()=>navigate('company','company:strategy')],['Design system',()=>openDesignGroup('Design')],['Product system',()=>openDesignGroup('Product')],['Brand system',()=>openDesignGroup('Brand')],['Prompts',()=>navigate('prompts')],['Skills',()=>navigate('skills')]]){const b=button('',fn,'hq-reference');b.append(el('span','',label),el('span','','↗'));links.append(b)}
 aside.append(button('Agent connection guide',showAgentGuide));

}
function renderHQList(){
 const type=mode,defs={decisions:['Decisions','Prepared questions, with a recommendation and a recorded answer.','Request a decision',()=>editDecision()],updates:['Updates','Progress and evidence, attributed to the agent that submitted it.','Post update',()=>editUpdate()],company:['Company','The goal, the strategy, and the systems that guide the work.','Connection guide',showAgentGuide]};
 const [title,description,label,action]=defs[type],wrap=hqShell(title,'',button(label,action,type==='company'?'':'primary'));
 if(type==='company'){for(const r of hq.company)wrap.append(hqRow(find('company:'+r.id),r.status==='current'?'Current':'Draft'));const refs=hqSection(wrap,'Systems');for(const g of ['Design','Product','Brand'])refs.append(button(g+' system',()=>openDesignGroup(g),'hq-reference'));return}
 const search=el('div','library-search'),input=el('input');input.placeholder='Search '+title.toLowerCase();input.setAttribute('aria-label',input.placeholder);input.value=filter;search.append(input);wrap.append(search);
 if(type==='decisions'){const filters=el('div','filters');for(const [v,l] of [['open','Waiting for you'],['resolved','Resolved'],['all','All']])filters.append(button(l,()=>{hqFilter=v;renderHQList();focusContent()},hqFilter===v?'active':''));wrap.append(filters)}
 const results=el('div');wrap.append(results);
 function draw(){results.replaceChildren();const list=hqItems().filter(i=>i.mode===type&&(type!=='decisions'||hqFilter==='all'||i.record.status===hqFilter)&&(!filter||searchScore(i,filter)>0));for(const i of list)results.append(hqRow(i,type==='decisions'?(i.record.due||i.record.status):hqTime(i.record.createdAt)));if(!list.length)results.append(el('p','hq-empty',type==='decisions'?'No decisions in this view.':'No updates in this view.'));if(!results.querySelector('[tabindex="0"]'))results.querySelector('.item-row')?.setAttribute('tabindex','0')}
 input.oninput=()=>{filter=input.value;draw()};draw();
}
function hqContent(wrap,title,body){if(!body?.trim())return null;const section=el('section','hq-section');section.append(el('h2','',title),prose(body||'Not provided.'));wrap.append(section);return section}
function hqArtifact(wrap,path){if(!path)return;const row=el('div','hq-artifact');row.append(el('code','',path),button('Copy path',()=>copy(path)));if(/^https?:\/\//i.test(path)){const a=el('a','','Open ↗');a.href=path;a.target='_blank';a.rel='noopener noreferrer';row.append(a)}wrap.append(row)}
function renderHQReader(){
 const r=hqRecord();if(!r){hqShell('Unavailable','This record could not be found.');return}
 const wrap=el('article','reader hq-reader'),actions=el('div','reader-actions');actions.append(button('← Back',goBack),button('Copy',()=>copy(find(opened).body)));
 if(mode==='company')actions.append(button('Edit',()=>editCompany(r),'primary'));
 if(mode==='decisions'&&r.status==='open')actions.append(button('Record decision',()=>resolveDecision(r),'primary'));
 wrap.append(actions,el('h1','',r.title));view.replaceChildren(wrap);
 if(mode==='company'){wrap.append(el('p','description',r.status==='current'?'Current':'Draft'));hqContent(wrap,'Direction',r.body);hqContent(wrap,'Source',r.source);if(r.updatedAt)wrap.append(el('p','muted','Updated '+hqTime(r.updatedAt)+' · '+r.actor));return}
 wrap.append(el('p','description',r.actor+' · '+hqTime(r.createdAt)+' · '+(r.status==='open'?'Waiting for you':r.status)));
 if(mode==='decisions'){
  hqContent(wrap,'The question',r.body);hqContent(wrap,'Recommendation',r.recommendation);
  if(r.options?.length){const options=hqSection(wrap,'Options'),list=el('ol','hq-options');r.options.forEach(o=>list.append(el('li','',o)));options.append(list);}
  if(r.due)wrap.append(el('p','muted','Decision needed by '+r.due));
  hqArtifact(wrap,r.artifact);
  if(r.status==='resolved'){hqContent(wrap,'Recorded decision',r.answer);if(r.reason)hqContent(wrap,'Reason / feedback',r.reason);wrap.append(el('p','muted','Recorded by '+r.resolvedBy+' · '+hqTime(r.resolvedAt)),button('Reopen decision',async()=>{await hqMutate({action:'decision.reopen',actor:INSTANCE.owner,version:r.version,record:{id:r.id}});render()}))}
 }else{hqContent(wrap,'Update',r.body);hqArtifact(wrap,r.artifact);if(r.checks)hqContent(wrap,'Checks',r.checks);if(r.nextAction)hqContent(wrap,'Next action',r.nextAction)}
 if(r.workId){const ref='work:'+r.workId;wrap.append(hqRef(ref,'Open related work'))}
 const history=button('History',async()=>{const kind=mode==='decisions'?'decision':'update';const rows=await api('/api/hq/'+kind+'/'+encodeURIComponent(r.id)+'/history');history.remove();const section=hqSection(wrap,'History');for(const e of rows){const d=el('details','history-entry');d.append(el('summary','',hqTime(e.createdAt)+' · '+e.actor),el('pre','',JSON.stringify(e.record,null,2)));section.append(d)}});wrap.append(history);
}
function renderHQ(){if(opened)renderHQReader();else if(mode==='home')renderHome();else renderHQList();hqBadge()}
async function hqMutate(data){
 if(!data.requestId)data.requestId=uid();
 let out;for(let attempt=0;attempt<2;attempt++){try{out=await api('/api/hq',data);break}catch(e){if(e.httpStatus||attempt)throw e}}
 hq=await api('/api/hq');hqBadge();return out;
}
function hqWorkField(form,value){const l=el('label','','Related work'),s=el('select');l.htmlFor='f-workId';s.id='f-workId';s.name='workId';s.append(new Option('No related work',''));for(const w of state.work)s.append(new Option(w.title,w.id,false,value===w.id));form.append(l,s)}
function editDecision(){
 const requestId=uid(),id=uid();editDialog('Request a decision',f=>{field(f,'Agent / owner','actor','');field(f,'Decision','title','');field(f,'Question and context','body','','textarea').className='short';field(f,'Recommended choice and why','recommendation','','textarea').className='short';field(f,'Options · one per line','options','','textarea').className='short';field(f,'Evidence / artifact path','artifact','');field(f,'Needed by','due','').type='date';hqWorkField(f,'')},async()=>{const d=Object.fromEntries(new FormData($('#edit-form')));const actor=d.actor;d.options=d.options.split('\n').map(x=>x.trim()).filter(Boolean);await hqMutate({requestId,action:'decision.create',actor,record:{id,...d}});navigate('decisions','decisions:'+id)},'Submit request');
}
function editUpdate(){
 const requestId=uid(),id=uid();editDialog('Post update',f=>{field(f,'Agent / owner','actor','');field(f,'Title','title','');field(f,'What changed','body','','textarea').className='short';const l=el('label','','Status'),s=el('select');l.htmlFor='f-status';s.id='f-status';s.name='status';for(const v of ['working','waiting','returned','paused'])s.append(new Option(v,v));f.append(l,s);field(f,'Artifact / path','artifact','');field(f,'Checks actually run','checks','','textarea').className='short';field(f,'Next action','nextAction','','textarea').className='short';hqWorkField(f,'')},async()=>{const d=Object.fromEntries(new FormData($('#edit-form')));await hqMutate({requestId,action:'update.create',actor:d.actor,record:{id,...d}});navigate('updates','updates:'+id)},'Post update');
}
function hqChoices(form,label,name,options,value){
 const set=el('fieldset','hq-choices');set.append(el('legend','',label));options.forEach(([v,title],i)=>{const row=el('label','hq-choice'),radio=el('input');radio.type='radio';radio.name=name;radio.value=v;radio.id='f-'+name+'-'+i;radio.checked=v===value;row.append(radio,el('span','',title));set.append(row)});form.append(set);
}
function resolveDecision(r){
 const requestId=uid();editDialog('Record decision',f=>{hqChoices(f,'Choice','choice',[...r.options.map(o=>[o,o]),['custom','Write another answer']],'');field(f,'Other answer','answer','');field(f,'Reason / feedback','reason','','textarea').className='short'},async()=>{const d=Object.fromEntries(new FormData($('#edit-form'))),answer=d.choice==='custom'?d.answer:d.choice;if(!answer?.trim())throw Error('Choose an option or write an answer.');await hqMutate({requestId,action:'decision.resolve',actor:INSTANCE.owner,version:r.version,record:{id:r.id,answer,reason:d.reason}});render()},'Record decision');
}
function editCompany(r){
 const requestId=uid();editDialog('Edit '+r.title.toLowerCase(),f=>{field(f,'Direction and success criteria','body',r.body,'textarea');field(f,'Source / basis','source',r.source);const label=el('label','','Status'),s=el('select');label.htmlFor='f-status';s.id='f-status';s.name='status';s.append(new Option('Draft','draft',false,r.status==='draft'),new Option('Current','current',false,r.status==='current'));f.append(label,s)},async()=>{const d=Object.fromEntries(new FormData($('#edit-form')));await hqMutate({requestId,action:'company.edit',actor:INSTANCE.owner,version:r.version,record:{id:r.id,...d}});render()});
}
async function showAgentGuide(){try{const r=await fetch('/api/agent');if(!r.ok)throw Error('Connection guide unavailable');const text=await r.text();editDialog('Connect an agent',f=>field(f,'Local agent instructions','body',text,'textarea'),null,'Close');$('#edit-form textarea').readOnly=true}catch(e){toast(e.message)}}
async function initializeHQ(){installHQCommands();Object.assign(modes,{home:{name:'Home'},decisions:{name:'Decisions'}});const entries={...modes};for(const k of Object.keys(modes))delete modes[k];for(const k of ['admin','prompts','skills','files','insights','tasks','decisions','work','feed','bookmarks','canvas','contexts','design','principles','culture','company','profile','agents','plugins','mcps','updates','home',...Object.keys(entries)])if(entries[k])modes[k]=entries[k];Object.assign(iconPaths,{home:'M3 11l9-8 9 8 M5 10v11h14V10 M10 21v-7h4v7',decisions:'M9 5h11v14H4V5h2 M8 3h8v4H8z M8 12l2 2 5-5',updates:'M4 6h16 M4 12h16 M4 18h10',company:'M4 21V3h16v18 M8 7h2 M14 7h2 M8 11h2 M14 11h2 M10 21v-6h4v6'});hq=await api('/api/hq');hqConnected=true;committedState=structuredClone(state);hqPollTimer=setInterval(pollHQ,5000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollHQ()});}
async function pollHQ(){
 if(document.hidden||!state)return;
 try{const health=await api('/api/health');hqConnected=true;const changed=health.hqRevision!==hq.revision||health.workspaceRevision!==state.revision;
 if(changed){if(dirty||saveFailed||document.querySelector('dialog[open]')||document.activeElement?.matches('input,textarea,select,[contenteditable]')||savePending){hqPending=true;return}
 const was=document.activeElement,ref=was?.closest('[data-item]')?.dataset.item,within=!!was?.closest('#view'),scroll=view.scrollTop;
 if(health.hqRevision!==hq.revision)hq=await api('/api/hq');
 if(health.workspaceRevision!==state.revision){state=await api('/api/state');committedState=structuredClone(state)}
 if(hqModes.includes(mode)||(mode==='work')){render();if(ref){const row=[...view.querySelectorAll('[data-item]')].find(n=>n.dataset.item===ref);if(row)selectRow(row);else if(within)focusContent()}else if(within&&opened)focusContent();view.scrollTop=scroll}
 hqBadge();hqPending=false;
 }if(!saveFailed&&!savePending)$('#save-state').textContent='Saved on this Mac';
 }catch{hqConnected=false;if(!saveFailed&&!savePending)$('#save-state').textContent='Reconnecting…'}
}


function renderHandoffs(w,wrap){if(!w.handoffs?.length)return;
 const section=el('section','work-section');section.append(el('h2','','Saved handoffs'));
 for(const b of [...(w.handoffs||[])].reverse()){const row=el('details','history-entry');row.append(el('summary','',hqTime(b.createdAt)+' · '+b.id));row.append(el('p','muted','Prepared at workspace revision '+b.baseRevision+' · '+(b.memory?.length||0)+' selected excerpts'),el('pre','',b.text),button('Copy saved brief',()=>copy(b.text)));section.append(row)}

 wrap.append(section);
}
function reviewResult(w,r){
 editDialog('Review returned result',form=>{hqArtifact(form,r.artifact);hqChoices(form,'Review state','review',['unreviewed','direction','implementation','superseded'].map(v=>[v,reviewLabel(v)]),r.review);field(form,'Scoped feedback','feedback','','textarea').className='short'},async()=>{const d=Object.fromEntries(new FormData($('#edit-form'))),current=state.work.find(x=>x.id===w.id).returns.find(x=>x.id===r.id);current.reviews||=[];current.reviews.push({id:uid(),previous:current.review,review:d.review,feedback:d.feedback,actor:INSTANCE.owner,createdAt:new Date().toISOString()});current.review=d.review;await persist();renderWorkReader()},'Record review');
}
function adoptResult(w,r){
 editDialog('Use this artifact next',f=>{hqArtifact(f,r.artifact);f.append(el('p','muted','This makes the selected result the current artifact for this work. Earlier artifacts and reviews remain in history.'));field(f,'Next action','nextAction',w.nextAction,'textarea').className='short'},async()=>{const current=state.work.find(x=>x.id===w.id),result=current.returns.find(x=>x.id===r.id);if(result.review!=='implementation')throw Error('Record implementation acceptance before adopting this result.');current.adoptions||=[];current.adoptions.push({id:uid(),previousArtifact:current.artifact,returnId:r.id,artifact:r.artifact,actor:INSTANCE.owner,createdAt:new Date().toISOString()});current.artifact=result.artifact;current.currentReturnId=result.id;current.nextAction=$('#edit-form').elements.nextAction.value;await persist();renderWorkReader()},'Use as current artifact');
}

function installHQCommands(){
 const original=drawPicker;
 drawPicker=function(){original();if(pickAction!=='open')return;const q=$('#picker-search').value.trim().toLowerCase();const list=Object.entries(modes).filter(([k,m])=>!q||m.name.toLowerCase().includes(q)).slice(0,q?20:5),fragment=document.createDocumentFragment();for(const [k,m] of list){const b=button('',()=>{$('#picker').close();navigate(k)});b.append(icon(k),el('span','','Go to '+m.name));fragment.append(b)}$('#picker-results').prepend(fragment)};
 $('#picker-search').oninput=()=>drawPicker();
 document.addEventListener('keydown',e=>{if(e.metaKey&&e.altKey&&e.key.startsWith('Arrow'))return;if(e.key.toLowerCase()!=='n'||e.metaKey||e.ctrlKey||e.altKey||e.isComposing||document.querySelector('dialog[open]')||e.target.matches('input,textarea,select,[contenteditable]'))return;const fn={home:()=>editWork(null),work:()=>editWork(null),tasks:()=>editTask(null),decisions:editDecision,updates:editUpdate}[mode];if(fn&&!opened){e.preventDefault();fn()}});
}
