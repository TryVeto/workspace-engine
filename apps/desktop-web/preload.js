const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('workspaceDesktopWeb',{
 setVisible:visible=>ipcRenderer.invoke('web:set-visible',!!visible),open:url=>ipcRenderer.invoke('web:open',url),newTab:url=>ipcRenderer.invoke('web:new-tab',url),listTabs:()=>ipcRenderer.invoke('web:list-tabs'),activate:id=>ipcRenderer.invoke('web:activate',id),close:id=>ipcRenderer.invoke('web:close',id),back:()=>ipcRenderer.invoke('web:back'),forward:()=>ipcRenderer.invoke('web:forward'),reload:()=>ipcRenderer.invoke('web:reload'),context:()=>ipcRenderer.invoke('web:context'),screenshot:()=>ipcRenderer.invoke('web:screenshot'),act:action=>ipcRenderer.invoke('web:act',action),
 onState:fn=>{const handler=(_event,state)=>fn(state);ipcRenderer.on('web:state',handler);return()=>ipcRenderer.removeListener('web:state',handler)}
});
