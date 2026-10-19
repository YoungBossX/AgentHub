"""Qualification-only gates; never part of an image, runtime stage or Agent tool."""

CREATE_RELAY = '''
import json,subprocess,sys,time
from pathlib import Path
result=subprocess.run(json.loads(sys.argv[1]),capture_output=True,timeout=10)
if result.returncode:
    sys.stderr.buffer.write(result.stderr); sys.exit(result.returncode)
marker=Path(sys.argv[2]); pending=marker.with_suffix('.pending')
pending.write_bytes(result.stdout); pending.replace(marker)
deadline=time.monotonic()+15
while not Path(sys.argv[3]).exists():
    if time.monotonic()>deadline: sys.exit(78)
    time.sleep(.02)
sys.stdout.buffer.write(result.stdout)
'''

# The container exec really runs while the test's API worker waits for its
# response. Only a fixed qualification probe is delayed, not target code.
RUNNING_PROBE = '''
import sys,time
from pathlib import Path
Path('/work/.agenthub-interruption-probe').write_text(sys.argv[1])
time.sleep(120)
raise AssertionError('qualification probe was not interrupted')
'''
