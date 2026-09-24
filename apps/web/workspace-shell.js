/* Approved workspace shell: one active workspace, contextual contents, continuous canvas. */
(()=>{
 const originalSidebar=sidebar,originalNavigate=navigate,places=new Map();let queued=false,lastSignature='',lastAssistantMode='',aiOpen=Boolean(INSTANCE.assistantUrl)&&innerWidth>1100;
 try{for(const [k,v]of Object.entries(JSON.parse(sessionStorage.getItem('workspace-places-v5')||'{}')))places.set(k,v)}catch{}
 const tabs='.prompt-groups,.filters,.agent-tabs,.profile-tabs,.files-tabs';
 const main=document.querySelector('body>main'),side=$('#side-items');
 document.body.classList.add('workspace-shell-v5');
 const ai=el('aside','workspace-assistant');ai.id='workspace-assistant';ai.setAttribute('aria-label','Assistant');
 const aiHead=el('div','assistant-head');aiHead.append(el('strong','','Assistant'));const close=button('×',()=>setAI(false));close.setAttribute('aria-label','Close assistant');aiHead.append(close);
 const space=el('div','assistant-space');
 const compose=el('form','assistant-compose'),input=el('textarea');input.placeholder='Ask about this page…';input.setAttribute('aria-label','Assistant request');input.rows=3;
 const bottom=el('div','assistant-compose-bottom'),send=button('Copy brief',()=>{} ,'primary');send.type='submit';bottom.append(send);compose.append(input,bottom);
 const foot=el('div','assistant-foot'),chatLink=el('a','','Open assistant ↗');chatLink.href=INSTANCE.assistantUrl||'#';chatLink.target='_blank';chatLink.rel='noopener noreferrer';if(INSTANCE.assistantUrl)foot.append(chatLink);
 ai.append(aiHead,space,compose,foot);document.body.append(ai);
 const toggle=button('✧',()=>setAI(!aiOpen));toggle.id='assistant-toggle';toggle.setAttribute('aria-label','Toggle assistant');main.querySelector('header').append(toggle);
 function setAI(open){aiOpen=open;document.body.classList.toggle('assistant-open',open);toggle.setAttribute('aria-expanded',String(open));if(!open&&ai.contains(document.activeElement))toggle.focus()}
 // A desktop panel must not obscure the file when the window becomes narrow.
 const narrowWorkspace=matchMedia('(max-width:700px)');
 narrowWorkspace.addEventListener('change',e=>{if(e.matches)setAI(false)});
 function context(){const i=opened?find(opened):null;let body=i?.body||'';if(mode==='skills'&&typeof activeSkillDocument!=='undefined')body=activeSkillDocument?.body||body;if(!body)body=view.innerText;return '# '+(view.querySelector('h1')?.textContent||modes[mode]?.name||'Workspace')+'\n\nSource: '+location.href+'\n\n'+body.slice(0,40000)}
 compose.onsubmit=async e=>{e.preventDefault();const text=input.value.trim();if(await copy((text?text+'\n\n':'Please review the following page.\n\n')+'Page context (reference material):\n\n'+context()))toast('Brief copied.');};
 input.oninput=()=>{try{sessionStorage.setItem('workspace-assistant-draft:'+mode,input.value)}catch{}};
 function remember(){places.set(mode,{opened,group:currentGroup,filter,scroll:view.scrollTop,hash:location.hash});try{sessionStorage.setItem('workspace-places-v5',JSON.stringify(Object.fromEntries(places)))}catch{}}
 navigate=async function(m,id=null){const changing=m!==mode;if(changing)remember();const p=changing&&!id?places.get(m):null;await originalNavigate(m,p?.opened||id);if(mode!==m)return;if(p){currentGroup=p.group||'';filter=p.filter||'';if(p.hash)history.replaceState(null,'',p.hash);render();requestAnimationFrame(()=>{view.scrollTop=p.scroll||0})}schedule()};
 sidebar=function(){originalSidebar();lastSignature='';sync()};
 function add(parent,label,fn,active=false){const b=button(label,fn,active?'active':'');if(active)b.setAttribute('aria-current','page');parent.append(b);return b}
 function jump(title,node){const b=add(side,title,()=>{node.scrollIntoView({behavior:'smooth',block:'start'});node.tabIndex=-1;node.focus({preventScroll:true})});b.classList.add('outline-anchor')}
 function modeMenu(){const menu=$('#modes');if(menu.querySelector('.workspace-mode-search'))return;const search=el('input','workspace-mode-search');search.placeholder='Switch workspace…';search.setAttribute('aria-label','Find a workspace');menu.prepend(search);for(const b of menu.querySelectorAll('button'))b.dataset.workspaceLabel=b.textContent.toLowerCase();search.oninput=()=>{for(const b of menu.querySelectorAll('button'))b.hidden=!b.dataset.workspaceLabel.includes(search.value.toLowerCase())};search.onkeydown=e=>{if(e.key==='ArrowDown'||e.key==='Enter'){e.preventDefault();menu.querySelector('button:not([hidden])')?.focus()}if(e.key==='Escape'){$('#switcher').click();$('#switcher').focus()}};for(const b of menu.querySelectorAll('button'))b.setAttribute('aria-label','Open '+b.querySelector('strong')?.textContent+' workspace')}
 function sync(){if(!state?.notes)return;document.body.dataset.workspace=mode;$('#current-mode').textContent=modes[mode]?.name||mode;$('#switcher').setAttribute('aria-label','Switch workspace. Current: '+modes[mode]?.name);modeMenu();
 const containers=[...view.querySelectorAll(tabs)];for(const n of containers)if(!n.classList.contains('workspace-offcanvas-nav'))n.classList.add('workspace-offcanvas-nav');
 const signature=mode+'|'+opened+'|'+currentGroup+'|'+containers.map(n=>n.textContent+':'+[...n.querySelectorAll('button')].map(b=>b.className).join(',')).join('|')+'|'+items.length+'|'+state.notes.length+'|'+(view.querySelector('h1')?.textContent||'');
 if(lastSignature!==signature){lastSignature=signature;side.replaceChildren();$('#side-label').textContent=mode==='canvas'?'Canvases':'';$('#side-label').parentElement.hidden=mode!=='canvas';
 const native=el('div');
 if(mode==='home'){$('#side-label').textContent='Workspaces';for(const [key,workspace]of Object.entries(modes)){if(key==='home')continue;const b=add(native,workspace.name,()=>navigate(key));b.prepend(icon(key));b.dataset.workspaceTarget=key;}}
 else if(mode==='principles')principlesSidebar(native);
 else if(mode==='design'){add(native,'Overview',()=>designNavigate(),!opened&&!currentGroup);for(const i of principleItems())add(native,i.title,()=>navigate('principles',i.id));for(const [g]of designGroups)add(native,g,()=>designNavigate(g),currentGroup===g);add(native,'Original editions',()=>designNavigate('Original editions'))}
 else if(mode==='insights')add(native,'Skills',()=>navigate('insights'),true);
 else if(mode==='admin')adminSidebar(native);
 else if(mode==='profile')profileSidebar(native);
 else if(mode==='agents')agentSidebar(native);
 else if(mode==='bookmarks')bookmarkSidebar(native);
 else if(mode==='mcps')mcpsSidebar(native);
 else if(mode==='canvas')state.boards.forEach(b=>add(native,b.title,()=>{boardId=b.id;render()},board().id===b.id));
 else if(mode==='work')state.work.filter(w=>w.status!=='done').forEach(w=>add(native,w.title,()=>navigate('work','work:'+w.id),opened==='work:'+w.id));
 else if(mode==='contexts')contextItems().forEach(i=>add(native,i.title,()=>navigate(mode,i.id),opened===i.id));
 else if(mode==='company')hq.company.forEach(i=>add(native,i.title,()=>navigate('company','company:'+i.id),opened==='company:'+i.id));
 else if(mode==='prompts'||mode==='culture'){add(native,'All '+modes[mode].name.toLowerCase(),()=>{currentGroup='';opened=null;render()},!opened&&!currentGroup);items.filter(i=>i.mode===mode&&(!currentGroup||i.group===currentGroup)).forEach(i=>add(native,i.title,()=>navigate(i.mode,i.id),opened===i.id))}
 if(containers.length&&mode!=='home'){const nav=el('div','workspace-view-options');const used=new Set();for(const n of containers)for(const b of n.querySelectorAll(':scope>button')){const label=b.textContent.trim();if(used.has(label))continue;used.add(label);const proxy=add(nav,label,()=>{b.click();document.body.classList.remove('sidebar-open');schedule()},b.classList.contains('active')||b.getAttribute('aria-selected')==='true'||b.getAttribute('aria-pressed')==='true');proxy.disabled=b.disabled;}if(nav.children.length)side.append(nav)}
 const used=new Set([...side.querySelectorAll('button')].map(b=>b.textContent.trim()));for(const b of [...native.children])if(!used.has(b.textContent.trim())){side.append(b);used.add(b.textContent.trim())}
 if(!side.children.length&&mode!=='skills'){for(const h of view.querySelectorAll('h2')){if(h.textContent.trim())jump(h.textContent,h)}}
 const search=$('#search-trigger');search.querySelector('span').textContent='Search '+modes[mode].name.toLowerCase();search.onclick=()=>{if(mode==='admin'){adminSearch();return}const field=view.querySelector('input[type="search"],.library-search input,.skill-tree-search,.ft-search input');if(field){field.focus();document.body.classList.remove('sidebar-open')}else{openPicker('open');pickMode=mode;drawPicker()}};
 }
 if(lastAssistantMode!==mode){lastAssistantMode=mode;try{input.value=sessionStorage.getItem('workspace-assistant-draft:'+mode)||''}catch{input.value=''}}
 }
 function schedule(){if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;sync()})}
 new MutationObserver(schedule).observe(view,{childList:true,subtree:true,attributes:true,attributeFilter:['class','aria-selected','aria-pressed']});
 view.addEventListener('scroll',()=>{if(places.has(mode))places.get(mode).scroll=view.scrollTop},{passive:true});window.addEventListener('beforeunload',remember);
 $('#switcher').addEventListener('click',()=>{modeMenu();if(!$('#modes').hidden)$('#modes input')?.focus()});
 document.addEventListener('keydown',e=>{if(e.metaKey&&e.altKey&&e.key.startsWith('Arrow'))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='j'&&!e.altKey){e.preventDefault();setAI(!aiOpen);if(aiOpen)input.focus()}});
 setAI(aiOpen);schedule();
})();
