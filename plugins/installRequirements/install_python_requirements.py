import os
import log
import subprocess
from pathlib import Path

plugins_path = Path(os.path.abspath(__file__)).parent.parent.absolute()

def pip_install(root, file):
    req_filepath = os.path.join(root, file)
    log.info(f'Found: {req_filepath}')
    p = subprocess.Popen(f'cmd /c pip install -r "{req_filepath}"', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for out in p.stdout:
        log.debug(str(out))
    for err in p.stderr:
        log.error(str(err))

def crawl(_callback):
    log.info(f'Scanning {plugins_path} for requirements')
    for root, dirs, files in os.walk(plugins_path):
        for file in files:
            if file == "requirements.txt":
                _callback(root, file)

crawl(pip_install)