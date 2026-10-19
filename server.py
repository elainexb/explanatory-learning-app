#!/usr/bin/env python3
"""Local-only, dependency-free card learning POC. Never expose publicly."""
import argparse
from copy import deepcopy
from html import escape
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import signal
import sqlite3
from urllib.parse import urlsplit, parse_qs
import webbrowser

from core import RuleError, apply, public_state, find
from store import Store
from generation import GenerationService
from preferences import PreferenceNotes
from references import References
from conversation import Conversations, settings_event, ensure as ensure_conversation, append as conversation_event

ROOT = Path(__file__).resolve().parent


def make_server(store, port=8767, ai_service=None):
    ai_service=ai_service or GenerationService(store,ROOT/'data/codex-runs')
    refs=ai_service.references
    conversations=Conversations(store)
    def conversation_payload(topic_id,job_id=None,error=None):
        active=ai_service.get(ai_service.active) if ai_service.active else None
        if active and active['status'] not in ('queued','running'):active=None
        return {'conversation':conversations.get(topic_id),'state':public_state(store.read()),'job':ai_service.get(job_id) if job_id else None,'active':{k:active[k] for k in ('id','topic_id','phase','status','progress') if k in active} if active else None,'discussion_error':error}
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def send(self, status, value, kind='application/json; charset=utf-8'):
            body = json.dumps(value, ensure_ascii=False).encode() if kind.startswith('application/json') else value
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def allowed_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.allowed_host():
                return self.send(403, {'error': 'Open through the local launcher.'})
            path = urlsplit(self.path).path
            if path in ('/', '/index.html'):
                return self.send(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/state':
                return self.send(200, {'state': public_state(store.read()), 'token': token})
            assets={'/assets/cytoscape-3.34.3.min.js':('vendor/cytoscape-3.34.3.min.js','text/javascript; charset=utf-8'),'/assets/learning-graph.js':('learning-graph.js','text/javascript; charset=utf-8'),'/assets/learning-graph.css':('learning-graph.css','text/css; charset=utf-8')}
            if path in assets:
                file,kind=assets[path];return self.send(200,(ROOT/file).read_bytes(),kind)
            if path == '/api/graph':
                try:
                    params=parse_qs(urlsplit(self.path).query)
                    return self.send(200,{**ai_service.learning_graph.payload(params.get('id',[None])[0],params.get('topic_id',[None])[0]),'state':public_state(store.read())})
                except RuleError as exc:return self.send(exc.status,{'error':str(exc)})
            if path == '/api/conversation':
                try:return self.send(200,conversation_payload(parse_qs(urlsplit(self.path).query).get('topic_id',[''])[0]))
                except RuleError as exc:return self.send(exc.status,{'error':str(exc)})
            if path in ('/api/references/image','/api/references/view'):
                try:
                    key=parse_qs(urlsplit(self.path).query).get('id',[''])[0]
                    item=find(store.read(),'references',key)
                    if path.endswith('/image'):return self.send(200,refs.image(item).read_bytes(),item['mime'])
                    name=escape(item['name']);body=''
                    if item['kind']=='image':body=f'<img alt="{name}" src="/api/references/image?id={item["id"]}" style="max-width:100%;height:auto">'
                    elif item['kind']=='text':body='<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+escape(item['text'])+'</pre>'
                    else:body='<p><a href="'+escape(item['url'],quote=True)+'" target="_blank" rel="noopener noreferrer">Open original page</a></p><p>Saving a URL does not mean the page was read or verified.</p>'
                    html='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+name+'</title><body style="font:16px/1.8 system-ui;max-width:900px;margin:32px auto;padding:0 20px"><h1>'+name+'</h1><p>Locally saved reference original -  '+('Enabled for future generation' if item['enabled'] else 'Disabled; original retained for review')+'</p>'+body+'</body></html>'
                    return self.send(200,html.encode(),'text/html; charset=utf-8')
                except RuleError as exc:return self.send(exc.status,{'error':str(exc)})
            if path == '/api/selection':
                try:return self.send(200, {'selection':ai_service.selection.get(parse_qs(urlsplit(self.path).query).get('id',[''])[0])})
                except RuleError as exc:return self.send(exc.status,{'error':str(exc)})
            if path == '/api/ai/job':
                try:
                    key=parse_qs(urlsplit(self.path).query).get('id',[''])[0]
                    return self.send(200, {'job':ai_service.get(key)})
                except RuleError as exc:return self.send(exc.status, {'error':str(exc)})
            return self.send(404, {'error': 'This page does not exist.'})

        def do_POST(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if not self.allowed_host() or self.headers.get('Origin') != origin or not secrets.compare_digest(self.headers.get('X-Local-Token', ''), token):
                return self.send(403, {'error': 'Invalid request origin. Reopen the local page.'})
            if self.path not in ('/api/graph/create','/api/graph/send','/api/graph/continue','/api/graph/confirm','/api/graph/edit','/api/graph/accept','/api/graph/discard','/api/graph/defer','/api/selection/create','/api/selection/send','/api/selection/continue','/api/selection/confirm','/api/selection/accept','/api/selection/discard','/api/action','/api/references/change','/api/ai/start','/api/ai/summarize-topic','/api/ai/confirm-outline','/api/ai/resume','/api/ai/cancel','/api/ai/discard','/api/ai/accept','/api/preferences/prepare','/api/preferences/confirm','/api/conversation/send','/api/conversation/continue','/api/conversation/context','/api/conversation/wait','/api/conversation/defer'):
                return self.send(404, {'error': 'This operation does not exist.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= (7500000 if self.path=='/api/references/change' else 1000000) or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise RuleError('Request too large or malformed.')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data,dict):raise RuleError('Invalid request format.')
                if self.path.startswith('/api/graph/'):
                    manager=ai_service.learning_graph;op=self.path.rsplit('/',1)[1];key=data.get('id');error=None
                    if op=='create':key=manager.create(data)
                    elif op=='send':
                        try:manager.send(data)
                        except RuleError as exc:error=str(exc)
                    elif op=='continue':manager.start(key)
                    elif op=='confirm':manager.start(key,data.get('plan_id'))
                    elif op=='edit':manager.edit(data)
                    elif op=='accept':manager.accept(data)
                    elif op=='discard':manager.discard(key)
                    elif op=='defer':manager.defer(key)
                    return self.send(200,{**manager.payload(key),'state':public_state(store.read()),'error':error})
                if self.path.startswith('/api/selection/'):
                    editor=ai_service.selection;op=self.path.rsplit('/',1)[1];key=data.get('id');error=None;result=None
                    if op=='create':key=editor.create(data)
                    elif op=='send':
                        try:editor.send(data)
                        except RuleError as exc:error=str(exc)
                    elif op=='continue':editor.start(key)
                    elif op=='confirm':editor.start(key,data.get('plan_id'))
                    elif op=='accept':_,result=editor.accept(data)
                    elif op=='discard':editor.discard(key)
                    return self.send(200,{'selection':editor.get(key),'state':public_state(store.read()),'error':error,'result':result})
                if self.path=='/api/conversation/context':
                    conversations.reset_context(data)
                    return self.send(200,conversation_payload(data.get('topic_id')))
                if self.path=='/api/conversation/defer':
                    if ai_service.active and ai_service.get(ai_service.active)['topic_id']==data.get('topic_id'):raise RuleError('The current task is running. Wait or stop it first; original requirements are retained.',409)
                    conversations.defer_pending(data)
                    return self.send(200,conversation_payload(data.get('topic_id')))
                if self.path=='/api/conversation/wait':
                    topic_id=data.get('topic_id')
                    active_id=ai_service.active
                    def wait_note(s):conversation_event(ensure_conversation(s,topic_id),'user','waiting','Chose to explicitly continue discussing new messages later and keep the current task.' if active_id else 'Chose to explicitly continue discussing saved messages later.',job_id=active_id)
                    store.change(wait_note,bump_revision=False)
                    return self.send(200,conversation_payload(topic_id))
                if self.path=='/api/conversation/send':
                    event=conversations.submit(data);identifier=event.get('job_id');error=None
                    if not identifier and not ai_service.active:
                        try:identifier=ai_service.begin_discussion(data.get('topic_id'),data.get('related_job_id'))
                        except RuleError as exc:error=str(exc)
                    return self.send(200,conversation_payload(data.get('topic_id'),identifier,error))
                if self.path=='/api/conversation/continue':
                    topic_id=data.get('topic_id');find(store.read(),'topics',topic_id)
                    interrupt=data.get('interrupt_job_id')
                    if interrupt and ai_service.active:
                        active=ai_service.get(ai_service.active)
                        if interrupt!=active['id'] or active['topic_id']!=topic_id:raise RuleError('The active task changed. Check the current state before choosing; your message is saved.',409)
                        def note(s):conversation_event(ensure_conversation(s,topic_id),'user','interrupted','Chose to stop the current task and discuss new messages first.',job_id=interrupt)
                        store.change(note,bump_revision=False)
                        ai_service.cancel(interrupt)
                        worker=getattr(ai_service,'worker',None)
                        if worker:worker.join(timeout=7)
                        if ai_service.active:raise RuleError('Stop request recorded. The current task is still ending. Messages are retained; continue discussing later.',409)
                    identifier=ai_service.begin_discussion(topic_id,data.get('related_job_id'))
                    return self.send(200,conversation_payload(topic_id,identifier))
                if self.path == '/api/references/change':
                    state,result=refs.change(data)
                    return self.send(200,{'state':public_state(state),'result':result})
                if self.path == '/api/ai/start':
                    identifier=ai_service.begin(data)
                    return self.send(200, {'job':ai_service.get(identifier)})
                if self.path == '/api/ai/summarize-topic':
                    identifier=ai_service.begin(data,summary=True)
                    return self.send(200, {'job':ai_service.get(identifier)})
                if self.path == '/api/ai/confirm-outline':
                    identifier=ai_service.confirm_outline(data.get('id'))
                    return self.send(200, {'job':ai_service.get(identifier)})
                if self.path == '/api/ai/cancel':return self.send(200, {'job':ai_service.cancel(data.get('id'))})
                if self.path == '/api/ai/resume':
                    identifier=ai_service.resume(data.get('id'))
                    return self.send(200, {'job':ai_service.get(identifier)})
                if self.path == '/api/ai/discard':return self.send(200, {'job':ai_service.discard(data.get('id'))})
                if self.path == '/api/ai/accept':
                    state,result=ai_service.accept(data.get('id'))
                    return self.send(200, {'state':public_state(state),'result':result,'job':ai_service.get(data.get('id'))})
                if self.path == '/api/preferences/prepare':return self.send(200, {'preference':ai_service.prepare_preference(data.get('text'))})
                if self.path == '/api/preferences/confirm':return self.send(200, {'preference':ai_service.confirm_preference(data.get('id'))})
                def act(s):
                    key=data.get('topic_id');before=deepcopy(s.get('topics',{}).get(key))
                    result=apply(s,data)
                    if before and data.get('action')=='edit_topic':settings_event(s,key,before,s['topics'][key])
                    return result
                state, result = store.change(act)
                return self.send(200, {'state': public_state(state), 'result': result})
            except RuleError as exc:
                return self.send(exc.status, {'error': str(exc)})
            except (ValueError, UnicodeDecodeError):
                return self.send(400, {'error': 'Cannot read the operation data.'})
            except (sqlite3.Error,OSError):
                return self.send(503, {'error': 'Could not save right now. Original content was not overwritten. Check disk space or try again later.'})
    server=ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.ai_service=ai_service
    return server


def main():
    parser = argparse.ArgumentParser(description='Local Card Learning POC')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--db', type=Path, default=ROOT / 'data' / 'poc-library.sqlite3')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--preferences-dir',type=Path,default=None,help='Override the confirmed-preference note directory; defaults to shared local Codex memory notes')
    args = parser.parse_args()
    store = Store(args.db, ROOT / 'seed.json')
    try:
        service=GenerationService(store,args.db.parent/'codex-runs',notes=PreferenceNotes(args.preferences_dir))
        server = make_server(store, args.port, service)
    except OSError as exc:
        raise SystemExit(f'Cannot start local page: {exc}. Check whether the port is already in use. Do not launch the program twice.')
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'Card Learning POC started: {url}\nData file: {args.db}\nClose this window or press Control+C  to stop the server.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    def interrupted(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGHUP,interrupted)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.ai_service.close()
        server.server_close()


if __name__ == '__main__':
    main()
