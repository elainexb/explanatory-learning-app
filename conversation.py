"""Topic-local visible dialogue, explicit decisions, and traceable artifact links."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from uuid import uuid4

from core import RuleError, find, text


def now():return datetime.now(timezone.utc).isoformat()


def ensure(state,topic_id):
    topic=find(state,'topics',topic_id)
    conversations=state.setdefault('conversations',{})
    if topic_id not in conversations:
        conversations[topic_id]={'topic_id':topic_id,'seq':0,'effective_version':0,'events':[]}
        append(conversations[topic_id],'system','snapshot','Started this topic discussion. Earlier generation records remain in version history.',snapshot=deepcopy(topic))
    return conversations[topic_id]


def append(conversation,role,kind,value,**fields):
    conversation['seq']+=1
    event={'id':uuid4().hex,'seq':conversation['seq'],'created_at':now(),'role':role,'type':kind,'text':value,**fields}
    conversation['events'].append(event)
    return event


def pending(conversation):
    return [e for e in conversation.get('events',[]) if e['role']=='user' and e.get('status') in ('pending','failed')]


def context(conversation):
    events=conversation['events'];start=0
    for i,event in enumerate(events):
        if event['type']=='context_summary':start=i
    values=[{k:deepcopy(e[k]) for k in ('id','seq','role','type','text','status','questions','answers','job_id','changes','related_job_id','related_card_id','snapshot','before','after','effective_version','deferred_event_ids','question_event_id') if k in e} for e in events[start:]]
    if len(values)>100 or len(json.dumps(values,ensure_ascii=False))>45000:
        raise RuleError('This discussion exceeds the context limit. Save a confirmed summary under “Discussion context” first. Earlier records are retained; no AI request was sent.')
    return values


def validate_response(raw):
    if not isinstance(raw,dict):raise RuleError('AI The discussion response has an invalid format. Your message is saved; you can continue discussing.')
    kind=raw.get('kind')
    if kind not in ('answer','clarify','proposal'):raise RuleError('AI The response did not identify whether it answers, clarifies, or proposes a plan. Your message is retained.')
    message=text(raw.get('message'),'AI Response',12000,True)
    questions=raw.get('questions')
    if not isinstance(questions,list) or len(questions)>3:raise RuleError('AI  questions have an invalid format. Clarify at most three key questions at a time.')
    result=[]
    for q in questions:
        if not isinstance(q,dict):raise RuleError('AI  questions have an invalid format.')
        options=q.get('options')
        if not isinstance(options,list) or not 2<=len(options)<=5:raise RuleError('AI A question must provide two to five distinct options and allow a free-text answer.')
        choices=[]
        for option in options:
            if not isinstance(option,dict):raise RuleError('AI Invalid option format.')
            choices.append({k:text(option.get(k),'Option'+k,80 if k=='id' else 1200,True) for k in ('id','label','impact')})
        ids=[o['id'] for o in choices]
        if len(set(ids))!=len(ids):raise RuleError('AI Duplicate option IDs. Continue the discussion to try again.')
        recommended=text(q.get('recommended_option_id',''),'Recommended option',80)
        if recommended and recommended not in ids:raise RuleError('AI The recommended option does not exist. Your original message is retained.')
        result.append({'id':text(q.get('id'),'Question ID',80,True),'question':text(q.get('question'),'Question',2000,True),'options':choices,'recommended_option_id':recommended,'reason':text(q.get('reason'),'Recommendation reason',2000,True)})
    if len({q['id'] for q in result})!=len(result):raise RuleError('AI Duplicate question IDs.')
    if (kind=='clarify')!=bool(result):raise RuleError('AI  response type does not match its questions. This was not treated as an executable plan.')
    changes=raw.get('changes',[]);warnings=raw.get('warnings',[])
    if not isinstance(changes,list) or any(not isinstance(x,str) for x in changes) or len(changes)>30:raise RuleError('AI Invalid plan change descriptions.')
    if not isinstance(warnings,list) or any(not isinstance(x,str) for x in warnings):raise RuleError('AI Invalid verification notes.')
    if kind!='proposal' and (raw.get('outline') or raw.get('reuse_card_ids')):raise RuleError('An answer or clarification cannot also be a ready outline proposal.')
    return {'kind':kind,'message':message,'questions':result,'changes':[text(x,'Change description',2000,True) for x in changes],'warnings':[text(x,'Verification note',3000) for x in warnings]}


class Conversations:
    def __init__(self,store):self.store=store

    def get(self,topic_id):
        state=self.store.read();find(state,'topics',topic_id)
        return deepcopy(state.get('conversations',{}).get(topic_id,{'topic_id':topic_id,'seq':0,'effective_version':0,'events':[]}))

    def submit(self,data):
        submission=data.get('submission_id')
        if not isinstance(submission,str) or not re.fullmatch(r'[A-Za-z0-9-]{16,80}',submission):raise RuleError('Invalid submission ID. Keep your input and try again.')
        def save(state):
            c=ensure(state,data.get('topic_id'))
            old=next((e for e in c['events'] if e.get('submission_id')==submission),None)
            if old:return deepcopy(old)
            related_job=data.get('related_job_id');related_card=data.get('related_card_id')
            if related_job and find(state,'generations',related_job)['topic_id']!=c['topic_id']:raise RuleError('The selected version does not belong to this topic. Select another version.',409)
            if related_card:find(state,'cards',related_card)
            value=text(data.get('text',''),'Message',2000)
            answers=data.get('answers',[])
            if not isinstance(answers,list):raise RuleError('Invalid answer format.')
            captured=[];answer_to=None
            if answers:
                answer_to=data.get('question_event_id')
                if answer_to!=c.get('awaiting_questions'):raise RuleError('These questions have been answered or updated. View the current discussion; earlier answers will not be overwritten.',409)
                event=next((e for e in c['events'] if e['id']==answer_to),None)
                expected={q['id']:q for q in event['questions']}
                if len(answers)!=len(expected):raise RuleError('Select an option or write an answer for every question in this round.')
                seen=set()
                for answer in answers:
                    if not isinstance(answer,dict) or answer.get('question_id') not in expected or answer['question_id'] in seen:raise RuleError('Questions have changed or an answer is duplicated. Review the original questions.',409)
                    q=expected[answer['question_id']];seen.add(q['id'])
                    option_id=answer.get('option_id','');option=next((o for o in q['options'] if o['id']==option_id),None)
                    custom=text(answer.get('text',''),'Additional answer',1000)
                    if option_id and not option:raise RuleError('That option is not in the original question. Choose an existing option or write your own answer.')
                    if not option and not custom:raise RuleError('Choose an option or write your thoughts for each question.')
                    captured.append({'question_id':q['id'],'question':q['question'],'option_id':option_id,'option_label':option['label'] if option else '', 'text':custom})
                combined='\n'.join('Regarding “'+a['question']+'”: '+a['option_label']+('; '+a['text'] if a['text'] else '') for a in captured)
                value=text(combined+('\n'+value if value else ''),'Answer',2000,True)
                c['awaiting_questions']=None
            if not value:raise RuleError('Write a question or idea, or answer the current options.')
            event=append(c,'user','answers' if captured else 'message',value,submission_id=submission,status='pending',answers=captured,answer_to=answer_to,related_job_id=related_job,related_card_id=related_card)
            return deepcopy(event)
        return self.store.change(save,bump_revision=False)[1]

    def reset_context(self,data):
        value=text(data.get('summary'),'Confirmed discussion summary',4000,True)
        def save(state):
            c=ensure(state,data.get('topic_id'))
            if c.get('awaiting_questions'):raise RuleError('Answer or clarify the current questions before summarizing context. The original questions are retained.',409)
            if any(e.get('status')=='running' for e in c['events']):raise RuleError('A reply is still being generated. Wait for it to finish before summarizing context.',409)
            append(c,'system','context_summary',value)
            return deepcopy(c)
        return self.store.change(save,bump_revision=False)[1]

    def defer_pending(self,data):
        def save(state):
            c=ensure(state,data.get('topic_id'))
            if data.get('seq')!=c['seq']:raise RuleError('New discussion records exist. Refresh before deciding which requests to defer.',409)
            if any(e.get('status')=='running' for e in c['events']):raise RuleError('A reply is still being generated. Wait or stop the current task first.',409)
            events=pending(c);question=c.get('awaiting_questions')
            if not events and not question:raise RuleError('There are no pending requests or questions.',409)
            for event in events:event['status']='deferred'
            c['awaiting_questions']=None
            append(c,'user','deferred_requests','Chose to defer these pending requests or questions for this round and keep the existing plan. Original messages and questions are retained; they can be explicitly raised again later.',deferred_event_ids=[e['id'] for e in events],question_event_id=question)
            return deepcopy(c)
        return self.store.change(save,bump_revision=False)[1]


def completed(state,job,response=None,error=None):
    if not (job.get('conversation_turn_id') or job.get('trace_turn_id') or job.get('trace_body')):return
    c=ensure(state,job['topic_id'])
    for e in c['events']:
        belongs=(e['seq']<=job['conversation_seq']) if job.get('conversation_turn_id') else e['id']==job.get('trace_turn_id')
        if e['role']=='user' and e.get('status') in ('pending','failed','running') and belongs:
            e.update(status='failed' if error else 'completed')
    if any(e.get('job_id')==job['id'] and e['role']=='assistant' and e.get('attempt',0)==job.get('run_attempt',0) for e in c['events']):return
    if error:
        append(c,'assistant','failure',error,job_id=job['id'],attempt=job.get('run_attempt',0))
    else:
        event=append(c,'assistant',response['kind'],response['message'],job_id=job['id'],attempt=job.get('run_attempt',0),questions=response['questions'],changes=response['changes'],warnings=response['warnings'])
        if job.get('conversation_turn_id'):
            if response['kind']=='clarify':c['awaiting_questions']=event['id']
            elif response['kind']=='proposal':c['awaiting_questions']=None


def check_current(state,job,in_progress=False):
    c=state.get('conversations',{}).get(job['topic_id'])
    if not c:return
    if c['effective_version']!=job.get('conversation_version',0):raise RuleError('A newer adjustment plan was confirmed in the discussion. This older result cannot be continued directly; view the newer version.',409)
    if c.get('awaiting_questions'):raise RuleError('Key questions still require your choice. Answer them before confirming the plan.',409)
    if any(e.get('status') in ('pending','running','failed') and not (in_progress and e['id']==job.get('trace_turn_id') and e.get('job_id')==job['id'] and e.get('status') in ('running','failed')) for e in c['events'] if e['role']=='user'):
        raise RuleError('A new message has not finished discussion and is not reflected in this result. Continue or resume under “Discuss and adjust” first.',409)


def confirm_plan(state,job):
    c=state.get('conversations',{}).get(job['topic_id'])
    if not c:return job.get('conversation_version',0)
    if job['status']!='outline_confirmed':
        c['effective_version']+=1
        c['effective_request']=job.get('request','')
        job['conversation_version']=c['effective_version']
        append(c,'user','confirmed_plan','Confirmed this outline plan and continued to generate body candidates.',job_id=job['id'],effective_version=c['effective_version'])
    return c['effective_version']


def settings_event(state,topic_id,before,after):
    c=state.get('conversations',{}).get(topic_id)
    if c and before!=after:append(c,'user','settings','Saved changes to the learning goal, preferences, or references on the page.',before=deepcopy(before),after=deepcopy(after))
