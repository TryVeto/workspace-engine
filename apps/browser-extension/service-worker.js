const HOST='com.workspace.web';

async function pageSnapshot(tab){
  let context={selection:'',text:'',description:''};
  try{
    const [{result}]=await chrome.scripting.executeScript({
      target:{tabId:tab.id},
      func:()=>({
        selection:String(getSelection?.()?.toString?.()||'').slice(0,20000),
        text:String(document.body?.innerText||'').slice(0,250000),
        description:String(document.querySelector('meta[name="description"]')?.content||'').slice(0,1000)
      })
    });
    context=result||context;
  }catch{}
  let screenshot='';
  try{screenshot=await chrome.tabs.captureVisibleTab(tab.windowId,{format:'jpeg',quality:55})}catch{}
  const tabs=(await chrome.tabs.query({currentWindow:true})).slice(0,100).map(t=>({
    title:t.title||'',url:t.url||'',active:!!t.active,pinned:!!t.pinned
  }));
  return {
    title:tab.title||context.description||'Web page',
    url:tab.url||'',
    selection:context.selection,
    text:context.text,
    screenshot,
    tabs,
    browser:navigator.userAgent,
    capturedAt:new Date().toISOString()
  };
}

async function captureActive(){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id||!/^https?:/i.test(tab.url||''))throw Error('Open a normal web page first.');
  const record=await pageSnapshot(tab);
  const response=await chrome.runtime.sendNativeMessage(HOST,{type:'capture',requestId:crypto.randomUUID(),record});
  if(!response?.ok)throw Error(response?.error||'Workspace did not accept the page.');
  await chrome.storage.local.set({lastCapture:response});
  await chrome.action.setBadgeText({text:'✓',tabId:tab.id});
  setTimeout(()=>chrome.action.setBadgeText({text:'',tabId:tab.id}).catch(()=>{}),1800);
  return response;
}

chrome.runtime.onMessage.addListener((message,_sender,sendResponse)=>{
  if(message?.type!=='capture-active')return;
  captureActive().then(sendResponse).catch(error=>sendResponse({ok:false,error:error.message}));
  return true;
});
chrome.commands.onCommand.addListener(command=>{
  if(command==='send-current-page')captureActive().catch(()=>{});
});
