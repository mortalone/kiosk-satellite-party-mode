from pathlib import Path
import subprocess,time,base64,io
from PIL import Image

def adb(*args):return subprocess.check_output(['adb',*args],text=True)
adb('shell','wm','size','720x1280');adb('shell','wm','density','320')
adb('install','-r','/tmp/party-android-qa/qa.apk')
adb('shell','am','start','-n','me.jxl.kiosk.partyqa/me.jxl.kiosk.plugins.partymode.PartyQaActivity')
time.sleep(7)
out=Path('dist/qa');out.mkdir(parents=True,exist_ok=True)
for mode in ['main','search','placement','playlists','settings','lyrics']:
 adb('shell','am','broadcast','-a','party.qa.MODE','--es','mode',mode)
 time.sleep(3)
 logs=adb('logcat','-d','-s','PARTY_QA:I','AndroidRuntime:E')
 if 'FATAL EXCEPTION' in logs or f'QA_READY {mode}' not in logs: raise RuntimeError(logs[-15000:])
 png=subprocess.check_output(['adb','exec-out','screencap','-p'])
 (out/f'{mode}.png').write_bytes(png)
 image=Image.open(io.BytesIO(png)).resize((360,640));data=io.BytesIO();image.convert('RGB').save(data,format='JPEG',quality=83)
 print(f'QA_IMAGE_{mode}='+base64.b64encode(data.getvalue()).decode())
print('Native Android UI smoke checks passed (mock MA; not a Pi benchmark).')
