import json, subprocess
from pathlib import Path
binary=Path('E:/NodeJs/node_global/node_modules/@anthropic-ai/claude-code/bin/claude.exe')
assert binary.is_file()
short=subprocess.run([str(binary),'--version'],capture_output=True,text=True,timeout=15)
assert short.returncode==0
try:
    subprocess.run([str(binary),'--version','x'*40000],capture_output=True,timeout=15)
except OSError as error:
    result={'binaryExists':True,'shortExitCode':short.returncode,'version':short.stdout.strip(),
            'longArgumentCharacters':40000,'errorClass':type(error).__name__,'errno':error.errno,'winerror':error.winerror}
    assert error.winerror==206 and isinstance(error,FileNotFoundError)
else: raise AssertionError('Expected Windows argv limit')
Path('C:/Users/XCC/AppData/Local/Temp/agenthub-edit-20261009/argv-probe.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
