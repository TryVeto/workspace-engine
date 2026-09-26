function webItems(){return items.filter(i=>i.mode==='web')}
function webAttached(ref){return state.work.filter(w=>(w.sources||[]).includes(ref))}
function webDate(value){try{return new Date(value).toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})}catch{return''}}
function webContext(record){return [
  '# '+record.title,
  'URL: '+record.url,
  'Captured: '+record.capturedAt,
  record.selection?'## Selected text\n'+record.selection:'',
  record.body?'## Page text\n'+record.body:'',
  record.tabs?.length?'## Other open tabs\n'+record.tabs.map(t=>'- '+t.title+' — '+t.url).join('\n'):''
].filter(Boolean).join('\n\n')}
function openWebExternally(i){const a=document.createElement('a');a.href=i.url;a.target='_blank';a.rel='noopener noreferrer';a.click()}
async function openWebInside(i){if(!window.workspaceDesktopWeb)return openWebExternally(i);await window.workspaceDesktopWeb.open(i.url);await window.workspaceDesktopWeb.setVisible(true)}
function attachWeb(i){
 const works=state.work.filter(w=>w.status!=='abandoned');
 if(!works.length)return toast('Create a work item first.');
 editDialog('Attach page to work',form=>{
   const label=el('label','','Work'),select=el('select');select.name='workId';select.setAttribute('aria-label','Work');
   for(const w of works){const o=el('option','',w.title);o.value=w.id;o.selected=(w.sources||[]).includes(i.id);select.append(o)}
   form.append(label,select,el('p','callout','The page becomes a source on the work object. The original capture stays in Web.'));
 },async()=>{
   const id=$('#edit-form').elements.workId.value,w=state.work.find(w=>w.id===id);if(!w)throw Error('Work is no longer available.');
   w.sources||=[];if(!w.sources.includes(i.id))w.sources.push(i.id);await persist();render();toast('Page attached to '+w.title)
 },'Attach');
}
function promptWebURL(newTab=false){
 editDialog(newTab?'New task page':'Open a page',f=>{const u=field(f,'URL','url','https://');u.type='url'},async()=>{
   const raw=$('#edit-form').elements.url.value.trim();let u;try{u=new URL(raw)}catch{throw Error('Enter a complete web address.')}
   if(!['http:','https:'].includes(u.protocol))throw Error('Use an HTTP or HTTPS page.');
   if(!window.workspaceDesktopWeb){openWebExternally({url:u.href});return}
   if(newTab)await window.workspaceDesktopWeb.newTab(u.href);else await window.workspaceDesktopWeb.open(u.href);
 },newTab?'Open new tab':'Open');
}
async function webDesktopControls(parent){
 if(!window.workspaceDesktopWeb)return;
 const bar=el('div','web-desktop-bar'),back=button('←',()=>window.workspaceDesktopWeb.back()),forward=button('→',()=>window.workspaceDesktopWeb.forward()),reload=button('Reload',()=>window.workspaceDesktopWeb.reload()),add=button('+ Tab',()=>promptWebURL(true)),select=el('select');
 select.setAttribute('aria-label','Task page tab');
 async function refresh(){const state=await window.workspaceDesktopWeb.listTabs();select.replaceChildren();for(const tab of state.tabs){const o=el('option','',tab.title||tab.url||'Page');o.value=tab.id;o.selected=tab.id===state.activeId;select.append(o)}back.disabled=!state.tabs.find(t=>t.id===state.activeId)?.canGoBack;forward.disabled=!state.tabs.find(t=>t.id===state.activeId)?.canGoForward}
 select.onchange=async()=>{await window.workspaceDesktopWeb.activate(select.value);await refresh()};
 bar.append(back,forward,reload,select,add);parent.append(bar);await refresh();
 window.workspaceDesktopWeb.onState(()=>refresh().catch(()=>{}));
}
function renderWeb(){
 if(opened)return renderWebReader();
 view.replaceChildren();
 const wrap=el('div','library web-library'),head=el('div','library-head'),intro=el('div');
 intro.append(el('h1','','Web'),el('p','','Pages brought into the work—not another browser.'));
 const open=button('Open task page',()=>promptWebURL(false),'primary');
 head.append(intro,open);wrap.append(head);webDesktopControls(wrap).catch(()=>{});
 const records=webItems(),unattached=records.filter(i=>!webAttached(i.id).length);
 const summary=el('div','web-summary');summary.append(el('strong','',String(records.length)),el('span','',' captured · '+unattached.length+' unattached'));wrap.append(summary);
 const results=el('div','web-results');
 for(const i of records){
   const row=el('div','item-row web-row');row.dataset.item=i.id;row.tabIndex=selected===i.id?0:-1;row.onfocus=()=>selectRow(row,false);
   row.onkeydown=e=>{if(e.target===row&&['Enter','ArrowRight'].includes(e.key)){e.preventDefault();navigate('web',i.id)}};
   const openItem=button('',()=>navigate('web',i.id),'open-item');openItem.append(el('strong','',i.title),el('p','',i.group+' · '+webDate(i.capturedAt)));
   const linked=webAttached(i.id);row.append(icon('web'),openItem,el('span','status '+(linked.length?'done':''),linked.length?linked.length+' work':'Unattached'),button('Attach',()=>attachWeb(i)));
   results.append(row);
 }
 if(!records.length){const empty=el('div','empty');empty.append(el('h2','','Bring the web into the work.'),el('p','','Use the Workspace extension in Dia or Chrome, or open a task page in the desktop shell. Captured pages will appear here.'));results.append(empty)}
 wrap.append(results);view.append(wrap);
}
async function renderWebReader(){
 const i=find(opened);view.replaceChildren();if(!i){view.append(el('p','empty','This page is unavailable.'));return}
 const wrap=el('article','reader web-reader'),actions=el('div','reader-actions');
 actions.append(button('← Back',goBack),button('Attach to work',()=>attachWeb(i)),button('Open in browser ↗',()=>openWebExternally(i)),button('Work on this page',()=>openWebInside(i),'primary'));
 wrap.append(actions,el('h1','',i.title));
 const meta=el('p','description',i.group+' · '+webDate(i.capturedAt));wrap.append(meta);
 const loading=el('p','muted','Loading captured context…');wrap.append(loading);view.append(wrap);
 try{
   const record=await api('/api/web/'+encodeURIComponent(i.id.slice(4)));
   if(mode!=='web'||opened!==i.id)return;
   loading.remove();
   const attached=webAttached(i.id);if(attached.length){const a=el('p','web-attached','Attached to '+attached.map(w=>w.title).join(' · '));wrap.append(a)}
   const link=el('a','web-url',record.url);link.href=record.url;link.target='_blank';link.rel='noopener noreferrer';wrap.append(link);
   if(record.screenshot){const image=el('img','web-shot');image.src='/api/web-asset/'+encodeURIComponent(record.id);image.alt='Captured page view';wrap.append(image)}
   if(record.selection){const section=el('section','web-section');section.append(el('h2','','Selected text'),prose(record.selection));wrap.append(section)}
   if(record.body){const section=el('section','web-section');section.append(el('h2','','Page context'),prose(record.body.slice(0,50000)));if(record.body.length>50000)section.append(el('p','muted','Preview shortened. Copy agent context includes the complete captured text.'));wrap.append(section)}
   if(record.tabs?.length){const details=el('details','web-tabs'),summary=el('summary','',record.tabs.length+' tabs captured with this page');details.append(summary);for(const tab of record.tabs){const a=el('a','',tab.title||tab.url);a.href=tab.url;a.target='_blank';a.rel='noopener noreferrer';details.append(a)}wrap.append(details)}
   actions.append(button('Copy agent context',()=>copy(webContext(record))));
 }catch(e){loading.textContent=e.message}
}
