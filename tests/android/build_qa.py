from pathlib import Path
import os, subprocess, zipfile, sys
root = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'tools'))
from qr_asset import generate
sdk = Path(os.environ['ANDROID_HOME'])
bt = sorted((sdk/'build-tools').glob('*'), key=lambda p: tuple(int(x) for x in p.name.split('.')))[-1]
jar = sdk/'platforms/android-35/android.jar'
out = Path('/tmp/party-android-qa'); out.mkdir(exist_ok=True)
classes = out/'classes'; classes.mkdir(exist_ok=True)
dex = out/'dex'; dex.mkdir(exist_ok=True)
subprocess.run(['javac','--release','8','-cp',str(jar),'-d',str(classes),*map(str,(root/'sdk/src').rglob('*.java')),*map(str,(root/'src').rglob('*.java')),str(root/'tests/android/PartyQaActivity.java'),str(generate(root,out/'qr-asset'))],check=True)
subprocess.run([str(bt/'d8'),'--min-api','26','--lib',str(jar),'--output',str(dex),*map(str,classes.rglob('*.class'))],check=True)
apk=out/'qa.apk'
subprocess.run([str(bt/'aapt2'),'link','-o',str(apk),'-I',str(jar),'--manifest',str(root/'tests/android/AndroidManifest.xml')],check=True)
with zipfile.ZipFile(apk,'a') as z:
 for f in dex.glob('*.dex'): z.write(f,f.name)
key=out/'qa.keystore'
subprocess.run(['keytool','-genkeypair','-keystore',str(key),'-storepass','public-fixture','-keypass','public-fixture','-alias','qa','-keyalg','RSA','-dname','CN=Party QA','-validity','30'],check=True)
subprocess.run([str(bt/'apksigner'),'sign','--ks',str(key),'--ks-pass','pass:public-fixture',str(apk)],check=True)
