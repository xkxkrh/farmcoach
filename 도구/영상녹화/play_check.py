import base64, os, subprocess, sys, threading, time, urllib.request, functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
name, wait = sys.argv[1], float(sys.argv[2])
open(os.path.join(OUT, "play2.html"), "w", encoding="utf-8").write(
    '<!doctype html><body style="margin:0;background:#000"><video id="v" src="%s?r=%d" muted autoplay style="width:1200px"></video>' % (name, time.time()))
class Q(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path.split("?")[0])
        if not rng or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        a, b = rng.replace("bytes=", "").split("-")
        start = int(a or 0); end = int(b) if b else size - 1
        f = open(path, "rb"); f.seek(start)
        import io
        data = f.read(end - start + 1); f.close()
        self.send_response(206)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        return io.BytesIO(data)
srv = ThreadingHTTPServer(("127.0.0.1", 9448), functools.partial(Q, directory=OUT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
p = subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--remote-debugging-port=9336",
                      "--user-data-dir=" + os.path.join(HERE, "profile4"), "--no-first-run", "--window-size=1300,900", "--autoplay-policy=no-user-gesture-required",
                      "http://127.0.0.1:9448/play2.html"], stderr=subprocess.DEVNULL)
for _ in range(50):
    try: urllib.request.urlopen("http://127.0.0.1:9336/json"); break
    except Exception: time.sleep(0.3)
time.sleep(1)
c = CDP(9336, "play2.html")
time.sleep(2)
if len(sys.argv) > 3:
    print("seek:", c.js("new Promise(r=>{const v=document.getElementById('v'); v.pause(); v.onseeked=()=>r(v.currentTime); v.currentTime=%s;})" % sys.argv[3]))
time.sleep(wait)
print(c.js("(()=>{const v=document.getElementById('v'); return {t:v.currentTime, paused:v.paused, dur:v.duration, err:v.error&&v.error.code}})()"))
shot = c.call("Page.captureScreenshot", format="jpeg", quality=80)
open(os.path.join(OUT, "play_check.jpg"), "wb").write(base64.b64decode(shot["data"]))
try: c.call("Browser.close")
except Exception: pass
srv.shutdown()
