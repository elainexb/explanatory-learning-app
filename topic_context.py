"""Topic-local user requirements. Knowledge sources and shared memory are separate."""
from core import RuleError, find


def supplements(state,topic_id):
    find(state,'topics',topic_id)
    jobs=sorted(state.get('generations',{}).values(),key=lambda j:j.get('created_at',''))
    return [{'generation_id':j['id'],'parent_id':j.get('parent_id'),'created_at':j.get('created_at'),'status':j.get('status'),'request':j['request']} for j in jobs if j.get('topic_id')==topic_id and not j.get('selection_id') and not j.get('graph_session_id') and j.get('phase') not in ('summary','discussion') and not (j.get('phase')=='details' and j.get('parent_id')==j.get('outline_job_id')) and j.get('request','').strip()]


def summary_input(state,topic_id):
    topic=find(state,'topics',topic_id);covered=set(topic.get('expansion_covered_requests',[]));items=[i for i in supplements(state,topic_id) if i['generation_id'] not in covered]
    if len(items)>60 or sum(len(i['request']) for i in items)>16000:
        raise RuleError('Previous requirements exceed this version’s summarization limit. Organize key points in expansion preferences first; no AI request was sent.')
    return {'saved_expansion':topic.get('expansion',''),'supplements':items}
