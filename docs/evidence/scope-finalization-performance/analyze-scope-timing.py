import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

base=Path(__file__).parent
def stamp(value):
    parsed=datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
report={}
for tag, count in [('original',8),('revised',6),('browser',6)]:
    folder=base/('scope-timing-'+tag)
    proof=json.loads((folder/'acceptance.json').read_text(encoding='utf-8'))
    assert len(proof['snapshots'])==count
    assert all(s['available'] and s['entries']==517 for s in proof['snapshots'])
    with sqlite3.connect((folder/'fresh.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        rows=[]
        for run in proof['runs']:
            state,raw=db.execute('select state,metrics_json from taskrun where id=?',(run['runId'],)).fetchone()
            metrics=json.loads(raw)
            assert state=='completed' and metrics['adapterType']=='scripted_mock'
            assert metrics['taskRunScopeDecision']['status']=='passed'
            assert metrics['completionValidation']['functionalAcceptance']=='not_evaluated'
            entries=metrics['preRunCheckpoint']['scopeBaseline']['entries']
            claim=metrics['scopeFinalizationClaim']['claimedAt']
            decision=metrics['taskRunScopeDecision']['timestamp']
            rows.append({'runId':run['runId'],'seconds':run['seconds'],'finalizationSeconds':(stamp(decision)-stamp(claim)).total_seconds(),'scopeBaselineEntries':len(entries),'scopeBaselineSha256':sha(entries),'completion':metrics['completionValidation']})
        report[tag]={'runs':rows,'totalSnapshots':count,'snapshotSeconds':[s['seconds'] for s in proof['snapshots']],'maxHealthMilliseconds':max(x['milliseconds'] for x in proof['health'])}
for left,right in zip(report['original']['runs'],report['revised']['runs']):
    assert left['scopeBaselineSha256']==right['scopeBaselineSha256']
old=sum(r['seconds'] for r in report['original']['runs'])/2
new=sum(r['seconds'] for r in report['revised']['runs'])/2
old_scope=sum(r['finalizationSeconds'] for r in report['original']['runs'])/2
new_scope=sum(r['finalizationSeconds'] for r in report['revised']['runs'])/2
report['comparison']={'meanTaskSecondsBefore':old,'meanTaskSecondsAfter':new,'taskReductionPercent':(1-new/old)*100,'meanFinalizationSecondsBefore':old_scope,'meanFinalizationSecondsAfter':new_scope,'finalizationReductionPercent':(1-new_scope/old_scope)*100,'boundaries':['Two sequential tasks per version; same host and baseline entry hashes; no general benchmark claim','Browser acceptance ran during regression load; not included in before/after timing comparison','No real provider invocation; ScriptedMock with deliberately simulated Codex failure']}
(base/'scope-timing-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report['comparison']))
