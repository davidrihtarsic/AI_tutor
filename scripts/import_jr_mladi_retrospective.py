#!/usr/bin/env python3
"""Import reconstructed JR-MLADI legacy conversations into runtime data v2.0.

The source package is retrospective: original questions/answers are historical,
while classification and LearningEvidence are reconstructed. Exact per-message
timestamps were not available, so imported events keep timestamp="" and carry
course_schedule_dates plus source_turn for order/provenance.
"""
from __future__ import annotations
import argparse, json, shutil, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import COURSES_FILE, ENROLLMENTS_FILE, SESSIONS_DIR, STUDENTS_DIR, USERS_FILE
from services.storage_service import update_student_state

INTENT = {
 'debugging':'debugging','conceptual_question':'concept_explanation','solution_request':'code_request',
 'how_to_question':'question','resource_request':'question','planning_or_extension':'question',
 'statement_or_feedback':'other','meta_tutor':'other','social_or_introduction':'other','off_topic':'other'}
PROBLEM = {
 'conceptual_understanding':'conceptual','code_syntax_or_logic':'syntax','hardware_wiring':'hardware',
 'algorithm_or_task_design':'algorithmic','toolchain_or_connection_error':'hardware',
 'resource_navigation':'organizational','tutor_usage':'organizational','general_support':'other','out_of_scope':'other'}
STRATEGY = {
 'guided_debugging':'diagnostic_question','provide_verified_resource_then_probe':'explanation',
 'experiential_task_scaffolding':'hint','change_representation_and_reduce_repetition':'explanation',
 'scaffold_before_full_solution':'hint','redirect_to_course':'explanation',
 'explain_with_concrete_example_then_check':'check_understanding','minimum_useful_support':'hint'}
TOPIC = {'general':'general_robotics','button_input':'digital_io','ai_tutor_meta':'general_robotics',
         'arduino_installation':'general_robotics','c_cpp_control_flow':'conditional_statements',
         'robotics_course':'general_robotics'}

def load(path, default):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding='utf-8'))
def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def merge_unique(items, additions, key):
    out=list(items); seen={key(x) for x in out}
    for x in additions:
        k=key(x)
        if k not in seen: out.append(x); seen.add(k)
    return out

def classification(c):
    sig=c.get('understanding_signal','neutral')
    return {
      'intent': INTENT.get(c.get('intent'),'other'), 'topic': TOPIC.get(c.get('topic'), c.get('topic') or 'general_robotics'),
      'subtopic': c.get('topic') or 'general', 'problem_type': PROBLEM.get(c.get('problem_type'),'other'),
      'student_state': 'stuck' if sig=='negative' else ('exploring' if sig=='positive' else 'uncertain'),
      'possible_misconception': c.get('possible_misconception'), 'teacher_attention': bool(c.get('teacher_attention',False)),
      'teacher_attention_reason': c.get('teacher_attention_reason'),
      'response_strategy': STRATEGY.get(c.get('response_strategy'),'hint'),
      'understanding_signal': sig if sig in {'positive','neutral','negative'} else 'neutral',
      'communication_style':'appropriate', 'reconstructed':True, 'reconstruction_source':'legacy-retrospective-v1'}

def evidence(e):
    axes=e.get('axis_evidence',{}) or {}
    out={'evidence_type':e.get('type','neutral'),'reason':'Retrospectively reconstructed from the historical learner turn.',
         'reconstructed':True,'reconstruction_source':'legacy-retrospective-v1'}
    for a in ('understanding','progress','independence'):
        x=axes.get(a,{}) or {}; w=float(x.get('weight',0) or 0)
        out[a+'_value'] = float(x.get('value',0.5)) if w>0 else None
        out[a+'_weight'] = w
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('source', type=Path); ap.add_argument('--apply', action='store_true'); args=ap.parse_args()
    src=args.source.resolve(); data=src/'data'
    courses=load(data/'courses_import.json',[]); users=load(data/'users_import.json',[]); enroll=load(data/'enrollments_import.json',[])
    # Reconcile legacy IDs globally. Same legacy ID across workshops is one account; nickname collisions get a suffix.
    by_legacy={}; used={str(u.get('nickname','')).casefold() for u in load(USERS_FILE,[])}
    for u in users:
        legacy=str(u.get('source_legacy_id','')).strip(); base=str(u.get('nickname') or 'legacy').strip()
        if legacy in by_legacy: continue
        name=base; n=2
        while name.casefold() in used: name=f'{base} [legacy {n}]'; n+=1
        used.add(name.casefold()); by_legacy[legacy]=name
    source_user_to_name={u['user_id']:by_legacy[str(u.get('source_legacy_id','')).strip()] for u in users}
    print(f'Source: {len(courses)} courses, {len(users)} source identities -> {len(by_legacy)} accounts')
    sess=list((data/'sessions').glob('*/*.jsonl')); print(f'Sessions: {len(sess)}')
    counts=Counter()
    if not args.apply:
        for p in sess:
            for line in p.read_text(encoding='utf-8').splitlines():
                x=json.loads(line); counts[x.get('type')]+=1
        print('Events:',dict(counts)); print('DRY RUN only. Re-run with --apply to write runtime data.'); return

    live_courses=load(COURSES_FILE,[])
    course_add=[]
    for c in courses:
        course_add.append({'id':c['id'],'name':c['name'],'registration_code':'HIST-'+c['id'].upper(),
          'registration_open':False,'enabled':True,'historical_import':True,'schedule_dates':c.get('dates',[]),
          'source_invitation':c.get('source_invitation')})
    save(COURSES_FILE, merge_unique(live_courses,course_add,lambda x:str(x.get('id'))))

    live_users=load(USERS_FILE,[]); user_add=[{'nickname':n,'password':'','enabled':False,'historical_import':True,'source_legacy_id':k} for k,n in by_legacy.items()]
    save(USERS_FILE, merge_unique(live_users,user_add,lambda x:str(x.get('nickname','')).casefold()))

    # Source enrollment uses user_id; convert to current nickname/student_id contract.
    enroll_add=[]
    for x in enroll:
        uid=x.get('user_id') or x.get('student_id'); name=source_user_to_name.get(uid)
        if name: enroll_add.append({'student_id':name,'course_id':x['course_id'],'historical_import':True})
    save(ENROLLMENTS_FILE, merge_unique(load(ENROLLMENTS_FILE,[]),enroll_add,lambda x:(x.get('student_id'),x.get('course_id'))))

    # Import sessions in exact current JSONL event naming. Existing same session_id is skipped.
    existing=set()
    for p in SESSIONS_DIR.glob('*/*.jsonl'):
        try:
            first=json.loads(p.read_text(encoding='utf-8').splitlines()[0]); existing.add(first.get('session_id'))
        except Exception: pass
    imported=0
    for sp in sess:
        rows=[json.loads(l) for l in sp.read_text(encoding='utf-8').splitlines() if l.strip()]
        meta=rows[0]; sid=meta['session_id']
        if sid in existing: continue
        name=source_user_to_name[meta['user_id']]; course=meta['course_id']; out=[]
        out.append({'timestamp':'','event_type':'session_started','session_id':sid,'student_id':name,'course_id':course,
                    'started_at':'','historical_import':True,'timestamp_precision':'unknown_within_course_schedule',
                    'course_schedule_dates':meta.get('course_schedule_dates',[]),'source_file':meta.get('source_file'),
                    'source_thread_id':meta.get('source_thread_id')})
        for r in rows[1:]:
            common={'timestamp':'','session_id':sid,'student_id':name,'course_id':course,'tutor_id':'robotics','activity_id':None,
                    'classroom_revision':1,'historical_import':True,'timestamp_precision':'unknown_within_course_schedule',
                    'course_schedule_dates':r.get('course_schedule_dates',[]),'source_turn':r.get('source_turn'),
                    'source_file':r.get('source_file'),'source_thread_id':r.get('source_thread_id')}
            if r.get('type')=='student_message':
                cl=classification(r.get('classification',{})); ev=evidence(r.get('learning_evidence',{}))
                out.append({**common,'event_type':'student_message','message':r.get('message',''),'classification':cl,
                            'learning_evidence':ev,'moderation_flagged':False,'moderation_reconstructed':False})
                update_student_state(name,course,'robotics',cl['topic'],cl['understanding_signal'],ev)
                counts['student_message']+=1
            elif r.get('type')=='tutor_message':
                out.append({**common,'event_type':'tutor_message','answer':r.get('message',''),
                            'response_strategy':'historical_original_response','scaffolding_mode':r.get('scaffolding_mode_reconstructed','balanced'),
                            'scaffolding_reason':'Retrospectively reconstructed; original tutor did not use current adaptive scaffolding.',
                            'original_historical_response':True})
                counts['tutor_message']+=1
        dest=SESSIONS_DIR/course/(sp.stem+'.jsonl'); dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in out)+'\n',encoding='utf-8'); imported+=1
    print(f'Imported {imported} sessions; {counts["student_message"]} student and {counts["tutor_message"]} tutor messages.')
    print('Historical events intentionally have empty timestamps; use dashboard time window "all history" for these courses.')

if __name__=='__main__': main()
