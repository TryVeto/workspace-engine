/* Shared finishing details; source content and feature behavior remain owned by their modules. */
(()=>{
 const switcher=document.querySelector('#switcher'),menu=document.querySelector('#modes');
 switcher.querySelector('.chevron').replaceChildren(icon('chevron'));switcher.title='Switch workspace';
 const search=document.querySelector('#search-trigger');for(const n of [...search.childNodes])if(n.nodeType===Node.TEXT_NODE)n.remove();search.prepend(icon('search'));search.querySelector('kbd').textContent='/';
 for(const b of document.querySelectorAll('button'))decorateControl(b);
 document.querySelector('#assistant-toggle').title='Toggle assistant · ⌘J';document.querySelector('.assistant-head button').title='Close assistant';
 function polishMenu(){
  for(const b of menu.querySelectorAll('button')){if(b.dataset.crafted)continue;b.dataset.crafted='true';const mark=b.lastElementChild;if(mark?.tagName==='SPAN'&&mark.textContent.trim()==='✓'){mark.replaceChildren(icon('check'));b.setAttribute('aria-current','page')}b.title=b.querySelector('strong')?.textContent||'';}
  const input=menu.querySelector('input');if(!input||input.dataset.crafted)return;input.dataset.crafted='true';input.autocomplete='off';input.spellcheck=false;
  const empty=el('p','workspace-menu-empty','No matching workspaces.');empty.hidden=true;empty.setAttribute('role','status');menu.append(empty);
  input.addEventListener('input',()=>{empty.hidden=!!menu.querySelector('button:not([hidden])')});
  input.onkeydown=e=>{const visible=[...menu.querySelectorAll('button:not([hidden])')];if(e.key==='Enter'){e.preventDefault();visible[0]?.click()}else if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();(e.key==='ArrowDown'?visible[0]:visible.at(-1))?.focus()}else if(e.key==='Escape'){e.preventDefault();menu.hidden=true;switcher.setAttribute('aria-expanded','false');switcher.focus()}};
 }
 new MutationObserver(polishMenu).observe(menu,{childList:true,subtree:true});polishMenu();
 switcher.addEventListener('click',()=>{if(!menu.hidden){const input=menu.querySelector('input');if(input?.value){input.value='';input.dispatchEvent(new Event('input'))}}});
})();
