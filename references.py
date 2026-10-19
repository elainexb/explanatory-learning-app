"""Topic-owned reference records and local immutable image originals. No model or URL fetching."""
import base64
import os
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import re
from uuid import uuid4

from core import RuleError,find,text,sources
from conversation import settings_event

MAX_IMAGE=5*1024*1024

class References:
    def __init__(self,store,root):self.store=store;self.root=Path(root).resolve()

    def change(self,data):
        created=[]
        def operation(s):
            if type(data.get('revision')) is not int or data['revision']!=s['revision']:raise RuleError('References changed in another window. Refresh before continuing.',409)
            topic=find(s,'topics',data.get('topic_id'));op=data.get('operation')
            records=s.setdefault('references',{})
            before=[{k:r[k] for k in ('id','name','kind','enabled','version')} for r in records.values() if r['topic_id']==topic['id']]
            if op=='add':
                if sum(r['topic_id']==topic['id'] for r in records.values())>=30:raise RuleError('This version saves at most 30 references per topic. Organize them first.')
                key=uuid4().hex;kind=data.get('kind');name=text(data.get('name'),'Reference name',160,True)
                item={'id':key,'topic_id':topic['id'],'kind':kind,'name':name,'enabled':True,'version':1,'created_at':datetime.now(timezone.utc).isoformat()}
                if kind=='text':item['text']=text(data.get('text'),'Reference text',20000,True)
                elif kind=='url':item['url']=sources([{'url':data.get('url'),'title':name}])[0]['url']
                elif kind=='image':
                    encoded=data.get('image_base64')
                    if not isinstance(encoded,str) or len(encoded)>((MAX_IMAGE+2)//3)*4:raise RuleError('Images cannot exceed 5 MB.')
                    try:blob=base64.b64decode(encoded,validate=True)
                    except (ValueError,TypeError):raise RuleError('Cannot read the image. Select a PNG, JPG, or WebP again.')
                    if not blob or len(blob)>MAX_IMAGE:raise RuleError('The image is empty or exceeds 5 MB.')
                    if blob.startswith(b'\x89PNG\r\n\x1a\n'):mime,ext='image/png','png'
                    elif blob.startswith(b'\xff\xd8\xff'):mime,ext='image/jpeg','jpg'
                    elif len(blob)>12 and blob[:4]==b'RIFF' and blob[8:12]==b'WEBP':mime,ext='image/webp','webp'
                    else:raise RuleError('Only PNG, JPG, and WebP images are supported. Renaming the extension is not sufficient.')
                    self.root.mkdir(parents=True,exist_ok=True)
                    if self.root.is_symlink():raise RuleError('The reference directory is invalid. Nothing was saved.')
                    path=self.root/(key+'.'+ext)
                    with path.open('xb') as f:
                        created.append(path);f.write(blob);f.flush();os.fsync(f.fileno())
                    path.chmod(0o600)
                    item.update(filename=path.name,mime=mime,size=len(blob),sha256=sha256(blob).hexdigest())
                else:raise RuleError('Choose text, a web URL, or an image.')
                records[key]=item
            elif op in ('rename','toggle'):
                item=find(s,'references',data.get('id'))
                if item['topic_id']!=topic['id']:raise RuleError('This reference does not belong to the current topic.',409)
                if op=='rename':item['name']=text(data.get('name'),'Reference name',160,True)
                else:
                    if type(data.get('enabled')) is not bool:raise RuleError('Invalid reference enabled state.')
                    item['enabled']=data['enabled']
                item['version']+=1;key=item['id']
            else:raise RuleError('This reference operation is not supported.')
            topic['version']+=1
            after=[{k:r[k] for k in ('id','name','kind','enabled','version')} for r in records.values() if r['topic_id']==topic['id']]
            settings_event(s,topic['id'],{'references':before},{'references':after})
            return {'id':key,'topic_id':topic['id']}
        try:return self.store.change(operation)
        except Exception:
            for path in created:path.unlink(missing_ok=True)
            raise

    def image(self,item):
        if item.get('kind')!='image' or not re.fullmatch(r'[a-f0-9]{32}\.(png|jpg|webp)',item.get('filename','')):raise RuleError('This reference is not a readable image.',404)
        path=self.root/item['filename']
        if path.is_symlink() or not path.is_file() or path.resolve().parent!=self.root.resolve():raise RuleError('The original image moved or no longer exists. Add it again.',404)
        if sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise RuleError('The image changed outside the app. Add it again and verify it.',409)
        return path

    def snapshot(self,state,topic_id):
        refs=[deepcopy(r) for r in state.get('references',{}).values() if r['topic_id']==topic_id and r['enabled']]
        if sum(r['kind']=='image' for r in refs)>4 or sum(len(r.get('text','')) for r in refs)>40000:
            raise RuleError('Each generation uses at most four images and 40,000 reference text characters. Disable material not needed this round.')
        for i,r in enumerate(refs,1):
            r['label']='R'+str(i)
            if r['kind']=='image':self.image(r)
        return refs
