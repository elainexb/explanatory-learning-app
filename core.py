"""Card/topic rules. No browser, HTTP, filesystem or model dependencies."""
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4


class RuleError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def text(value, label, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise RuleError(f'{label} is required' if required and not value else f'{label} has an invalid format or exceeds {limit} characters.')
    return value.strip()


def sources(value):
    if not isinstance(value, list) or len(value) > 30:
        raise RuleError('Sources must be a list of at most 30 items.')
    out = []
    for item in value:
        if not isinstance(item, dict):
            raise RuleError('Invalid source format.')
        url = text(item.get('url'), 'Source URL', 2000, True)
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in ('https', 'http') and bool(parsed.hostname) and not parsed.username
        except ValueError:
            valid = False
        if not valid:
            raise RuleError('Enter a complete http or https URL for the source.')
        out.append({'title': text(item.get('title', ''), 'Source title', 200) or url, 'url': url})
    return out


def find(state, collection, key):
    if not isinstance(key, str) or key not in state.get(collection,{}):
        raise RuleError('This item does not exist. Reopen the page.', 404)
    return state[collection][key]


def impact(state, card_id):
    return sorted(t['id'] for t in state['topics'].values() if card_id in t['cards'])


def content(data, existing=None, preserve_body=False):
    existing = existing or {}
    body=text(data.get('body'), 'Body', 60000, True)
    if preserve_body:body=data['body']
    return {'title': text(data.get('title'), 'Title', 160, True),
            'body': body,
            'sources': sources(data.get('sources', existing.get('sources', [])))}


def public_state(state):
    out = deepcopy(state)
    out.pop('history', None)
    out.pop('conversations', None)
    out.pop('graph_sessions', None)
    out.pop('graph_history', None)
    out['selection_edits']={k:{f:s[f] for f in ('id','card_id','quote','status','updated_at')} for k,s in state.get('selection_edits',{}).items()}
    out['generations']={key:{k:job[k] for k in ('id','topic_id','status','count','created_at','completed_at','phase','parent_id','outline_job_id','request','selection_id','card_id','graph_session_id') if k in job}|{'base_topic_version':job.get('topic_snapshot',{}).get('version'),'completed_count':len(job.get('checkpoint',{}).get('cards',[]))} for key,job in state.get('generations',{}).items()}
    return out


def apply(state, data, *, exact_body=False):
    if not isinstance(data, dict):
        raise RuleError('Invalid operation format.')
    if type(data.get('revision')) is not int or data['revision'] != state['revision']:
        raise RuleError('Content changed in another window. Nothing was saved. Refresh the latest content and preview again.', 409)
    op = data.get('action')
    now = datetime.now(timezone.utc).isoformat()
    if op == 'create_card':
        value = content(data)
        topic_id = data.get('topic_id')
        topic = find(state, 'topics', topic_id) if topic_id else None
        key = uuid4().hex
        state['cards'][key] = dict(value, id=key, version=1,
                                  provenance={'note': 'Written manually by the user. Sources are user-provided and have not been automatically fact-checked.'})
        if topic:
            topic['cards'].append(key)
            topic['version'] += 1
        return {'id': key}
    if op in ('create_topic', 'edit_topic'):
        value = {'title': text(data.get('title'), 'Topic name', 160, True),
                 'goal': text(data.get('goal', ''), 'Learning goal', 2000),
                 'expansion': text(data.get('expansion', ''), 'Expansion preferences', 2000)}
        if op == 'create_topic':
            key = uuid4().hex
            state['topics'][key] = dict(value, id=key, cards=[], version=1)
        else:
            topic = find(state, 'topics', data.get('topic_id'))
            key = topic['id']
            if any(topic.get(k,'')!=v for k,v in value.items()):
                if topic.get('expansion','')!=value['expansion']:
                    topic['expansion_covered_requests']=[j['id'] for j in state.get('generations',{}).values() if j.get('topic_id')==topic['id'] and j.get('phase')!='summary' and j.get('request','').strip()]
                topic.update(value)
                topic['version'] += 1
        return {'id': key}
    if op == 'set_topic_cards':
        topic = find(state, 'topics', data.get('topic_id'))
        ids = data.get('cards')
        if not isinstance(ids, list) or any(not isinstance(k, str) for k in ids) or len(ids) != len(set(ids)):
            raise RuleError('A topic cannot contain duplicate cards. Provide a valid list.')
        for key in ids:
            find(state, 'cards', key)
        topic['cards'] = ids[:]
        topic['version'] += 1
        return {'id': topic['id']}
    if op == 'propose_card':
        card = find(state, 'cards', data.get('card_id'))
        value = content(data, card, preserve_body=exact_body)
        if all(card[k] == value[k] for k in value):
            raise RuleError('No content has changed. Make a change before previewing.')
        key = uuid4().hex
        state['proposals'][key] = {'id': key, 'card_id': card['id'], 'before': deepcopy(card),
            'after': value, 'base_version': card['version'], 'impact': impact(state, card['id']),
            'status': 'pending', 'created_at': now}
        return {'id': key}
    if op in ('revise_proposal', 'accept_proposal', 'discard_proposal'):
        proposal = find(state, 'proposals', data.get('proposal_id'))
        if proposal['status'] != 'pending':
            raise RuleError('This candidate has already been handled and cannot be adopted or discarded again.', 409)
        card = find(state, 'cards', proposal['card_id'])
        if op == 'discard_proposal':
            proposal['status'] = 'discarded'
            return {'id': proposal['id']}
        if card['version'] != proposal['base_version'] or impact(state, card['id']) != proposal['impact']:
            raise RuleError('The card or its topic references changed. Discard the old candidate, then edit and preview the latest content.', 409)
        if op == 'revise_proposal':
            value = content(data, card)
            if all(card[k] == value[k] for k in value):
                raise RuleError('The candidate matches saved content. Continue editing or discard it.')
            proposal['after'] = value
        else:
            state['history'].append({'card_id': card['id'], 'before': deepcopy(card), 'proposal_id': proposal['id'], 'accepted_at': now})
            card.update(deepcopy(proposal['after']))
            card['version'] += 1
            card['provenance'] = dict(card.get('provenance', {}), note='The user adopted an AI selection edit. Original provenance is retained; review the current facts and sources against the change notes.' if proposal.get('origin')=='ai_selection' else 'Manual changes adopted. Initial provenance is retained; the current content and its source mapping have not been automatically fact-checked.')
            proposal['status'] = 'accepted'
            proposal['accepted_at'] = now
        return {'id': proposal['id']}
    raise RuleError('This operation is not supported.')
