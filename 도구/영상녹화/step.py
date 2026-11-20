"""Helpers to drive the seller site. Usage: py step.py upload | click "<text>" | js "<code>" ; saves out/peek.jpg"""
import base64, json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "팜코치_발주서_샘플.xlsx")


def connect():
    c = CDP(9333, "farmfood.adminplus.co.kr")
    c.call("Emulation.setDeviceMetricsOverride", width=1920, height=1080, deviceScaleFactor=1, mobile=False)
    return c


def set_file(c, selector="input[type=file]", path=SAMPLE):
    doc = c.call("DOM.getDocument", depth=-1, pierce=True)
    nid = c.call("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)["nodeId"]
    c.call("DOM.setFileInputFiles", files=[path], nodeId=nid)


def click_text(c, text, scope="button,a,label,[role=button],li,span,div"):
    return c.js("""(()=>{const t=%s;const els=[...document.querySelectorAll(%s)].filter(e=>e.offsetParent&&e.textContent.trim().replace(/\\s+/g,' ')===t);
      const e=els[els.length-1]; if(!e) return 'NOT FOUND'; e.scrollIntoView({block:'center'}); e.click(); return 'clicked '+e.tagName;})()""" % (json.dumps(text), json.dumps(scope)))


def shot(c, name="peek.jpg"):
    s = c.call("Page.captureScreenshot", format="jpeg", quality=70)
    open(os.path.join(HERE, "out", name), "wb").write(base64.b64decode(s["data"]))


if __name__ == "__main__":
    c = connect()
    cmd = sys.argv[1]
    if cmd == "upload":
        set_file(c); print("file set")
    elif cmd == "click":
        print(click_text(c, sys.argv[2]))
    elif cmd == "js":
        r = c.js(sys.argv[2], timeout=120); print(json.dumps(r, ensure_ascii=False, indent=1) if not isinstance(r, str) else r)
    time.sleep(float(os.environ.get("WAIT", "1.5")))
    shot(c)
