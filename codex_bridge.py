"""Thin, bounded adapter to the installed Codex app-server and ChatGPT plan."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import tomllib
from decimal import Decimal, InvalidOperation

class CodexError(Exception):pass
class Cancelled(CodexError):pass


def check_subscription(account, raw):
    buckets=raw.get('rateLimitsByLimitId') or {'codex':raw.get('rateLimits')}
    bucket=buckets.get('codex')
    if not isinstance(bucket,dict):raise CodexError('Cannot verify the Codex usage allowance. No generation request was sent.')
    credit=bucket.get('credits') or {}
    try:zero=Decimal(str(credit.get('balance')))==0
    except InvalidOperation:zero=False
    windows=[bucket.get('primary'),bucket.get('secondary')]
    if account.get('type')!='chatgpt' or account.get('planType')!='plus':
        raise CodexError('Cannot confirm a ChatGPT Plus session. Nothing was generated. Check your login in Codex.')
    if credit.get('hasCredits') is not False or credit.get('unlimited') is not False or not zero:
        raise CodexError('Cannot confirm subscription-only usage: extra credits are present or their status is unknown. Nothing was generated.')
    if bucket.get('rateLimitReachedType') is not None or any(not isinstance(w,dict) or type(w.get('usedPercent')) not in (int,float) or not 0<=w['usedPercent']<100 for w in windows):
        raise CodexError('Codex  usage allowance is exhausted or unknown. Wait for it to reset before trying again.')
    return {'type':account['type'],'plan':account['planType'],'remaining':[100-w['usedPercent'] for w in windows]}


def resolve_codex():
    bundled=Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex')
    if bundled.is_file() and os.access(bundled,os.X_OK):return str(bundled)
    return shutil.which('codex')


def run_generation(prompt, schema, cancelled, progress, log_dir, image_paths=None):
    binary=resolve_codex()
    if not binary:raise CodexError('Codex was not found on this computer. Check your installed Codex runtime.')
    log_dir=Path(log_dir);log_dir.mkdir(parents=True,exist_ok=True)
    (log_dir/'prompt.txt').write_text(prompt,encoding='utf-8')
    config=Path.home()/'.codex/config.toml'
    cfg=tomllib.loads(config.read_text()) if config.exists() else {}
    args=[binary,'app-server','--listen','stdio://','-c','forced_login_method="chatgpt"','-c','model_provider="openai"','-c','memories.generate_memories=false','-c','memories.use_memories=true','-c','features.apps=false']
    for section in ('mcp_servers','plugins'):
        for name in cfg.get(section,{}):args+=['-c',section+'.'+name+'.enabled=false']
    env={k:v for k,v in os.environ.items() if not k.endswith('_API_KEY') and k not in ('CODEX_API_KEY','CODEX_ACCESS_TOKEN','OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_API_BASE','OPENAI_ORG_ID','OPENAI_PROJECT_ID')}
    events=queue.Queue();number=0;thread_id=None;turn_id=None;messages=[];finished=None
    err=tempfile.TemporaryFile();trace=(log_dir/'events.jsonl').open('w',encoding='utf-8')
    proc=None
    def record(value):trace.write(json.dumps(value,ensure_ascii=False)+'\n');trace.flush()
    def send(method,params):
        nonlocal number
        number+=1;record({'method':method,'direction':'request'})
        proc.stdin.write((json.dumps({'id':number,'method':method,'params':params},ensure_ascii=False)+'\n').encode());proc.stdin.flush();return number
    def consume(v):
        nonlocal finished
        method=v.get('method');params=v.get('params') or {};item=params.get('item') or {}
        if method=='item/completed' and item.get('type')=='agentMessage' and item.get('text'):messages.append(item['text'])
        if method=='turn/completed':finished=params.get('turn') or {}
        if method in ('item/started','item/completed'):
            event={'method':method,'type':item.get('type'),'status':item.get('status')}
            if item.get('type')=='commandExecution':
                event['command']=item.get('command');event['output']=(item.get('aggregatedOutput') or '')[:3000]
                progress('Reading relevant preferences and references...')
            record(event)
        if 'id' in v and method:
            proc.stdin.write((json.dumps({'id':v['id'],'error':{'code':-32601,'message':'This generation client does not approve external side effects.'}})+'\n').encode());proc.stdin.flush()
    def receive(expected=None,seconds=30):
        if expected is None and finished is not None:return
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            if cancelled.is_set():raise Cancelled('Generation cancelled. Saved cards are unchanged.')
            try:v=events.get(timeout=.2)
            except queue.Empty:continue
            if v is None:raise CodexError('Codex  connection closed. No new cards were saved.')
            if expected is not None and v.get('id')==expected and not v.get('method'):
                if 'error' in v:
                    record({'rpc_error':v['error']})
                    raise CodexError('Codex  did not complete the request. Try again later. Diagnostics are saved locally.')
                return v.get('result') or {}
            consume(v)
            if expected is None and finished is not None:return
        raise CodexError('Timed out waiting for Codex. No new cards were saved. You can explicitly retry later.')
    try:
        if cancelled.is_set():raise Cancelled('Generation cancelled.')
        progress('Connecting to local Codex and checking the Plus allowance...')
        proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0,cwd=Path(__file__).parent,env=env)
        def read():
            for line in proc.stdout:
                try:events.put(json.loads(line))
                except (ValueError,UnicodeDecodeError):continue
            events.put(None)
        threading.Thread(target=read,daemon=True).start()
        receive(send('initialize',{'clientInfo':{'name':'local_card_learning','title':'Leaflet - Local Card Learning','version':'0.2'},'capabilities':{'experimentalApi':True}}))
        proc.stdin.write(b'{"method":"initialized","params":{}}\n');proc.stdin.flush()
        account=receive(send('account/read',{'refreshToken':False})).get('account') or {}
        limits=receive(send('account/rateLimits/read',{}))
        subscription=check_subscription(account,limits)
        models=receive(send('model/list',{})).get('data') or []
        selected=next((m for m in models if m.get('isDefault')),None)
        if not selected:raise CodexError('Cannot confirm an available model. Nothing was generated.')
        if image_paths and 'image' not in selected.get('inputModalities',['text','image']):raise CodexError('The current model does not support image input. Disable images or try again later.')
        inputs=[{'type':'text','text':prompt}]+[{'type':'localImage','path':str(path)} for path in (image_paths or [])]
        if image_paths:(log_dir/'image-inputs.json').write_text(json.dumps([str(path) for path in image_paths],ensure_ascii=False))
        started=receive(send('thread/start',{'cwd':str(Path(__file__).parent),'ephemeral':True,'model':selected['model'],'approvalPolicy':'never','sandbox':'read-only','experimentalRawEvents':False}),40)
        thread_id=started['thread']['id']
        progress('Codex  is generating candidates from the topic and remembered preferences...')
        turn=receive(send('turn/start',{'threadId':thread_id,'input':inputs,'approvalPolicy':'never','effort':'low','outputSchema':schema}),40)
        turn_id=turn['turn']['id']
        receive(seconds=240)
        if cancelled.is_set():raise Cancelled('Generation cancelled. Candidates will not be adopted automatically.')
        if finished.get('status')!='completed':raise CodexError('Codex  did not finish generating. No new cards were saved.')
        result=None
        for message in reversed(messages):
            try:result=json.loads(message);break
            except ValueError:continue
        if not isinstance(result,dict):raise CodexError('The result format is incomplete. Generate again; saved content is unchanged.')
        (log_dir/'candidate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return result,{'model':selected['model'],'subscription':subscription,'thread_id':thread_id}
    finally:
        if proc:
            if cancelled.is_set() and thread_id and turn_id and proc.poll() is None:
                try:send('turn/interrupt',{'threadId':thread_id,'turnId':turn_id})
                except OSError:pass
            proc.terminate()
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        err.seek(0);diagnostic=err.read().decode('utf-8',errors='replace').lower()
        (log_dir/'diagnostic.json').write_text(json.dumps({'exit_code':proc.returncode if proc else None,'stderr_flags':{key:key in diagnostic for key in ('error','failed','timeout','permission denied','operation not permitted')}},ensure_ascii=False),encoding='utf-8')
        trace.close();err.close()
