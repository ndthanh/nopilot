"""Stateful Python Playwright action runner, also bundled into replay projects."""
import json
import sys
import pathlib
import re
import socket
import ipaddress
import urllib.parse
import zipfile
import csv
import io
import uuid
from collections import deque
from reliability import validate_actions
import xml.etree.ElementTree as ET

def public(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password or p.port not in (None,80,443):raise ValueError('Use a public HTTP(S) URL')
    if any(not ipaddress.ip_address(a[4][0]).is_global for a in socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)):raise ValueError('Private network URL is not allowed')
    return url

def origin(url):
    p=urllib.parse.urlsplit(url);return p.scheme,p.hostname,p.port or (443 if p.scheme=='https' else 80)

def xlsx_rows(path):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist())>8*1024*1024:raise ValueError('Spreadsheet is too large')
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));rows=[]
        for row in sheet.findall('.//s:sheetData/s:row',ns)[:101]:
            values={}
            for cell in row.findall('s:c',ns):
                col=re.sub(r'\d','',cell.get('r',''));v=cell.find('s:v',ns)
                value=v.text if v is not None else ''.join(cell.find('s:is',ns).itertext()) if cell.find('s:is',ns) is not None else ''
                if cell.get('t')=='s':value=strings[int(value)]
                values[col]=value or ''
            rows.append(values)
    if not rows:return []
    return [{header.strip():row.get(col,'') for col,header in rows[0].items() if header.strip()} for row in rows[1:] if any(row.values())]

class BrowserSession:
    def __init__(self,url,directory,headless=True):
        try:from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as error:raise RuntimeError('Install optional browser dependencies with: .venv\\Scripts\\python.exe -m pip install -r requirements-browser.txt') from error
        self.url=public(url);self.allowed=origin(url);self.directory=pathlib.Path(directory).resolve();self.directory.mkdir(parents=True,exist_ok=True)
        self.history=[];self.files={};self.tables={};self.steps=0
        self.events=deque(maxlen=100)
        self.driver=sync_playwright().start()
        try:
            self.browser=self.driver.chromium.launch(channel='msedge',headless=headless)
            self.context=self.browser.new_context(accept_downloads=True,service_workers='block')
            self.context.set_default_timeout(6000);self.page=self.context.new_page()
            self.page.on('console',lambda msg:self.event('console',level=msg.type,message=msg.text[:1200]) if msg.type in ('error','warning') else None)
            self.page.on('pageerror',lambda error:self.event('pageerror',message=str(error)[:1200]))
            self.page.on('requestfailed',lambda req:self.event('requestfailed',url=self.safe_url(req.url),failure=str(req.failure)[:300]))
            self.page.on('response',lambda res:self.event('http_error',url=self.safe_url(res.url),status=res.status) if res.status>=400 else None)
            self.page.on('dialog',lambda dialog:dialog.dismiss())
            self.context.on('page',lambda popup:popup.close() if popup!=self.page else None)
            def guard(route):
                try:
                    public(route.request.url)
                    if route.request.is_navigation_request() and route.request.frame==self.page.main_frame and origin(route.request.url)!=self.allowed:raise ValueError('Outside authorized origin')
                    route.continue_()
                except Exception as error:
                    self.event('blocked',url=self.safe_url(route.request.url),reason=str(error)[:200]);route.abort()
            self.context.route('**/*',guard)
            if hasattr(self.context,'route_web_socket'):self.context.route_web_socket('**/*',lambda ws:ws.close())
            self.execute({'action':'goto','url':url})
        except BaseException:self.close();raise

    @staticmethod
    def safe_url(url):
        parts=urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,'',''))[:1200]

    def event(self,kind,**data):self.events.append({'kind':kind,**data})

    def diagnostics(self):return {'url':self.safe_url(self.page.url),'events':list(self.events),'note':'Bounded console warnings/errors and failed/blocked requests; URL query strings, headers and response bodies are omitted.'}

    def snapshot(self):
        return {'url':self.page.url,'title':self.page.title(),'text':self.page.locator('body').inner_text()[:16000],
                'fields':self.page.locator('input,select,textarea').evaluate_all("es=>es.slice(0,100).map(e=>({tag:e.tagName,type:e.type,id:e.id,name:e.name,value:e.value,checked:e.checked,disabled:e.disabled,options:e.options?Array.from(e.options).map(o=>({value:o.value,text:o.text})):undefined,placeholder:e.placeholder,ariaLabel:e.getAttribute('aria-label'),attributes:Object.fromEntries(Array.from(e.attributes).filter(a=>!['value','style','class'].includes(a.name)).map(a=>[a.name,a.value])),label:e.labels?.[0]?.innerText||e.parentElement?.innerText.slice(0,150)}))"),
                'buttons':self.page.locator('button,input[type=submit]').evaluate_all("es=>es.slice(0,80).map(e=>({text:e.innerText||e.value,id:e.id,type:e.type,ariaLabel:e.getAttribute('aria-label')}))"),
                'links':self.page.locator('a[href]').evaluate_all("es=>es.slice(0,60).map(e=>({text:e.innerText,url:e.href}))"),
                'downloads':list(self.files),'tables':self.tables}

    def execute(self,item,row=None):
        if getattr(self,'cancel_check',lambda:False)():raise InterruptedError('Pause requested; completed actions are retained, do not replay them blindly')
        if not isinstance(item,dict):raise ValueError('Each action must be an object')
        item=dict(item)
        if row is not None:
            for key,value in list(item.items()):
                if isinstance(value,str):
                    for column,data in row.items():value=value.replace('${'+column+'}',data)
                    item[key]=value
        self.steps+=1
        if self.steps>1500:raise ValueError('Browser action budget exhausted')
        action=item.get('action');selector=item.get('selector','')
        if not isinstance(selector,str) or len(selector)>500:raise ValueError('Invalid selector')
        if action=='goto':
            target=public(item['url'])
            if origin(target)!=self.allowed:raise ValueError('Navigation must stay on the user supplied origin')
            self.page.goto(target,wait_until='domcontentloaded',timeout=30000)
        elif action=='snapshot':return self.snapshot()
        elif action=='diagnostics':return self.diagnostics()
        elif action=='record':
            data=item.get('data')
            if not isinstance(data,(dict,list)):raise ValueError('record data must be a JSON object or array')
            encoded=json.dumps(data,ensure_ascii=False,indent=2)
            if len(encoded.encode('utf-8'))>65536:raise ValueError('Structured note exceeds64KiB')
            name='notes-'+uuid.uuid4().hex[:10]+'.json'
            with (self.directory/name).open('x',encoding='utf-8') as file:file.write(encoded)
            return {'ok':True,'action':'record','name':name,'data':data}
        elif action=='inspect':
            if not selector:raise ValueError('inspect requires a CSS selector')
            return {'elements':self.page.locator(selector).evaluate_all("es=>es.slice(0,80).map(e=>({tag:e.tagName,text:(e.innerText||e.textContent||'').slice(0,3000),attributes:Object.fromEntries(Array.from(e.attributes).map(a=>[a.name,a.value])),rect:(r=>({x:r.x,y:r.y,width:r.width,height:r.height}))(e.getBoundingClientRect()),html:e.outerHTML.slice(0,6000)}))")}
        elif action=='read_resource':
            url=public(urllib.parse.urljoin(self.page.url,item['url']))
            if origin(url)!=self.allowed:raise ValueError('Resource must stay on the authorized origin')
            response=self.context.request.get(url,max_redirects=0,timeout=30000)
            try:
                if 300<=response.status<400:raise ValueError('Resource redirects are not followed')
                data=response.body()
                if len(data)>2*1024*1024:raise ValueError('Resource exceeds2MiB')
                return {'url':url,'status':response.status,'contentType':response.headers.get('content-type',''),'text':data.decode('utf-8',errors='replace')[:100000]}
            finally:response.dispose()
        elif action=='upload_csv':
            content=item.get('content')
            if not isinstance(content,str) or len(content.encode('utf-8'))>1024*1024 or '\x00' in content:raise ValueError('CSV must be UTF-8 text up to1MiB')
            rows=list(csv.reader(io.StringIO(content)))
            if not rows or len(rows)>2000 or any(len(row)>100 for row in rows):raise ValueError('Expected1..2000 CSV rows with at most100columns')
            target=self.directory/'generated-submission.csv';target.write_text(content,encoding='utf-8',newline='')
            self.page.locator(selector).set_input_files(str(target))
        elif action=='check':self.page.locator(selector).set_checked(item.get('checked',True) is True)
        elif action=='click':self.page.locator(selector).click()
        elif action=='fill':self.page.locator(selector).fill(str(item['value'])[:4000])
        elif action=='select':self.page.locator(selector).select_option(str(item['value']))
        elif action=='press':
            if item.get('key') not in ('Enter','Tab','Escape','ArrowDown','ArrowUp'):raise ValueError('Unsupported key')
            self.page.locator(selector).press(item['key'])
        elif action=='wait':self.page.locator(selector).wait_for(state='visible',timeout=10000)
        elif action=='assert_text':
            text=str(item['text'])
            actual=self.page.locator(selector or 'body').inner_text()
            if not text.strip() or (text not in actual and ' '.join(text.split()) not in ' '.join(actual.split())):raise AssertionError('Expected text not present: '+text[:200])
        elif action=='download':
            name=item['name']
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',name) or name.startswith('.'):raise ValueError('Invalid download name')
            link=self.page.locator(selector);href=link.get_attribute('href')
            target=self.directory/name
            if href and urllib.parse.urlsplit(urllib.parse.urljoin(self.page.url,href)).scheme in ('http','https'):
                url=urllib.parse.urljoin(self.page.url,href)
                for redirect in range(6):
                    public(url)
                    if origin(url)!=self.allowed:raise ValueError('Download must stay on the authorized origin')
                    response=self.context.request.get(url,max_redirects=0,timeout=30000)
                    if response.status in (301,302,303,307,308):
                        url=urllib.parse.urljoin(url,response.headers.get('location',''));response.dispose();continue
                    if not response.ok:raise RuntimeError('Download HTTP '+str(response.status))
                    if int(response.headers.get('content-length','0'))>2*1024*1024:raise ValueError('Download exceeds 2 MiB')
                    data=response.body();response.dispose()
                    if len(data)>2*1024*1024:raise ValueError('Download exceeds 2 MiB')
                    target.write_bytes(data);break
                else:raise ValueError('Too many download redirects')
            else:
                with self.page.expect_download(timeout=30000) as download:link.click()
                download.value.save_as(target)
            if target.stat().st_size>2*1024*1024:target.unlink();raise ValueError('Download exceeds 2 MiB')
            self.files[name]=target
        elif action=='read_xlsx':
            name=item['name']
            if name not in self.files:raise ValueError('Only files downloaded in this session can be read')
            self.tables[name]=xlsx_rows(self.files[name])
        elif action=='for_each_row':
            table=self.tables.get(item.get('table'))
            if table is None:raise ValueError('Download/read_xlsx before iterating a table')
            steps=item.get('steps',[])
            if not isinstance(steps,list) or not 1<=len(steps)<=20:raise ValueError('Expected 1..20 row steps')
            if any(step.get('action') not in ('fill','click','press','select','check','assert_text','wait') for step in steps):raise ValueError('Unsupported row action')
            for values in table:
                for step in steps:
                    resolved={key:(self.template(value,values) if isinstance(value,str) else value) for key,value in step.items()}
                    self.execute(resolved);self.history.append(resolved)
        else:raise ValueError('Unsupported browser action: '+str(action))
        return {'ok':True,'action':action}

    def run(self,actions):
        validate_actions(actions)  # Reject the whole malformed batch before its first mutation.
        results=[]
        for action in actions:
            try:
                result=self.execute(action)
                if action.get('action')!='for_each_row':self.history.append(action)
                results.append(result)
            except Exception as error:
                return {'ok':False,'error':str(error)[:1800],'completed':len(results),'results':results,'observation':self.snapshot(),'diagnostics':self.diagnostics()}
        return {'ok':True,'results':results,'observation':self.snapshot()}

    @staticmethod
    def template(value,row):
        for column,data in row.items():value=value.replace('${'+column+'}',data)
        return value

    def close(self):
        if getattr(self,'browser',None):self.browser.close()
        if getattr(self,'driver',None):self.driver.stop()

def replay(project,headless=True):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    data=json.loads((pathlib.Path(project)/'actions.json').read_text(encoding='utf-8'))
    session=BrowserSession(data['url'],pathlib.Path(project)/'downloads',headless=headless)
    try:
        # Replays one action at a time; exported traces can contain >30 actions.
        for action in data['actions']:
            result=session.run([action])
            if not result['ok']:raise RuntimeError(json.dumps(result,ensure_ascii=False))
        print(json.dumps(session.snapshot(),ensure_ascii=False,indent=2))
    finally:session.close()
