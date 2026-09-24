/* Skills filesystem and editable Markdown documents. */
let skillExtras={examples:[],research:''},activeSkillDocument=null,skillReadSequence=0;
let skillTreeQuery='',skillTreeFocus='',skillViewMode='read',skillLastRoute='',skillReaderKey='';
const skillScroll=new Map(),skillExpanded=new Set();
let skillLastSelection=null;
try{const saved=JSON.parse(localStorage.getItem('workspace-skills-explorer')||'{}');for(const id of saved.expanded||[])skillExpanded.add(id);skillLastSelection=saved.last||null;for(const [key,value] of Object.entries(saved.scroll||{}))if(Number.isFinite(value))skillScroll.set(key,value)}catch{}
function saveSkillPlace(){try{localStorage.setItem('workspace-skills-explorer',JSON.stringify({expanded:[...skillExpanded],last:skillLastSelection,scroll:Object.fromEntries(skillScroll)}))}catch{}}
function skillList(){return items.filter(i=>i.mode==='skills')}
function skillFile(){return new URLSearchParams(location.hash.split('?')[1]||'').get('file')||'SKILL.md'}
function skillHash(id,file='SKILL.md'){return '#skills/'+encodeURIComponent(id)+(file==='SKILL.md'?'':'?file='+encodeURIComponent(file))}
function skillRouteTitle(){if(opened==='template')return 'Skill template';if(opened==='examples')return 'Skill examples';if(opened==='research')return 'Creative direction research';if(opened?.startsWith('example-'))return skillExtras.examples.find(e=>'example-'+e.id===opened)?.title||'Example';return find(opened)?.title||'Skills'}
function skillPageActions(){return el('div','skill-page-actions')}
function skillsSidebar(side){} // The package tree is beside the reader.
function skillLink(url,label){try{const u=new URL(url);if(!['http:','https:'].includes(u.protocol))return el('span','',label);const a=el('a','skill-link',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a}catch{return el('span','',label)}}
function skillMarkdownLink(target,label,image){if(image)return el('span','',label?'[Image: '+label+']':'[Image]');return skillLink(target,label)}
function skillGlyph(kind){
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 20 20');svg.setAttribute('aria-hidden','true');svg.classList.add('skill-glyph');
 const path=document.createElementNS(svg.namespaceURI,'path');
 path.setAttribute('d',({folder:'M2.5 5.5h5l1.5 2h8.5v8H2.5z M2.5 5.5v-2h5l1.5 2h8.5v2',video:'M3 4h10v12H3z M13 8l4-3v10l-4-3 M6 7l4 3-4 3z',image:'M3 3h14v14H3z M3 14l4-5 4 4 3-3 3 4 M12 6h.1',file:'M5 2.5h6l4 4v11H5z M11 2.5v4h4 M7.5 10h5 M7.5 13h5',chevron:'m7 5 5 5-5 5'})[kind]||'M5 2.5h10v15H5z');svg.append(path);return svg
}
function ensureSkillExplorer(){
 let shell=view.querySelector('.skill-explorer');if(shell)return shell;
 view.replaceChildren();shell=el('div','skill-explorer');
 const nav=el('aside','skill-tree-panel');nav.setAttribute('aria-label','Skill files');
 const head=el('div','skill-tree-head');head.append(el('h1','','Skills'));
 const refreshButton=button('Refresh',async()=>{refreshButton.disabled=true;try{await refresh();renderSkillsRoute()}catch{toast('Could not refresh skills. Try again.')}finally{refreshButton.disabled=false}});
 head.append(refreshButton);
 const search=el('input','skill-tree-search');search.type='search';search.placeholder='Find a file…';search.setAttribute('aria-label','Find a skill file');
 search.value=skillTreeQuery;search.oninput=()=>{skillTreeQuery=search.value;renderSkillTree()};
 search.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();skillTreeQuery='';search.value='';renderSkillTree();focusSkillTree()}else if(e.key==='ArrowDown'||e.key==='Enter'){e.preventDefault();e.stopPropagation();const row=visibleSkillRows()[0];row?.focus()}};
 const tree=el('ul','skill-tree');tree.setAttribute('role','tree');tree.setAttribute('aria-label','Skills and files');tree.addEventListener('keydown',handleSkillTreeKey);

 nav.append(head,search,tree);
 const pane=el('section','skill-document-pane');pane.setAttribute('aria-label','File viewer');pane.tabIndex=-1;
 let scrollTimer;pane.addEventListener('scroll',()=>{if(skillReaderKey)skillScroll.set(skillReaderKey,pane.scrollTop);clearTimeout(scrollTimer);scrollTimer=setTimeout(saveSkillPlace,120)},{passive:true});
 shell.append(nav,pane);view.append(shell);return shell
}
function currentSkillTreeKey(){return opened?.startsWith('skills:')?opened+'|'+skillFile():opened||''}
function revealSkillFile(){
 if(!opened?.startsWith('skills:'))return;
 skillExpanded.add(opened);const parts=skillFile().split('/');parts.pop();let path='';
 for(const part of parts){path=path?path+'/'+part:part;skillExpanded.add(opened+'|'+path)}
}
function skillOpen(id,file='SKILL.md',focusReader=false){
 const pane=view.querySelector('.skill-document-pane');if(pane&&skillReaderKey)skillScroll.set(skillReaderKey,pane.scrollTop);
 opened=id;selected=id;mode='skills';backTarget=null;
 history.pushState(null,'',skillHash(id,file));skillTreeFocus=id.startsWith('skills:')?id+'|'+file:id;
 revealSkillFile();renderSkillsRoute();view.querySelector('.skill-explorer')?.classList.remove('show-files');document.body.classList.remove('sidebar-open');
 if(focusReader)requestAnimationFrame(()=>focusSkillReader());saveSkillPlace()
}
function renderSkillsRoute(){
 skillImageResize?.disconnect();
 const shell=ensureSkillExplorer();
 if(!catalogReady){renderSkillTree();const pane=shell.querySelector('.skill-document-pane');pane.replaceChildren(el('p','skill-loading',catalogError?'Could not load skills. Use Refresh to retry.':'Loading skills…'));return true}
 if(!opened&&skillList().length){
  const prior=skillList().find(i=>i.id===skillLastSelection?.id),item=prior||skillList()[0];
  opened=item.id;selected=item.id;const file=prior&&item.files?.some(f=>f.path===skillLastSelection.file)?skillLastSelection.file:'SKILL.md';
  history.replaceState(null,'',skillHash(item.id,file));if(!prior){skillExpanded.add(item.id+'|references');skillExpanded.add(item.id+'|evals')}
 }
 if(skillLastRoute!==location.hash){revealSkillFile();skillLastRoute=location.hash}
 if(opened?.startsWith('skills:')&&skillFile().startsWith('exemplars/'))history.replaceState(null,'',skillHash(opened,skillFile().replace('exemplars/','examples/')));
 if(opened?.startsWith('example-')){const ex=skillExtras.examples.find(e=>'example-'+e.id===opened),item=ex&&skillList().find(i=>i.folder===ex.folder);if(item){opened=item.id;history.replaceState(null,'',skillHash(item.id,'evals/comparison.md'));revealSkillFile()}}
 if(opened?.startsWith('skills:')){skillLastSelection={id:opened,file:skillFile()};saveSkillPlace()}
 renderSkillTree();activeSkillDocument=null;skillReadSequence++;
 document.title=skillRouteTitle()+' · '+state.name;$('#breadcrumb').replaceChildren(document.createTextNode(state.name),el('span','','/'),document.createTextNode('Skills'));
 if(opened==='template')renderSkillTemplate();
 else if(opened==='examples')renderSkillExamples();
 else if(opened==='research')renderSkillResearch();
 else if(opened?.startsWith('example-'))renderSkillExample(opened.slice(8));
 else if(opened?.startsWith('skills:'))renderSkillDocument();
 else skillArticle('No skills available','Refresh to reconnect your configured skill folders.');
 return true
}
function skillArticle(title,description){
 const pane=ensureSkillExplorer().querySelector('.skill-document-pane');
 skillReaderKey=currentSkillTreeKey();pane.replaceChildren();
 const wrap=el('article','reader skill-reader'),actions=el('div','reader-actions');
 const files=button('Files',()=>toggleSkillFiles(),'skill-files-toggle');files.setAttribute('aria-label','Show skill files');actions.append(files);
 wrap.append(actions,el('h1','',title));if(description)wrap.append(el('p','description',description));pane.append(wrap);
 requestAnimationFrame(()=>{if(pane.contains(wrap))pane.scrollTop=skillScroll.get(skillReaderKey)||0});
 return {wrap,actions}
}
function showSkillFiles(){ensureSkillExplorer().classList.add('show-files');if(document.body.classList.contains('workspace-shell-v5'))document.body.classList.add('sidebar-open')}
function toggleSkillFiles(){if(document.body.classList.contains('workspace-shell-v5')){document.body.classList.toggle('sidebar-open');if(document.body.classList.contains('sidebar-open'))focusSkillTree();return}const shell=ensureSkillExplorer();shell.classList.toggle('show-files');if(shell.classList.contains('show-files'))focusSkillTree();else focusSkillReader()}
function focusSkillTree(){const row=visibleSkillRows().find(r=>r.dataset.treeKey===(skillTreeFocus||currentSkillTreeKey()))||visibleSkillRows()[0];row?.focus({preventScroll:true});row?.scrollIntoView({block:'nearest'})}
function focusSkillReader(){const pane=view.querySelector('.skill-document-pane');const h=pane?.querySelector('h1');if(h){h.tabIndex=-1;h.focus({preventScroll:true})}else pane?.focus({preventScroll:true})}
function visibleSkillRows(){return [...view.querySelectorAll('.skill-tree [role="treeitem"]')].filter(n=>!n.closest('[hidden]'))}
function renderSkillTree(){
 const tree=view.querySelector('.skill-tree');if(!tree)return;
 const hadFocus=tree.contains(document.activeElement),oldTop=tree.scrollTop,focused=document.activeElement?.dataset.treeKey;
 tree.replaceChildren();const query=skillTreeQuery.trim().toLowerCase(),selectedKey=currentSkillTreeKey();
 function node(parent,data,level){
  const li=el('li','skill-tree-row');li.setAttribute('role','treeitem');li.setAttribute('aria-level',level);li.setAttribute('aria-label',data.label);li.dataset.treeKey=data.key;li.tabIndex=-1;
  const folder=!!data.children,expanded=folder&&(query||skillExpanded.has(data.key));
  if(folder)li.setAttribute('aria-expanded',String(!!expanded));else li.setAttribute('aria-selected',String(data.key===selectedKey));
  if(data.disabled)li.setAttribute('aria-disabled','true');
  const line=el('div','skill-tree-line');line.style.paddingLeft=(10+(level-1)*16)+'px';
  const chevron=skillGlyph('chevron');chevron.classList.add('skill-tree-chevron');if(!folder)chevron.style.visibility='hidden';line.append(chevron);
  if(data.number)line.append(el('span','skill-tree-number',data.number));else line.append(skillGlyph(folder?'folder':data.kind==='image'?'image':data.kind==='video'?'video':'file'));
  const label=el('span','skill-tree-name',data.label);line.append(label);line.title=data.full||data.label;if(data.children&&data.label==='evals')line.append(el('span','skill-tree-count',String(data.children.length)));li.append(line);parent.append(li);
  li._skillNode=data;
  const act=()=>{if(data.disabled)return toast('This file type cannot be previewed.');if(folder){if(skillExpanded.has(data.key))skillExpanded.delete(data.key);else skillExpanded.add(data.key);skillTreeFocus=data.key;renderSkillTree();saveSkillPlace()}else{skillOpen(data.id,data.file||'SKILL.md');focusSkillTree()}};
  line.onclick=e=>{e.stopPropagation();li.focus();act()};
  li.addEventListener('focus',e=>{if(e.target!==li)return;skillTreeFocus=data.key;for(const row of tree.querySelectorAll('[role="treeitem"]'))row.tabIndex=row===li?0:-1});
  li._activate=act;
  if(folder){const group=el('ul','skill-tree-group');group.setAttribute('role','group');group.hidden=!expanded;li.append(group);for(const child of data.children)node(group,child,level+1)}
 }
 for(const item of skillList()){
  const paths=item.files||[{path:'SKILL.md',readable:true}],matches=paths.filter(f=>!query||(item.title+' '+item.folder+' '+f.path).toLowerCase().includes(query));if(!matches.length)continue;
  const children=[],dirs=new Map([['',children]]);
  for(const file of matches){
   const parts=file.path.split('/');let prefix='';
   for(const part of parts.slice(0,-1)){const next=prefix?prefix+'/'+part:part;if(!dirs.has(next)){const branch=[];dirs.get(prefix).push({key:item.id+'|'+next,label:part,children:branch});dirs.set(next,branch)}prefix=next}
   dirs.get(prefix).push({key:item.id+'|'+file.path,label:parts.at(-1),full:file.path,id:item.id,file:file.path,kind:file.kind,disabled:!file.readable})
  }
  function sort(list){list.sort((a,b)=>{const rank=n=>n.file==='SKILL.md'?0:n.file==='AGENTS.md'?1:n.children?({references:2,examples:3,evals:4}[n.label]||5):6;return rank(a)-rank(b)||a.label.localeCompare(b.label)});for(const n of list)if(n.children)sort(n.children)}sort(children);
  node(tree,{key:item.id,label:item.title,number:item.key,children},1)
 }
 const extras=[['template','Template.md',!!skillExtras.template],['research','Research.md',!!skillExtras.research]];
 for(const [id,label,available] of extras)if(available&&(!query||label.toLowerCase().includes(query)))node(tree,{key:id,label,id},1);
 if(!tree.children.length){const msg=el('li','skill-tree-empty',catalogReady?'No matching files.':'Loading files…');msg.setAttribute('role','none');tree.append(msg)}
 const rows=visibleSkillRows(),target=rows.find(r=>r.dataset.treeKey===(focused||skillTreeFocus))||rows.find(r=>r.dataset.treeKey===selectedKey)||rows[0];if(target)target.tabIndex=0;
 tree.scrollTop=oldTop;if(hadFocus)target?.focus({preventScroll:true})
}
function handleSkillTreeKey(e){
 if(e.metaKey||e.ctrlKey||e.altKey)return;
 const row=e.target.closest('[role="treeitem"]');if(!row)return;
 const rows=visibleSkillRows(),at=rows.indexOf(row),data=row._skillNode;let target;
 if(e.key==='ArrowDown')target=rows[Math.min(at+1,rows.length-1)];
 else if(e.key==='ArrowUp')target=rows[Math.max(at-1,0)];
 else if(e.key==='Home')target=rows[0];
 else if(e.key==='End')target=rows.at(-1);
 else if(e.key==='ArrowRight'){if(data.children){if(row.getAttribute('aria-expanded')==='false')row._activate();else target=row.querySelector('[role="group"]>[role="treeitem"]')}}
 else if(e.key==='ArrowLeft'){if(data.children&&row.getAttribute('aria-expanded')==='true')row._activate();else target=row.parentElement.closest('[role="treeitem"]')}
 else if(e.key==='Enter'||e.key===' '){row._activate()}
 else if(e.key==='Tab')return;
 else return;
 e.preventDefault();e.stopPropagation();target?.focus({preventScroll:true});target?.scrollIntoView({block:'nearest'})
}
function skillKeydown(e){
 if(mode!=='skills'||document.querySelector('dialog[open]')||!$('#modes').hidden||e.isComposing)return false;
 if(e.altKey)return false;
 const target=e.target,typing=target.closest?.('input,textarea,select,[contenteditable="true"]');
 if(e.metaKey||e.ctrlKey){
  if(e.key.toLowerCase()==='p'){e.preventDefault();if(e.shiftKey)view.querySelector('.skill-more')?.click();else{showSkillFiles();view.querySelector('.skill-tree-search')?.focus()}return true}
  if(e.key.toLowerCase()==='s'){e.preventDefault();if(activeSkillDocument?.key)skillSave(activeSkillDocument);return true}
  return false
 }
 if(typing)return false;
 if(e.key==='F6'&&target.closest?.('.skill-explorer')){e.preventDefault();if(target.closest('.skill-tree-panel'))focusSkillReader();else focusSkillTree();return true}
 if(!target.closest?.('.skill-explorer'))return false;
 if(e.key==='/'){e.preventDefault();showSkillFiles();view.querySelector('.skill-tree-search').focus();return true}
 if(e.key==='Escape'){e.preventDefault();showSkillFiles();focusSkillTree();return true}
 if(e.key.toLowerCase()==='c'){e.preventDefault();if(activeSkillDocument)copy(activeSkillDocument.text);return true}
 const item=skillList().find(i=>i.key===e.key);
 if(item&&!e.repeat){e.preventDefault();skillOpen(item.id);focusSkillTree();return true}
 return false
}
function renderSkillTemplate(){
 const {wrap,actions}=skillArticle('Skill template');const text=skillExtras.template;if(!text){wrap.append(el('p','empty','Template unavailable. Refresh to try again.'));return}
 const starter=text.match(/```markdown\n([\s\S]*?)```/)?.[1]||text;activeSkillDocument={text,body:text};
 actions.append(el('span','skill-file-path','Template.md'),button('Copy SKILL.md',()=>copy(starter),'primary'),button('Copy guide',()=>copy(text)));
 const body=el('div','prose skill-prose');body.append(skillMarkdown(text.replace(/^# [^\n]+\n/,''),skillMarkdownLink,true));wrap.append(body)
}
function renderSkillResearch(){
 const {wrap,actions}=skillArticle('Creative direction research');actions.append(el('span','skill-file-path','Research.md'),button('Copy',()=>copy(skillExtras.research),'primary'));activeSkillDocument={text:skillExtras.research};
 const body=el('div','prose skill-prose');body.append(skillMarkdown(skillExtras.research,skillMarkdownLink,true));wrap.append(body)
}

/* Per-document drafts and conditional saves. Unedited Markdown stays byte-for-byte intact. */
const skillEdits=new Map();
let skillActiveEdit=null;
function skillDraftKey(key){return 'workspace-skill-draft:'+key}
function skillKeepDraft(record){
 try{
  if(record.text===record.saved&&!record.pending)sessionStorage.removeItem(skillDraftKey(record.key));
  else sessionStorage.setItem(skillDraftKey(record.key),JSON.stringify({text:record.text,saved:record.saved,sha256:record.sha256,pending:record.pending}));
  record.storageFailed=false;
 }catch{record.storageFailed=true}
}
function skillChange(record,text){
 record.text=text;record.body=text;if(!record.conflict)record.error='';skillKeepDraft(record);skillPaintSave(record);
 clearTimeout(record.timer);record.timer=setTimeout(()=>skillSave(record),900);
}
function skillPaintSave(record){
 if(record.statusNode?.isConnected){
  record.statusNode.textContent=record.busy?'Saving…':record.error?(record.conflict?'Changed elsewhere':'Not saved'):record.text!==record.saved?'Unsaved':record.editable?'Saved':'Read only';
  record.statusNode.classList.toggle('has-error',!!record.error);
 }
 if(record.notice?.isConnected){
  record.notice.replaceChildren();record.notice.hidden=!record.error&&!record.storageFailed;
  if(record.error){record.notice.append(el('span','',record.error),button(record.conflict?'Compare versions':'Retry',()=>record.conflict?skillCompare(record):skillSave(record)),button('Download draft',()=>download(record.file.split('/').pop(),record.text,'text/markdown')))}
  else if(record.storageFailed)record.notice.append(el('span','','Draft recovery is unavailable. Keep this tab open until Saved.'));
 }
}
async function skillSave(record){
 clearTimeout(record.timer);
 if(record.busy||record.conflict||!record.editable||record.text===record.saved&&!record.pending)return;
 if(!record.pending)record.pending={id:record.id.slice(7),file:record.file,text:record.text,sha256:record.sha256,requestId:crypto.randomUUID()};
 skillKeepDraft(record);record.busy=true;record.error='';skillPaintSave(record);
 try{
  const result=await api('/api/skill-save',record.pending);
  record.saved=result.text;record.sha256=result.sha256;record.pending=null;
  const item=find(record.id);if(item&&record.file==='SKILL.md'){item.body=result.text;item.sha256=result.sha256}
 }catch(error){
  record.error=error.message;record.conflict=error.httpStatus===409;
  if(error.httpStatus===400)record.pending=null;
 }finally{
  record.busy=false;skillKeepDraft(record);skillPaintSave(record);
  if(!record.error&&record.text!==record.saved)skillSave(record);
 }
}
window.addEventListener('beforeunload',e=>{
 if([...skillEdits.values()].some(r=>r.busy||r.pending||r.text!==r.saved)){e.preventDefault();e.returnValue=''}
});
function skillDialog(title){
 const dialog=el('dialog','skill-dialog'),head=el('div','skill-dialog-head');head.append(el('h2','',title),button('Close',()=>dialog.close()));
 dialog.append(head);document.body.append(dialog);const prior=document.activeElement;
 dialog.addEventListener('close',()=>{dialog.remove();if(prior?.isConnected)prior.focus()});
 dialog.showModal();return dialog
}
async function skillCompare(record){
 const dialog=skillDialog('This file changed elsewhere');
 dialog.append(el('p','','Your draft is kept. Compare it with the saved file before choosing what to keep.'));
 try{
  const latest=await api('/api/skill-doc/'+encodeURIComponent(record.id.slice(7))+'?file='+encodeURIComponent(record.file));
  const columns=el('div','skill-compare-drafts');
  for(const [title,text] of [['Your draft',record.text],['Saved file',latest.text]]){
   const section=el('section');section.append(el('h3','',title),el('pre','',text));columns.append(section)
  }
  dialog.append(columns,button('Copy my draft',()=>copy(record.text)),button('Use saved file',()=>{
   download(record.file.split('/').pop()+'.draft.md',record.text,'text/markdown');
   record.text=record.saved=latest.text;record.sha256=latest.sha256;record.pending=null;record.conflict=false;record.error='';skillKeepDraft(record);dialog.close();renderSkillsRoute()
  }),button('Save my draft over this version',()=>{
   record.sha256=latest.sha256;record.saved=latest.text;record.pending=null;record.conflict=false;record.error='';dialog.close();skillSave(record)
  }))
 }catch(e){dialog.append(el('p','',e.message))}
}
async function skillHistory(record){
 const dialog=skillDialog('Version history');dialog.append(el('p','muted','Restoring creates a new revision.'));
 try{
  const result=await api('/api/skill-history/'+encodeURIComponent(record.id.slice(7))+'?file='+encodeURIComponent(record.file));
  if(!result.versions.length)dialog.append(el('p','','No edits in Workspace yet.'));
  for(const version of result.versions){
   const detail=el('details','skill-history-version');
   detail.append(el('summary','','Before '+new Date(version.created*1000).toLocaleString()),el('pre','',version.text),
    button('Copy this version',()=>copy(version.text)),
    button('Restore this version',()=>{
     if(record.busy||record.text!==record.saved||record.error)return toast('Save or resolve the current draft first.');
     skillChange(record,version.text);dialog.close();renderSkillsRoute();skillSave(record)
    }));
   dialog.append(detail)
  }
 }catch(e){dialog.append(el('p','',e.message))}
}
function skillBlocks(text){
 const match=text.match(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/);
 const prefix=match?.[0]||'',lines=text.slice(prefix.length).match(/[^\n]*\n|[^\n]+$/g)||[];
 const blocks=[];let raw='',fence='';
 const flush=()=>{if(raw){blocks.push({raw});raw=''}};
 for(const line of lines){
  const mark=line.match(/^\s*(\x60{3,}|~{3,})/);
  if(mark){raw+=line;if(!fence)fence=mark[1][0];else if(mark[1][0]===fence){fence='';flush()}continue}
  if(!fence&&/^\s*$/.test(line)){flush();blocks.push({raw:line,blank:true});continue}
  if(!fence&&/^#{1,6}\s/.test(line)){flush();blocks.push({raw:line});continue}
  raw+=line
 }
 flush();return {prefix,blocks}
}
function skillDocumentLinks(item,file,wrap){
 return (target,label,image)=>{
  if(image)return skillRelativeImage(item,file,target,label);
  if(target.startsWith('#')){const a=el('a','',label);a.href=target;a.onclick=e=>{e.preventDefault();wrap.querySelector('[id="'+CSS.escape(target.slice(1))+'"]')?.scrollIntoView({block:'start'})};return a}
  if(/^https?:\/\//.test(target)){
   try{const u=new URL(target);if(u.origin===location.origin&&u.hash.startsWith('#skills/example-')){
    const a=el('a','',label);a.href=skillHash(item.id,'evals/comparison.md');a.onclick=e=>{e.preventDefault();skillOpen(item.id,'evals/comparison.md',true)};return a
   }}catch{}
   return skillLink(target,label)
  }
  if(/^[a-z]+:/i.test(target)||target.startsWith('/')||target.includes('\\'))return el('span','',label);
  try{
   const u=new URL(target,'http://skill.invalid/'+file);let relative=decodeURIComponent(u.pathname.slice(1));
   relative=relative.replace(/^exemplars\//,'examples/');
   const a=el('a','',label);a.href=skillHash(item.id,relative);
   a.onclick=e=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;e.preventDefault();skillOpen(item.id,relative,true)};return a
  }catch{return el('span','',label)}
 }
}
function skillInlineComparison(ex){
 const section=el('section','skill-inline-eval'),tabs=el('div','skill-comparison'),frame=el('iframe','skill-example-frame');
 frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-downloads');frame.setAttribute('referrerpolicy','no-referrer');
 const link=skillLink(ex.runs.TEST.url,'Open separately ↗');let buttons=[];
 function choose(arm){
  const run=ex.runs[arm];frame.src=run.url;frame.title=ex.title+' — '+(arm==='TEST'?'with the skill':'without the skill');link.href=run.url;
  buttons.forEach(([key,b])=>{b.classList.toggle('primary',key===arm);b.setAttribute('aria-pressed',String(key===arm))});
 }
 for(const [arm,label] of [['TEST','With the skill'],['CONTROL','Without the skill']]){
  const b=button(label,()=>choose(arm));buttons.push([arm,b]);tabs.append(b)
 }
 tabs.setAttribute('role','group');tabs.setAttribute('aria-label','Compare example versions');tabs.append(link);section.append(tabs,frame);choose('TEST');
 const details=el('details','skill-record');details.append(el('summary','','Brief and original evidence'),el('p','',ex.brief||''),el('p','',ex.note||''));
 for(const [arm,run] of Object.entries(ex.runs)){
  details.append(el('h3','',arm==='TEST'?'With the skill':'Without the skill'),el('p','muted',run.status+' · '+run.model+' · '+Math.round(run.elapsed_seconds)+' seconds'),el('p','muted','Output SHA-256: '+run.output_hash));
  const links=el('div','skill-files');
  for(const file of run.files.filter(f=>f==='notes.md'||f==='study.mp4'||f.startsWith('source/')||/contact-sheet|technical-checks/.test(f)))links.append(skillLink(new URL(file,run.url).href,file));
  details.append(links)
 }
 section.append(details);return section
}
async function renderSkillDocument(){
 const item=find(opened);if(!item){skillArticle('Skill unavailable','Refresh to reconnect the source.');return}
 const id=opened,file=skillFile(),key=currentSkillTreeKey(),sequence=skillReadSequence;
 const {wrap,actions}=skillArticle('');wrap.querySelector('h1')?.remove();wrap.classList.add('skill-editable-reader');
 const path=el('span','skill-file-path',item.folder+' / '+file);path.title=path.textContent;
 const status=el('span','skill-save-state','Loading…');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const menuButton=button('•••',()=>{menu.hidden=!menu.hidden;menuButton.setAttribute('aria-expanded',String(!menu.hidden));if(!menu.hidden)menu.querySelector('button')?.focus()},'skill-more');
 menuButton.setAttribute('aria-label','File actions');menuButton.setAttribute('aria-haspopup','menu');menuButton.setAttribute('aria-expanded','false');
 const menu=el('div','skill-file-menu');menu.hidden=true;menu.setAttribute('role','menu');
 actions.append(path,status,menuButton,menu);
 const notice=el('div','skill-save-notice');notice.hidden=true;notice.setAttribute('role','alert');
 const body=el('div','prose skill-prose skill-editable-body');body.textContent='Loading file…';wrap.append(notice,body);
 let record;
 function closeMenu(){menu.hidden=true;menuButton.setAttribute('aria-expanded','false')}
 menu.addEventListener('keydown',e=>{
  const buttons=[...menu.querySelectorAll('button')],at=buttons.indexOf(document.activeElement);
  if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeMenu();menuButton.focus()}
  if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();e.stopPropagation();buttons[(at+(e.key==='ArrowDown'?1:buttons.length-1))%buttons.length]?.focus()}
 });
 menu.addEventListener('focusout',()=>setTimeout(()=>{if(!menu.contains(document.activeElement)&&document.activeElement!==menuButton)closeMenu()},0));
 function action(label,fn){const b=button(label,()=>{closeMenu();fn()});b.setAttribute('role','menuitem');menu.append(b)}
 function draw(){
  if(!body.isConnected)return;body.replaceChildren();
  if(skillViewMode==='source'||!/\.md$/i.test(file)){
   const input=el('textarea','skill-source-editor');input.value=record.text;input.readOnly=!record.editable;input.setAttribute('aria-label','Markdown source');input.spellcheck=false;
   const size=()=>{input.style.height='auto';input.style.height=Math.max(400,input.scrollHeight)+'px'};
   input.oninput=()=>{skillChange(record,input.value);size()};input.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();input.blur();showSkillFiles();focusSkillTree();skillSave(record)}};body.append(input);requestAnimationFrame(size);return
  }
  const {prefix,blocks}=skillBlocks(record.text);const links=skillDocumentLinks(item,file,wrap);
  const assemble=()=>prefix+blocks.map(b=>b.raw).join('');
  let nonempty=0;
  blocks.forEach((block,index)=>{
   if(block.blank)return;
   const cell=el('div','skill-edit-block');cell.dataset.block=index;
   function show(){cell.replaceChildren(skillMarkdown(block.raw,links,false));cell.classList.remove('is-editing')}
   show();
   if(record.editable){
    cell.tabIndex=0;cell.setAttribute('aria-label','Edit '+(block.raw.replace(/[#*>\x60]/g,'').trim().slice(0,70)||'section'));
    const begin=()=>{
     if(cell.classList.contains('is-editing'))return;
     const heading=block.raw.match(/^(#{1,6} )([^\r\n]*)(\r?\n)?$/);
     const ending=heading?heading[3]||'':block.raw.match(/(?:\r?\n)+$/)?.[0]||'';
     const input=el('textarea','skill-block-input');input.value=heading?heading[2]:block.raw.slice(0,block.raw.length-ending.length);
     input.setAttribute('aria-label',heading?'Heading text':'Section text');input.spellcheck=true;
     if(heading)input.classList.add('heading-'+heading[1].trim().length);
     const size=()=>{input.style.height='0px';input.style.height=input.scrollHeight+'px'};
     input.oninput=()=>{block.raw=(heading?heading[1]:'')+input.value+ending;skillChange(record,assemble());size()};
     input.onblur=()=>{skillActiveEdit=null;show();skillSave(record)};
     input.onkeydown=e=>{
      if(e.key==='Escape'){e.preventDefault();e.stopPropagation();input.blur();showSkillFiles();focusSkillTree()}
      if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){e.preventDefault();input.blur();cell.focus()}
     };
     cell.classList.add('is-editing');cell.replaceChildren(input);skillActiveEdit=input;size();input.focus();input.setSelectionRange(input.value.length,input.value.length);size()
    };
    cell.onclick=e=>{if(!e.target.closest('a,button,textarea'))begin()};
    cell.onkeydown=e=>{if(e.target===cell&&['Enter',' '].includes(e.key)){e.preventDefault();e.stopPropagation();begin()}}
   }
   body.append(cell);nonempty++;
   if(file==='evals/comparison.md'&&nonempty===2){
    const ex=skillExtras.examples.find(e=>e.folder===item.folder);if(ex)body.append(skillInlineComparison(ex))
   }
  });
  if(!blocks.some(b=>!b.blank)&&record.editable){
   body.append(button('Start writing…',()=>{skillViewMode='source';draw();body.querySelector('textarea')?.focus()}))
  }
 }
 try{
  const doc=await api('/api/skill-doc/'+encodeURIComponent(id.slice(7))+'?file='+encodeURIComponent(file));
  if(mode!=='skills'||opened!==id||sequence!==skillReadSequence)return;
  if(doc.kind==='video'){renderSkillVideo(doc,item);return}
  if(doc.kind==='image'){renderSkillImage(doc,item,key);return}
  record=skillEdits.get(key);
  if(!record||record.text===record.saved&&!record.pending&&!record.busy){
   record={key,id,file,text:doc.text,saved:doc.text,sha256:doc.sha256,editable:doc.editable,error:'',pending:null};skillEdits.set(key,record);
   try{
    const draft=JSON.parse(sessionStorage.getItem(skillDraftKey(key))||'null');
    if(draft&&(draft.text!==draft.saved||draft.pending)){
     Object.assign(record,draft);
     if(doc.sha256!==record.sha256&&doc.text!==record.pending?.text){record.conflict=true;record.error='The saved file changed while you were away. Your draft is kept.'}
     else if(!record.pending&&record.text!==record.saved)record.error='Recovered your unsaved draft.';
    }
   }catch{}
  }
  record.body=record.text;record.statusNode=status;record.notice=notice;activeSkillDocument=record;
  action(skillViewMode==='source'?'Document view':'Markdown source',()=>{skillViewMode=skillViewMode==='source'?'read':'source';renderSkillsRoute()});
  action('Copy file',()=>copy(record.text));action('Download',()=>download(file.split('/').pop(),record.text,'text/markdown'));
  if(file==='SKILL.md')action('Use in run',()=>prepareSkillRun(item.id));action('Version history',()=>skillHistory(record));action('Add to canvas',()=>pin(item.id));
  draw();skillPaintSave(record);
  requestAnimationFrame(()=>{if(wrap.isConnected)view.querySelector('.skill-document-pane').scrollTop=skillScroll.get(key)||0});
  if(record.pending&&!record.conflict)skillSave(record);
 }catch(error){if(mode==='skills'&&sequence===skillReadSequence){status.textContent='Unavailable';body.replaceChildren(el('p','',error.message),button('Try again',()=>renderSkillsRoute()))}}
}

function renderSkillExamples(){const {wrap}=skillArticle('Skill examples','');
 for(const ex of skillExtras.examples){const section=el('section','skill-example-summary');section.append(el('h2','',ex.id+'. '+ex.title),el('p','',ex.description));const a=el('div','skill-example-actions');a.append(button(ex.kind==='video'?'Watch & compare':'Try & compare',()=>skillOpen('example-'+ex.id),'primary'));const i=items.find(i=>i.mode==='skills'&&i.folder===ex.folder);if(i)a.append(button('Read skill',()=>skillOpen(i.id)));section.append(a);wrap.append(section)}if(!skillExtras.examples.length)wrap.append(el('p','empty','No examples have been added.'));wrap.append(el('p','muted','Historical examples; current skill versions have not been evaluated.'))}
function renderSkillExample(id){const ex=skillExtras.examples.find(e=>e.id===id);if(!ex){skillArticle('Example unavailable','Return to Skills to choose another example.');return}const {wrap,actions}=skillArticle(ex.title,ex.description);wrap.classList.add('skill-example-reader');actions.append(button('All examples',()=>skillOpen('examples')));const i=items.find(i=>i.mode==='skills'&&i.folder===ex.folder);if(i)actions.append(button('Read skill',()=>skillOpen(i.id)));
 const choice=new URLSearchParams(location.hash.split('?')[1]||'').get('arm')==='CONTROL'?'CONTROL':'TEST';const run=ex.runs[choice];const tabs=el('div','skill-comparison');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','Compare example versions');for(const [arm,label] of [['TEST','With the skill'],['CONTROL','Without the skill']]){const b=button(label,()=>{history.replaceState(null,'','#skills/example-'+id+(arm==='CONTROL'?'?arm=CONTROL':''));renderSkillExample(id)},arm===choice?'primary':'');b.setAttribute('aria-pressed',String(arm===choice));tabs.append(b)}tabs.append(skillLink(run.url,'Open separately ↗'));wrap.append(tabs);
 const frame=el('iframe','skill-example-frame');frame.title=ex.title+' — '+(choice==='TEST'?'with the skill':'without the skill');frame.src=run.url;frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-downloads');frame.setAttribute('referrerpolicy','no-referrer');wrap.append(frame);
 wrap.append(el('p','muted','Made with an earlier skill version.'));const detail=el('details','skill-record');detail.append(el('summary','','Brief, checks & source files'),el('p','',ex.note||''),el('h2','','Brief'),el('p','',ex.brief||''));detail.append(el('h2','','Recorded run'),el('p','',run.status+' · '+run.model+' · '+Math.round(run.elapsed_seconds)+' seconds'),el('p','muted','Output SHA-256: '+run.output_hash));const links=el('div','skill-files');for(const file of run.files.filter(f=>f==='notes.md'||f==='study.mp4'||f.startsWith('source/')||/contact-sheet|technical-checks/.test(f))){const url=new URL(file,run.url);links.append(skillLink(url.href,file==='notes.md'?'First-return notes':file))}detail.append(links);wrap.append(detail);}


const skillImagePlaces=new Map();
let skillImageResize=null;
function skillAssetURL(id,file,download=false){return '/api/skill-asset/'+encodeURIComponent(id.slice(7))+'?file='+encodeURIComponent(file)+(download?'&download=1':'')}
function skillRelativeImage(item,file,target,label){
 if(/^https?:\/\//i.test(target))return skillLink(target,label||'Open image');
 if(/^[a-z]+:/i.test(target)||target.startsWith('/')||target.includes('\\'))return el('span','',label||'Image unavailable');
 try{
  const relative=decodeURIComponent(new URL(target,'http://skill.invalid/'+file).pathname.slice(1));
  const entry=item.files?.find(f=>f.path===relative&&f.kind==='image'&&f.readable);
  if(!entry)return el('span','',label||'Image unavailable');
  const a=el('a','skill-inline-image');a.href=skillHash(item.id,relative);a.setAttribute('aria-label','Open image: '+(label||relative));
  const img=el('img');img.alt=label||relative.split('/').pop();img.loading='lazy';img.src=skillAssetURL(item.id,relative);
  img.onerror=()=>{a.replaceChildren(el('span','','Image unavailable — '+relative))};
  a.append(img);a.onclick=e=>{if(e.metaKey||e.ctrlKey||e.altKey||e.shiftKey)return;e.preventDefault();skillOpen(item.id,relative,true)};return a
 }catch{return el('span','',label||'Image unavailable')}
}
function renderSkillImage(doc,item,key){
 const {wrap,actions}=skillArticle('');wrap.querySelector('h1')?.remove();wrap.classList.add('skill-editable-reader','skill-image-reader');
 const file=doc.file,path=el('span','skill-file-path',item.folder+' / '+file);path.title=path.textContent;
 const controls=el('div','skill-image-controls');controls.setAttribute('role','group');controls.setAttribute('aria-label','Image zoom');
 const previous=skillImagePlaces.get(key),place=previous||{fit:true,scale:1};
 const stage=el('div','skill-image-stage');stage.tabIndex=0;stage.setAttribute('role','region');stage.setAttribute('aria-label','Image preview. Plus and minus zoom; zero fits the image.');
 const canvas=el('div','skill-image-canvas'),img=el('img','skill-reference-image');img.alt=file.split('/').pop();img.draggable=false;canvas.append(img);stage.append(canvas);
 const meta=el('div','skill-image-meta'),dimensions=el('span','','Loading image…');dimensions.setAttribute('role','status');meta.append(dimensions);
 const scaleLabel=el('span','skill-image-scale','');scaleLabel.setAttribute('aria-live','polite');
 function layout(){
  if(!img.naturalWidth||!stage.isConnected)return;
  if(place.fit)place.scale=Math.min(1,Math.max(24,stage.clientWidth-48)/img.naturalWidth,Math.max(24,stage.clientHeight-48)/img.naturalHeight);
  const w=img.naturalWidth*place.scale,h=img.naturalHeight*place.scale;
  img.style.width=w+'px';img.style.height=h+'px';
  canvas.style.width=Math.max(stage.clientWidth,w+48)+'px';canvas.style.height=Math.max(stage.clientHeight,h+48)+'px';
  scaleLabel.textContent=Math.round(place.scale*100)+'%';fit.setAttribute('aria-pressed',String(place.fit));actual.setAttribute('aria-pressed',String(!place.fit&&place.scale===1));
  less.disabled=place.scale<=.05;more.disabled=place.scale>=8;
  skillImagePlaces.set(key,place)
 }
 function zoom(scale){
  const centerX=(stage.scrollLeft+stage.clientWidth/2)/Math.max(place.scale,.001),centerY=(stage.scrollTop+stage.clientHeight/2)/Math.max(place.scale,.001);
  place.fit=false;place.scale=Math.max(.05,Math.min(8,scale));layout();
  stage.scrollLeft=centerX*place.scale-stage.clientWidth/2;stage.scrollTop=centerY*place.scale-stage.clientHeight/2;
 }
 const fit=button('Fit',()=>{place.fit=true;layout();stage.scrollTo(0,0)}),actual=button('100%',()=>zoom(1));
 const less=button('−',()=>zoom(place.scale/1.25)),more=button('+',()=>zoom(place.scale*1.25));less.setAttribute('aria-label','Zoom out');more.setAttribute('aria-label','Zoom in');
 controls.append(fit,actual,less,scaleLabel,more);
 const original=el('a','skill-image-open','Open original ↗');original.href=skillAssetURL(item.id,file);original.target='_blank';original.rel='noopener noreferrer';
 const save=el('a','skill-image-open','Download');save.href=skillAssetURL(item.id,file,true);save.download=doc.name;
 actions.append(path,original,save);meta.append(controls);
 const notes=file.replace(/\.[^.]+$/,'.md');
 if(item.files?.some(f=>f.path===notes))meta.append(button('Notes',()=>skillOpen(item.id,notes,true)));
 wrap.append(meta,stage);
 const reference='Image reference: '+item.folder+'/'+file+'\nOriginal file: '+doc.path+'\nSHA-256: '+doc.sha256+(notes!==file&&item.files?.some(f=>f.path===notes)?'\nCompanion notes: '+notes:'');
 activeSkillDocument={...doc,text:reference,body:reference}; // Copy/context identifies the asset; it does not claim to attach pixels.
 stage.onkeydown=e=>{
  if(e.metaKey||e.ctrlKey||e.altKey||e.isComposing)return;
  if(['+','=','-','0'].includes(e.key)){e.preventDefault();e.stopPropagation();if(e.key==='0'){place.fit=true;layout();stage.scrollTo(0,0)}else zoom(place.scale*(e.key==='-'?.8:1.25))}
 };
 for(const b of [fit,actual,less,more])b.disabled=true;
 img.onload=()=>{
  if(!wrap.isConnected)return;
  dimensions.textContent=img.naturalWidth+' × '+img.naturalHeight+' · '+file.split('.').pop().toUpperCase();
  for(const b of [fit,actual,less,more])b.disabled=false;layout();
  skillImageResize=new ResizeObserver(()=>{if(stage.isConnected)layout();else skillImageResize?.disconnect()});skillImageResize.observe(stage)
 };
 img.onerror=()=>{dimensions.textContent='Image unavailable';stage.replaceChildren(el('p','','The browser could not display this image.'),button('Try again',()=>renderSkillsRoute()))};
 img.src=skillAssetURL(item.id,file);
 requestAnimationFrame(()=>{if(stage.isConnected&&document.activeElement?.classList.contains('skill-document-pane'))stage.focus({preventScroll:true})});
}


function renderSkillVideo(doc,item){
 const {wrap,actions}=skillArticle('');wrap.querySelector('h1')?.remove();wrap.classList.add('skill-editable-reader','skill-video-reader');
 const path=el('span','skill-file-path',item.folder+' / '+doc.file);path.title=path.textContent;actions.append(path);
 const original=el('a','skill-image-open','Open original ↗');original.href=skillAssetURL(item.id,doc.file);original.target='_blank';original.rel='noopener noreferrer';
 const save=el('a','skill-image-open','Download');save.href=skillAssetURL(item.id,doc.file,true);save.download=doc.name;actions.append(original,save);
 const meta=el('div','skill-image-meta'),info=el('span','','Loading video…');info.setAttribute('role','status');meta.append(info);
 const notes=doc.file.replace(/\.[^.]+$/,'.md');if(item.files?.some(f=>f.path===notes))meta.append(button('Notes',()=>skillOpen(item.id,notes,true)));
 const stage=el('div','skill-video-stage'),video=el('video','skill-reference-video');video.controls=true;video.preload='metadata';video.playsInline=true;video.setAttribute('aria-label',doc.name);
 video.onloadedmetadata=()=>{if(!video.isConnected)return;const seconds=Number.isFinite(video.duration)?Math.round(video.duration):0;info.textContent=video.videoWidth+' × '+video.videoHeight+' · '+Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')+' · '+doc.file.split('.').pop().toUpperCase()};
 video.onerror=()=>{info.textContent='Video unavailable';stage.replaceChildren(el('p','','The browser could not play this video.'),button('Try again',()=>renderSkillsRoute()))};
 video.onkeydown=e=>{if(!e.metaKey&&!e.ctrlKey&&!e.altKey&&e.key!=='Escape')e.stopPropagation()};
 video.src=skillAssetURL(item.id,doc.file);stage.append(video);wrap.append(meta,stage);
 const reference='Video reference: '+item.folder+'/'+doc.file+'\nOriginal file: '+doc.path+'\nSHA-256: '+doc.sha256;
 activeSkillDocument={...doc,text:reference,body:reference}
}
