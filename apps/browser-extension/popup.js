const send=document.querySelector('#send'),status=document.querySelector('#status'),open=document.querySelector('#open');
send.onclick=async()=>{
  send.disabled=true;status.textContent='Sending…';open.hidden=true;
  try{
    const result=await chrome.runtime.sendMessage({type:'capture-active'});
    if(!result?.ok)throw Error(result?.error||'Could not send this page.');
    status.textContent='Sent to Workspace.';
    open.href='http://127.0.0.1:18999'+result.openUrl;open.hidden=false;
  }catch(e){status.textContent=e.message}finally{send.disabled=false}
};
(async()=>{
 const {lastCapture}=await chrome.storage.local.get('lastCapture');
 if(lastCapture?.openUrl){open.href='http://127.0.0.1:18999'+lastCapture.openUrl;open.hidden=false}
})();
