/* Local folder import cards: preparing never uploads or executes project code. */
(() => {
  const views=new Map();
  const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
  function button(v,text,fn,primary=false){const e=make('button','project-action'+(primary?' primary':''),text);e.onclick=async()=>{e.disabled=true;try{await fn();}catch(error){toast(error.message);}finally{if(e.isConnected)e.disabled=false;}};return e;}
  async function action(v,name){v.plan=await api(`/api/dev/${v.cid}/${name}`,{planId:v.id});v.signature='';render(v);}
  function render(v){
    const p=v.plan;const signature=JSON.stringify([p.status,p.commit,v.current]);if(signature===v.signature)return;v.signature=signature;
    v.root.replaceChildren();
    const head=make('div','project-card-heading');head.append(make('strong','','Workspace · '+p.name),make('span','project-badge',p.status==='accepted'?(v.current===p.projectId?'Đang dùng':'Đã nhập'):p.status==='review'?'Chờ duyệt nhập':p.status));v.root.append(head);
    v.root.append(make('p','','Thư mục đã chọn: '+p.originalDirectory),make('p','project-muted','Nhập một bản sao source theo .nopilotignore vào Nopilot. Thư mục gốc được giữ nguyên. Không nhập .git, không tự upload hoặc chạy code.'));
    if(p.status==='review'){
      v.root.append(make('p','',`${p.fileCount} file nguồn · ${p.sourceBytes.toLocaleString()} byte · bỏ qua ${p.skippedCount} mục.`));
      const detail=make('details','project-detail');detail.append(make('summary','','Xem file được nhập và quy tắc bỏ qua'),make('p','','Quy tắc: '+p.ignore.file+' · '+p.ignore.ruleCount+' patterns'),make('pre','',p.files.join('\n')),make('p','','Đã bỏ qua (tối đa 200 mục):'),make('pre','',p.skipped.join('\n')||'Không có'),make('p','','Source sau khi nhập: '+p.sourceDirectory),make('p','','Commit backup: '+p.commitMessage));v.root.append(detail);
      if(p.contractStatus!=='valid')v.root.append(make('p','project-muted','Dự án chưa có nopilot.json hợp lệ. Sau khi nhập, dùng /iterate để Copilot bổ sung contract trước khi chạy.'));
      const actions=make('div','project-actions');actions.append(button(v,'Nhập workspace và lưu Git backup',()=>action(v,'workspace-confirm'),true),button(v,'Hủy nhập',()=>action(v,'workspace-reject')));v.root.append(actions);
    }else if(p.status==='accepted'){
      v.root.append(make('p','','Source đang làm việc: '+p.sourceDirectory),make('p','project-muted','Git backup '+(p.commit||'').slice(0,8)+'. Mỗi ZIP sửa cần bạn duyệt trước khi cập nhật và chạy.'));
      const actions=make('div','project-actions');
      if(v.current===p.projectId)actions.append(button(v,'Yêu cầu sửa dự án',async()=>window.nopilotDraft('/iterate '+(p.question||'Hãy sửa dự án: [mô tả thay đổi].')),true));
      else actions.append(button(v,'Chuyển sang workspace này',()=>action(v,'workspace-select'),true));
      actions.append(button(v,'Mở source workspace',()=>api(`/api/dev/${v.cid}/open-folder`,{projectId:p.projectId})));
      const help=make('a','project-action','Hướng dẫn vòng phát triển');help.href='/help#loop';help.target='_blank';help.rel='noopener noreferrer';actions.append(help);v.root.append(actions);
    }else v.root.append(make('p','project-muted','Chưa chọn workspace này. Dùng /workspace để chuẩn bị lại.'));
  }
  async function sync(conversation){
    for(const m of conversation.messages){
      if(!m.workspacePlanId)continue;
      const slot=document.querySelector(`[data-workspace-plan="${m.workspacePlanId}"]`);if(!slot)continue;
      const key=conversation.id+':'+m.workspacePlanId;let v=views.get(key);
      if(!v){v={cid:conversation.id,id:m.workspacePlanId,root:make('section','chat-project-card'),signature:'',pending:false};views.set(key,v);}
      if(slot.firstChild!==v.root)slot.replaceChildren(v.root);
      v.current=conversation.activeProjectId;
      if(v.plan)render(v);
      if(!v.plan&&!v.pending){v.pending=true;try{v.plan=await api(`/api/workspaces/${v.cid}/${v.id}`);render(v);}catch(error){v.root.textContent=error.message;}finally{v.pending=false;}}
    }
  }
  window.nopilotWorkspaces={sync};
})();
