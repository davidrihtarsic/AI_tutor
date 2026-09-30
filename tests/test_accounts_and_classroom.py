import json
from services.tutor_service import get_tutor

def test_course_configuration_can_change(tmp_path, monkeypatch):
    import services.classroom_service as classroom
    monkeypatch.setattr(classroom,'CLASSROOM_CONFIG',tmp_path/'classroom.json'); monkeypatch.setattr(classroom,'CLASSROOM_EVENTS',tmp_path/'events.jsonl')
    tutor=get_tutor('robotics'); activity=tutor['activities'][0]['id'] if tutor['activities'] else None
    before=classroom.get_classroom_config('robotika26')
    after=classroom.update_classroom_config('robotika26','robotics',activity)
    assert after['revision'] >= before['revision']
    assert classroom.get_classroom_config('robotika26')['activity_id']==activity

def test_student_display_history_is_course_specific(tmp_path,monkeypatch):
    import services.storage_service as storage
    monkeypatch.setattr(storage,'SESSIONS_DIR',tmp_path/'sessions'); storage.SESSIONS_DIR.mkdir(parents=True)
    a=storage.create_session('robot01','robotika26'); storage.append_event(a['session_id'],{'event_type':'student_message','session_id':a['session_id'],'student_id':'robot01','course_id':'robotika26','message':'R?'})
    b=storage.create_session('robot01','elektronika26'); storage.append_event(b['session_id'],{'event_type':'student_message','session_id':b['session_id'],'student_id':'robot01','course_id':'elektronika26','message':'E?'})
    hist=storage.student_display_history('robot01','robotika26')
    assert [x['text'] for x in hist]==['R?']

def test_session_path_uses_course_and_short_timestamp(tmp_path,monkeypatch):
    import services.storage_service as storage
    monkeypatch.setattr(storage,'SESSIONS_DIR',tmp_path/'sessions'); storage.SESSIONS_DIR.mkdir(parents=True)
    session=storage.create_session('ana','robotika26'); files=list((tmp_path/'sessions'/'robotika26').glob('*.jsonl'))
    assert len(files)==1 and len(files[0].stem)>=15
    assert storage.get_session_metadata(session['session_id'])['course_id']=='robotika26'

def test_course_enrolment_many_to_many(tmp_path,monkeypatch):
    import services.course_service as courses
    monkeypatch.setattr(courses,'COURSES_FILE',tmp_path/'courses.json'); monkeypatch.setattr(courses,'ENROLLMENTS_FILE',tmp_path/'enrollments.json')
    courses.upsert_course('robotika26','Robotika26','R26'); courses.upsert_course('elektronika26','Elektronika26','E26')
    courses.enroll_student('maja','robotika26'); courses.enroll_student('maja','elektronika26')
    assert {x['id'] for x in courses.courses_for_student('maja')}=={'robotika26','elektronika26'}
    assert courses.registration_course_for_code('R26')['id']=='robotika26'

def test_analytics_course_filter_and_pairing(tmp_path,monkeypatch):
    import services.storage_service as storage
    import services.analytics_service as analytics
    monkeypatch.setattr(storage,'SESSIONS_DIR',tmp_path/'sessions'); storage.SESSIONS_DIR.mkdir(parents=True)
    session=storage.create_session('robot01','robotika26'); sid=session['session_id']
    classification={'topic':'pwm','problem_type':'conceptual','possible_misconception':None}
    storage.append_event(sid,{'event_type':'student_message','session_id':sid,'student_id':'robot01','course_id':'robotika26','tutor_id':'robotics','message':'Kaj je PWM?','classification':classification})
    storage.append_event(sid,{'event_type':'tutor_message','session_id':sid,'student_id':'robot01','course_id':'robotika26','tutor_id':'robotics','answer':'PWM ...'})
    summary=analytics.classroom_summary('robotics',0,'robotika26')
    assert summary['message_count']==1
    assert summary['drilldown']['topics']['pwm'][0]['answer']=='PWM ...'

def test_active_course_and_chat_lock_are_independent_per_course(tmp_path, monkeypatch):
    import services.classroom_service as classroom
    monkeypatch.setattr(classroom, 'CLASSROOM_CONFIG', tmp_path/'classroom.json')
    monkeypatch.setattr(classroom, 'CLASSROOM_EVENTS', tmp_path/'events.jsonl')

    classroom.set_active_course('robotika26')
    assert classroom.get_active_course_id() == 'robotika26'

    classroom.set_chat_enabled('robotika26', False)
    assert classroom.get_classroom_config('robotika26')['chat_enabled'] is False
    assert classroom.get_classroom_config('elektronika26')['chat_enabled'] is True

    classroom.set_active_course('elektronika26')
    assert classroom.get_active_course_id() == 'elektronika26'
    # Switching active course must not silently unlock/alter another course.
    assert classroom.get_classroom_config('robotika26')['chat_enabled'] is False
