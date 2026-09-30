#!/usr/bin/env python3
"""Migrate pre-v1.2 class-based runtime data to course-based storage.

Default is dry-run. Use --apply only after reviewing the plan.
"""
from __future__ import annotations
import argparse, json, re, shutil
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'

def load(path,default): return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
def save(path,data): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def slug(value):
    s=value.strip().lower().replace('č','c').replace('š','s').replace('ž','z')
    s=re.sub(r'[^a-z0-9_-]+','_',s).strip('_'); return s or 'course'
def unique_path(directory, stem):
    p=directory/f'{stem}.jsonl'; n=2
    while p.exists(): p=directory/f'{stem}_{n:02d}.jsonl'; n+=1
    return p

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--apply',action='store_true'); args=ap.parse_args()
    users=load(DATA/'users.json',[]); classes=load(DATA/'classes.json',[])
    class_ids=sorted({str(u.get('class','')).strip() for u in users if str(u.get('class','')).strip()} | {str(c.get('class','')).strip() for c in classes if str(c.get('class','')).strip()})
    mapping={c:slug(c) for c in class_ids}
    courses=[]
    for c in class_ids:
        old=next((x for x in classes if str(x.get('class','')).strip()==c),{})
        courses.append({'id':mapping[c],'name':c,'registration_code':old.get('registration_code',c),'registration_open':bool(old.get('registration_open',False)),'enabled':True})
    enrollments=[{'student_id':u['nickname'],'course_id':mapping[str(u.get('class','')).strip()]} for u in users if u.get('nickname') and str(u.get('class','')).strip() in mapping]
    session_files=sorted((DATA/'sessions').glob('*/*.jsonl')); plans=[]
    for path in session_files:
        events=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
        if not events: continue
        student=str(events[0].get('student_id','')); user=next((u for u in users if u.get('nickname')==student),{})
        course_id=mapping.get(str(user.get('class','')).strip())
        if not course_id:
            print(f'WARNING: session {path} has no course mapping for {student}; skipped'); continue
        started=str(events[0].get('started_at') or events[0].get('timestamp') or '')
        try: dt=datetime.fromisoformat(started.replace('Z','+00:00'))
        except ValueError: dt=datetime.now(timezone.utc)
        plans.append((path,course_id,dt.strftime('%Y-%m-%d_%H%M'),events))
    print('v1.2 course migration plan'); print('Courses:',mapping); print('Enrollments:',len(enrollments)); print('Sessions:',len(plans)); print('Mode:','APPLY' if args.apply else 'DRY-RUN')
    if not args.apply: return
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S'); backup=DATA/'backups'/f'v12_courses_{stamp}'; backup.mkdir(parents=True)
    for name in ['users.json','classes.json']:
        if (DATA/name).exists(): shutil.copy2(DATA/name,backup/name)
    for folder in ['sessions','students','config']:
        if (DATA/folder).exists(): shutil.copytree(DATA/folder,backup/folder,dirs_exist_ok=True)
    save(DATA/'courses.json',courses); save(DATA/'enrollments.json',enrollments)
    save(DATA/'users.json',[{k:v for k,v in u.items() if k!='class'} for u in users])
    # Per-course classroom config: legacy global setting becomes starting config for every migrated course.
    legacy=load(DATA/'config'/'classroom.json',{})
    if 'courses' not in legacy:
        base={k:legacy.get(k) for k in ['tutor_id','activity_id','revision','updated_at']}
        save(DATA/'config'/'classroom.json',{'courses':{c['id']:dict(base) for c in courses}})
    # Student state becomes course-specific using the student's legacy class.
    for path in (DATA/'students').glob('*.json'):
        state=load(path,{}); sid=str(state.get('student_id','')); user=next((u for u in users if u.get('nickname')==sid),{}); cid=mapping.get(str(user.get('class','')).strip())
        if cid and 'courses' not in state:
            state['courses']={cid:{'tutors':state.pop('tutors',{})}}; save(path,state)
    # Rebuild session tree by course and readable short timestamp.
    tmp=DATA/'sessions_v12_tmp'; shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir()
    for old,cid,stem,events in plans:
        outdir=tmp/cid; outdir.mkdir(parents=True,exist_ok=True); out=unique_path(outdir,stem)
        with out.open('w',encoding='utf-8') as h:
            for event in events:
                event['course_id']=cid; h.write(json.dumps(event,ensure_ascii=False)+'\n')
    shutil.rmtree(DATA/'sessions'); tmp.rename(DATA/'sessions'); (DATA/'sessions'/'.gitkeep').touch()
    print('Backup:',backup); print('Migration completed.')
if __name__=='__main__': main()
