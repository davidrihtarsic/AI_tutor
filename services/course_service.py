"""JSON-based course settings and many-to-many student enrolments."""
from __future__ import annotations
import json
from typing import Any
from config import COURSES_FILE, ENROLLMENTS_FILE

def _load(path, default):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding='utf-8'))
def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def load_courses() -> list[dict[str, Any]]:
    data=_load(COURSES_FILE, [])
    if not isinstance(data,list): raise ValueError('data/courses.json mora vsebovati JSON seznam tečajev.')
    return [x for x in data if isinstance(x,dict)]
def load_enrollments() -> list[dict[str,str]]:
    data=_load(ENROLLMENTS_FILE, [])
    if not isinstance(data,list): raise ValueError('data/enrollments.json mora vsebovati JSON seznam vpisov.')
    return [x for x in data if isinstance(x,dict)]
def configured_courses(): return sorted({str(x.get('id','')).strip() for x in load_courses() if str(x.get('id','')).strip()})
def get_course(course_id):
    if not course_id: return None
    return next((x for x in load_courses() if str(x.get('id','')).strip()==course_id.strip()), None)
def registration_course_for_code(code):
    code=code.strip(); return next((x for x in load_courses() if x.get('registration_open',False) and str(x.get('registration_code','')).strip()==code), None)
def upsert_course(course_id, name, registration_code, registration_open=True):
    course_id=course_id.strip(); name=name.strip() or course_id; registration_code=registration_code.strip()
    if not course_id: raise ValueError('Vnesite oznako tečaja.')
    if not registration_code: raise ValueError('Vnesite registracijsko kodo.')
    items=load_courses()
    if any(str(x.get('id','')).strip()!=course_id and str(x.get('registration_code','')).strip()==registration_code for x in items): raise ValueError('Ta registracijska koda je že uporabljena pri drugem tečaju.')
    target=next((x for x in items if str(x.get('id','')).strip()==course_id), None)
    if target is None: target={'id':course_id}; items.append(target)
    target.update({'name':name,'registration_code':registration_code,'registration_open':bool(registration_open),'enabled':target.get('enabled',True)}); _save(COURSES_FILE,items); return target
def set_registration_open(course_id,is_open):
    items=load_courses(); target=next((x for x in items if str(x.get('id','')).strip()==course_id.strip()),None)
    if target is None: raise ValueError('Tečaj ne obstaja.')
    target['registration_open']=bool(is_open); _save(COURSES_FILE,items)
def enroll_student(student_id,course_id):
    items=load_enrollments()
    if not any(x.get('student_id')==student_id and x.get('course_id')==course_id for x in items): items.append({'student_id':student_id,'course_id':course_id}); _save(ENROLLMENTS_FILE,items)
def courses_for_student(student_id):
    ids={x.get('course_id') for x in load_enrollments() if x.get('student_id')==student_id}; return [x for x in load_courses() if x.get('id') in ids and x.get('enabled',True)]
def student_ids_for_course(course_id):
    if not course_id: return None
    return {str(x.get('student_id')) for x in load_enrollments() if x.get('course_id')==course_id}
