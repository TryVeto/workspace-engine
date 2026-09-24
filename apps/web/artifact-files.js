/* Canonical Workspace artifact home. */
(()=>{
 let data={status:{},artifacts:[]},intake=[],roots=[],source='All sources',selected=null,search='',routeLegacy=null,seq=0,intakeSeq=0,intakeOffset=0,intakeMore=false,searchTimer,active=false;
 const top=["Inbox","Company","Product","Projects","Brand","Archive"];
 const expanded=new Set(["Inbox","Projects"]);
 const E=(t,c='',x='')=>{const n=document.createElement(t);n.className=c;n.textContent=x;return n};
 const B=(x,fn,c='')=>{const b=E('button',c,x);b.type='button';b.onclick=async()=>{try{await fn()}catch(e){toast(e.message)}};return b};
 const bytes=n=>n<1024?n+" B":n<1048576?(n/1024).toFixed(0)+" KB":n<1073741824?(n/1048576).toFixed(1)+" MB":(n/1073741824).toFixed(1)+" GB";
 const short=p=>String(p||'').replace(/^\/Users\/[^/]+\//,'~/');
 const rootName=p=>p.split('/').filter(Boolean).pop()||p;
 function storageLabel(){
  const s=data.status||{};
  if(s.provider==='r2'&&s.ready&&s.verified)return 'Cloudflare R2 · '+(s.bucket||'verified');
  if(s.provider==='r2'&&s.ready)return 'R2 configured · not yet verified';
  if(s.provider==='r2')return 'R2 selected · not configured';
  return 'Stored on this device';
 }
 async function load(){
  const n=++seq;
  const [a,s]=await Promise.all([api('/api/artifacts'),api('/api/files/status')]);
  if(n!==seq||mode!=='files'||!active)return;
  data=a;roots=s.roots||[];
  await fetchIntake();
  if(n!==seq||mode!=='files'||!active)return;
  const ref=String(opened||'');
  if(ref.startsWith('files:artifact-')){
   const id=ref.slice('files:artifact-'.length),artifact=data.artifacts.find(x=>x.id===id);
   if(artifact){selected=id;const parts=artifact.logical_path.split('/');expanded.add(parts[0]);if(parts[0]==='Projects'&&parts[1])expanded.add('Projects/'+parts[1])}
  }
  draw();
 }
 function tabs(root){
  const bar=E('div','files-tabs artifact-tabs');
  bar.append(B('Workspace',()=>{},'active'));
  for(const pair of [['folders','Sources'],['collections','Collections'],['review','Needs review']]){
   const key=pair[0],label=pair[1];
   bar.append(B(label,()=>{active=false;++seq;++intakeSeq;return routeLegacy&&routeLegacy(key)}));
  }
  root.append(bar);
 }
 function draw(){
  if(mode!=='files'||!active)return;
  const focused=document.activeElement,folderFocus=focused?.dataset?.folderPath,rowFocus=focused?.dataset?.artifactId;
  document.title='Files · '+INSTANCE.name;
  const root=E('div','files-page artifact-page'),head=E('div','files-head artifact-head');
  const title=E('div');title.append(E('h1','','Files'),E('p','artifact-subtitle',''));
  const status=E('div','artifact-storage',storageLabel());
  status.classList.toggle('ready',data.status&&data.status.provider==='r2'&&data.status.ready);
  head.append(title,status);root.append(head);tabs(root);
  const grid=E('div','artifact-grid');
  grid.append(drawSources(),drawHome(),drawRight());
  root.append(grid,drawFoot());view.replaceChildren(root);
  if(folderFocus)root.querySelector('[data-folder-path="'+CSS.escape(folderFocus)+'"]')?.focus();
  else if(rowFocus)root.querySelector('[data-artifact-id="'+CSS.escape(rowFocus)+'"]')?.focus();
 }
 function drawSources(){
  const pane=E('aside','artifact-sources'),h=E('div','artifact-pane-head');
  h.append(E('h2','','Sources'));pane.append(h);
  pane.append(B('All sources',()=>{return chooseSource('All sources')},source==='All sources'?'active':''));
  const ordered=[...roots].sort((a,b)=>({Desktop:0,Downloads:1,Documents:2,Projects:3}[rootName(a)]??9)-({Desktop:0,Downloads:1,Documents:2,Projects:3}[rootName(b)]??9));
  for(const p of ordered){
   const b=B(rootName(p),()=>{return chooseSource(p)},source===p?'active':'');
   b.title=p;pane.append(b);
  }
  pane.append(E('p','artifact-source-note','Sources are intake. Placing a file copies and verifies it; the original stays where it is.'));
  return pane;
 }
 function groupArtifacts(){
  const result=new Map(top.map(k=>[k,[]]));
  for(const a of data.artifacts||[]){
   const first=a.logical_path.split('/')[0];
   (result.get(first)||result.get('Inbox')).push(a);
  }
  return result;
 }
 function drawHome(){
  const pane=E('section','artifact-home'),head=E('div','artifact-pane-head'),copybox=E('div');
  copybox.append(E('h2','',INSTANCE.name+' files'),E('p','',''));
  head.append(copybox);pane.append(head);
  const tree=E('div','artifact-tree');tree.setAttribute('role','tree');const groups=groupArtifacts();
  for(const key of top){
   const items=groups.get(key)||[],open=expanded.has(key);
   const folder=B((open?'⌄ ':'› ')+key,()=>{open?expanded.delete(key):expanded.add(key);draw()},'artifact-folder');
   folder.dataset.folderPath=key;folder.setAttribute('aria-level','1');folder.setAttribute('role','treeitem');
   folder.setAttribute('aria-expanded',String(open));
   if(items.length)folder.append(E('span','artifact-count',String(items.length)));tree.append(folder);
   if(!open)continue;
   if(key==='Projects')drawProjects(tree,items);
   else for(const a of items)tree.append(artifactRow(a,1));
   if(!items.length)tree.append(E('p','artifact-empty-row','Nothing here yet.'));
  }
  pane.append(tree);return pane;
 }
 function drawProjects(tree,items){
  const groups=new Map();
  for(const a of items){
   const parts=a.logical_path.split('/'),name=parts[1]||'Unsorted';
   if(!groups.has(name))groups.set(name,[]);groups.get(name).push(a);
  }
  for(const entry of [...groups].sort((a,b)=>a[0].localeCompare(b[0]))){
   const name=entry[0],list=entry[1],key='Projects/'+name,open=expanded.has(key);
   const folder=B((open?'⌄ ':'› ')+name,()=>{open?expanded.delete(key):expanded.add(key);draw()},'artifact-folder project');
   folder.dataset.folderPath=key;folder.setAttribute('role','treeitem');folder.setAttribute('aria-level','2');folder.setAttribute('aria-expanded',String(open));
   folder.style.setProperty('--depth','1');
   folder.append(E('span','artifact-count',String(list.length)));tree.append(folder);
   if(open)for(const a of list)tree.append(artifactRow(a,2));
  }
 }
 function artifactRow(a,depth){
  const row=B('',()=>{selected=a.id;draw()},'artifact-row'+(selected===a.id?' selected':''));
  row.setAttribute('role','treeitem');row.setAttribute('aria-level',String(depth+1));row.setAttribute('aria-selected',String(selected===a.id));
  row.dataset.artifactId=a.id;row.style.setProperty('--depth',String(depth));
  row.append(E('span','artifact-name',a.title),E('span','artifact-meta',bytes(a.size||0)));
  row.title=a.logical_path;return row;
 }
 async function fetchIntake(){
  const request=++intakeSeq;
  const paths=source==='All sources'?roots:[source];
  const pages=await Promise.all(paths.map(p=>api('/api/files/inventory?q='+encodeURIComponent(p+'/ '+search.trim())+'&offset='+intakeOffset)));
  if(request!==intakeSeq||mode!=='files'||!active)return;
  intake=pages.flatMap((page,i)=>(page.files||[]).filter(f=>f.status==='available'&&f.path.startsWith(paths[i]+'/')));
  intake.sort((a,b)=>b.modified-a.modified||a.path.localeCompare(b.path));
  intakeMore=pages.some(p=>intakeOffset+100<p.total);
 }
 async function chooseSource(value){
  source=value;selected=null;intakeOffset=0;await fetchIntake();draw();
 }
 function drawIntake(){
  const list=document.querySelector('.artifact-intake');if(!list||!active)return;
  list.replaceChildren();
  for(const f of intake){
   const row=E('div','artifact-intake-row'),body=E('div');
   body.append(E('strong','',f.path.split('/').pop()),E('small','',short(f.path)));
   const placeButton=B('Place',()=>place(f),'primary');placeButton.setAttribute('aria-label','Place '+f.path.split('/').pop());
   row.append(body,placeButton);list.append(row);
  }
  if(!intake.length)list.append(E('p','empty','No matching local files.'));
  if(intakeOffset||intakeMore){
   const pager=E('div','files-actions');
   if(intakeOffset)pager.append(B('Previous files',async()=>{intakeOffset=Math.max(0,intakeOffset-100);await fetchIntake();drawIntake()}));
   if(intakeMore)pager.append(B('More files',async()=>{intakeOffset+=100;await fetchIntake();drawIntake()}));
   list.append(pager);
  }
 }
 function drawRight(){
  const pane=E('aside','artifact-right'),a=(data.artifacts||[]).find(x=>x.id===selected);
  if(a){drawInspector(pane,a);return pane}
  const head=E('div','artifact-pane-head'),copybox=E('div');
  copybox.append(E('h2','','Where does this belong?'),E('p','','Choose where to keep a copy.'));
  head.append(copybox);pane.append(head);
  const searchbox=E('input','artifact-search');
  searchbox.placeholder='Filter local files…';searchbox.value=search;
  searchbox.setAttribute('aria-label','Filter local files');
  searchbox.oninput=()=>{search=searchbox.value;intakeOffset=0;++intakeSeq;clearTimeout(searchTimer);searchTimer=setTimeout(()=>fetchIntake().then(drawIntake).catch(e=>toast(e.message)),160)};
  pane.append(searchbox);
  pane.append(E('div','artifact-intake'));
  queueMicrotask(drawIntake);return pane;
 }
 function drawInspector(pane,a){
  const head=E('div','artifact-pane-head'),copybox=E('div');
  copybox.append(E('h2','',a.title),E('p','',a.logical_path));head.append(copybox);pane.append(head);
  const facts=E('dl','artifact-facts');
  const pairs=[['Storage',storageLabel()],['Size',bytes(a.size||0)],['Source',short(a.source_path)],['SHA-256',a.sha256||'—']];
  for(const pair of pairs)facts.append(E('dt','',pair[0]),E('dd','',pair[1]));
  pane.append(facts);
  const actions=E('div','files-actions');
  actions.append(B('Open',()=>api('/api/artifacts',{action:'open',id:a.id}),'primary'));
  actions.append(B('Preview',()=>preview(a)),B('History',()=>showHistory(a)),B('Move',()=>move(a)));
  pane.append(actions,B('← Intake',()=>{selected=null;draw()},'artifact-back'));
 }
 async function preview(a){
  const r=await api('/api/artifacts',{action:'preview',id:a.id});
  const prior=document.querySelector('#artifact-preview');if(prior)prior.remove();
  const pre=E('pre','files-preview',r.text+(r.truncated?'\n\n[Preview limited to 20,000 bytes]':''));
  pre.id='artifact-preview';document.querySelector('.artifact-right')?.append(pre);
 }
 async function showHistory(a){
  const versions=await api('/api/artifacts/history?id='+encodeURIComponent(a.id));
  if(selected!==a.id||!active)return;
  document.querySelector('#artifact-history')?.remove();
  const box=E('div');box.id='artifact-history';box.append(E('h3','','Version history'));
  for(const v of versions){box.append(E('p','',new Date(v.created_at).toLocaleString()+' · '+bytes(v.size)+(v.id===a.current_version_id?' · Current':'')),E('small','',v.sha256))}
  document.querySelector('.artifact-right')?.append(box);
 }
 function promptDialog(title,label,value,onSave){
  const prior=document.activeElement,d=E('dialog','files-dialog'),h=E('div','dialog-head'),f=E('form');
  h.append(E('h2','',title),B('×',()=>d.close()));
  const l=E('label','',label),input=E('input');input.value=value;l.append(input);f.append(l);
  const err=E('p','files-error'),actions=E('div','dialog-actions');err.setAttribute('role','alert');
  const save=B('Save',async()=>{
   save.disabled=true;
   try{if(await onSave(input.value,save,err)!==false)d.close()}catch(e){err.textContent=e.message}
   finally{save.disabled=false}
  },'primary');
  actions.append(B('Cancel',()=>d.close()),save);
  f.onsubmit=e=>{e.preventDefault();save.click()};
  d.append(h,f,err,actions);document.body.append(d);
  d.addEventListener('close',()=>{d.remove();if(prior?.isConnected)prior.focus();else document.querySelector('.artifact-row.selected,.artifact-search')?.focus()});
  d.showModal();input.focus();input.select();
 }
 function place(f){
  let confirmedPath=null,confirmedRevision=null;
  promptDialog('Place in Workspace','Canonical location','Inbox/'+f.path.split('/').pop(),async(logical,save,err)=>{
   let dest=logical.trim().replaceAll('\\\\','/');
   if(!dest)dest='Inbox/'+f.path.split('/').pop();
   if(dest.endsWith('/'))dest+=f.path.split('/').pop();
   const existing=data.artifacts.find(a=>a.logical_path===dest);
   if(existing&&(confirmedPath!==dest||confirmedRevision!==existing.revision)){
    confirmedPath=dest;confirmedRevision=existing.revision;
    err.textContent='This location already has a file. Save a new version to keep both.';
    save.textContent='Save new version';return false;
   }
   const r=await api('/api/artifacts',{action:'promote',fileId:f.id,logicalPath:dest,...(existing?{revision:confirmedRevision}:{})});
   selected=r.artifact.id;opened=null;expandArtifact(r.artifact);await load();toast('Verified copy stored. Original preserved.');
  });
 }
 function expandArtifact(a){
  const parts=a.logical_path.split('/');expanded.add(parts[0]);
  if(parts[0]==='Projects'&&parts.length>2)expanded.add('Projects/'+parts[1]);
 }
 function move(a){
  promptDialog('Move artifact','Canonical location',a.logical_path,async logical=>{
   const r=await api('/api/artifacts',{action:'move',id:a.id,revision:a.revision,logicalPath:logical});
   selected=r.artifact.id;opened=null;expandArtifact(r.artifact);await load();toast('Location updated. Object bytes unchanged.');
  });
 }
 function drawFoot(){
  const foot=E('div','artifact-foot'),s=data.status||{};
  foot.append(E('span','',(s.artifacts||0)+' file'+(s.artifacts===1?'':'s')+' · '+bytes(s.logicalBytes||0)));
  const cloud=s.provider==='r2'&&s.ready;
  if(cloud&&!s.verified)foot.append(E('span','','Cloud storage has not been verified yet.'));
  return foot;
 }
 window.renderArtifactFilesHome=legacy=>{
  active=true;routeLegacy=legacy;
  view.replaceChildren(E('div','library','Loading files…'));
  load().catch(e=>view.replaceChildren(E('div','library',e.message)));
 };
 document.addEventListener('keydown',e=>{
  if(mode!=='files'||!active||document.querySelector('dialog[open]')||e.metaKey||e.ctrlKey||e.altKey||e.isComposing)return;
  const tree=e.target.closest('.artifact-tree');
  if(tree&&['ArrowDown','ArrowUp','Home','End','ArrowRight','ArrowLeft'].includes(e.key)){
   const rows=[...tree.querySelectorAll('[role="treeitem"]')],at=rows.indexOf(e.target);
   if(at<0)return;e.preventDefault();
   if(e.key==='ArrowRight'||e.key==='ArrowLeft'){
    if(e.target.hasAttribute('aria-expanded')&&e.target.getAttribute('aria-expanded')===(e.key==='ArrowRight'?'false':'true'))e.target.click();
    else rows[Math.max(0,Math.min(rows.length-1,at+(e.key==='ArrowRight'?1:-1)))]?.focus();
   }else rows[e.key==='Home'?0:e.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,at+(e.key==='ArrowDown'?1:-1)))]?.focus();
   return;
  }
  if(e.key==='/'&&!e.target.matches('input,textarea,select,[contenteditable]')){
   const q=document.querySelector('.artifact-search');if(q){e.preventDefault();q.focus();q.select()}
  }
 });
})();
