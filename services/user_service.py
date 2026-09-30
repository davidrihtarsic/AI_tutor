"""Very small JSON-based student account store (trusted-LAN prototype)."""
from __future__ import annotations
import json, shutil
from typing import Any
from config import USERS_EXAMPLE_FILE, USERS_FILE

def ensure_users_file():
    if USERS_FILE.exists(): return
    USERS_FILE.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(USERS_EXAMPLE_FILE,USERS_FILE) if USERS_EXAMPLE_FILE.exists() else USERS_FILE.write_text('[]\n',encoding='utf-8')
def load_users()->list[dict[str,Any]]:
    ensure_users_file(); data=json.loads(USERS_FILE.read_text(encoding='utf-8'))
    if not isinstance(data,list): raise ValueError('data/users.json mora vsebovati JSON seznam uporabnikov.')
    return [x for x in data if isinstance(x,dict)]
def save_users(users): USERS_FILE.write_text(json.dumps(users,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def authenticate_student(nickname,password):
    nickname=nickname.strip(); return next((u for u in load_users() if u.get('nickname')==nickname and u.get('password')==password and u.get('enabled',True)),None)
def get_user(nickname): return next((u for u in load_users() if u.get('nickname')==nickname),None)
def create_student(nickname,password):
    nickname=nickname.strip()
    if not nickname: raise ValueError('Vnesite uporabniško ime.')
    if len(password)<3: raise ValueError('Geslo naj vsebuje vsaj 3 znake.')
    users=load_users()
    if any(str(u.get('nickname','')).strip().casefold()==nickname.casefold() for u in users): raise ValueError('To uporabniško ime že obstaja.')
    user={'nickname':nickname,'password':password,'enabled':True}; users.append(user); save_users(users); return user
