import hashlib,json,sqlite3,sys
from pathlib import Path

ROOT=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007')
phase=sys.argv[1]
rows=[]
with sqlite3.connect(ROOT/'runtime.sqlite3') as db:
    for mode in ('codex','claude'):
        proof=json.loads((ROOT/f'attachment-{mode}-native.json').read_text(encoding='utf-8'))
        metrics,=db.execute('select metrics_json from taskrun where id=?',(proof['runId'],)).fetchone()
        canonical=json.loads(metrics)['canonicalContextSnapshot']['fields']['attachmentContext']
        assert canonical['trustLevel']=='conversation_reference'
        image_refs=[]
        attachments=[]
        for aid in proof['attachmentIds']:
            mid,original,sha,normalized,image_sha=db.execute('select message_id,payload,sha256,image_payload,image_sha256 from messageattachment where id=?',(aid,)).fetchone()
            assert mid==proof['messageId'] and hashlib.sha256(original).hexdigest()==sha
            if normalized:
                assert hashlib.sha256(normalized).hexdigest()==image_sha
                selected=next(entry for entry in canonical['value']['items'] if entry['id']==aid)
                assert selected['imageIncluded'] and selected['imageSha256']==image_sha
                image_refs.append(aid)
            attachments.append({'id':aid,'sha256':sha,'imageSha256':image_sha})
        assert 'base64' not in metrics and '/9j/' not in metrics
        rows.append({'mode':mode,'runId':proof['runId'],'metricsSha256':hashlib.sha256(metrics.encode()).hexdigest(),
                     'attachments':attachments,'imageInputs':image_refs,'context':canonical})
    before=sqlite3.connect(ROOT/'attachments-before.sqlite3')
    preserved={}
    for table in ('message','diff','taskrun'):
        count=0
        for row in before.execute(f'select * from {table}'):
            names=[column[1] for column in before.execute(f'pragma table_info({table})')]
            old=dict(zip(names,row));new=dict(zip(names,db.execute(f'select * from {table} where id=?',(old['id'],)).fetchone()))
            assert old==new,(table,old['id'],[key for key in old if old[key]!=new[key]])
            count+=1
        preserved[table]=count
    before.close()
if phase!='before-restart':
    original=json.loads((ROOT/'attachment-persistence-before-restart.json').read_text(encoding='utf-8'))
    assert rows==original['runs'] and preserved==original['preservedHistory']
report={'phase':phase,'runs':rows,'preservedHistory':preserved,'checks':['immutable original and normalized hashes match','native context references same attachment IDs and hashes','no binary in persisted metrics','pre-existing messages, diffs and TaskRuns unchanged','restart retains exact historical metrics' if phase!='before-restart' else 'captured before restart']}
(ROOT/f'attachment-persistence-{phase}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'phase':phase,'preservedHistory':preserved,'runs':len(rows)}))
