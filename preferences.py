"""Write only explicitly confirmed preference notes; never edit generated Codex memory."""
from datetime import datetime, date
from zoneinfo import ZoneInfo
import os
import tempfile
import hashlib
from pathlib import Path
import re

from core import RuleError, text

class PreferenceNotes:
    def __init__(self,root=None):
        self.root=Path(root) if root is not None else Path.home()/'.codex/memories/extensions/ad_hoc/notes'

    def confirm(self,identifier,value,note_date=None):
        if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise RuleError('Invalid preference record ID.')
        value=text(value,'Learning preference',800,True)
        content='# Learning preference confirmed in the local card app\n\nThe user explicitly clicked remember and confirmed the following preference.\n\n'+value+'\n'
        self.root.mkdir(parents=True,exist_ok=True)
        if self.root.is_symlink():raise RuleError('The memory directory is a symlink. Nothing was written; ask the maintainer to inspect it.')
        note_date=note_date or datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
        try:date.fromisoformat(note_date)
        except (ValueError,TypeError):raise RuleError('Invalid preference record date.')
        path=self.root/f'{note_date}-card-learning-{identifier}.md'
        if path.is_symlink():raise RuleError('Invalid preference record path. No files were overwritten.')
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.root,prefix='.card-learning-',suffix='.tmp',delete=False) as stream:
                temporary=Path(stream.name);stream.write(content);stream.flush();os.fsync(stream.fileno())
            temporary.chmod(0o600)
            try:os.link(temporary,path)
            except FileExistsError:
                if path.read_text(encoding='utf-8')!=content:raise RuleError('A preference record with this name differs. It was not overwritten.',409)
        finally:
            if temporary:temporary.unlink(missing_ok=True)
        return {'path':str(path),'sha256':hashlib.sha256(content.encode()).hexdigest()}

    def read_confirmed(self,records):
        values=[]
        for item in records.values():
            if item.get('status')!='remembered':continue
            expected=self.root/f"{item['note_date']}-card-learning-{item['id']}.md"
            if expected.is_symlink() or str(expected)!=item.get('path'):continue
            if expected.exists():
                raw=expected.read_text(encoding='utf-8')
                if hashlib.sha256(raw.encode()).hexdigest()==item.get('sha256'):
                    values.append({'path':str(expected),'preference':item['text']})
        if sum(len(v['preference']) for v in values)>16000:
            raise RuleError('Too many webpage-confirmed preferences. Organize them before generating; no request was sent.')
        return values
