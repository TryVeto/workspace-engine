/* Workspace block canvas v1: a Notion-shaped page of editable, reorderable objects. */
(()=>{
 if(typeof renderCanvas!=='function')return;
 const renderSpatialCanvas=renderCanvas,baseFocusContent=focusContent;
 const PAGE_KIND='block-page',VERSION=1;
 let canvasView='blocks',page=null,saveTimer=null,pendingFocus=null,dragging=null,menu=null,menuIndex=0,menuQuery='',menuMode='convert',menuTarget=null;
 const textTypes=new Set(['paragraph','heading1','heading2','callout']);
 const commands=[
  ['Basic','Text','Plain text','paragraph'],['Basic','Heading 1','Large section heading','heading1'],['Basic','Heading 2','Small section heading','heading2'],
  ['Basic','Checklist','Interactive checklist','checklist'],['Basic','Bulleted list','Simple list','bullets'],['Basic','Callout','Quiet emphasized text','callout'],
  ['Data','Table','Editable rows and columns','table'],['Data','Properties','Key / value properties','properties'],
  ['Workspace','Decision','Decision and status','decision'],['Workspace','Timeline','Dated events','timeline'],['Workspace','References','Links and source objects','references'],
  ['Basic','Divider','Horizontal rule','divider']
 ].map(([group,label,description,type])=>({group,label,description,type}));
 const clone=v=>JSON.parse(JSON.stringify(v));
 function make(type){
  const id=uid();
  if(type==='paragraph')return{id,type,span:12,text:''};
  if(type==='heading1'||type==='heading2')return{id,type,span:12,text:''};
  if(type==='callout')return{id,type,span:12,text:'Callout'};
  if(type==='checklist')return{id,type,span:6,items:[{id:uid(),text:'First item',done:false}]};
  if(type==='bullets')return{id,type,span:6,items:[{id:uid(),text:'First item'}]};
  if(type==='table')return{id,type,span:12,rows:[['Name','Owner','Status'],['Example','—','Open']]};
  if(type==='properties')return{id,type,span:6,rows:[['Status','Draft'],['Owner','—'],['Updated','Today']]};
  if(type==='decision')return{id,type,span:6,status:'Pending',text:'Decision to make'};
  if(type==='timeline')return{id,type,span:12,items:[{id:uid(),date:'Today',text:'Started'},{id:uid(),date:'Next',text:'Next milestone'}]};
  if(type==='references')return{id,type,span:6,items:[{id:uid(),title:'Reference',url:''}]};
  if(type==='divider')return{id,type,span:12};
  return{id,type:'paragraph',span:12,text:''};
 }
 function noteForBoard(){return state.notes.find(n=>n.kind===PAGE_KIND&&n.boardId===board().id)}
 function starter(){
  const migrated=board().cards.map(c=>({id:uid(),type:'reference',span:c.w>=620?12:6,ref:c.ref}));
  const blocks=migrated.length?migrated:[{id:uid(),type:'paragraph',span:12,text:''}];
  if(!blocks.some(b=>b.type==='paragraph'&&!(b.text||'').trim()))blocks.push({id:uid(),type:'paragraph',span:12,text:''});
  return{version:VERSION,title:board().title,blocks,updatedAt:new Date().toISOString()};
 }
 function normalize(raw){
  if(!raw||typeof raw!=='object'||!Array.isArray(raw.blocks))return starter();
  raw.version=VERSION;raw.title=String(raw.title||board().title).slice(0,200);
  raw.blocks=raw.blocks.filter(b=>b&&typeof b.id==='string'&&typeof b.type==='string').slice(0,500);
  if(!raw.blocks.length)raw.blocks.push(make('paragraph'));
  for(const b of raw.blocks){b.span=[4,6,8,12].includes(b.span)?b.span:12}
  return raw;
 }
 function loadPage(){
  const n=noteForBoard();if(!n)return starter();
  try{return normalize(JSON.parse(n.body))}catch{return starter()}
 }
 function ensureNote(){
  let n=noteForBoard();
  if(!n){n={id:'block-page-'+board().id,kind:PAGE_KIND,boardId:board().id,title:page.title||board().title,body:'',updatedAt:new Date().toISOString()};state.notes.push(n)}
  return n;
 }
 function writeState(){
  if(!page)return;
  page.updatedAt=new Date().toISOString();const n=ensureNote();n.title=page.title||board().title;n.body=JSON.stringify(page);n.updatedAt=page.updatedAt;
 }
 function saveSoon(delay=450){
  writeState();clearTimeout(saveTimer);saveTimer=setTimeout(()=>{saveTimer=null;persist().catch(()=>{})},delay);
 }
 function saveNow(){clearTimeout(saveTimer);saveTimer=null;writeState();return persist().catch(()=>{})}
 function blockBy(id){return page?.blocks.find(b=>b.id===id)}
 function blockIndex(id){return page?.blocks.findIndex(b=>b.id===id)??-1}
 function focusBlock(id,selector='[contenteditable="true"]'){
  requestAnimationFrame(()=>{const root=view.querySelector('[data-block-id="'+CSS.escape(id)+'"]');const n=root?.querySelector(selector)||root?.querySelector('button,input,select');if(n){n.focus({preventScroll:true});if(n.isContentEditable){const r=document.createRange();r.selectNodeContents(n);r.collapse(false);const s=getSelection();s.removeAllRanges();s.addRange(r)}root.scrollIntoView({block:'nearest'})}})
 }
 function replaceBlock(id,next){const i=blockIndex(id);if(i<0)return;next.id=id;page.blocks[i]=next;pendingFocus=id;saveSoon(0);renderBlockCanvas()}
 function insertAfter(id,b){const i=id?blockIndex(id):-1;page.blocks.splice(i<0?page.blocks.length:i+1,0,b);pendingFocus=b.id;saveSoon(0);renderBlockCanvas()}
 function removeBlock(id){
  const i=blockIndex(id);if(i<0)return;const fallback=page.blocks[i-1]?.id||page.blocks[i+1]?.id;
  page.blocks.splice(i,1);if(!page.blocks.length)page.blocks.push(make('paragraph'));pendingFocus=fallback||page.blocks[0].id;saveSoon(0);renderBlockCanvas()
 }
 function duplicateBlock(id){const i=blockIndex(id);if(i<0)return;const b=clone(page.blocks[i]);b.id=uid();for(const item of b.items||[])item.id=uid();page.blocks.splice(i+1,0,b);pendingFocus=b.id;saveSoon(0);renderBlockCanvas()}
 function moveBlock(id,to){
  const i=blockIndex(id);if(i<0)return;const [b]=page.blocks.splice(i,1);let j=to;if(i<to)j--;j=Math.max(0,Math.min(page.blocks.length,j));page.blocks.splice(j,0,b);pendingFocus=id;saveSoon(0);renderBlockCanvas()
 }
 function textOf(n){return (n.innerText||'').replace(/\r/g,'')}
 function caretOffset(n){const s=getSelection();if(!s.rangeCount)return textOf(n).length;const r=s.getRangeAt(0).cloneRange();r.selectNodeContents(n);r.setEnd(s.anchorNode,s.anchorOffset);return r.toString().length}
 function setPlainPaste(n){n.addEventListener('paste',e=>{e.preventDefault();const t=e.clipboardData.getData('text/plain');document.execCommand('insertText',false,t)})}
 function editable(tag,text,cls,label,onInput,onKey){
  const n=el(tag,cls);n.contentEditable='true';n.spellcheck=true;n.textContent=text||'';n.setAttribute('role','textbox');n.setAttribute('aria-label',label);n.dataset.placeholder=label;
  n.oninput=()=>onInput(textOf(n));n.onkeydown=onKey;setPlainPaste(n);return n
 }
 function textKey(e,b,n){
  if(menu&&menuTarget===b.id){if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();menuIndex=Math.max(0,Math.min(filteredCommands().length-1,menuIndex+(e.key==='ArrowDown'?1:-1)));drawMenu();return}if(e.key==='Enter'){e.preventDefault();chooseCommand(filteredCommands()[menuIndex]);return}if(e.key==='Escape'){e.preventDefault();closeMenu();return}}
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();const t=textOf(n),at=caretOffset(n);b.text=t.slice(0,at);const nb=make('paragraph');nb.text=t.slice(at);insertAfter(b.id,nb);return}
  if(e.key==='Backspace'&&!textOf(n)&&page.blocks.length>1){e.preventDefault();removeBlock(b.id)}
 }
 function updateSlash(b,n){
  b.text=textOf(n);saveSoon();
  if(b.text.startsWith('/'))openMenu(b.id,'convert',b.text.slice(1),n);else if(menuTarget===b.id&&menuMode==='convert')closeMenu()
 }
 function moreMenu(block,wrap){
  const menuBox=el('div','bc-more-menu');menuBox.hidden=true;
  const widthLabel=block.span===12?'Half width':'Full width';
  menuBox.append(
   button(widthLabel,()=>{block.span=block.span===12?6:12;saveSoon(0);renderBlockCanvas()}),
   button('Duplicate',()=>duplicateBlock(block.id)),
   button('Delete',()=>removeBlock(block.id))
  );
  const more=button('…',e=>{},'bc-more');more.setAttribute('aria-label','Block options');more.onclick=e=>{e.stopPropagation();document.querySelectorAll('.bc-more-menu').forEach(m=>{if(m!==menuBox)m.hidden=true});menuBox.hidden=!menuBox.hidden};
  wrap.append(more,menuBox)
 }
 function chrome(block,wrap){
  const gutter=el('div','bc-gutter'),add=button('+',()=>openMenu(block.id,'insert','',wrap),'bc-insert'),drag=button('⋮⋮',()=>{},'bc-drag');
  add.setAttribute('aria-label','Add block after');drag.setAttribute('aria-label','Move block');drag.draggable=true;
  drag.ondragstart=e=>{dragging=block.id;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',block.id);wrap.classList.add('dragging')};
  drag.ondragend=()=>{dragging=null;view.querySelectorAll('.bc-block').forEach(n=>n.classList.remove('dragging','drop-before','drop-after'))};
  drag.onkeydown=e=>{if(e.metaKey&&e.altKey&&e.key.startsWith('Arrow'))return;if(e.altKey&&!e.metaKey&&!e.ctrlKey&&['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();const i=blockIndex(block.id);moveBlock(block.id,i+(e.key==='ArrowDown'?2:-1))}};
  gutter.append(add,drag);wrap.append(gutter);moreMenu(block,wrap);
  wrap.ondragover=e=>{if(!dragging||dragging===block.id)return;e.preventDefault();const r=wrap.getBoundingClientRect(),after=e.clientY>r.top+r.height/2;wrap.classList.toggle('drop-before',!after);wrap.classList.toggle('drop-after',after)};
  wrap.ondragleave=()=>wrap.classList.remove('drop-before','drop-after');
  wrap.ondrop=e=>{if(!dragging||dragging===block.id)return;e.preventDefault();const r=wrap.getBoundingClientRect(),after=e.clientY>r.top+r.height/2;const from=blockIndex(dragging),target=blockIndex(block.id)+(after?1:0);const moving=page.blocks[from];page.blocks.splice(from,1);let next=target;if(from<target)next--;page.blocks.splice(Math.max(0,Math.min(page.blocks.length,next)),0,moving);dragging=null;saveSoon(0);renderBlockCanvas()};
 }
 function rowEditable(value,label,fn,cls=''){
  return editable('div',value,cls,label,fn,e=>{if(e.key==='Enter'){e.preventDefault();e.currentTarget.blur()}})
 }
 function renderReference(block,content){
  const i=find(block.ref),head=el('div','bc-object-head');head.append(icon(i?.mode||'notes'),el('strong','',i?.title||'Source unavailable'));content.append(head);
  if(i?.description||i?.body)content.append(el('p','bc-reference-summary',(i.description||i.body||'').slice(0,320)));
  if(i)content.append(button('Open',()=>navigate(i.mode==='notes'?'canvas':i.mode,i.id),'bc-inline-action'))
 }
 function renderText(block,content){
  const tag=block.type==='heading1'?'h2':block.type==='heading2'?'h3':'div',cls='bc-editable bc-'+block.type;
  const n=editable(tag,block.text,cls,block.type==='paragraph'?'Text':block.type==='callout'?'Callout':'Heading',v=>updateSlash(block,n),e=>textKey(e,block,n));if(block.type==='paragraph')n.dataset.placeholder="Type '/' for commands";content.append(n)
 }
 function renderChecklist(block,content,bullets=false){
  const list=el(bullets?'ul':'div',bullets?'bc-bullets':'bc-checklist');
  (block.items||[]).forEach((it,idx)=>{const row=el(bullets?'li':'div',bullets?'':'bc-check-row');
   if(!bullets){const check=el('input');check.type='checkbox';check.checked=!!it.done;check.setAttribute('aria-label','Complete item');check.onchange=()=>{it.done=check.checked;saveSoon()};row.append(check)}
   const n=editable('span',it.text,'bc-list-text','List item',v=>{it.text=v;saveSoon()},e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();const ni={id:uid(),text:'',...(bullets?{}:{done:false})};block.items.splice(idx+1,0,ni);pendingFocus=block.id+'::'+ni.id;saveSoon(0);renderBlockCanvas()}else if(e.key==='Backspace'&&!textOf(n)&&block.items.length>1){e.preventDefault();block.items.splice(idx,1);saveSoon(0);renderBlockCanvas()}});n.dataset.itemId=it.id;row.append(n);list.append(row)});
  content.append(list,button(bullets?'Add item':'Add action',()=>{const ni={id:uid(),text:'',...(bullets?{}:{done:false})};block.items.push(ni);pendingFocus=block.id+'::'+ni.id;saveSoon(0);renderBlockCanvas()},'bc-add-row'))
 }
 function renderTable(block,content){
  const table=el('table','bc-table');const rows=block.rows||[];
  rows.forEach((row,r)=>{const tr=el('tr');row.forEach((cell,c)=>{const td=el(r===0?'th':'td');const n=editable('div',cell,'','Table cell',v=>{block.rows[r][c]=v;saveSoon()},e=>{if(e.key==='Enter'){e.preventDefault();e.currentTarget.blur()}});td.append(n);tr.append(td)});table.append(tr)});content.append(table);
  const actions=el('div','bc-table-actions');actions.append(button('Add row',()=>{const cols=Math.max(1,block.rows[0]?.length||3);block.rows.push(Array(cols).fill(''));saveSoon(0);renderBlockCanvas()}),button('Add column',()=>{for(const row of block.rows)row.push('');saveSoon(0);renderBlockCanvas()}));content.append(actions)
 }
 function renderProperties(block,content){
  const rows=el('div','bc-properties');(block.rows||[]).forEach((r,idx)=>{const row=el('div','bc-property-row');row.append(rowEditable(r[0],'Property name',v=>{r[0]=v;saveSoon()},'bc-property-key'),rowEditable(r[1],'Property value',v=>{r[1]=v;saveSoon()},'bc-property-value'));rows.append(row)});content.append(rows,button('Add property',()=>{block.rows.push(['Property','']);saveSoon(0);renderBlockCanvas()},'bc-add-row'))
 }
 function renderDecision(block,content){
  const head=el('div','bc-object-head');head.append(icon('principles'),el('strong','','Decision'));const select=el('select','bc-status');['Pending','Decided','Superseded'].forEach(v=>{const o=el('option','',v);o.value=v;o.selected=v===block.status;select.append(o)});select.onchange=()=>{block.status=select.value;saveSoon()};head.append(select);content.append(head);
  content.append(editable('div',block.text,'bc-decision-text','Decision',v=>{block.text=v;saveSoon()},e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();e.currentTarget.blur()}}))
 }
 function renderTimeline(block,content){
  const head=el('div','bc-object-head');head.append(icon('tasks'),el('strong','','Timeline'));content.append(head);const list=el('div','bc-timeline');
  (block.items||[]).forEach(it=>{const row=el('div','bc-timeline-row');row.append(rowEditable(it.date,'Event date',v=>{it.date=v;saveSoon()},'bc-timeline-date'),rowEditable(it.text,'Event',v=>{it.text=v;saveSoon()},'bc-timeline-text'));list.append(row)});content.append(list,button('Add event',()=>{block.items.push({id:uid(),date:'',text:''});saveSoon(0);renderBlockCanvas()},'bc-add-row'))
 }
 function renderReferences(block,content){
  const head=el('div','bc-object-head');head.append(icon('bookmarks'),el('strong','','References'));content.append(head);const list=el('div','bc-references');
  (block.items||[]).forEach(it=>{const row=el('div','bc-reference-row');row.append(rowEditable(it.title,'Reference title',v=>{it.title=v;saveSoon()},'bc-ref-title'),rowEditable(it.url,'Reference URL',v=>{it.url=v;saveSoon()},'bc-ref-url'));list.append(row)});content.append(list,button('Add reference',()=>{block.items.push({id:uid(),title:'Reference',url:''});saveSoon(0);renderBlockCanvas()},'bc-add-row'))
 }
 function renderBlock(block){
  const wrap=el('section','bc-block bc-type-'+block.type+' bc-span-'+block.span);wrap.dataset.blockId=block.id;wrap.tabIndex=-1;chrome(block,wrap);const content=el('div','bc-content');wrap.append(content);
  if(textTypes.has(block.type))renderText(block,content);else if(block.type==='checklist')renderChecklist(block,content,false);else if(block.type==='bullets')renderChecklist(block,content,true);else if(block.type==='table')renderTable(block,content);else if(block.type==='properties')renderProperties(block,content);else if(block.type==='decision')renderDecision(block,content);else if(block.type==='timeline')renderTimeline(block,content);else if(block.type==='references')renderReferences(block,content);else if(block.type==='reference')renderReference(block,content);else if(block.type==='divider')content.append(el('hr','bc-divider'));else renderText(Object.assign(block,{type:'paragraph',text:block.text||''}),content);
  return wrap
 }
 function pageMarkdown(){
  const out=['# '+page.title,''];
  for(const b of page.blocks){
   if(textTypes.has(b.type)&&b.text)out.push(b.type==='heading1'?'## '+b.text:b.type==='heading2'?'### '+b.text:b.text,'');
   else if(b.type==='checklist')out.push(...(b.items||[]).map(i=>'- ['+(i.done?'x':' ')+'] '+i.text),'');
   else if(b.type==='bullets')out.push(...(b.items||[]).map(i=>'- '+i.text),'');
   else if(b.type==='table'&&b.rows?.length){const rows=b.rows.map(r=>r.map(v=>String(v??'').replaceAll('|','\\|'))),cols=Math.max(...rows.map(r=>r.length));const pad=r=>[...r,...Array(Math.max(0,cols-r.length)).fill('')];out.push('| '+pad(rows[0]).join(' | ')+' |','| '+Array(cols).fill('---').join(' | ')+' |',...rows.slice(1).map(r=>'| '+pad(r).join(' | ')+' |'),'')}
   else if(b.type==='properties')out.push(...(b.rows||[]).map(r=>'**'+(r[0]||'Property')+':** '+(r[1]||'')),'');
   else if(b.type==='decision')out.push('## Decision','**'+b.status+'** — '+b.text,'');
   else if(b.type==='timeline')out.push('## Timeline',...(b.items||[]).map(i=>'- **'+(i.date||'')+'** — '+(i.text||'')),'');
   else if(b.type==='references')out.push('## References',...(b.items||[]).map(i=>'- '+(i.url?'['+(i.title||i.url)+']('+i.url+')':(i.title||'Reference'))),'');
   else if(b.type==='divider')out.push('---','');
   else if(b.type==='reference'){const i=find(b.ref);if(i)out.push('## '+i.title,(i.url?i.url+'\n\n':'')+(i.body||i.description||''),'')}
  }
  return out.join('\n')
 }
 function renderBlockCanvas(){
  canvasView='blocks';page=loadPage();view.replaceChildren();const canvas=el('div','block-canvas');canvas.id='canvas';const article=el('article','bc-page');
  const top=el('div','bc-page-top'),title=editable('h1',page.title,'bc-title','Page title',v=>{page.title=v.slice(0,200)||'Untitled';board().title=page.title;saveSoon()},e=>{if(e.key==='Enter'){e.preventDefault();e.currentTarget.blur()}});
  title.onblur=()=>sidebar();const actions=el('div','bc-page-actions');
  actions.append(button('Copy page',()=>copy(pageMarkdown())));
  if(board().cards.length)actions.append(button('Spatial board · '+board().cards.length,()=>{canvasView='spatial';renderCanvas()}));
  top.append(title,actions);article.append(top);
  const grid=el('div','bc-grid');for(const b of page.blocks)grid.append(renderBlock(b));article.append(grid);
  const add=button('+ Add a block',()=>openMenu(page.blocks.at(-1)?.id||null,'insert','',add),'bc-bottom-add');article.append(add);canvas.append(article);view.append(canvas);
  if(pendingFocus){const [bid,item]=pendingFocus.split('::');requestAnimationFrame(()=>{if(item){const n=view.querySelector('[data-block-id="'+CSS.escape(bid)+'"] [data-item-id="'+CSS.escape(item)+'"]');n?.focus()}else focusBlock(bid)});pendingFocus=null}
 }
 function renderSpatial(){
  canvasView='spatial';closeMenu();renderSpatialCanvas();const actions=view.querySelector('.canvas-actions');if(actions){const back=button('← Block page',()=>{canvasView='blocks';renderBlockCanvas()});actions.prepend(back)}
 }
 function filteredCommands(){const q=menuQuery.trim().toLowerCase();return commands.filter(c=>!q||c.label.toLowerCase().includes(q)||c.type.includes(q)||c.group.toLowerCase().includes(q))}
 function openMenu(target,modeName='insert',query='',anchor=null){
  closeMenu();menuTarget=target;menuMode=modeName;menuQuery=query;menuIndex=0;menu=el('div','bc-slash-menu');menu.setAttribute('role','listbox');document.body.append(menu);
  drawMenu();positionMenu(anchor||view.querySelector('[data-block-id="'+CSS.escape(target||'')+'"]'))
 }
 function positionMenu(anchor){
  if(!menu||!anchor)return;const r=anchor.getBoundingClientRect(),w=300,h=Math.min(420,menu.scrollHeight||320);menu.style.left=Math.max(8,Math.min(innerWidth-w-8,r.left+24))+'px';menu.style.top=Math.max(8,Math.min(innerHeight-h-8,r.bottom+6))+'px'
 }
 function drawMenu(){
  if(!menu)return;menu.replaceChildren();const list=filteredCommands();let group='';
  list.forEach((c,i)=>{if(c.group!==group){group=c.group;menu.append(el('div','bc-menu-group',group))}const b=button('',()=>chooseCommand(c),i===menuIndex?'active':'');b.setAttribute('role','option');b.setAttribute('aria-selected',String(i===menuIndex));b.append(el('strong','',c.label),el('span','',c.description));menu.append(b)});
  if(!list.length)menu.append(el('div','bc-menu-empty','No matching blocks'))
 }
 function chooseCommand(c){
  if(!c)return;const b=make(c.type);
  if(menuMode==='convert'&&menuTarget){b.id=menuTarget;const i=blockIndex(menuTarget);if(i>=0)page.blocks[i]=b}else{const i=menuTarget?blockIndex(menuTarget):-1;page.blocks.splice(i<0?page.blocks.length:i+1,0,b)}
  const id=b.id;closeMenu();pendingFocus=id;saveSoon(0);renderBlockCanvas()
 }
 function closeMenu(){if(menu)menu.remove();menu=null;menuTarget=null;menuQuery='';menuIndex=0}
 renderCanvas=function(){if(canvasView==='spatial')return renderSpatial();return renderBlockCanvas()};
 focusContent=function(){if(mode==='canvas'&&canvasView==='blocks'){const n=view.querySelector('.bc-title,[contenteditable="true"],.bc-bottom-add');n?.focus({preventScroll:true});return}return baseFocusContent()};
 document.addEventListener('click',e=>{if(menu&&!e.target.closest('.bc-slash-menu,.bc-insert,.bc-bottom-add'))closeMenu();if(!e.target.closest('.bc-more,.bc-more-menu'))document.querySelectorAll('.bc-more-menu').forEach(m=>m.hidden=true)},true);
 document.addEventListener('keydown',e=>{
  if(mode!=='canvas'||canvasView!=='blocks'||document.querySelector('dialog[open]'))return;
  if(e.metaKey&&e.altKey&&e.key.startsWith('Arrow'))return;
  const typing=e.composedPath().some(n=>n instanceof Element&&(n.isContentEditable||n.matches('input,textarea,select,[role="textbox"]')));
  if(!typing&&e.key==='/'&&!e.metaKey&&!e.ctrlKey&&!e.altKey){e.preventDefault();e.stopImmediatePropagation();const b=make('paragraph');b.text='/';insertAfter(page.blocks.at(-1)?.id||null,b);requestAnimationFrame(()=>{const n=view.querySelector('[data-block-id="'+CSS.escape(b.id)+'"] [contenteditable]');if(n){n.focus();openMenu(b.id,'convert','',n)}})}
  if(menu&&!typing){if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();e.stopImmediatePropagation();menuIndex=Math.max(0,Math.min(filteredCommands().length-1,menuIndex+(e.key==='ArrowDown'?1:-1)));drawMenu()}else if(e.key==='Enter'){e.preventDefault();e.stopImmediatePropagation();chooseCommand(filteredCommands()[menuIndex])}else if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();closeMenu()}}
 },true);
 window.addEventListener('beforeunload',()=>{if(saveTimer){writeState()}});
})();