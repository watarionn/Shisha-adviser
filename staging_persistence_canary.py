from __future__ import annotations
import hashlib, json, sqlite3
from pathlib import Path
from shisha_advisor_app_v1_3 import load_modules
from shisha_multisession_store_v1_7 import SQLiteMultiSessionStore, now_ts

BASE = Path('/app') if Path('/app/shisha_recommender_v0_8.py').exists() else Path(__file__).resolve().parent
DB = Path('/tmp/shisha/shisha_advisor.db')
PRINCIPAL_ID = 'prn_staging_persistence_canary'
TOKEN_HASH = 'a5b426c9b8b9fc1a64ac59416bc8efcfb89eb0f285997680834536462977e2b6'

def ensure_principal(store):
    with store.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute(
            "INSERT OR IGNORE INTO principals(principal_id,display_name,token_hash,is_active,created_at) VALUES(?,?,?,?,?)",
            (PRINCIPAL_ID, 'Synthetic Staging Persistence Canary', TOKEN_HASH, 1, now_ts())
        )
        con.execute('COMMIT')

def make_state():
    modules = load_modules(BASE)
    rec = modules['recommender']
    dataset = rec.load_dataset(
        BASE/'recommender_flavors_v0_8.csv',
        BASE/'recommender_variants_v0_8.csv',
        BASE/'recommender_scores_v0_8.csv'
    )
    state = modules['orchestrator'].new_state(modules['feedback'])
    state, rr = modules['orchestrator'].process_turn('甘めがいい', state, modules, dataset)
    if not rr.get('recommendation_generated'):
        raise RuntimeError('Canary recommendation was not generated')
    state, sel = modules['orchestrator'].select_recommendation_candidate(state, dataset, 1)
    if sel.get('status') != 'SELECTED':
        raise RuntimeError(f'Canary selection failed: {sel}')
    state, fb = modules['orchestrator'].process_turn('これは好き', state, modules, dataset)
    if not fb.get('profile_updated'):
        raise RuntimeError('Canary feedback did not update profile')
    return state

def summarize(item, status):
    state=item['state']
    liked=state['profile'].get('liked_flavors', [])
    payload={
        'event':'STAGING_PERSISTENCE_CANARY',
        'status':status,
        'session_id':item['session_id'],
        'revision':item['revision'],
        'turn_no':state.get('turn_no'),
        'liked_flavor_ids':liked,
        'state_sha256':hashlib.sha256(json.dumps(state,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
    }
    DB.parent.mkdir(parents=True, exist_ok=True)
    (DB.parent/'staging_persistence_canary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,ensure_ascii=False), flush=True)

store=SQLiteMultiSessionStore(DB)
ensure_principal(store)
sessions=store.list_sessions(PRINCIPAL_ID, limit=10)
if sessions:
    item=store.load_session(PRINCIPAL_ID, sessions[0]['session_id'])
    summarize(item,'EXISTING')
else:
    created=store.create_session(PRINCIPAL_ID, make_state(), request_id='STAGING_PERSISTENCE_CANARY_INIT')
    item=store.load_session(PRINCIPAL_ID, created['session_id'])
    summarize(item,'CREATED')
