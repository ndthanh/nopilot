"use strict";
function mod(n){return Process.enumerateModules().find(m=>m.name.toLowerCase()===n.toLowerCase())||null;}
function exact(m,n){for(const e of m.enumerateExports())if(e.type==='function'&&(e.name||'')===n)return e.address;return null;}
function pref(m,p){return m.enumerateExports().filter(e=>e.type==='function'&&(e.name||'').indexOf(p)===0);}
function ps(p){try{return(!p||p.isNull())?null:p.toString();}catch(_){return null;}}
function cs(p){try{if(!p||p.isNull())return null;const x=p.readCString();return x&&x.length<512?x:null;}catch(_){return null;}}
function norm(t){return(t||'').replace(/&/g,'').trim().toLowerCase();}
const S={initialized:false,error:null,action:null,receiver:null,guiThread:null,scheduleOpen:false,openNative:null,ok:null,connectionDialog:null,authDialog:null,authUser:null,authPass:null,authOk:null,authCancel:null,authEdits:{},authButtons:{},pendingLogin:null,pendingOk:false,executingOk:false,buttons:{},accepts:[],events:[],hooks:[],batch:{armed:false,tooltipWidget:null,tooltipText:null,sourceWidget:null,sourceTime:null,pendingInvoke:false,executing:false,tooltips:{},connections:[],inputs:[],signals:[],activateOne:null,postThread:null},typeahead:{edit:null,table:null,pending:false,executing:false,targetSeen:false,targetDialog:null,query:'on-h',lastLineEdit:null,directConnected:false,filterButton:null,filterReceiver:null,pendingFilter:false,filterExecuting:false,bootstrapPending:false,bootstrapExecuting:false,bootstrapSent:false,bootstrapReceiver:null,bootstrapError:null,keyCtor:null,keyDtor:null,sendEvent:null,focusWidget:null,qApp:null,bootstrapApi:{},activateOnly:false,filterForm:{capturing:false,lineEdits:[],confirmed:null,enter:null,cancel:null,dateFrom:null,dateTo:null,pending:false,executing:false,fromValue:null,toValue:null,ready:false},saveQSignal:{object:null,value:null,pending:false,executing:false,activateFn:null,activateExport:null,last:null,selectDialog:null,fileEdit:null,okButton:null,exportPath:null,pendingSubmit:false,submitting:false,pendingClick:false,clicking:false,submitDelayMs:750,fullAuto:false},saveDiscover:{armed:true,started:Date.now(),qsignals:{},menuTexts:[],menuCalls:[],connections:[],candidates:[],lastReport:null,calibrationArmed:false,calibrationStart:0,confirmedObject:null,confirmedTime:0,confirmedValue:null,confirmedBacktrace:[],beforeObjects:[],afterObjects:[],autoCandidate:null,autoReason:null,autoGroups:[],itemLookups:[],confirmedItem:null,confirmedMenu:null,confirmedItemMemory:null,directCandidate:null,directItem:null,directMenu:null,directReady:false,directReason:null}}};
function ev(k,d){const e=Object.assign({kind:k,time:Date.now(),thread_id:Process.getCurrentThreadId()},d||{});S.events.push(e);if(S.events.length>400)S.events.shift();send({type:'event',event:e});}
function install(){try{
 if(S.initialized)return true;if(Process.platform!=='windows'||Process.arch!=='ia32'||Process.pointerSize!==4)throw new Error('This adapter requires Windows x86 MSVC ABI');
 const q=mod('qt-mt.dll'),u=mod('USER32.dll')||mod('user32.dll');if(!q||!u)return false;
 if(Process.enumerateModules().filter(m=>m.name.toLowerCase()==='qt-mt.dll').length!==1)throw new Error('Multiple qt-mt.dll modules: inspect module manifest');
 const conn=exact(q,'?connect@QObject@@SA_NPBV1@PBD01@Z'),act=exact(q,'?activated@QAction@@IAEXXZ'),notify=exact(q,'?notify@QApplication@@UAE_NPAVQObject@@PAVQEvent@@@Z');
 const lenA=exact(q,'?length@QString@@QBEIXZ'),uniA=exact(q,'?unicode@QString@@QBEPBVQChar@@XZ'),capA=exact(q,'?setCaption@QWidget@@UAEXABVQString@@@Z');
 const clicked=pref(q,'?clicked@QButton@@').concat(pref(q,'?clicked@QPushButton@@')),setButtons=pref(q,'?setText@QButton@@').concat(pref(q,'?setText@QPushButton@@'));
 const setLineA=exact(q,'?setText@QLineEdit@@UAEXABVQString@@@Z'),echoA=exact(q,'?setEchoMode@QLineEdit@@UAEXW4EchoMode@1@@Z');
 const qCtorA=exact(q,'??0QString@@QAE@XZ')||(pref(q,'??0QString@@QAE@XZ')[0]||{}).address;
 const qSetUnicodeA=(pref(q,'?setUnicode@QString@@')[0]||{}).address;
 const qDtorA=exact(q,'??1QString@@QAE@XZ')||(pref(q,'??1QString@@')[0]||{}).address;
 const dispatch=exact(u,'DispatchMessageW'),postThreadA=exact(u,'PostThreadMessageW'),setTimerA=exact(u,'SetTimer'),killTimerA=exact(u,'KillTimer');
 const tooltipAdds=pref(q,'?add@QToolTip@@');const activateSignals=pref(q,'?activate_signal@QObject@@');const eventTypeA=exact(q,'?type@QEvent@@QBE?AW4Type@1@XZ');const lineCtors=pref(q,'??0QLineEdit@@');const isCheckedE=pref(q,'?isChecked@QButton@@')[0]||null;
 const keyCtorCandidates=pref(q,'??0QKeyEvent@@');
 const keyCtorE=keyCtorCandidates.find(e=>(e.name||'').indexOf('W4Type@QEvent@@')>=0&&(e.name||'').indexOf('ABVQString@@')>=0)||null;
 const keyDtorE=pref(q,'??1QKeyEvent@@').find(e=>(e.name||'').indexOf('UAE@XZ')>=0)||pref(q,'??1QKeyEvent@@')[0]||null;
 const sendEventE=pref(q,'?sendEvent@QApplication@@').find(e=>(e.name||'').indexOf('SA_NPAVQObject@@PAVQEvent@@@Z')>=0)||null;
 const focusWidgetE=pref(q,'?focusWidget@QApplication@@').find(e=>(e.name||'').indexOf('QBEPAVQWidget@@XZ')>=0)||null;
 const qAppExports=q.enumerateExports().filter(e=>(e.name||'').toLowerCase().indexOf('qapp')>=0);
 const qAppE=qAppExports.find(e=>e.type==='variable'&&(e.name||'').indexOf('?qApp@@')===0)||null;
 S.typeahead.bootstrapApi={key_ctor:keyCtorE?keyCtorE.name:null,key_ctor_candidates:keyCtorCandidates.map(e=>e.name),key_dtor:keyDtorE?keyDtorE.name:null,send_event:sendEventE?sendEventE.name:null,focus_widget:focusWidgetE?focusWidgetE.name:null,qapp_export:qAppE?qAppE.name:null,qapp_candidates:qAppExports.map(e=>({name:e.name,type:e.type}))};

 if(!conn||!act||!notify||!lenA||!uniA||!capA||clicked.length===0||!setLineA||!echoA||!qCtorA||!qSetUnicodeA||!qDtorA||!dispatch||!postThreadA||!setTimerA||!killTimerA)throw new Error('required exports missing for full login');
 const qlen=new NativeFunction(lenA,'uint',['pointer'],'thiscall'),quni=new NativeFunction(uniA,'pointer',['pointer'],'thiscall');
 const callClicked=new NativeFunction(clicked[0].address,'void',['pointer'],'thiscall');
 const qtConnectFn=new NativeFunction(conn,'bool',['pointer','pointer','pointer','pointer'],'mscdecl');
 const setLineTextFn=new NativeFunction(setLineA,'void',['pointer','pointer'],'thiscall');

 const qCtor=new NativeFunction(qCtorA,'pointer',['pointer'],'thiscall');
 const qSetUnicode=new NativeFunction(qSetUnicodeA,'pointer',['pointer','pointer','uint'],'thiscall');
 const qDtor=new NativeFunction(qDtorA,'void',['pointer'],'thiscall');
 const isCheckedFn=isCheckedE?new NativeFunction(isCheckedE.address,'bool',['pointer'],'thiscall'):null;
 S.typeahead.keyCtor=keyCtorE?new NativeFunction(keyCtorE.address,'pointer',['pointer','int','int','int','int','pointer','int','uint'],'thiscall'):null;
 S.typeahead.keyDtor=keyDtorE?new NativeFunction(keyDtorE.address,'void',['pointer'],'thiscall'):null;
 S.typeahead.sendEvent=sendEventE?new NativeFunction(sendEventE.address,'bool',['pointer','pointer'],'mscdecl'):null;
 S.typeahead.focusWidget=focusWidgetE?new NativeFunction(focusWidgetE.address,'pointer',['pointer'],'thiscall'):null;
 try{S.typeahead.qApp=qAppE?qAppE.address.readPointer():null;}catch(_){S.typeahead.qApp=null;}
 S.batch.postThread=new NativeFunction(postThreadA,'bool',['uint','uint','uint','uint'],'stdcall');
 function readQ(p){try{const n=qlen(p);if(n>2048)return null;if(n===0)return '';const c=quni(p);return(!c||c.isNull())?null:c.readUtf16String(n);}catch(_){return null;}}
 const sigTextChanged=Memory.allocUtf8String('2textChanged(const QString&)'); const slotSearchEdit=Memory.allocUtf8String('1searchEditTextChanged(const QString&)');
 const activateOneA=exact(q,'?activate_signal@QObject@@IAEXH@Z'); S.batch.activateOne=activateOneA?new NativeFunction(activateOneA,'void',['pointer','int'],'thiscall'):null;
 const eventTypeFn=eventTypeA?new NativeFunction(eventTypeA,'int',['pointer'],'thiscall'):null; function eventType(p){try{return eventTypeFn?eventTypeFn(p):p.add(Process.pointerSize).readU32();}catch(_){return null;}}
 function makeQStringAndSet(target,text,secret){
   const wide=Memory.allocUtf16String(text), qobj=Memory.alloc(64);
   qobj.writeByteArray(new Uint8Array(64));
   try{qCtor(qobj);qSetUnicode(qobj,wide,text.length);setLineTextFn(target,qobj);}finally{try{qDtor(qobj);}catch(_){}if(secret){try{wide.writeByteArray(new Uint8Array((text.length+1)*2));}catch(_){}}}
 }
 function sendBootstrapO(){
   if(!S.typeahead.keyCtor||!S.typeahead.keyDtor||!S.typeahead.sendEvent)throw new Error('Qt key API unavailable: '+JSON.stringify(S.typeahead.bootstrapApi));
   let receiver=null;
   if(S.typeahead.focusWidget&&S.typeahead.qApp){try{receiver=S.typeahead.focusWidget(S.typeahead.qApp);}catch(e){ev('typeahead_focus_widget_error',{error:String(e),qapp:ps(S.typeahead.qApp)});}}
   if(!receiver||receiver.isNull())receiver=S.typeahead.table;
   if(!receiver||receiver.isNull())throw new Error('No bootstrap receiver');
   S.typeahead.bootstrapReceiver=receiver;
   const wide=Memory.allocUtf16String('o'),qobj=Memory.alloc(64),kev=Memory.alloc(192);qobj.writeByteArray(new Uint8Array(64));kev.writeByteArray(new Uint8Array(192));
   let constructed=false;
   try{ev('typeahead_bootstrap_qstring_begin',{});qCtor(qobj);qSetUnicode(qobj,wide,1);ev('typeahead_bootstrap_qstring_ready',{});ev('typeahead_bootstrap_key_ctor_begin',{event_type:6,key:79,ascii:111,state:0,autorepeat:0,count:1});S.typeahead.keyCtor(kev,6,79,111,0,qobj,0,1);constructed=true;ev('typeahead_bootstrap_key_ctor_return',{});const delivered=S.typeahead.sendEvent(receiver,kev);ev('typeahead_bootstrap_sent',{receiver:ps(receiver),key:79,ascii:111,event_type:6,delivered:!!delivered,qapp:ps(S.typeahead.qApp),api:S.typeahead.bootstrapApi});if(!delivered)throw new Error('QApplication::sendEvent returned false');S.typeahead.bootstrapSent=true;}finally{if(constructed){try{S.typeahead.keyDtor(kev);}catch(_){}}try{qDtor(qobj);}catch(_){}}
 }
 
 function reconcileAuth(){
   if(!S.authDialog)return;
   const d=ps(S.authDialog);
   for(const k in S.authButtons){const b=S.authButtons[k];if(b.dialog!==d)continue;const n=norm(b.text);if(n==='ok'&&b.slot==='1accept()')S.authOk=b.sender;else if(n==='cancel'&&b.slot==='1reject()')S.authCancel=b.sender;}
   const edits=Object.values(S.authEdits);S.authPass=edits.find(x=>x.password)?.ptrNative||S.authPass;S.authUser=edits.find(x=>!x.password)?.ptrNative||S.authUser;
   if(S.authUser&&S.authPass&&S.authOk)ev('authorization_mapping_ready',{dialog:d,username:ps(S.authUser),password:ps(S.authPass),ok_button:ps(S.authOk)});
 }
 function buildNativeOpener(actionPtr) {
   const csrc = `
   #include <stdint.h>
   typedef void (__attribute__((thiscall)) *action_fn_t)(void *self);
   typedef uintptr_t (__attribute__((stdcall)) *set_timer_t)(void *, uintptr_t, unsigned int, void *);
   typedef int (__attribute__((stdcall)) *kill_timer_t)(void *, uintptr_t);
   #define ACTION_FN ((uintptr_t) ${act.toString()})
   #define ACTION_SELF ((uintptr_t) ${actionPtr.toString()})
   #define SET_TIMER ((uintptr_t) ${setTimerA.toString()})
   #define KILL_TIMER ((uintptr_t) ${killTimerA.toString()})
   static int pending_timers = 0;
   static int active_callback = 0;
   void __attribute__((stdcall)) timer_proc(void *hwnd, unsigned int msg, uintptr_t id, unsigned int tick) {
     active_callback++;
     action_fn_t fn = (action_fn_t) ACTION_FN;
     kill_timer_t kill = (kill_timer_t) KILL_TIMER;
     if (kill) kill((void *)0, id);
     if (pending_timers > 0) pending_timers--;
     if (fn && ACTION_SELF) fn((void *) ACTION_SELF);
     active_callback--;
   }
   uintptr_t schedule(void) {
     set_timer_t set_timer = (set_timer_t) SET_TIMER;
     if (!set_timer) return 0;
     pending_timers++;
     uintptr_t id = set_timer((void *)0, (uintptr_t)0, 1, (void *)&timer_proc);
     if (!id) pending_timers--;
     return id;
   }
   int idle(void) { return pending_timers == 0 && active_callback == 0; }
   `;
   const cm = new CModule(csrc);
   const schedule = new NativeFunction(cm.schedule, 'pointer', [], 'mscdecl');
   S.openNative = {module: cm, timerProc: cm.timer_proc, schedule: schedule, idle: new NativeFunction(cm.idle,'int',[],'mscdecl')};
   ev('native_trampoline_ready', {action: ps(actionPtr), timer_proc: ps(cm.timer_proc), schedule: ps(cm.schedule)});
 }Interceptor.attach(conn,{onEnter(args){const sender=args[0],signal=cs(args[1]),receiver=args[2],slot=cs(args[3]);if((signal==='2textChanged(const QString&)'||signal==='2inputTextChanged(const QString&, bool)')&&(slot==='1searchEditTextChanged(const QString&)'||slot==='1inputTextChanged(const QString&, bool)')){S.typeahead.edit=sender;S.typeahead.table=receiver;ev('typeahead_mapping_found',{edit:ps(sender),table:ps(receiver)});}if(signal==='2doubleClicked()'&&slot==='1processClickEvent()'){if(!S.typeahead.table||ps(S.typeahead.table)===ps(sender)){S.typeahead.table=sender;ev('batch_table_activation_mapping_found',{table:ps(sender),receiver:ps(receiver)});}}S.batch.connections.push({time:Date.now(),sender:ps(sender),signal:signal,receiver:ps(receiver),slot:slot});if(S.batch.connections.length>30000)S.batch.connections.shift();if(signal==='2activated()'&&slot==='1actFileConnectActivated()'){S.action=args[0];S.receiver=args[2];buildNativeOpener(S.action);ev('connect_action_mapping_found',{action:ps(S.action),receiver:ps(S.receiver)});}if(signal==='2clicked()'&&slot==='1processClickEvent()'){const bk=ps(sender),bt=S.buttons[bk];if(bt&&norm(bt.text)==='filter'){S.typeahead.filterButton=sender;S.typeahead.filterReceiver=receiver;ev('filter_mapping_found',{button:bk,receiver:ps(receiver),text:bt.text});}}if(signal==='2clicked()'&&slot==='1accept()'){const k=ps(args[0]);S.accepts.push({sender:args[0],button:k,dialog:ps(args[2])});if(S.accepts.length>100)S.accepts.shift();reconcile();}
 const bk=ps(args[0]), bb=S.authButtons[bk];if(signal==='2clicked()'&&bb&&(slot==='1accept()'||slot==='1reject()')){bb.sender=args[0];bb.dialog=ps(args[2]);bb.slot=slot;reconcileAuth();}}});
 function reconcile(){if(!S.connectionDialog)return;const d=ps(S.connectionDialog);for(let i=S.accepts.length-1;i>=0;i--){const a=S.accepts[i],b=S.buttons[a.button];if(a.dialog===d&&b&&norm(b.text)==='ok'){S.ok=a.sender;ev('connection_ok_mapping_found',{button:a.button,dialog:d,text:b.text});return;}}}
 for(const e of setButtons){try{Interceptor.attach(e.address,{onEnter(args){const k=ps(this.context.ecx),t=readQ(args[0]);if(t!==null){S.buttons[k]=S.buttons[k]||{ptr:k};S.buttons[k].text=t;if(S.typeahead.filterForm.capturing){const nt=norm(t);if(nt==='confirmed')S.typeahead.filterForm.confirmed=this.context.ecx;else if(nt==='enter')S.typeahead.filterForm.enter=this.context.ecx;else if(nt==='cancel')S.typeahead.filterForm.cancel=this.context.ecx;if(S.typeahead.filterForm.confirmed&&S.typeahead.filterForm.enter&&S.typeahead.filterForm.lineEdits.length>=9){S.typeahead.filterForm.dateFrom=S.typeahead.filterForm.lineEdits[7];S.typeahead.filterForm.dateTo=S.typeahead.filterForm.lineEdits[8];S.typeahead.filterForm.ready=true;S.typeahead.filterForm.capturing=false;ev('filter_form_mapping_ready',{confirmed:ps(S.typeahead.filterForm.confirmed),date_from:ps(S.typeahead.filterForm.dateFrom),date_to:ps(S.typeahead.filterForm.dateTo),enter:ps(S.typeahead.filterForm.enter),line_edit_count:S.typeahead.filterForm.lineEdits.length});}}if(norm(t)==='filter'){for(let i=S.batch.connections.length-1;i>=0;i--){const c=S.batch.connections[i];if(c.sender===k&&c.signal==='2clicked()'&&c.slot==='1processClickEvent()'){S.typeahead.filterButton=this.context.ecx;S.typeahead.filterReceiver=ptr(c.receiver);ev('filter_mapping_found',{button:k,receiver:c.receiver,text:t});break;}}}S.authButtons[k]=S.authButtons[k]||{ptr:k};S.authButtons[k].text=t;reconcile();reconcileAuth();}}});}catch(_){}}
 Interceptor.attach(capA,{onEnter(args){const t=readQ(args[0]);if(t==='List of authorization transactions'&&!S.typeahead.targetSeen){S.typeahead.targetSeen=true;S.typeahead.targetDialog=this.context.ecx;ev('authorization_list_seen',{dialog:ps(S.typeahead.targetDialog),caption:t});}if(t==='Connection select'){S.connectionDialog=this.context.ecx;ev('connection_select_seen',{dialog:ps(S.connectionDialog)});reconcile();}else if(t==='TW CMS authorization'){S.authDialog=this.context.ecx;ev('authorization_seen',{dialog:ps(S.authDialog)});reconcileAuth();}}});
 Interceptor.attach(echoA,{onEnter(args){const k=ps(this.context.ecx),mode=args[0].toInt32();S.authEdits[k]=S.authEdits[k]||{ptr:k,ptrNative:this.context.ecx};S.authEdits[k].echo_mode=mode;S.authEdits[k].password=mode!==0;reconcileAuth();}});
 Interceptor.attach(setLineA,{onEnter(args){S.typeahead.lastLineEdit=this.context.ecx;const k=ps(this.context.ecx);S.authEdits[k]=S.authEdits[k]||{ptr:k,ptrNative:this.context.ecx};reconcileAuth();}});
 for(const e of lineCtors){try{Interceptor.attach(e.address,{onEnter(args){if(!S.typeahead.filterForm.capturing)return;const p=this.context.ecx,k=ps(p);if(!S.typeahead.filterForm.lineEdits.some(x=>ps(x)===k)){S.typeahead.filterForm.lineEdits.push(p);ev('filter_form_line_edit',{edit:k,index:S.typeahead.filterForm.lineEdits.length-1});}}});}catch(_){} }
 for(const e of tooltipAdds){try{Interceptor.attach(e.address,{onEnter(args){let widget=args[0],text=null;for(let i=1;i<5;i++){const t=readQ(args[i]);if(t&&t.length<300){text=t;break;}}if(text){const wk=ps(widget);S.batch.tooltips[wk]={widget:wk,text:text,time:Date.now(),export_name:e.name};if(text.toLowerCase().indexOf('batch operations')>=0){S.batch.tooltipWidget=widget;S.batch.tooltipText=text;const now=Date.now();if(S.batch.sourceTime===null||now<S.batch.sourceTime){S.batch.sourceWidget=widget;S.batch.sourceTime=now;}ev('batch_tooltip_cached',{widget:wk,text:text,source_widget:ps(S.batch.sourceWidget),armed:S.batch.armed,export_name:e.name});}}}});}catch(_){} }
 for(const e of activateSignals){try{Interceptor.attach(e.address,{onEnter(args){if(!S.batch.armed)return;const obj=this.context.ecx;if(S.batch.tooltipWidget&&ps(obj)===ps(S.batch.tooltipWidget)){const rec={time:Date.now(),object:ps(obj),export_name:e.name,arg0:ps(args[0])};S.batch.signals.push(rec);ev('batch_signal_observed',rec);}}});}catch(_){} }
 Interceptor.attach(notify,{onEnter(){if(S.guiThread===null)S.guiThread=Process.getCurrentThreadId();}});
 for(const e of clicked){try{Interceptor.attach(e.address,{onEnter(){if(S.ok&&ps(this.context.ecx)===ps(S.ok))ev('connection_ok_clicked_observed',{button:ps(S.ok)});}});}catch(_){}}
 Interceptor.attach(dispatch,{onEnter(){if(Process.getCurrentThreadId()!==S.guiThread)return;if(S.disposeRequested&&disposeIdle()){S.disposeAck=true;return;}if(S.saveLearning)S.saveLearning.dispatch();if(S.typeahead.bootstrapPending&&!S.typeahead.bootstrapExecuting){S.typeahead.bootstrapPending=false;S.typeahead.bootstrapExecuting=true;S.typeahead.bootstrapError=null;ev('typeahead_bootstrap_begin',{table:ps(S.typeahead.table),qapp:ps(S.typeahead.qApp),api:S.typeahead.bootstrapApi});try{sendBootstrapO();ev('typeahead_bootstrap_return',{receiver:ps(S.typeahead.bootstrapReceiver)});}catch(e){S.typeahead.bootstrapError=String(e);ev('typeahead_bootstrap_error',{error:S.typeahead.bootstrapError,receiver:ps(S.typeahead.bootstrapReceiver),api:S.typeahead.bootstrapApi});}S.typeahead.bootstrapExecuting=false;}if(S.typeahead.pending&&!S.typeahead.executing){S.typeahead.pending=false;S.typeahead.executing=true;S.typeahead.targetSeen=false;ev('typeahead_invoke_begin',{edit:ps(S.typeahead.edit),table:ps(S.typeahead.table),query:S.typeahead.query,activation_signal_index:21});try{if(S.typeahead.activateOnly){S.typeahead.activateOnly=false;S.batch.activateOne(S.typeahead.table,21);ev('current_operation_activation_return',{table:ps(S.typeahead.table),signal_index:21});}else{if(!S.typeahead.edit)throw new Error('Type-ahead lazy QLineEdit not ready');makeQStringAndSet(S.typeahead.edit,S.typeahead.query,false);ev('typeahead_text_set',{edit:ps(S.typeahead.edit),query:S.typeahead.query});S.batch.activateOne(S.typeahead.table,21);ev('typeahead_activation_return',{table:ps(S.typeahead.table),signal_index:21});}}catch(e){S.typeahead.activateOnly=false;ev('typeahead_invoke_error',{error:String(e)});}S.typeahead.executing=false;}if(S.typeahead.filterForm.pending&&!S.typeahead.filterForm.executing){S.typeahead.filterForm.pending=false;S.typeahead.filterForm.executing=true;ev('filter_submit_begin',{from:S.typeahead.filterForm.fromValue,to:S.typeahead.filterForm.toValue});try{const checked=isCheckedFn?!!isCheckedFn(S.typeahead.filterForm.confirmed):true;if(checked){callClicked(S.typeahead.filterForm.confirmed);ev('filter_confirmed_unchecked',{button:ps(S.typeahead.filterForm.confirmed)});}else ev('filter_confirmed_already_unchecked',{button:ps(S.typeahead.filterForm.confirmed)});makeQStringAndSet(S.typeahead.filterForm.dateFrom,S.typeahead.filterForm.fromValue,false);ev('filter_date_from_set',{edit:ps(S.typeahead.filterForm.dateFrom),value:S.typeahead.filterForm.fromValue});makeQStringAndSet(S.typeahead.filterForm.dateTo,S.typeahead.filterForm.toValue,false);ev('filter_date_to_set',{edit:ps(S.typeahead.filterForm.dateTo),value:S.typeahead.filterForm.toValue});callClicked(S.typeahead.filterForm.enter);ev('filter_enter_return',{button:ps(S.typeahead.filterForm.enter)});}catch(e){ev('filter_submit_error',{error:String(e)});}S.typeahead.filterForm.executing=false;}if(S.typeahead.pendingFilter&&!S.typeahead.filterExecuting){S.typeahead.pendingFilter=false;S.typeahead.filterExecuting=true;ev('filter_invoke_begin',{button:ps(S.typeahead.filterButton)});S.typeahead.filterForm={capturing:true,lineEdits:[],confirmed:null,enter:null,cancel:null,dateFrom:null,dateTo:null,pending:false,executing:false,fromValue:null,toValue:null,ready:false};try{callClicked(S.typeahead.filterButton);ev('filter_invoke_return',{button:ps(S.typeahead.filterButton)});}catch(e){ev('filter_invoke_error',{error:String(e)});}S.typeahead.filterExecuting=false;}if(S.batch.pendingInvoke&&!S.batch.executing){S.batch.pendingInvoke=false;S.batch.executing=true;ev('batch_invoke_begin',{widget:ps(S.batch.sourceWidget),signal_index:4});try{S.batch.activateOne(S.batch.sourceWidget,4);ev('batch_invoke_return',{widget:ps(S.batch.sourceWidget),signal_index:4});}catch(e){ev('batch_invoke_error',{error:String(e)});}S.batch.executing=false;}if(S.scheduleOpen){S.scheduleOpen=false;const id=S.openNative.schedule();ev('native_open_scheduled',{timer_id:ps(id),timer_proc:ps(S.openNative.timerProc)});}if(S.pendingOk&&!S.executingOk){S.pendingOk=false;S.executingOk=true;ev('ok_invoke_begin',{button:ps(S.ok)});try{callClicked(S.ok);ev('ok_invoke_return',{});}catch(e){ev('ok_invoke_error',{error:String(e)});}S.executingOk=false;}if(S.pendingLogin){const job=S.pendingLogin;S.pendingLogin=null;ev('login_begin',{set_username:true,set_password:true});try{makeQStringAndSet(S.authUser,job.username,false);makeQStringAndSet(S.authPass,job.password,true);callClicked(S.authOk);ev('login_return',{clicked_ok:true});}catch(e){ev('login_error',{error:String(e)});}job.password=null;}}});
 S.queueOpen=function(){if(!S.action)return{ok:false,error:'Connect QAction not mapped'};if(S.guiThread===null)return{ok:false,error:'GUI thread unknown'};S.scheduleOpen=true;ev('open_queued',{action:ps(S.action),gui_thread:S.guiThread});const ok=S.batch.postThread(S.guiThread,0,0,0);ev('open_wake_posted',{posted:ok});if(!ok)S.scheduleOpen=false;return{ok:!!ok,queued:!!ok};};
 S.queueOk=function(){if(!S.ok)return{ok:false,error:'Connection OK not mapped'};S.pendingOk=true;const ok=S.batch.postThread(S.guiThread,0,0,0);ev('ok_wake_posted',{posted:ok});if(!ok)S.pendingOk=false;return{ok:!!ok,queued:!!ok};};
 S.queueLogin=function(username,password){if(!S.authUser||!S.authPass||!S.authOk)return{ok:false,error:'Authorization mapping not ready'};if(S.pendingLogin)return{ok:false,error:'Login pending'};S.pendingLogin={username:username,password:password};ev('login_queued',{set_username:true,set_password:true});const ok=S.batch.postThread(S.guiThread,0,0,0);ev('login_wake_posted',{posted:ok});if(!ok)S.pendingLogin=null;return{ok:!!ok,queued:!!ok};};
 S.saveLearning=createSaveLearning({q:q,readQ:readQ,postThread:S.batch.postThread,buttonText:k=>(S.buttons[k]||{}).text});
 S.initialized=true;send({type:'log',message:'native modal flow ready'});return true;
}catch(e){S.error=String(e);send({type:'log',message:'flow error: '+e});return false;}}
let bootObserver=null,installationStarted=false;
function tryInstall(){if(S.initialized||installationStarted)return;if(mod('qt-mt.dll')&&mod('user32.dll')){installationStarted=true;moduleManifest('install');install();}}
moduleManifest('script_loaded');
if(typeof Process.attachModuleObserver==='function')bootObserver=Process.attachModuleObserver({onAdded(m){if(/^(qt-mt|user32)\.dll$/i.test(m.name))tryInstall();}});else{S.error='Frida Process.attachModuleObserver API is required';}
tryInstall();
rpc.exports={
submitfilter(fromValue,toValue){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};if(!S.typeahead.filterForm.ready)return{ok:false,error:'Filter form mapping not ready',line_edit_count:S.typeahead.filterForm.lineEdits.length,confirmed:ps(S.typeahead.filterForm.confirmed),enter:ps(S.typeahead.filterForm.enter)};if(!/^\d{8}$/.test(fromValue)||!/^\d{8}$/.test(toValue))return{ok:false,error:'Dates must be ddMMyyyy'};S.typeahead.filterForm.fromValue=fromValue;S.typeahead.filterForm.toValue=toValue;S.typeahead.filterForm.pending=true;ev('filter_submit_queued',{from:fromValue,to:toValue});const ok=S.batch.postThread(S.guiThread,0,0,0);if(!ok)S.typeahead.filterForm.pending=false;return{ok:!!ok,queued:!!ok,from:fromValue,to:toValue};},
activatecurrentoperation(){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};if(!S.typeahead.table)return{ok:false,error:'Batch table not mapped'};if(!S.batch.activateOne||!S.batch.postThread)return{ok:false,error:'Native functions not ready'};S.typeahead.pending=true;S.typeahead.query=null;S.typeahead.activateOnly=true;ev('current_operation_activation_queued',{table:ps(S.typeahead.table),signal_index:21});const ok=S.batch.postThread(S.guiThread,0,0,0);if(!ok){S.typeahead.pending=false;S.typeahead.activateOnly=false;}return{ok:!!ok,queued:!!ok,table:ps(S.typeahead.table),signal_index:21};},
bootstraptypeahead(){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};if(!S.typeahead.table)return{ok:false,error:'Batch table not mapped'};if(S.typeahead.edit)return{ok:true,already_ready:true,edit:ps(S.typeahead.edit),table:ps(S.typeahead.table)};if(!S.typeahead.keyCtor||!S.typeahead.keyDtor||!S.typeahead.sendEvent)return{ok:false,error:'Qt key API unavailable',api:S.typeahead.bootstrapApi};if(S.typeahead.bootstrapPending||S.typeahead.bootstrapExecuting)return{ok:false,error:'Bootstrap pending/executing'};S.typeahead.bootstrapPending=true;S.typeahead.bootstrapSent=false;S.typeahead.bootstrapError=null;ev('typeahead_bootstrap_queued',{table:ps(S.typeahead.table),qapp:ps(S.typeahead.qApp),api:S.typeahead.bootstrapApi});const ok=S.batch.postThread(S.guiThread,0,0,0);ev('typeahead_bootstrap_wake_posted',{posted:ok});if(!ok)S.typeahead.bootstrapPending=false;return{ok:!!ok,queued:!!ok,table:ps(S.typeahead.table),qapp:ps(S.typeahead.qApp),api:S.typeahead.bootstrapApi};},
invokefilter(){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};if(!S.typeahead.filterButton)return{ok:false,error:'Filter button not mapped'};if(S.typeahead.pendingFilter||S.typeahead.filterExecuting)return{ok:false,error:'Filter invoke pending/executing'};S.typeahead.pendingFilter=true;ev('filter_invoke_queued',{button:ps(S.typeahead.filterButton),receiver:ps(S.typeahead.filterReceiver)});const ok=S.batch.postThread(S.guiThread,0,0,0);ev('filter_wake_posted',{posted:ok});if(!ok)S.typeahead.pendingFilter=false;return{ok:!!ok,queued:!!ok,button:ps(S.typeahead.filterButton)};},
adopttypeaheadedit(){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};if(S.typeahead.edit)return{ok:true,already:true,edit:ps(S.typeahead.edit),table:ps(S.typeahead.table)};if(S.typeahead.lastLineEdit&&S.typeahead.table){S.typeahead.edit=S.typeahead.lastLineEdit;ev('typeahead_edit_adopted',{edit:ps(S.typeahead.lastLineEdit),table:ps(S.typeahead.table)});return{ok:true,adopted:true,edit:ps(S.typeahead.lastLineEdit),table:ps(S.typeahead.table)};}return{ok:false,error:'No QLineEdit candidate observed yet',last_line_edit:ps(S.typeahead.lastLineEdit),table:ps(S.typeahead.table)};},
invoketypeahead(query){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};if(!S.typeahead.table||!S.typeahead.edit)return{ok:false,error:'Type-ahead lazy QLineEdit not ready. Open Batch operations and type one bootstrap character first.',edit:ps(S.typeahead.edit),table:ps(S.typeahead.table)};if(!S.batch.activateOne||!S.batch.postThread)return{ok:false,error:'Native functions not ready'};if(S.typeahead.pending||S.typeahead.executing)return{ok:false,error:'Type-ahead invoke pending/executing'};S.typeahead.query=query||'on-h';S.typeahead.pending=true;ev('typeahead_invoke_queued',{edit:ps(S.typeahead.edit),table:ps(S.typeahead.table),query:S.typeahead.query,activation_signal_index:21});const ok=S.batch.postThread(S.guiThread,0,0,0);ev('typeahead_wake_posted',{posted:ok});if(!ok)S.typeahead.pending=false;return{ok:!!ok,queued:!!ok,edit:ps(S.typeahead.edit),table:ps(S.typeahead.table),query:S.typeahead.query,signal_index:21};},
invokebatch(){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};if(!S.batch.activateOne)return{ok:false,error:'activate_signal(int) missing'};if(!S.batch.sourceWidget)return{ok:false,error:'Batch source widget not discovered'};S.batch.pendingInvoke=true;ev('batch_invoke_queued',{widget:ps(S.batch.sourceWidget),signal_index:4});const ok=S.batch.postThread(S.guiThread,0,0,0);ev('batch_invoke_wake_posted',{posted:ok});if(!ok)S.batch.pendingInvoke=false;return{ok:!!ok,queued:!!ok,widget:ps(S.batch.sourceWidget),signal_index:4};},
armbatch(){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};S.batch.armed=true;S.batch.inputs=[];S.batch.signals=[];let best=null;for(const k in S.batch.tooltips){const t=S.batch.tooltips[k];if((t.text||'').toLowerCase().indexOf('batch operations')>=0&&(!best||t.time<best.time))best=t;}if(best){S.batch.sourceWidget=ptr(best.widget);S.batch.sourceTime=best.time;S.batch.tooltipWidget=S.batch.sourceWidget;S.batch.tooltipText=best.text;}ev('batch_capture_armed',{cached_tooltip_widget:ps(S.batch.tooltipWidget),cached_tooltip_text:S.batch.tooltipText});return{ok:true,cached_tooltip_widget:ps(S.batch.tooltipWidget),cached_tooltip_text:S.batch.tooltipText};},
batchsnapshot(){const w=ps(S.batch.tooltipWidget);return{source_widget:ps(S.batch.sourceWidget),source_time:S.batch.sourceTime,tooltip_widget:w,tooltip_text:S.batch.tooltipText,tooltips:Object.values(S.batch.tooltips).filter(t=>(t.text||'').toLowerCase().indexOf('batch operations')>=0),connections:S.batch.connections.filter(c=>c.sender===w||c.receiver===w),inputs:S.batch.inputs,signals:S.batch.signals,events:S.events.slice(-300)};},
status(){const learning=S.saveLearning?S.saveLearning.compact():null;return{learning:learning,initialized:S.initialized,error:S.error,action_ready:!!S.action,gui_thread:S.guiThread,connection_seen:!!S.connectionDialog,ok_ready:!!S.ok,authorization_seen:!!S.authDialog,authorization_dialog:ps(S.authDialog),schedule_open:S.scheduleOpen,pending_ok:S.pendingOk,authorization_mapping_ready:!!(S.authUser&&S.authPass&&S.authOk),authorization_username:ps(S.authUser),authorization_password:ps(S.authPass),authorization_ok:ps(S.authOk),pending_login:!!S.pendingLogin,typeahead_ready:!!(S.typeahead.table&&S.typeahead.edit),typeahead_edit:ps(S.typeahead.edit),typeahead_last_line_edit:ps(S.typeahead.lastLineEdit),typeahead_table:ps(S.typeahead.table),authorization_list_seen:S.typeahead.targetSeen,authorization_list_dialog:ps(S.typeahead.targetDialog),typeahead_direct_connected:S.typeahead.directConnected,filter_ready:!!S.typeahead.filterButton,filter_button:ps(S.typeahead.filterButton),filter_receiver:ps(S.typeahead.filterReceiver),filter_form_ready:S.typeahead.filterForm.ready,filter_confirmed:ps(S.typeahead.filterForm.confirmed),filter_date_from:ps(S.typeahead.filterForm.dateFrom),filter_date_to:ps(S.typeahead.filterForm.dateTo),filter_enter:ps(S.typeahead.filterForm.enter),filter_line_edit_count:S.typeahead.filterForm.lineEdits.length,typeahead_bootstrap_sent:S.typeahead.bootstrapSent,typeahead_bootstrap_receiver:ps(S.typeahead.bootstrapReceiver),typeahead_bootstrap_error:S.typeahead.bootstrapError,typeahead_qapp:ps(S.typeahead.qApp),typeahead_bootstrap_api:S.typeahead.bootstrapApi,save_qsignal_ready:!!(learning&&learning.verified),save_qsignal_object:ps(S.typeahead.saveQSignal.object),save_qsignal_value:S.typeahead.saveQSignal.value,save_qsignal_activate_export:S.typeahead.saveQSignal.activateExport,save_qsignal_last:S.typeahead.saveQSignal.last,save_select_dialog:ps(S.typeahead.saveQSignal.selectDialog),save_file_edit:ps(S.typeahead.saveQSignal.fileEdit),save_ok_button:ps(S.typeahead.saveQSignal.okButton),save_submit_ready:!!(S.typeahead.saveQSignal.fileEdit&&S.typeahead.saveQSignal.okButton),save_pending_submit:S.typeahead.saveQSignal.pendingSubmit,save_pending_click:S.typeahead.saveQSignal.pendingClick,save_submit_delay_ms:S.typeahead.saveQSignal.submitDelayMs,save_full_auto:S.typeahead.saveQSignal.fullAuto,save_export_path:S.typeahead.saveQSignal.exportPath,save_discovery_armed:S.typeahead.saveDiscover.armed,save_discovery_qsignal_count:Object.keys(S.typeahead.saveDiscover.qsignals).length,save_discovery_candidate_count:S.typeahead.saveDiscover.candidates.length,save_calibration_armed:S.typeahead.saveDiscover.calibrationArmed,save_calibration_confirmed_object:S.typeahead.saveDiscover.confirmedObject,save_calibration_confirmed_time:S.typeahead.saveDiscover.confirmedTime,save_fingerprint_candidate:S.typeahead.saveDiscover.autoCandidate,save_fingerprint_reason:S.typeahead.saveDiscover.autoReason,save_menu_item:S.typeahead.saveDiscover.confirmedItem,save_menu_object:S.typeahead.saveDiscover.confirmedMenu,save_menu_item_lookup_count:S.typeahead.saveDiscover.itemLookups.length,save_direct_ready:S.typeahead.saveDiscover.directReady,save_direct_candidate:S.typeahead.saveDiscover.directCandidate,save_direct_item:S.typeahead.saveDiscover.directItem,save_direct_menu:S.typeahead.saveDiscover.directMenu,save_direct_reason:S.typeahead.saveDiscover.directReason};},
open(){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};return S.queueOpen?S.queueOpen():{ok:false,error:'not initialized'};},
pressok(){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};return S.queueOk?S.queueOk():{ok:false,error:'not initialized'};},
login(username,password){if(S.disposeRequested)return{ok:false,error:'SHUTTING_DOWN'};return S.queueLogin?S.queueLogin(username,password):{ok:false,error:'not initialized'};},
result(){return{status:this.status(),events:S.events};},
learnsave(){return S.saveLearning?S.saveLearning.arm():{ok:false,error:'NOT_INITIALIZED'};},
finishsavelearning(){return S.saveLearning?S.saveLearning.finish():{ok:false,error:'NOT_INITIALIZED'};},
savereport(){return S.saveLearning?S.saveLearning.report():{error:'NOT_INITIALIZED'};},
invokeqsignalsave(){return S.saveLearning?S.saveLearning.queueReplay():{ok:false,error:'NOT_INITIALIZED'};},
savecommandstatus(id){return S.saveLearning?S.saveLearning.commandStatus(id):{ok:false,error:'NOT_INITIALIZED'};},
moduleaudit(){return moduleManifest('rpc');},
safedispose(){if(!disposeIdle())return{ok:false,error:'NATIVE_OR_MODAL_ACTIVE'};if(S.openNative&&S.guiThread!==null&&!S.disposeAck){S.disposeRequested=true;S.batch.postThread(S.guiThread,0,0,0);return{ok:false,error:'WAITING_GUI_DISPOSE_ACK'};}const r=S.saveLearning?S.saveLearning.dispose():{ok:true};if(r.ok&&bootObserver)bootObserver.detach();return r;},
autoadoptdirectsave(){return{ok:false,error:'LEGACY_SAVE_DISABLED_USE_H_J_M',note:'No fixed menu ID or item memory offset is used'};},
adoptdirectsave(){return{ok:false,error:'LEGACY_SAVE_DISABLED_USE_H_J_M',note:'No fixed menu ID or item memory offset is used'};},
fullexport(){return{ok:false,error:'LEGACY_SAVE_DISABLED_USE_H_J_M',note:'No fixed menu ID or item memory offset is used'};},
validatefingerprint(){return{ok:false,error:'LEGACY_SAVE_DISABLED_USE_H_J_M',note:'No fixed menu ID or item memory offset is used'};},
validatedirectsave(){return{ok:false,error:'LEGACY_SAVE_DISABLED_USE_H_J_M',note:'No fixed menu ID or item memory offset is used'};}
};
function disposeIdle(){return !(S.scheduleOpen||S.pendingOk||S.executingOk||S.pendingLogin||S.batch.executing||S.typeahead.executing||S.typeahead.filterExecuting||S.typeahead.filterForm.executing||(S.openNative&&!S.openNative.idle())||(S.saveLearning&&S.saveLearning.compact().executing));}
function moduleManifest(reason){
 const modules=Process.enumerateModules(),main=Process.mainModule||modules[0];
 const describe=m=>({name:m.name,path:m.path,base:m.base.toString(),size:m.size});
 const manifest={agent_build:'outcome-learning-1',reason:reason,time:Date.now(),pid:Process.id,arch:Process.arch,pointer_size:Process.pointerSize,main_module:main?describe(main):null,qt_modules:modules.filter(m=>m.name.toLowerCase()==='qt-mt.dll').map(describe),modules:modules.map(describe)};
 send({type:'log',message:'[MODULE_MANIFEST] '+JSON.stringify({pid:manifest.pid,arch:manifest.arch,main_module:manifest.main_module,qt_modules:manifest.qt_modules})});return manifest;
}
// Outcome-first learning. Integrated into agent.js by the build script.
function createSaveLearning(api) {
  const q=api.q, readQ=api.readQ, hooks=[], hookReport=[], objects=new Map(), signals=new Map();
  const edges=[], stacks=new Map(), samples=[];
  let generation=0, token=0, attempt=0, commandSerial=0, armed=null, selected=null;
  let job=null, executing=false, disposed=false, degraded=false, hookErrors=0, sampleSerial=0;
  const commands=new Map(), dialogs=new Map(), limits={objects:30000,edges:20000,samples:20};
  const reportCaption='List of authorization transactions';
  function log(kind,detail){ev('sl_'+kind,detail||{});}
  function failure(where,error){hookErrors++;log('hook_error',{where:where,error:String(error)});}
  function key(p){return typeof p==='string'?p:ps(p);}
  function reference(p,type){const a=key(p),r=(type==='QSignal'?signals:objects).get(a);return a?{address:a,generation:r?r.generation:null,type:type||'QObject'}:null;}
  function same(a,b){return !!(a&&b&&a.generation!==null&&a.address===b.address&&a.generation===b.generation&&a.type===b.type);}
  function live(r){if(!r||r.generation===null)return false;const x=(r.type==='QSignal'?signals:objects).get(r.address);if(!(x&&x.generation===r.generation&&x.state==='live'))return false;if(r.type==='QSignal'){const base=objects.get(r.address);return !!(base&&base.state==='live'&&base.generation===x.qobject_generation);}return true;}
  function rec(r){return live(r)?(r.type==='QSignal'?signals:objects).get(r.address):null;}
  function chain(r){const out=[],seen=new Set();while(r&&out.length<32){if(!live(r))break;const k=r.address+':'+r.generation;if(seen.has(k))break;seen.add(k);const x=rec(r);out.push({object:r,caption:x.caption||null,name:x.name||null});r=x.parent;}return out;}
  function under(r,root){return chain(r).some(x=>same(x.object,root));}
  function trace(context,caller){const describe=p=>{const m=Process.findModuleByAddress(p);return{address:p.toString(),module:m?m.name:null,rva:m?p.sub(m.base).toString():null};};let frames=[];let error=null;try{frames=Thread.backtrace(context,Backtracer.ACCURATE).map(describe);}catch(e){error=String(e);}return{caller:describe(caller),frames:frames,error:error};}
  function ctor(table,p,parent,name){const a=key(p);let x=table.get(a);if(x&&x.state==='constructing'){x.depth++;return;}if(!x&&table.size>=limits.objects){degraded=true;log('registry_limit',{limit:limits.objects});return;}table.set(a,{generation:++generation,state:'constructing',depth:1,parent:parent||null,name:name||null,caption:null});}
  function ctorDone(table,a){const x=table.get(a);if(x&&x.state==='constructing'&&--x.depth===0)x.state='live';}
  function invalidate(table,a){const x=table.get(a);if(x){x.state='dead';if(selected&&selected.signal.address===a)log('mapping_invalidated',{object:a,reason:'destructor'});}}
  function active(tid){return(stacks.get(tid)||[]).map(x=>({token:x.token,kind:x.kind,signal:x.signal,thread_id:tid,trace:x.trace}));}
  function startSignal(context,self,caller,kind){const tid=Process.getCurrentThreadId(),xs=stacks.get(tid)||[];const frame={token:++token,kind:kind,signal:reference(self,'QSignal'),trace:(armed||executing)?trace(context,caller):null};if(xs.length>=64){degraded=true;log('stack_limit',{thread_id:tid});return null;}xs.push(frame);stacks.set(tid,xs);if(armed||executing)log('signal_enter',{token:frame.token,signal:frame.signal,kind:kind});return{tid:tid,token:frame.token};}
  function endSignal(frame){if(!frame)return;const xs=stacks.get(frame.tid)||[],i=xs.findIndex(x=>x.token===frame.token);if(i>=0)xs.splice(i,1);if(!xs.length)stacks.delete(frame.tid);}
  function follow(signal,root){
    const paths=[],pending=[{node:signal,signature:null,steps:[],seen:[]}];
    while(pending.length&&paths.length<32){const item=pending.shift();if(item.steps.length>=6)continue;
      for(const e of edges){if(!e.active||!same(e.sender,item.node)||!live(e.receiver))continue;if(item.signature&&e.signal!==item.signature)continue;
        const step={signal:e.signal,receiver:e.receiver,member:e.slot},steps=item.steps.concat([step]);
        if(under(e.receiver,root))paths.push({steps:steps,anchored_to_report:true});
        const edgeKey=e.sender.address+e.signal+e.receiver.address+e.slot;
        if(e.slot&&e.slot[0]==='2'&&item.seen.indexOf(edgeKey)<0)pending.push({node:e.receiver,signature:e.slot,steps:steps,seen:item.seen.concat([edgeKey])});
      }
    }return paths;
  }
  function form(sample){
    const bound=edges.filter(e=>e.active&&same(e.receiver,sample.dialog));
    const edit=bound.find(e=>e.signal==='2textChanged(const QString&)'&&e.slot==='1edFileNameTextChanged(const QString&)'&&live(e.sender));
    const ok=bound.find(e=>e.signal==='2clicked()'&&e.slot==='1accept()'&&live(e.sender)&&norm(api.buttonText(e.sender.address))==='ok');
    return{filename_edit:edit?edit.sender:null,ok_button:ok?ok.sender:null,ready:!!(edit&&ok)};
  }
  function candidateList(sample){const result=[],seen=new Set();
    for(const frame of sample.active_signals){const r=frame.signal;if(!r||seen.has(r.address+':'+r.generation))continue;seen.add(r.address+':'+r.generation);
      const paths=follow(r,sample.report),reasons=[];
      if(!live(r))reasons.push('SIGNAL_LIFETIME_NOT_LIVE');
      if(!live(sample.report))reasons.push('REPORT_LIFETIME_NOT_LIVE');
      if(!sample.owner_matches_report)reasons.push('DIALOG_OWNER_NOT_REPORT');
      if(!paths.length)reasons.push('SIGNAL_RECEIVER_NOT_ANCHORED_TO_REPORT');
      if(sample.thread_id!==S.guiThread)reasons.push('THREAD_NOT_GUI');
      if(!capabilities.lifecycle)reasons.push('LIFECYCLE_HOOKS_MISSING');
      if(degraded||hookErrors)reasons.push('CAPTURE_DEGRADED');
      result.push({signal:r,kind:'QSignal',eligible:reasons.length===0,reasons:reasons,receiver_routes:paths,outgoing_connections:edges.filter(e=>e.active&&same(e.sender,r)).map(e=>({signal:e.signal,receiver:e.receiver,slot:e.slot,receiver_owner_chain:chain(e.receiver)})),trace:frame.trace});
    }return result;
  }
  function evaluate(sample){
    sample.form=form(sample);if(sample.form.ready){sample.observed_form=sample.form;sample.form_observed_ready=true;}sample.candidates=candidateList(sample);
    const eligible=sample.candidates.filter(x=>x.eligible);
    sample.status=!sample.form_observed_ready?'WAITING_FORM_EVIDENCE':!sample.shown?'WAITING_EXEC_OR_SHOW':eligible.length===1?'UNIQUE_CANDIDATE':eligible.length>1?'AMBIGUOUS_SIGNALS':'NO_ELIGIBLE_SIGNAL';
    if(sample.mode==='learn'&&sample.status==='UNIQUE_CANDIDATE'&&(!selected||selected.sample_id!==sample.id||!same(selected.signal,eligible[0].signal)))selected={signal:eligible[0].signal,report:sample.report,sample_id:sample.id,verified:false};
    if(sample.mode==='replay'&&job&&sample.command_id===job.id&&sample.status==='UNIQUE_CANDIDATE'&&same(eligible[0].signal,job.signal)){
      if(!job.outcome_seen){job.outcome_seen=true;job.status='outcome_observed';job.dialog=sample.dialog;log('replay_outcome',{command_id:job.id,dialog:sample.dialog,report:sample.report,form:sample.form,note:'Qt outcome observed; caller may remain inside modal exec until operator cancels'});}
    }
    if(sample.last_logged_status!==sample.status){sample.last_logged_status=sample.status;log('sample_status',{sample_id:sample.id,status:sample.status,mode:sample.mode,eligible_count:eligible.length,form:sample.form});}
  }
  function observeDialog(self,context,caller,source){
    const dialog=reference(self),object=rec(dialog);if(!object||object.caption!=='Select file')return;
    const tid=Process.getCurrentThreadId();let sample=null;
    if(armed){
      if(armed.sample_id)sample=samples.find(x=>x.id===armed.sample_id&&same(x.dialog,dialog));
      if(!sample){
        if(armed.sample_id){log('extra_dialog_ignored',{dialog:dialog,attempt:armed.id});return;}
        sample={id:++sampleSerial,attempt:armed.id,mode:'learn',report:armed.report,dialog:dialog,thread_id:tid,active_signals:active(tid),owner_chain:chain(dialog),owner_matches_report:under(dialog,armed.report),sources:[],shown:false,closed:false,trace:trace(context,caller)};
        armed.sample_id=sample.id;samples.push(sample);log('outcome_candidate',{sample_id:sample.id,dialog:dialog,owner_matches_report:sample.owner_matches_report,active_signals:sample.active_signals,trace:sample.trace});
      }
    }else if(executing&&job){
      sample=samples.find(x=>x.command_id===job.id&&same(x.dialog,dialog));
      if(!sample){sample={id:++sampleSerial,mode:'replay',command_id:job.id,report:job.report,dialog:dialog,thread_id:tid,active_signals:active(tid),owner_chain:chain(dialog),owner_matches_report:under(dialog,job.report),sources:[],shown:false,closed:false,trace:trace(context,caller)};samples.push(sample);}
    }
    if(!sample)return;
    if(sample.sources.indexOf(source)<0)sample.sources.push(source);
    if(source==='exec'||source==='show'){sample.shown=true;dialogs.set(dialog.address,{object:dialog,open:true});}
    evaluate(sample);
  }
  function updateForms(){for(const sample of samples.slice(-3)){if(live(sample.dialog)&&!sample.closed)evaluate(sample);}}
  function closeDialog(self,source){const r=reference(self),d=dialogs.get(key(self));if(d&&same(d.object,r))d.open=false;for(const sample of samples){if(same(sample.dialog,r)){sample.closed=true;sample.close_source=source;}}}
  const exports=q.enumerateExports().filter(e=>e.type==='function');
  const attached=new Set();
  function hook(label,pattern,callbacks){const matches=exports.filter(e=>pattern.test(e.name));let count=0;
    for(const e of matches){if(attached.has(e.address.toString()))continue;try{
      const guarded={};for(const name of ['onEnter','onLeave'])if(callbacks[name])guarded[name]=function(...args){try{return callbacks[name].apply(this,args);}catch(error){failure(label+':'+name,error);}};
      hooks.push(Interceptor.attach(e.address,guarded));attached.add(e.address.toString());count++;
    }catch(error){failure(label,error);}}
    hookReport.push({label:label,matched:matches.length,attached:count,names:matches.map(e=>e.name)});log('hook_inventory',hookReport[hookReport.length-1]);return count;
  }
  let activateEntry=exports.find(e=>e.name==='?activate@QSignal@@QAEXXZ')||null;
  if(!activateEntry){try{activateEntry=q.enumerateSymbols().find(e=>e.type==='function'&&(e.name==='?activate@QSignal@@QAEXXZ'||e.name==='QSignal::activate()'))||null;}catch(error){log('symbol_lookup_unavailable',{error:String(error)});}}
  const activate=activateEntry?new NativeFunction(activateEntry.address,'void',['pointer'],{abi:'thiscall',scheduling:'cooperative'}):null;
  const objCtor=hook('QObject::ctor',/^\?\?0QObject@@QAE@PAV0@PBD@Z$/,{onEnter(args){this.object=ps(this.context.ecx);ctor(objects,this.context.ecx,reference(args[0]),cs(args[1]));},onLeave(){ctorDone(objects,this.object);}});
  const objDtor=hook('QObject::dtor',/^\?\?1QObject@@/,{onEnter(){invalidate(objects,ps(this.context.ecx));invalidate(signals,ps(this.context.ecx));closeDialog(this.context.ecx,'QObject destructor');}});
  const sigCtor=hook('QSignal::ctor',/^\?\?0QSignal@@/,{onEnter(){this.object=ps(this.context.ecx);ctor(signals,this.context.ecx,null,null);},onLeave(){ctorDone(signals,this.object);const r=signals.get(this.object),base=objects.get(this.object);if(r&&base)r.qobject_generation=base.generation;}});
  const sigDtor=hook('QSignal::dtor',/^\?\?1QSignal@@/,{onEnter(){invalidate(signals,ps(this.context.ecx));}});
  const connectCount=hook('QObject::connect',/^\?connect@QObject@@SA_NPBV1@PBD01@Z$/,{onEnter(args){this.edge={sender:reference(args[0],signals.has(ps(args[0]))&&live(reference(args[0],'QSignal'))?'QSignal':null),signal:cs(args[1]),receiver:reference(args[2]),slot:cs(args[3]),active:true};},onLeave(ret){
    if(!(ret.toInt32()&255))return;const e=this.edge;
    const relevant=e.sender&&((e.sender.type==='QSignal')||e.signal==='2clicked()'||(e.slot&&/edFileNameTextChanged|accept\(|reject\(/.test(e.slot)));
    if(!relevant)return;if(edges.length>=limits.edges){degraded=true;log('edge_limit',{limit:limits.edges});return;}edges.push(e);if(armed||executing)log('connection',e);updateForms();
  }});
  const disconnectCount=hook('QObject::disconnect',/^\?disconnect@QObject@@SA_NPBV1@PBD01@Z$/,{onEnter(args){this.pattern={sender:ps(args[0]),signal:cs(args[1]),receiver:ps(args[2]),slot:cs(args[3])};},onLeave(ret){if(!(ret.toInt32()&255))return;const p=this.pattern;for(const e of edges)if((!p.sender||e.sender.address===p.sender)&&(!p.receiver||e.receiver.address===p.receiver)&&(!p.signal||e.signal===p.signal)&&(!p.slot||e.slot===p.slot))e.active=false;}});
  if(activateEntry){
    try{hooks.push(Interceptor.attach(activateEntry.address,{onEnter(){try{this.frame=startSignal(this.context,this.context.ecx,this.returnAddress,'activate');}catch(e){failure('activate enter',e);}},onLeave(){endSignal(this.frame);}}));log('activate_profile',{name:activateEntry.name,address:ps(activateEntry.address),prototype:'void QSignal::activate()',abi:'thiscall',extra_integer_argument:false});}catch(e){failure('activate hook',e);}
  }
  const variantCount=hook('QSignal::signal(QVariant)',/^\?signal@QSignal@@[IQ]AEXABVQVariant@@@Z$/,{onEnter(){this.frame=startSignal(this.context,this.context.ecx,this.returnAddress,'variant_signal');},onLeave(){endSignal(this.frame);}});
  const intCount=hook('QSignal::intSignal(int)',/^\?intSignal@QSignal@@[IQ]AEXH@Z$/,{onEnter(args){this.frame=startSignal(this.context,this.context.ecx,this.returnAddress,'int_signal');if(armed||executing)log('integer_observed',{signal:reference(this.context.ecx,'QSignal'),value:args[0].toInt32(),note:'diagnostic only; never used as selector'});},onLeave(){endSignal(this.frame);}});
  hook('QWidget::setCaption',/^\?setCaption@QWidget@@UAEXABVQString@@@Z$/,{onEnter(args){const t=readQ(args[0]),r=rec(reference(this.context.ecx));if(r&&t!==null)r.caption=t;if(t==='Select file')observeDialog(this.context.ecx,this.context,this.returnAddress,'caption');}});
  hook('QDialog::exec',/^\?exec@QDialog@@[QU]AEHXZ$/,{onEnter(){this.object=this.context.ecx;observeDialog(this.context.ecx,this.context,this.returnAddress,'exec');},onLeave(){closeDialog(this.object,'exec returned');}});
  hook('QWidget/QDialog::show',/^\?show@Q(Widget|Dialog)@@[QU]AEXXZ$/,{onEnter(){observeDialog(this.context.ecx,this.context,this.returnAddress,'show');}});
  hook('QWidget/QDialog::hide',/^\?hide@Q(Widget|Dialog)@@[QU]AEXXZ$/,{onEnter(){closeDialog(this.context.ecx,'hide');}});
  hook('QDialog::accept/reject',/^\?(accept|reject)@QDialog@@[QU]AEXXZ$/,{onEnter(){closeDialog(this.context.ecx,'accept/reject');}});
  hook('QFileDialog::ctor (optional)',/^\?\?0QFileDialog@@/,{onEnter(){if(armed||executing)log('qfiledialog_ctor_candidate',{object:ps(this.context.ecx),trace:trace(this.context,this.returnAddress)});}});
  const capabilities={lifecycle:!!(objCtor&&objDtor&&sigCtor&&sigDtor&&disconnectCount),connections:!!connectCount,activation:!!activateEntry,variant_hook:!!variantCount,int_hook:!!intCount,replay:!!(activate&&objCtor&&objDtor&&sigCtor&&sigDtor&&connectCount&&disconnectCount)};
  function reports(){return Array.from(objects.entries()).filter(([a,x])=>x.state==='live'&&x.caption===reportCaption).map(([a])=>reference(a));}
  function isDialogOpen(){return Array.from(dialogs.values()).some(d=>d.open&&live(d.object));}
  function report(){for(const sample of samples)if(sample.mode==='learn')evaluate(sample);return{version:'outcome-learning-1',capabilities:capabilities,hooks:hookReport,armed:armed,selected:selected,mapping_live:!!(selected&&live(selected.signal)&&live(selected.report)),verified:!!(selected&&selected.verified&&live(selected.signal)&&live(selected.report)),samples:samples,commands:Array.from(commands.values()),executing:executing,dialog_open:isDialogOpen(),registry:{objects:objects.size,signals:signals.size,edges:edges.length},diagnostic_connections:edges.filter(e=>e.active).slice(-5000),diagnostic_connections_truncated:edges.filter(e=>e.active).length>5000,degraded:degraded,hook_errors:hookErrors,active_signals:Array.from(stacks.entries()).map(([tid])=>({thread_id:tid,frames:active(tid)})),report_candidates:reports()};}
  function arm(){
    if(disposed||S.disposeRequested)return{ok:false,error:'DISPOSED_OR_SHUTTING_DOWN'};if(executing||job&&job.status==='queued')return{ok:false,error:'REPLAY_BUSY'};
    if(isDialogOpen())return{ok:false,error:'CLOSE_SELECT_FILE_FIRST'};
    const roots=reports();if(roots.length!==1)return{ok:false,error:'REPORT_OWNER_NOT_UNIQUE',report_candidates:roots,expected_caption:reportCaption};
    if(!capabilities.lifecycle||!capabilities.connections)return{ok:false,error:'REQUIRED_HOOKS_MISSING',capabilities:capabilities};
    if(samples.length>=limits.samples)return{ok:false,error:'SAMPLE_LIMIT_RESTART_RUN'};
    selected=null;armed={id:++attempt,report:roots[0],sample_id:null,time:Date.now()};log('armed',armed);return{ok:true,armed:armed,instruction:'Manually choose child File > Save as, observe Select file, Cancel, then j'};
  }
  function finishLearning(){if(executing)return{ok:false,error:'REPLAY_STILL_EXECUTING'};if(isDialogOpen())return{ok:false,error:'CLOSE_SELECT_FILE_FIRST'};if(armed&&armed.sample_id){const sample=samples.find(x=>x.id===armed.sample_id);if(sample)evaluate(sample);}const result=report();armed=null;result.armed=null;log('learning_finished',{candidate:result.selected,verified:result.verified});return{ok:!!(result.selected&&result.mapping_live),report:result};}
  function validateSelection(){
    if(!selected)return'NO_UNIQUE_LEARNED_CANDIDATE';if(!live(selected.signal)||!live(selected.report))return'STALE_MAPPING_RELEARN';
    const sample=samples.find(x=>x.id===selected.sample_id);if(!sample)return'SAMPLE_MISSING';
    const candidates=candidateList(sample).filter(x=>x.eligible);if(candidates.length!==1||!same(candidates[0].signal,selected.signal))return'LEARNED_ROUTE_CHANGED';
    if(!capabilities.replay)return'REPLAY_CAPABILITY_UNAVAILABLE';return null;
  }
  function queueReplay(){
    if(disposed||S.disposeRequested)return{ok:false,error:'DISPOSED_OR_SHUTTING_DOWN'};if(armed)return{ok:false,error:'FINISH_LEARNING_WITH_J_FIRST'};
    if(executing||job&&job.status==='queued')return{ok:false,error:'REPLAY_BUSY'};if(isDialogOpen())return{ok:false,error:'CLOSE_SELECT_FILE_FIRST'};
    if(samples.length>=limits.samples)return{ok:false,error:'SAMPLE_LIMIT_RESTART_RUN'};const error=validateSelection();if(error)return{ok:false,error:error};
    const command={id:++commandSerial,status:'queued',signal:selected.signal,report:selected.report,queued_at:Date.now(),outcome_seen:false,finished:false};job=command;commands.set(command.id,command);
    const posted=api.postThread(S.guiThread,0,0,0);if(!posted){command.status='failed';command.error='WAKE_POST_FAILED';command.finished=true;log('wake_failed',{command_id:command.id});return{ok:false,command_id:command.id,error:command.error};}
    log('replay_queued',{command_id:command.id,signal:command.signal,posted:true});return{ok:true,queued:true,command_id:command.id,note:'Queued only; not dialog success'};
  }
  function dispatch(){
    if(disposed||executing||!job||job.status!=='queued')return;const command=job;
    if(Date.now()-command.queued_at>15000){command.status='failed';command.error='QUEUE_EXPIRED';command.finished=true;return;}
    const error=validateSelection();if(error){command.status='failed';command.error=error;command.finished=true;log('replay_rejected',{command_id:command.id,error:error});return;}
    executing=true;command.status='started';command.started_at=Date.now();log('replay_begin',{command_id:command.id,signal:command.signal,thread_id:Process.getCurrentThreadId()});
    try{activate(ptr(command.signal.address));command.status=command.outcome_seen?'completed':'failed';if(!command.outcome_seen)command.error='NO_MATCHING_SELECT_FILE_OUTCOME';if(command.outcome_seen&&selected&&same(selected.signal,command.signal)){selected.verified=true;S.typeahead.saveQSignal.object=ptr(selected.signal.address);S.typeahead.saveQSignal.activateFn=activate;S.typeahead.saveQSignal.activateExport=activateEntry.name;S.typeahead.saveQSignal.value=null;}}
    catch(e){command.status='failed';command.error=String(e);}
    finally{command.finished=true;command.returned_at=Date.now();executing=false;log('replay_return',{command_id:command.id,status:command.status,outcome_seen:command.outcome_seen,error:command.error||null,verified:!!(selected&&selected.verified)});}
  }
  function commandStatus(id){const command=commands.get(Number(id));if(!command)return{ok:false,error:'UNKNOWN_COMMAND'};if(command.status==='queued'&&Date.now()-command.queued_at>15000){command.status='failed';command.error='QUEUE_NOT_DISPATCHED';command.finished=true;}return{ok:true,command:command};}
  function dispose(){if(executing)return{ok:false,error:'CLOSE_MODAL_REPLAY_FIRST'};disposed=true;armed=null;if(job&&job.status==='queued'){job.status='cancelled';job.finished=true;}for(const h of hooks)h.detach();return{ok:true,disposed:true};}
  function compact(){return{version:'outcome-learning-1',armed:!!armed,selected:selected,mapping_live:!!(selected&&live(selected.signal)&&live(selected.report)),verified:!!(selected&&selected.verified&&live(selected.signal)&&live(selected.report)),executing:executing,dialog_open:isDialogOpen(),degraded:degraded,hook_errors:hookErrors,capabilities:capabilities};}
  log('ready',{capabilities:capabilities,required_report_caption:reportCaption});
  return{arm:arm,finish:finishLearning,report:report,compact:compact,queueReplay:queueReplay,dispatch:dispatch,commandStatus:commandStatus,dispose:dispose};
}

