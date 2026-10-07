from pathlib import Path
import subprocess,time,base64,io
from PIL import Image
import zxingcpp

def adb(*args):return subprocess.check_output(['adb',*args],text=True)
adb('shell','wm','size','720x1280');adb('shell','wm','density','320')
adb('install','-r','/tmp/party-android-qa/qa.apk')
adb('shell','am','start','-n','me.jxl.kiosk.partyqa/me.jxl.kiosk.plugins.partymode.PartyQaActivity')
time.sleep(7)
pid=adb('shell','pidof','me.jxl.kiosk.partyqa').strip()
if not pid:raise RuntimeError('Party QA process did not start')
out=Path('dist/qa');out.mkdir(parents=True,exist_ok=True)
for mode in ['main','qrlarge','qrsmall','search','placement','playlists','settings','lyrics','discolyrics','ai','similar','dj','switch','searchswitches','trackbuttons','trackbuttonsoff','menucategories','guestpage']:
 adb('shell','am','broadcast','-a','party.qa.MODE','--es','mode',mode)
 time.sleep(3)
 logs=adb('logcat','--pid='+pid,'-d','-s','PARTY_QA:I','AndroidRuntime:E')
 if 'FATAL EXCEPTION' in logs or f'QA_READY {mode}' not in logs: raise RuntimeError(logs[-15000:])
 png=subprocess.check_output(['adb','exec-out','screencap','-p'])
 (out/f'{mode}.png').write_bytes(png)
 if mode in ['main','guestpage']:
  qrpng=subprocess.check_output(['adb','exec-out','cat',f'/sdcard/Android/data/me.jxl.kiosk.partyqa/files/qr-{mode}.png'])
  (out/f'{mode}-qr-bitmap.png').write_bytes(qrpng)
  expected=logs.split(f'QA_QR_URL {mode} ')[-1].splitlines()[0].strip()
  qr=Image.open(io.BytesIO(qrpng)).convert('RGBA')
  for size in [650,420,320,240]:
   bg=Image.new('RGBA',(size,size),'#090e17');bg.alpha_composite(qr.resize((size,size),Image.Resampling.LANCZOS))
   if not any(code.text==expected for code in zxingcpp.read_barcodes(bg.convert('RGB'))):raise AssertionError((mode,size,'actual Android QR decode failed'))

 image=Image.open(io.BytesIO(png)).resize((360,640));data=io.BytesIO();image.convert('RGB').save(data,format='JPEG',quality=83)
 print(f'QA_IMAGE_{mode}='+base64.b64encode(data.getvalue()).decode())
print('Native Android UI smoke checks passed (mock MA; not a Pi benchmark).')
