/* Project consent and progress stay in the conversation. No model calls here. */
(() => {
  const views=new Map();
  const active=['starting','installing','running'];
  const names={review:'Chờ bạn đồng ý',starting:'Đang chuẩn bị',installing:'Đang cài dependencies',running:'Đang chạy',succeeded:'Hoàn tất',failed:'Chạy lỗi',error:'Lỗi',stopped:'Đã dừng',timeout:'Hết thời gian',interrupted:'Bị gián đoạn',log_limit:'Đạt giới hạn log'};
  function make(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
  function btn(text,fn,primary=false){const b=make('button','project-action'+(primary?' primary':''),text);b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){toast(e.message);}finally{if(b.isConnected)b.disabled=false;}};return b;}
  async function post(v,action,body){return api(`/api/dev/${v.cid}/${action}`,body);}
  function error(v,e){v.signature='';v.root.replaceChildren(make('strong','','Chưa thể chạy thử ZIP'),make('p','project-muted',e.message),btn('Xem lại kế hoạch',()=>prepare(v,true)),btn('Soạn yêu cầu bổ sung contract',async()=>window.nopilotDraft?.('/develop Hãy xuất lại ZIP dự án vừa sửa, giữ đầy đủ những thay đổi đã yêu cầu, bổ sung hoặc sửa nopilot.json theo schema và trả ZIP tải được. Không chỉ mô tả bằng chữ.')),btn('Xem trong Nâng cao',()=>window.nopilotDev?.openArtifact(v.cid,v.aid)));}
  async function prepare(v,fresh=false,target){
    if(v.pending)return;v.pending=true;v.root.replaceChildren(make('p','project-muted','Đang đọc contract và chuẩn bị kế hoạch…'));
    try{v.plan=await post(v,'launch-plan',{artifactId:v.aid,fresh,...(target?{targetProjectId:target}:{})});v.signature='';render(v);}catch(e){error(v,e);}finally{v.pending=false;}
  }
  function render(v){
    const p=v.plan;if(!p)return;
    const signature=JSON.stringify([p.status,p.stage,p.run?.status,p.run?.bytes,p.run?.exitCode]);
    if(v.signature===signature)return;
    // Review forms remain stable while the conversation polls.
    v.signature=signature;v.root.replaceChildren();
    const head=make('div','project-card-heading');head.append(make('strong','',p.projectName),make('span','project-badge',names[p.status]||p.status));v.root.append(head);
    if(p.status==='review'){
      v.root.append(make('p','',p.update?'Cập nhật project “'+p.targetProjectName+'” và chạy thử bản mới?':'Bạn muốn chạy thử dự án này?'));
      const steps=make('ol','project-steps');
      if(p.update)steps.append(make('li','','Lưu source hiện tại vào Git → áp dụng ZIP đã xem diff.'));
      else if(!p.skipGit)steps.append(make('li','','Chuẩn bị project và lưu commit local.'));
      steps.append(make('li','',p.installNeeded?'Tự tạo/cập nhật venv và cài dependencies theo contract.':p.contract.install?'Dùng lại venv; dependencies còn khớp.':'Chỉ dùng Python, không cài thêm packages.'));
      const task=p.contract.tasks[p.task];steps.append(make('li','',`${p.task==='check'?'Kiểm tra':'Chạy'} ${task.entrypoint} ${JSON.stringify(task.args)} · tối đa ${task.timeoutSeconds} giây.`));v.root.append(steps);
      const detail=make('details','project-detail');detail.append(make('summary','','Xem kế hoạch'+(p.update?' và diff':'')));
      if(p.requirements)detail.append(make('p','','Dependencies từ PyPI:'),make('pre','',p.requirements));
      detail.append(make('p','','Source và lệnh được khóa theo phiên bản đã xem. Mã chạy với quyền tài khoản Windows của bạn; stdin đóng.'));
      if(p.update){detail.append(make('p','','Snapshot đầy đủ: file không có trong ZIP sẽ bị xóa.'),make('pre','',p.update.changes.map(f=>f.change+' '+f.path).join('\n')),make('pre','',p.update.diff));}
      if(!p.skipGit){detail.append(make('label','','Commit message (có thể sửa)'));const message=make('textarea');message.setAttribute('aria-label','Commit message của kế hoạch chạy');message.value=p.commitMessage;v.message=message;detail.append(message);}
      if(!p.skipGit)detail.append(btn('Xem ZIP trong Nâng cao',()=>window.nopilotDev?.openArtifact(v.cid,v.aid)));
      detail.append(btn('Lập lại kế hoạch ZIP',()=>prepare(v,true)));
      v.root.append(detail,make('p','project-muted','Mã chạy với quyền Windows của bạn. Đồng ý một lần cho đúng kế hoạch cài/chạy này. Log giữ local; không tự gửi Copilot.'));
      const actions=make('div','project-actions');
      const accept=btn(p.update?'Cập nhật và chạy':p.task==='check'?'Chạy kiểm tra':p.installNeeded?'Đồng ý cài và chạy':'Chạy thử',async()=>{const next=await post(v,'launch-confirm',{launchId:p.id,message:v.message?.value});v.plan=next;v.signature='';render(v);},true);
      if(!p.skipGit&&v.message){accept.disabled=!v.message.value.trim();v.message.oninput=()=>accept.disabled=!v.message.value.trim();if(accept.disabled)detail.open=true;}
      actions.append(accept);
      actions.append(btn('Để sau',async()=>{v.root.replaceChildren(make('p','project-muted','Chưa chạy dự án.'),btn('Xem lại kế hoạch',()=>{v.signature='';render(v);}));v.dismissed=true;}));
      if(p.update)actions.append(btn('Tạo project riêng',()=>prepare(v,true,'new')));
      v.root.append(actions);
    }else{
      v.root.append(make('p','',p.stage));
      if(p.commit)v.root.append(make('small','project-muted','Git '+p.commit.slice(0,8)));
      const actions=make('div','project-actions');
      if(active.includes(p.status))actions.append(btn('Dừng',async()=>{v.plan=await post(v,'launch-stop',{launchId:p.id});v.signature='';render(v);}));
      actions.append(btn('Mở source',()=>post(v,'open-folder',{projectId:p.projectId})));
      if(p.runId)actions.append(btn('Mở thư mục chạy',()=>post(v,'open-run-folder',{runId:p.runId})));
      if(p.runId)actions.append(btn('Xem log',async()=>{v.logsOpen=!v.logsOpen;v.logBox.hidden=!v.logsOpen;if(v.logsOpen)await loadLog(v);}));
      if(p.run?.status==='running'&&p.task==='start'&&p.contract.previewUrl){const a=make('a','project-action primary','Mở ứng dụng');a.href=p.contract.previewUrl;a.target='_blank';a.rel='noopener noreferrer';a.title='URL do contract khai báo; chưa kiểm tra health';actions.append(a);}
      if(!active.includes(p.status)){
        if(p.status==='succeeded')actions.append(btn('Chạy lại',async()=>{v.plan=await post(v,'launch-rerun',{projectId:p.projectId});v.signature='';render(v);}));
        else actions.append(btn('Xem lại kế hoạch ZIP',()=>prepare(v,true)));
        if(p.contract.tasks.check)actions.append(btn('Kiểm tra',async()=>{v.plan=await post(v,'launch-check',{projectId:p.projectId});v.signature='';render(v);}));
        actions.append(btn('Yêu cầu sửa',async()=>{await post(v,'select-project',{projectId:p.projectId});window.nopilotDraft?.('/iterate Hãy sửa dự án: [mô tả yêu cầu]. Nếu có log đính kèm riêng, đọc cùng source.');}));
      }
      v.root.append(actions);v.logBox=make('pre','project-log');v.logBox.hidden=!v.logsOpen;v.root.append(v.logBox);
      if(v.logsOpen&&p.runId)loadLog(v);
    }
  }
  async function loadLog(v){try{const p=v.plan;if(!p?.runId||!v.logBox)return;const log=await api(`/api/dev/${v.cid}/logs?runId=${p.runId}&offset=0`);v.logBox.textContent=log.text||'Đang chờ log…';}catch(e){v.logBox.textContent=e.message;}}
  async function sync(conversation){
    const zipMessages=conversation.messages.filter(m=>m.artifacts?.some(a=>a.name.toLowerCase().endsWith('.zip')));
    const latest=zipMessages.at(-1)?.id;
    for(const message of zipMessages)for(const artifact of projectZips(message.artifacts)){
      const slot=document.querySelector(`[data-project-artifact="${artifact.id}"]`);if(!slot)continue;
      const key=conversation.id+':'+artifact.id;let v=views.get(key);
      if(!v){v={cid:conversation.id,aid:artifact.id,root:make('section','chat-project-card'),plan:null,signature:'',pending:false,logsOpen:false};views.set(key,v);
        if(message.id===latest)prepare(v);else v.root.append(btn('Xem kế hoạch chạy dự án này',()=>prepare(v)));
      }
      if(slot.firstChild!==v.root)slot.replaceChildren(v.root);
      if(v.plan&&active.includes(v.plan.status)&&!v.polling){v.polling=true;try{v.plan=await api(`/api/launches/${v.cid}/${v.plan.id}`);render(v);}catch(e){error(v,e);}finally{v.polling=false;}}
    }
  }
  window.nopilotProjects={sync};
})();
