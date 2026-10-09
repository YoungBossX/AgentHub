import hashlib,json,sqlite3,sys
from pathlib import Path

ROOT=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-creation-20261009')
ROOT.mkdir(exist_ok=True)
DB=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/runtime.sqlite3')
TABLES=['workspace','session','message','task','taskrun','diff','messageattachment','agentprofiledraft','agentruntimeconfig']
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=lambda v:hashlib.sha256(v).hexdigest() if isinstance(v,bytes) else str(v)).encode()).hexdigest()
with sqlite3.connect(DB) as db:
    db.row_factory=sqlite3.Row
    active=db.execute("select id,state from taskrun where state in ('created','queued','streaming','applying_changes','collecting_diff','starting_preview')").fetchall()
    assert not active, 'Active runs exist'
    assert not any(json.loads(row['context_json']).get('groupSummary',{}).get('state')=='calling' for row in db.execute('select context_json from message'))
    if sys.argv[1]=='before':
        with sqlite3.connect(ROOT/'before.sqlite3') as backup: db.backup(backup)
        rows={t:{r['id']:digest(dict(r)) for r in db.execute('select * from '+t)} for t in TABLES}
        (ROOT/'history-before.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps({t:len(v) for t,v in rows.items()}))
    else:
        before=json.loads((ROOT/'history-before.json').read_text())
        changes=[]
        with sqlite3.connect(ROOT/'before.sqlite3') as old:
            old.row_factory=sqlite3.Row
            for table,rows in before.items():
                current={r['id']:dict(r) for r in db.execute('select * from '+table)}
                for rid,sha in rows.items():
                    assert rid in current,(table,rid)
                    if digest(current[rid])!=sha:
                        original=dict(old.execute('select * from '+table+' where id=?',(rid,)).fetchone())
                        fields=[k for k in original if original[k]!=current[rid][k]]
                        assert table in {'task','agentruntimeconfig'} and fields==['updated_at'],(table,rid,fields)
                        changes.append({'table':table,'id':rid,'field':'updated_at','before':original['updated_at'],'after':current[rid]['updated_at']})
        report={'passed':True,'phase':sys.argv[1],'preserved':{t:len(v) for t,v in before.items()},'allowedTimestampChanges':changes}
        (ROOT/('history-'+sys.argv[1]+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        if sys.argv[1] in {'before-restart','after-restart'}:
            proof=json.loads((ROOT/'native.json').read_text(encoding='utf-8'))
            preserved={}
            for table,condition,ids in [
                ('agentprofiledraft','id=?',(proof['profile']['id'],)),
                ('message','session_id=?',(proof['session']['id'],)),
                ('task','session_id=?',(proof['session']['id'],)),
                ('taskrun','id=?',(proof['execution']['runId'],)),
                ('diff','id=?',(proof['execution']['diffs'][0]['id'],)),
            ]:
                preserved[table]={r['id']:digest(dict(r)) for r in db.execute('select * from '+table+' where '+condition,ids)}
            source=Path(proof['session']['worktreePath'])/'apps/demo/src/App.tsx'
            value={'rows':preserved,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest()}
            if sys.argv[1]=='after-restart':
                assert value==json.loads((ROOT/'native-restart-before.json').read_text()),'Native profile or evidence changed'
            (ROOT/('native-restart-'+('before' if sys.argv[1]=='before-restart' else 'after')+'.json')).write_text(json.dumps(value,indent=2),encoding='utf-8')
