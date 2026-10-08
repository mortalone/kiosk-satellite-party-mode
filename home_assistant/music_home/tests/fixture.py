from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import html
ROOT=Path(__file__).resolve().parents[1]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/':data=(ROOT/'tests/fixture.html').read_bytes();kind='text/html'
  elif path=='/music-home-card.js':data=(ROOT/'music-home-card.js').read_bytes();kind='text/javascript'
  elif path.startswith('/cover/'):
   names=['SWEET1','NICE1','SOMMER 2026','DANSKE FAVORITTER','KLASSISK','NATTENS PULS','AFTENLYS','RADIO','RO I HUSET','STJERNESTØV','MAISON','VINYL']
   i=int(path.rsplit('/',1)[1]);palette=[('#faa88d','#694769'),('#b597e5','#3b516e'),('#56c6ce','#147982'),('#7bc77a','#385240'),('#dabe79','#756435'),('#5379b1','#242455')];a,b=palette[i%len(palette)];name=html.escape(names[i%len(names)])
   data=f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs><rect width="400" height="400" fill="url(#g)"/><circle cx="235" cy="165" r="138" fill="#ffffff20"/><circle cx="235" cy="165" r="93" fill="#1118"/><circle cx="235" cy="165" r="25" fill="{a}"/><path d="M0 245Q200 100 400 220L400 400H0" fill="#0003"/><text x="22" y="326" fill="white" font-family="Arial" font-weight="bold" font-size="28">{name}</text><text x="22" y="360" fill="#fffc" font-family="Arial" font-size="15">MUSIC HOME · DEMO</text></svg>'''.encode();kind='image/svg+xml'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
ThreadingHTTPServer(('127.0.0.1',18104),Handler).serve_forever()
