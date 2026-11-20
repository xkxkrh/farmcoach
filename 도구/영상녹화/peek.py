"""Usage: py peek.py [js-to-run] -> runs JS in the seller tab, prints result, saves screenshot to out/peek.jpg"""
import base64, json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP
HERE = os.path.dirname(os.path.abspath(__file__))
c = CDP(9333, "farmfood.adminplus.co.kr")
c.call("Emulation.setDeviceMetricsOverride", width=1920, height=1080, deviceScaleFactor=1, mobile=False)
if len(sys.argv) > 1:
    code = sys.argv[1]
    if os.path.isfile(code):
        code = open(code, encoding="utf-8").read()
    r = c.js(code, timeout=120)
    print(json.dumps(r, ensure_ascii=False, indent=1) if not isinstance(r, str) else r)
time.sleep(float(os.environ.get("WAIT", "0.8")))
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
shot = c.call("Page.captureScreenshot", format="jpeg", quality=70)
open(os.path.join(HERE, "out", "peek.jpg"), "wb").write(base64.b64decode(shot["data"]))
