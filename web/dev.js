/* Local workspace, explicit human approvals and resumable explorer controls. */
(() => {
  const q = id => document.getElementById(id);
  const panel = q('devPanel');
  let cid = null, data = null, projectId = null, readRevision = null, checkpointId = null;
  let runId = null, latestRunId = null, offset = 0, refreshing = false, lastRefreshError = null;
  const reviewed = new Set(), recoveryReviewed = new Set(), iterations = new Map();
  let approvalView = '', explorerView = '', flowView = '';
  let incomingZip=null, updateReview=null;
  const statusNames = {queued:'Đang chờ',running:'Đang chạy',starting:'Đang chuẩn bị',paused:'Đã tạm dừng',waiting_turns:'Chờ bạn cấp thêm lượt',awaiting_approval:'Chờ duyệt / kết quả chạy',completed:'Hoàn tất đợt này',needs_recovery:'Cần khôi phục có kiểm tra',closed:'Đã đóng browser',succeeded:'Thành công',failed:'Chạy lỗi',stopped:'Đã dừng',timeout:'Hết thời gian',log_limit:'Đạt giới hạn log',error:'Lỗi',interrupted:'Bị gián đoạn'};
  const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  function showError(error){q('devNotice').textContent='Không thực hiện được: '+error.message;toast(error.message);}
  function button(text,action,cls='dev-button'){const b=node('button',cls,text);b.onclick=async()=>{b.disabled=true;try{await action();await refresh();}catch(e){showError(e);}finally{b.disabled=false;}};return b;}
  async function post(action,value={}){if(!cid)throw new Error('Chọn conversation trước');return api(`/api/dev/${cid}/${action}`,value);}
  function project(){return data?.projects.find(p=>p.id===projectId);}
  function show(){panel.hidden=false;q('artifactsPanel').classList.remove('open');q('artifactsPanel').classList.add('closed');refresh();}
  function hide(){panel.hidden=true;}
  function options(select,values,selected){const old=JSON.stringify([...select.options].map(o=>[o.value,o.textContent]));if(old!==JSON.stringify(values)){select.replaceChildren();for(const [value,text] of values){const o=node('option','',text);o.value=value;select.append(o);}}if(values.some(v=>v[0]===selected))select.value=selected;}
  function renderProjects(){
    if(!data.projects.some(p=>p.id===projectId)){projectId=data.projects.at(-1)?.id||null;readRevision=null;}
    options(q('zipTarget'),[['','Chọn project nhận bản sửa…'],...data.projects.map(p=>[p.id,p.name])],q('zipTarget').value);
    options(q('devProject'),data.projects.length?data.projects.map(p=>[p.id,p.name+(p.running?' · đang chạy':'')]):[['','Chưa có project']],projectId||'');
    const p=project();q('projectDetails').hidden=!p;if(!p)return;
    q('devRevision').textContent=`Revision ${p.revision.slice(0,12)} · ${p.files.length} files · ${(p.bytes/1024).toFixed(1)} KB`;
    const files=p.files.map(f=>[f.path,f.path]);options(q('devFile'),files,q('devFile').value);
    const entries=p.files.filter(f=>f.path.endsWith('.py')).map(f=>[f.path,f.path]);
    const defaultEntry=entries.find(v=>/(^|\/)(run|main|app)\.py$/.test(v[0]))?.[0]||entries[0]?.[0];
    options(q('devEntry'),entries,q('devEntry').value||defaultEntry);
    const checkpoints=p.checkpoints.map(c=>[c.id,new Date(c.at).toLocaleTimeString('vi-VN')+' · '+c.label]);
    if(!checkpoints.some(c=>c[0]===checkpointId))checkpointId=checkpoints[0]?.[0]||null;
    options(q('devCheckpoint'),checkpoints,checkpointId);
    q('devSave').disabled=p.running||!readRevision;q('devRollback').disabled=p.running||!checkpointId;q('devPropose').disabled=p.running||!entries.length;
    q('devInstall').disabled=p.running||!p.files.some(f=>f.path==='requirements.txt');renderFlow(p);
  }
  function renderFlow(p){
    const signature=cid+p.id+p.revision+JSON.stringify(p.contract)+JSON.stringify(p.environment)+JSON.stringify(data.approvals)+JSON.stringify(data.runs.map(r=>[r.id,r.status,r.exitCode]));
    if(signature===flowView)return;flowView=signature;
    const view=q('devFlow');view.replaceChildren();
    const contract=p.contract;
    if(contract?.status!=='valid'){view.append(node('p','approval-warning',contract?.error||'Đang đọc nopilot.json…'),node('p','dev-muted','ZIP cũ vẫn có thể dùng phần điều khiển thủ công bên dưới. Không đoán hoặc chạy lệnh từ README.'));return;}
    const spec=contract.manifest;
    view.append(node('p','',`${spec.name} · nopilot.json v${spec.schemaVersion} · Python`));
    view.append(node('p','dev-muted','Source: '+p.sourceDirectory));
    const installed=!spec.install||p.environment?.ready;
    view.append(node('p','',spec.install?(installed?'1. Dependencies khớp requirements/Python; dùng lại venv.':'1. Cần duyệt cài dependencies cho requirements/Python hiện tại.'):'1. Không khai báo dependencies; venv sẽ tạo khi duyệt chạy.'));
    const actions=node('div','dev-actions');
    const propose=async task=>{await post('contract-propose',{projectId:p.id,revision:p.revision,task});await refresh();q('approvalList').scrollIntoView({block:'nearest'});};
    const pending=task=>data.approvals.some(a=>a.projectId===p.id&&a.revision===p.revision&&a.contractTask===task&&a.status==='pending');
    if(spec.install){const b=button('1 · Đề xuất cài dependencies',()=>propose('install'));b.disabled=p.running||pending('install');actions.append(b);}
    for(const task of ['start','check']){if(!spec.tasks[task])continue;const cfg=spec.tasks[task];
      const b=button(task==='start'?'2 · Đề xuất chạy theo manifest':'3 · Đề xuất kiểm tra theo manifest',()=>propose(task),task==='start'?'dev-button primary':'dev-button');
      b.disabled=p.running||!installed||pending(task);actions.append(b);
      view.append(node('p','dev-muted',`${task}: ${cfg.entrypoint} ${JSON.stringify(cfg.args)} · timeout ${cfg.timeoutSeconds}s`));
    }
    view.append(actions,node('p','dev-muted','Đề xuất chỉ tạo phiếu duyệt. Cài/chạy cần Duyệt một lần; không tự gửi log lên Copilot.'));
    if(spec.previewUrl){const active=data.runs.find(r=>r.projectId===p.id&&r.revision===p.revision&&r.contractTask==='start'&&r.status==='running');
      view.append(node('p','dev-muted','URL do project khai báo, chưa kiểm tra health: '+spec.previewUrl));
      if(active){const a=node('a','dev-button','Mở URL ứng dụng');a.href=spec.previewUrl;a.target='_blank';a.rel='noopener noreferrer';view.append(a);}
    }
    const last=[...data.runs].reverse().find(r=>r.projectId===p.id&&r.revision===p.revision&&r.contractTask);
    if(last)view.append(node('p','',`Gần nhất: ${last.contractTask} · ${statusNames[last.status]||last.status} · exit ${last.exitCode??'…'}`));
  }
  function renderApprovals(){
    const signature=cid+JSON.stringify(data.approvals)+JSON.stringify(data.projects.map(p=>[p.id,p.name]));
    if(signature===approvalView)return;approvalView=signature;
    const list=q('approvalList');list.replaceChildren();
    for(const approval of [...data.approvals].reverse().filter(a=>a.status==='pending')){
      const card=node('section','approval-card');card.append(node('h3','',approval.contractTask?'Duyệt task '+approval.contractTask+' · Python':approval.kind==='install'?'Duyệt cài dependency':'Duyệt chạy Python'));
      card.append(node('p','',`${data.projects.find(p=>p.id===approval.projectId)?.name||approval.projectId} · revision ${approval.revision.slice(0,12)} · timeout ${approval.timeout}s`));
      card.append(node('pre','dev-command',approval.commands.map(argv=>argv.map(a=>JSON.stringify(a)).join(' ')).join('\n')));
      card.append(node('p','dev-muted','Thư mục chạy: '+approval.cwd));
      card.append(node('p','approval-warning',approval.executionMode==='container'?'Container Linux: không mạng, project chỉ đọc, chỉ ghi tạm trong container và trả stdout/stderr. Chưa hỗ trợ Edge hoặc cài dependency trong chế độ này.':'Chạy bản sao mã đúng revision đã duyệt. Mã vẫn có quyền tài khoản Windows của bạn. Venv tách dependency; đây không phải sandbox giới hạn truy cập máy hoặc mạng.'));
      if(approval.returnsLogToCopilot)card.append(node('p','dev-muted','Sau khi chạy, phần đuôi stdout/stderr sẽ được gửi lại Copilot để tiếp tục tác vụ này.'));
      if(approval.resetRuntime)card.append(node('p','approval-warning','Khi duyệt: venv cũ và receipt được chuyển vào environment-backups, rồi tạo venv mới. Dependencies đã đổi hoặc chưa có receipt phù hợp.'));
      if(approval.requirements)card.append(node('pre','dev-code',approval.requirements));
      const review=button('Xem mã trước khi duyệt',async()=>{projectId=approval.projectId;renderProjects();q('devFile').value=approval.entrypoint;await loadFile();});card.append(review);
      const label=node('label','dev-review');const check=node('input');check.type='checkbox';check.checked=reviewed.has(approval.id);label.append(check,document.createTextNode('Tôi đã xem mã và đồng ý đúng lệnh này.'));card.append(label);
      const actions=node('div','dev-actions');const approve=button('Duyệt một lần',async()=>{await post('approve',{approvalId:approval.id});reviewed.delete(approval.id);},'dev-button primary');approve.disabled=!check.checked;
      check.onchange=()=>{if(check.checked)reviewed.add(approval.id);else reviewed.delete(approval.id);approve.disabled=!check.checked;};
      actions.append(approve,button('Từ chối',async()=>{await post('reject',{approvalId:approval.id});toast('Đã từ chối; không chạy mã.');}));card.append(actions);list.append(card);
    }
  }
  function renderExplorers(){
    const signature=cid+JSON.stringify(data.explorers);
    if(signature===explorerView)return;explorerView=signature;
    const list=q('explorerList');list.replaceChildren();
    for(const task of [...data.explorers].reverse()){
      const card=node('section','explorer-card');card.append(node('h3','',statusNames[task.status]||task.status));card.append(node('p','',`${task.turns}/${task.budget} lượt · ${task.url}`));
      if(task.task.length>240){const detail=node('details','dev-muted');detail.append(node('summary','','Xem yêu cầu đầy đủ'),node('p','',task.task));card.append(detail);}else card.append(node('p','dev-muted',task.task));if(task.error)card.append(node('p','approval-warning',task.error));
      if(task.checkpointAt)card.append(node('p','dev-muted','Checkpoint: '+new Date(task.checkpointAt).toLocaleString('vi-VN')));
      if(task.progress?.lastAction)card.append(node('p','dev-muted','Thao tác gần nhất: '+task.progress.lastAction));
      if(task.activeTool)card.append(node('p','dev-muted','Đang thực hiện: '+task.activeTool));
      if(task.repairs)card.append(node('p','dev-muted',`Đã sửa phản hồi sai schema: ${task.repairs} lượt (có tính ngân sách)`));
      if(task.progress?.reason)card.append(node('p','approval-warning',task.progress.reason+' '+task.progress.suggestion));
      if(task.deliverables?.length){const passed=task.deliverables.filter(d=>d.replayPassed).length;card.append(node('p','dev-muted',`Project replay: ${passed} đã kiểm chứng · ${task.deliverables.length-passed} cần sửa/kiểm tra`));}
      const act=(action,value={})=>api(`/api/explorers/${cid}/${task.id}/${action}`,value);
      const actions=node('div','dev-actions');
      if(['running','queued'].includes(task.status))actions.append(button('Tạm dừng sau thao tác hiện tại',()=>act('pause')));
      if(task.status==='paused')actions.append(button('Tiếp tục',()=>act('resume'),'dev-button primary'));
      if(task.status==='waiting_turns'){
        card.append(node('p','approval-warning','Đã hết ngân sách lượt. Browser vẫn được giữ; Copilot không được gọi tiếp khi chưa có sự đồng ý của bạn.'));
        actions.append(button('Cấp thêm 20 lượt',()=>act('grant',{turns:20}),'dev-button primary'));
      }
      if(task.status==='needs_recovery'){
        card.append(node('p','approval-warning','Backend/Teams đã bị gián đoạn. Browser sẽ mở mới tại URL cuối, không tự chạy lại click/form trước đó. Hãy kiểm tra chat Teams trước khi khôi phục.'));
        const label=node('label','dev-review');const check=node('input');check.type='checkbox';check.checked=recoveryReviewed.has(task.id);label.append(check,document.createTextNode('Tôi đã kiểm tra lượt chat đang dở trong Teams.'));card.append(label);
        const recoveryTask=node('textarea','dev-iteration');recoveryTask.placeholder='Tùy chọn: yêu cầu cần làm tiếp sau khôi phục…';recoveryTask.value=iterations.get(task.id)||'';recoveryTask.oninput=()=>iterations.set(task.id,recoveryTask.value);card.append(recoveryTask);const recover=button('Khôi phục browser mới',async()=>{await act('recover',{acknowledge:true,task:recoveryTask.value});iterations.delete(task.id);},'dev-button primary');recover.disabled=!check.checked;check.onchange=()=>{if(check.checked)recoveryReviewed.add(task.id);else recoveryReviewed.delete(task.id);recover.disabled=!check.checked;};actions.append(recover);
      }
      if(['completed','paused'].includes(task.status)){
        const input=node('textarea','dev-iteration');input.setAttribute('aria-label','Yêu cầu iterate cho explorer');input.placeholder='Yêu cầu sửa hoặc khám phá tiếp trong cùng phiên…';input.value=iterations.get(task.id)||'';input.oninput=()=>iterations.set(task.id,input.value);card.append(input);
        actions.append(button('Gửi yêu cầu iterate',async()=>{await act('iterate',{task:input.value});iterations.delete(task.id);}));
      }
      if(task.status!=='closed')actions.append(button('Đóng browser',()=>act('close')));
      card.append(actions);list.append(card);
    }
  }
  function renderRuns(){
    const values=[...data.runs].reverse().map(r=>[r.id,`${r.id.slice(0,8)} · ${statusNames[r.status]||r.status}`]);
    const newest=values[0]?.[0]||null;if(newest!==latestRunId){latestRunId=newest;runId=newest;offset=0;q('devLog').textContent='';}else if(!values.some(v=>v[0]===runId)){runId=newest;offset=0;q('devLog').textContent='';}
    options(q('devRun'),values.length?values:[['','Chưa có lượt chạy']],runId||'');
    const run=data.runs.find(r=>r.id===runId);q('devStop').disabled=!run||!['starting','running'].includes(run.status);
    q('devRunFolder').disabled=!run;q('devRunStatus').textContent=run?`${statusNames[run.status]||run.status} · exit ${run.exitCode??'…'} · ${(run.bytes/1024).toFixed(1)} KB`:'Log xuất hiện sau khi bạn duyệt chạy.';
  }
  async function refresh(){
    if(panel.hidden||refreshing)return;
    const current=window.nopilotCurrentConversation?.();if(!current)return;
    if(cid!==current){incomingZip=null;updateReview=null;q('zipInspector').hidden=true;q('updateReview').hidden=true;q('gitLog').textContent='';q('gitMessage').value='';cid=current;projectId=null;readRevision=null;runId=null;latestRunId=null;offset=0;q('devLog').textContent='';q('devEditor').value='';}
    refreshing=true;const requested=cid;
    try{
      const loaded=await api('/api/dev/'+cid);if(cid!==requested)return;data=loaded;
      if(lastRefreshError){q('devNotice').textContent='Đã kết nối lại backend.';lastRefreshError=null;}
      renderProjects();renderApprovals();renderExplorers();renderRuns();
      if(runId){const log=await api(`/api/dev/${cid}/logs?runId=${runId}&offset=${offset}`);offset=log.offset;if(log.text){const view=q('devLog'),stick=view.scrollHeight-view.clientHeight-view.scrollTop<40;view.textContent=(view.textContent+log.text).slice(-120000);if(stick)view.scrollTop=view.scrollHeight;}}
    }catch(e){q('devNotice').textContent=e.message;lastRefreshError=e.message;}finally{refreshing=false;}
  }
  async function loadFile(){if(!projectId||!q('devFile').value)return;const result=await post('read',{projectId,path:q('devFile').value});q('devEditor').value=result.content;readRevision=result.revision;q('devNotice').textContent='Đã đọc '+result.path;q('devSave').disabled=project()?.running||false;}
  window.nopilotDev={openArtifact:async(conversationId,artifactId)=>{show();cid=conversationId;try{const info=await post('inspect',{artifactId});incomingZip={artifactId,zipSha256:info.zipSha256};q('updateReview').hidden=true;updateReview=null;q('zipInspector').hidden=false;q('zipTree').textContent=info.files.map(f=>f.path+(f.directory?'/':` · ${f.bytes} B`)).join('\n');q('zipInfo').textContent=`${info.name} · ${(info.expandedBytes/1024).toFixed(1)} KB sau giải nén · SHA-256 ${info.zipSha256.slice(0,16)}`;q('extractZip').onclick=async()=>{try{const result=await post('extract',{artifactId,zipSha256:info.zipSha256});projectId=result.id;q('zipInspector').hidden=true;await refresh();toast('Đã tạo workspace riêng; chưa chạy mã.');}catch(e){toast(e.message);}};}catch(e){toast(e.message);}}};
  q('previewUpdate').onclick=async()=>{try{const pid=q('zipTarget').value;if(!pid||!incomingZip)throw new Error('Chọn project đích trước.');updateReview=await post('update-preview',{projectId:pid,...incomingZip});q('updateReview').hidden=false;q('updateChanges').textContent='Project đích: '+updateReview.projectName+'\nSource: '+updateReview.sourceDirectory+'\nRevision: '+updateReview.baseRevision.slice(0,12)+'\n\n'+(updateReview.changes.map(f=>f.change+' '+f.path).join('\n')||'Không có thay đổi source.');q('updateDiff').textContent=updateReview.diff;q('updateMessage').value=updateReview.commitMessage;q('updateAccepted').checked=false;q('applyUpdate').disabled=true;}catch(e){showError(e);}};
  function reviewUpdate(){q('applyUpdate').disabled=!updateReview||!q('updateAccepted').checked||!q('updateMessage').value.trim();}
  q('updateAccepted').onchange=reviewUpdate;q('updateMessage').oninput=reviewUpdate;
  q('cancelUpdate').onclick=()=>{updateReview=null;q('updateReview').hidden=true;};
  q('applyUpdate').onclick=async()=>{if(!updateReview||!q('updateAccepted').checked)return;q('applyUpdate').disabled=true;try{const result=await post('update-apply',{projectId:updateReview.projectId,reviewId:updateReview.id,revision:updateReview.baseRevision,message:q('updateMessage').value});projectId=result.project.id;readRevision=null;updateReview=null;q('updateReview').hidden=true;q('zipInspector').hidden=true;q('gitLog').textContent=result.git.log||'';q('gitMessage').value='';await refresh();toast('Đã apply và commit local. '+result.environment.reason);}catch(e){showError(e);reviewUpdate();}};
  q('gitHistory').onclick=async()=>{try{if(!projectId)return;const result=await post('git-status',{projectId});q('gitLog').textContent=result.error||result.log||'Chưa khởi tạo Git. Commit đầu tiên sẽ tạo repository local.';if(!q('gitMessage').value.trim())q('gitMessage').value=result.suggestedMessage||'';}catch(e){showError(e);}};
  q('gitCommit').onclick=async()=>{try{const p=project();if(!p)return;const result=await post('git-commit',{projectId:p.id,revision:p.revision,message:q('gitMessage').value});q('gitLog').textContent=result.log||'';await refresh();toast('Đã commit local.');}catch(e){showError(e);}};
  q('toggleDev').onclick=show;q('closeDev').onclick=hide;q('toggleArtifacts').addEventListener('click',hide);
  q('devProject').onchange=async()=>{projectId=q('devProject').value;q('gitLog').textContent='';q('gitMessage').value='';readRevision=null;q('devDiffText').textContent='';renderProjects();await loadFile();};q('devFile').onchange=()=>loadFile().catch(e=>toast(e.message));q('devRead').onclick=()=>loadFile().catch(e=>toast(e.message));
  q('devSave').onclick=async()=>{try{const changed=await post('patch',{projectId,revision:readRevision,files:[{path:q('devFile').value,content:q('devEditor').value}]});q('devDiffText').textContent=changed.diff?.diff||'Không có thay đổi.';await refresh();await loadFile();toast('Đã lưu và tạo checkpoint. Các phiếu duyệt mã cũ sẽ bị từ chối.');}catch(e){toast(e.message);}};
  q('devNew').onclick=async()=>{try{const result=await post('create',{name:'Python project',files:[{path:'run.py',content:'# Edit this project, then propose a run for human approval.\nprint("Hello from nopilot")\n'}]});projectId=result.id;await refresh();await loadFile();}catch(e){toast(e.message);}};
  q('devCheckpoint').onchange=()=>checkpointId=q('devCheckpoint').value;
  q('devDiff').onclick=async()=>{try{const result=await post('diff',{projectId,checkpoint:checkpointId});q('devDiffText').textContent=result.diff||'Không có thay đổi so với checkpoint.';}catch(e){toast(e.message);}};
  q('devRollback').onclick=async()=>{try{await post('rollback',{projectId,checkpoint:checkpointId});readRevision=null;await refresh();await loadFile();toast('Đã khôi phục; phiên bản trước rollback cũng có checkpoint.');}catch(e){toast(e.message);}};
  q('devExport').onclick=async()=>{try{await post('export',{projectId});toast('Đã xuất ZIP vào artifacts.');}catch(e){toast(e.message);}};
  q('devRepair').onclick=()=>{const p=project();if(!p)return;if(p.running){showError(new Error('Dừng project trước khi đóng gói source để sửa.'));return;}if(window.nopilotDraft?.('/project "'+p.sourceDirectory+'" Hãy sửa dự án: [mô tả lỗi hoặc yêu cầu]. Giữ/cập nhật nopilot.json, kèm NOPILOT_COMMIT_MESSAGE.txt do bạn viết, và trả ZIP snapshot source đầy đủ. Nếu có log đính kèm riêng, hãy đọc cùng source.'))hide();};
  q('devFolder').onclick=()=>post('open-folder',{projectId}).catch(e=>toast(e.message));
  async function propose(kind){const timeout=Number(q('devTimeout').value);await post('propose',{projectId,revision:project().revision,kind,entrypoint:kind==='install'?'requirements.txt':q('devEntry').value,arguments:kind==='install'?[]:q('devArgs').value,timeout,executionMode:q('devExecutionMode').value});await refresh();}
  q('devPropose').onclick=()=>propose('run').catch(showError);q('devInstall').onclick=()=>propose('install').catch(showError);
  q('devRunFolder').onclick=()=>post('open-run-folder',{runId}).catch(e=>toast(e.message));
  q('devRun').onchange=()=>{runId=q('devRun').value;offset=0;q('devLog').textContent='';refresh();};q('devStop').onclick=async()=>{try{await post('stop',{runId});await refresh();}catch(e){toast(e.message);}};
  setInterval(refresh,1200);
})();
