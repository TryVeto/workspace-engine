// Explicit skill-run evidence. Ordinary navigation never reports application.
function skillRunRequest(action, run, extra={}) {
 const body={action,runId:run.id||run,...extra};
 const key='skill-run-request:'+JSON.stringify(body);
 let requestId=sessionStorage.getItem(key);
 if(!requestId){requestId=uid();sessionStorage.setItem(key,requestId)}
 return api('/api/skill-runs',{...body,requestId}).then(result=>{sessionStorage.removeItem(key);return result});
}
function prepareSkillRun(skillId=null){
 const runId=uid();
 editDialog('Use a skill',form=>{
  const label=el('label','','Skill'),select=el('select');select.name='skill';
  for(const item of items.filter(x=>x.mode==='skills'&&x.stable!==false)){
   const option=el('option','',item.title);option.value=item.id.replace(/^skills:/,'');select.append(option);
  }
  if(skillId)select.value=skillId.replace(/^skills:/,'');
  label.append(select);form.append(label);
  field(form,'Task','task','').required=true;
  field(form,'Agent or client','client','Workspace').required=true;
 },async()=>{
  const form=$('#edit-form');
  const result=await skillRunRequest('prepare',runId,{skillId:form.elements.skill.value,task:form.elements.task.value,client:form.elements.client.value});
  navigate('insights','run:'+result.id);
 },'Prepare run');
}
function skillRunLabel(stage){return ({prepared:'Prepared',read:'Instructions read',reported_applied:'Reported applied',result_returned:'Result returned',result_reviewed:'Result reviewed'})[stage]||stage}
function skillRunTime(at){return new Date(at).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'medium'})}
async function drawSkillRun(host,run){
 if(String(opened||'').startsWith('run:')){document.title=run.task+' · '+state.name;$('#breadcrumb').textContent=state.name+' / '+run.task}
 const head=el('div','skill-run-head');
 head.append(el('h2','',run.task),el('p','muted',run.client+' · '+run.actor));
 const revision=el('details','skill-run-revision');revision.append(el('summary','','Skill revision'),el('code','',run.revision));
 head.append(revision);host.append(head);
 const timeline=el('ol','skill-run-timeline');
 for(const event of run.events){
  const row=el('li'),title=el('strong','',skillRunLabel(event.stage));
  row.append(title,el('time','muted',skillRunTime(event.at)),el('span','muted',event.actor));
  if(event.artifactId)row.append(el('p','',event.artifactId));
  if(event.outcome)row.append(el('p','',event.outcome[0].toUpperCase()+event.outcome.slice(1)));
  timeline.append(row);
 }
 host.append(timeline);
 const actions=el('div','skill-run-actions');host.append(actions);
 const stages=new Set(run.events.map(x=>x.stage));
 const perform=async action=>{
  try{const result=await skillRunRequest(action,run);if(action==='read'){
    host.replaceChildren();await drawSkillRun(host,result);
    const box=el('details','skill-run-instructions');box.open=true;box.append(el('summary','','Instructions'),el('pre','',result.instructions));host.append(box);

   }else{host.replaceChildren();drawSkillRun(host,result)}
  }catch(error){toast(error.message)}
 };
 if(!stages.has('read'))actions.append(button('Read instructions',()=>perform('read'),'primary'));
 else if(!stages.has('reported_applied'))actions.append(button('Report applied',()=>perform('reported_applied'),'primary'));
 else if(!stages.has('result_returned'))actions.append(button('Return result',()=>{
  editDialog('Return result',form=>field(form,'Artifact or result reference','artifact',''),async()=>{
   const result=await skillRunRequest('result_returned',run,{artifactId:$('#edit-form').elements.artifact.value});
   host.replaceChildren();drawSkillRun(host,result);
  },'Record result');
 },'primary'));
 else if(!stages.has('result_reviewed')){
  for(const outcome of ['accepted','revised','rejected'])actions.append(button(({accepted:'Accept',revised:'Request revision',rejected:'Reject'})[outcome],async()=>{
   try{const result=await skillRunRequest('result_reviewed',run,{outcome});host.replaceChildren();drawSkillRun(host,result)}catch(error){toast(error.message)}
  },outcome==='accepted'?'primary':''));
 }
}
async function renderSkillInsights(){
 const wrap=hqShell(modes.insights?.name||'Insights','',button('Use a skill',()=>prepareSkillRun()));
 await drawSkillInsights(wrap);
 await drawKnowledgeStatus(wrap);
}
async function drawSkillInsights(wrap){
 const host=el('section','skill-insights');wrap.append(host);
 try{
  if(String(opened||'').startsWith('run:')){
   const data=await api('/api/skill-runs?runId='+encodeURIComponent(opened.slice(4)));
   if(!host.isConnected)return;
   host.append(button('← Skills',()=>navigate('insights')));
   await drawSkillRun(host,data.runs[0]);return;
  }
  const data=await api('/api/insights/skills');
  if(!host.isConnected)return;
  const table=el('table','skill-insights-table'),thead=el('thead'),tr=el('tr');
  for(const label of ['Skill','Reported runs','Last used'])tr.append(el('th','',label));thead.append(tr);table.append(thead);
  const body=el('tbody');table.append(body);
  for(const skill of data.skills){
   const row=el('tr'),name=el('td');
   name.append(button(skill.title,()=>openSkillRunTimeline(skill,host),'skill-insight-name'));
   row.append(name,el('td','',skill.reportedRuns),el('td','',skill.lastUsed?new Date(skill.lastUsed).toLocaleDateString():'—'));
   body.append(row);
  }
  host.append(table);
  const coverage=el('details','skill-insights-coverage');coverage.append(el('summary','','Coverage'),el('p','',data.coverage));host.append(coverage);
  if(!data.skills.length)host.append(el('p','empty','No skills connected.'));
 }catch(error){host.append(el('p','empty','Could not load skill runs. '+error.message))}
}
async function openSkillRunTimeline(skill,host){
 try{
  const data=await api('/api/skill-runs?skillId='+encodeURIComponent(skill.id));
  if(!host.isConnected)return;host.replaceChildren();
  const head=el('div','skill-run-head');head.append(button('← Skills',()=>{const parent=host.parentElement;host.remove();drawSkillInsights(parent)}),el('h2','',skill.title),button('Use this skill',()=>prepareSkillRun(skill.id)));host.append(head);
  if(!data.runs.length){host.append(el('p','empty','No reported runs yet.'));return}
  for(const run of data.runs){const section=el('section','skill-run');host.append(section);drawSkillRun(section,run)}
 }catch(error){toast(error.message)}
}

async function drawKnowledgeStatus(host){
 try{const status=await api('/api/knowledge');if(!status.configured||!host.isConnected)return;
  const row=el('div','knowledge-status');row.append(el('span','muted',status.backedUp?'Knowledge backed up':status.committed?'Knowledge committed · backup pending':'Knowledge saved locally'));
  if(status.conflicts.length)row.append(el('span','','Edits need reconciliation'));
  else if(!status.committed)row.append(button('Commit changes',()=>editDialog('Commit knowledge',form=>field(form,'What changed?','summary',''),async()=>{await api('/api/knowledge',{summary:$('#edit-form').elements.summary.value});render()},'Commit')));
  host.append(row);
 }catch{ /* Optional knowledge backing never blocks reading or reporting. */ }
}
