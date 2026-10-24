"""Bounded browser schemas, durable summaries and evidence-based loop detection."""
import hashlib
import json

ACTION_KEYS={
 'goto':({'url'},set()), 'snapshot':(set(),set()), 'diagnostics':(set(),set()),
 'inspect':({'selector'},set()),'read_resource':({'url'},set()),
 'click':({'selector'},set()),'fill':({'selector','value'},set()),
 'select':({'selector','value'},set()),'check':({'selector'}, {'checked'}),
 'press':({'selector','key'},set()),'wait':({'selector'},set()),
 'assert_text':({'text'},{'selector'}),'download':({'selector','name'},set()),
 'read_xlsx':({'name'},set()),'upload_csv':({'selector','content'},set()),
 'record':({'data'},{'pause'}),'for_each_row':({'table','steps'},set())}

def validate_actions(actions,row=False):
    if not isinstance(actions,list) or not 1<=len(actions)<=(20 if row else 30):raise ValueError('Expected bounded nonempty browser actions')
    for item in actions:
        if not isinstance(item,dict) or not isinstance(item.get('action'),str) or item['action'] not in ACTION_KEYS:raise ValueError('Unknown browser action')
        action=item['action'];required,optional=ACTION_KEYS[action]
        if not required<=item.keys() or not item.keys()<=required|optional|{'action'}:raise ValueError('Invalid keys for '+action)
        if row and action not in ('fill','click','press','select','check','assert_text','wait'):raise ValueError('Unsupported row action')
        for key in ('selector','url','name','table','text','key','content','value'):
            if key in item and (not isinstance(item[key],str) or len(item[key])>(1048576 if key=='content' else 4000 if key in ('text','value') else 500)):raise ValueError('Invalid text field: '+key)
        for key in ('checked','pause'):
            if key in item and type(item[key]) is not bool:raise ValueError(key+' must be boolean')
        if action=='record':
            if not isinstance(item['data'],(dict,list)) or len(json.dumps(item['data'],allow_nan=False).encode())>65536:raise ValueError('Invalid structured record')
        if action=='for_each_row':validate_actions(item['steps'],row=True)

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def progress(item,message,result,cached=False):
    """Only repeated mutations/errors pause. Repeated read-only observations are allowed."""
    state=item.setdefault('progress',{'recent':[],'stalled':0,'failures':0})
    observation=result.get('observation',item.get('observation',{})) if isinstance(result,dict) else {}
    visible={k:observation.get(k) for k in ('url','text','fields','buttons','links','tables')}
    signature=fingerprint({'tool':message['tool'],'arguments':message['arguments'],'visible':visible})
    actions=message['arguments'].get('actions',[])
    mutating=message['tool'] not in ('playwright','session.memory','project.list','project.read','project.diff','project.inspect') or any(a['action'] in ('click','fill','check','select','press','upload_csv','for_each_row','goto') for a in actions)
    recent=state['recent'];repeat=bool(recent and recent[-1]['signature']==signature)
    state['stalled']=(state['stalled']+1 if repeat else 1) if mutating or cached else 0
    state['failures']=state['failures']+1 if isinstance(result,dict) and result.get('ok') is False else 0
    recent.append({'turn':item['turns'],'tool':message['tool'],'id':message['id'],'signature':signature,'ok':result.get('ok',True) if isinstance(result,dict) else True,'cached':cached})
    state['recent']=recent[-8:];state['lastAction']=message['tool']+': '+', '.join(a['action'] for a in actions)
    if state['stalled']>=3 or state['failures']>=3:
        state['reason']='Ba lần thao tác không đổi trạng thái quan sát được.' if state['stalled']>=3 else 'Ba lần gọi tool liên tiếp bị lỗi.'
        state['suggestion']='Kiểm tra diagnostics và selector, đổi cách tiếp cận rồi tiếp tục; không cần cấp thêm lượt nếu vẫn còn ngân sách.'
        item['pauseRequested']=True
    else:state['reason']='';state['suggestion']=''
    return state

def summary(item):
    return {'version':1,'id':item['id'],'status':item['status'],'phase':item['phase'],
      'turns':item['turns'],'budget':item['budget'],'url':item.get('lastUrl',item['url']),
      'projects':item.get('projects',[]),'deliverables':item.get('deliverables',[])[-10:],'downloads':item.get('downloadNames',[]),
      'progress':item.get('progress',{}),'pendingCall':item.get('pendingCall') if item['phase'] in ('tool_inflight','waiting_run') else None,
      'recentResults':[{'turn':t['turn'],'ok':t.get('toolResult',{}).get('ok'),'error':t.get('toolResult',{}).get('error','')[:400]} for t in item['trace'][-6:]],
      'answer':item.get('answer','')[:2000],'recoveryReason':item.get('recoveryReason',''),
      'notes':item.get('notes',[])[-12:],'imageBatches':list(item.get('imageBatches',{})),
      'resumePolicy':'Fresh DOM after restart; never replay uncertain side effects or grant turns automatically.'}
