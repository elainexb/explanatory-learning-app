"""Read-only failure evidence. Rejected output never becomes an adoptable candidate."""
from copy import deepcopy
import json
import re

from core import RuleError


class ResultCheckError(RuleError):
    def __init__(self, message, issues):
        super().__init__(message)
        self.issues = issues


def reference_issues(raw, references):
    provided = {r['id']: r for r in references}
    report = raw.get('reference_report', [])
    if not isinstance(report, list):
        return {'malformed': True, 'missing': list(provided), 'extra': [], 'duplicates': [], 'invalid': []}
    ids = [r.get('id') for r in report if isinstance(r, dict) and isinstance(r.get('id'), str)]
    return {
        'malformed': len(ids) != len(report),
        'missing': [i for i in provided if i not in ids],
        'extra': list(dict.fromkeys(i for i in ids if i not in provided)),
        'duplicates': list(dict.fromkeys(i for i in ids if ids.count(i) > 1)),
        'invalid': [r['id'] for r in report if isinstance(r, dict) and isinstance(r.get('id'), str) and r.get('status') not in ('read', 'partial', 'unavailable')],
    }


def rejected_preview(raw):
    """Bounded, allowlisted display data, with no executable HTML or private memory fields."""
    if not isinstance(raw, dict):
        return None
    def value(v, limit=3000):
        return v[:limit] if isinstance(v, str) else ''
    result = {}
    for key in ('scope', 'rationale', 'expansion_summary', 'message'):
        if isinstance(raw.get(key), str):
            result[key] = value(raw[key])
    for key, fields in (('outline', ('title', 'learns', 'why')), ('cards', ('title', 'body'))):
        items = raw.get(key)
        if isinstance(items, list):
            result[key] = [{f: value(i.get(f), 60000 if f == 'body' else 3000) for f in fields} for i in items[:60] if isinstance(i, dict)]
            if len(items) > 60:
                result['display_note'] = 'Preview shows only the first 60 items, not proof of completeness or validity.'
    report = raw.get('reference_report')
    if isinstance(report, list):
        result['reference_report'] = [{k: value(i.get(k)) for k in ('id', 'status', 'summary')} for i in report[:60] if isinstance(i, dict)]
    warnings = raw.get('warnings')
    if isinstance(warnings, list):
        result['warnings'] = [value(w) for w in warnings[:60] if isinstance(w, str)]
    return result or None


def saved_raw(log_root, key):
    """Legacy failures retained native output on disk but not in the job record."""
    if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{32}', key):
        return None
    root = log_root.resolve()
    path = root / key / 'candidate.json'
    try:
        if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 8_000_000:
            return None
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError):
        return None


def recovery(job, jobs, raw=None):
    """Advisory information only: no DB writes, model calls, or eligibility changes."""
    info = deepcopy(job.get('failure', {}))
    preview = deepcopy(job.get('rejected_preview'))
    if preview is None:
        preview = rejected_preview(raw)
    issues = reference_issues(raw, job.get('references', [])) if isinstance(raw, dict) and job.get('phase') != 'summary' else {}
    if any(issues.values()):
        info.update(kind='reference_report', issues=issues)
    if info.get('kind') == 'reference_report':
        issues = info.get('issues', {})
        info['title'] = 'AI Content was returned, but reference validation failed'
        parts = []
        if issues.get('extra'):
            parts.append(f'AI Included  {len(issues["extra"])}  reading reports not in this round’s reference list')
        if issues.get('missing'):
            names = {r['id']: r.get('name', r['id']) for r in job.get('references', [])}
            parts.append('Missing reading reports for: ' + ', '.join(names[i] for i in issues['missing']))
        if issues.get('duplicates'):
            parts.append('Some reference IDs are duplicated')
        if issues.get('invalid') or issues.get('malformed'):
            parts.append('Some reports have an invalid format or reading status')
        info['explanation'] = '; '.join(parts) + '. The program cannot reliably map the references, so this result is not eligible for adoption.'
        if not job.get('references'):
            info['explanation'] += 'No registered references were enabled this round. This does not ask you to fix uploaded files.'
    elif preview:
        info.update(title='AI Content was returned, but result validation failed', explanation=job.get('error', 'The returned content does not yet meet this round’s requirements.'))
    elif job.get('status') == 'cancelled':
        info.update(title='Generation cancelled', explanation='No complete candidate was saved. Keep the request to prepare another generation.')
    else:
        info.update(title='Generation did not complete', explanation=job.get('error', 'The cause is not yet known. Diagnostics are saved locally.'))
    info['preview'] = preview
    parent = jobs.get(job.get('parent_id'))
    eligible = ('outline_ready', 'outline_confirmed', 'ready')
    info['parent_id'] = parent['id'] if parent and parent.get('topic_id') == job.get('topic_id') and parent.get('status') in eligible else None
    outline = jobs.get(job.get('outline_job_id'))
    info['outline_id'] = outline['id'] if outline and outline.get('topic_id') == job.get('topic_id') and outline.get('status') in ('outline_ready', 'outline_confirmed') else None
    return info
