/* Current adopted principles live in the revisioned workspace store. */
function principleItems(){return(state.notes||[]).filter(n=>n.kind==='principle').map(n=>({...n,id:'principles:'+n.id,mode:'principles',readonly:true,group:'Principles'}))}
function principlesSidebar(side){for(const i of principleItems())side.append(button(i.title,()=>navigate('principles',i.id),opened===i.id?'active':''))}
function renderPrinciples(){
 view.replaceChildren();const list=principleItems(),chosen=list.find(i=>i.id===opened)||list[0];
 const wrap=el('article','reader principles-reader');
 if(!chosen){wrap.append(el('h1','','Principles'),el('p','','No principles have been added.'));view.append(wrap);return}
 const actions=el('div','reader-actions');actions.append(button('Copy',()=>copy(chosen.body)),button('Download',()=>download(chosen.title+'.md',chosen.body,'text/markdown')));
 wrap.append(actions,el('h1','',chosen.title));
 const body=el('div','prose');body.append(window.skillMarkdown?window.skillMarkdown(chosen.body.replace(/^# [^\n]+\n/,''),(url,label)=>{const a=el('a','',label);if(/^https?:\/\//.test(url)){a.href=url;a.target='_blank';a.rel='noopener noreferrer'}return a}):prose(chosen.body));wrap.append(body);view.append(wrap);
 $('#breadcrumb').replaceChildren(document.createTextNode(state.name),el('span','','/'),document.createTextNode('Principles'),el('span','','/'),document.createTextNode(chosen.title));
 document.title=chosen.title+' · Workspace';
}
