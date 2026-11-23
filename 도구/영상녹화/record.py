"""팜코치 발주 가이드 영상 녹화.
- 실제 주문/결제/충전 신청 버튼은 절대 누르지 않음 (가리키기만 함).
- 결과: out/order-guide.mp4
Usage: py record.py [--dry]   (--dry: 녹화 없이 장면만 실행)
"""
import base64, json, os, shutil, sys, threading, time, urllib.request, zipfile, re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from xml.sax.saxutils import escape
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import CDP
import fixmp4

PDF_IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slides")  # extract_slides.py 로 꺼낸 PDF 사진
OUT = os.path.join(HERE, "out"); FR = os.path.join(OUT, "frames2")
SAMPLE = os.path.join(HERE, "팜코치_발주서.xlsx")
W, H = 1920, 1080
DRY = "--dry" in sys.argv
PRODUCT = os.environ.get("PRODUCT", "(팜)조생귤 5kg 로얄과 (S)")
SEARCH = os.environ.get("SEARCH", "조생귤 5kg 로얄과")
BASE = "https://farmfood.adminplus.co.kr/partner-app/"

# ---------------------------------------------------------------- sample order file
def make_sample():
    src = zipfile.ZipFile(os.path.join(HERE, "order_template.xlsx"))
    vals = ['박새로이', '010-1234-5678', '박새로이', '010-1234-5678', '02841', '서울특별시 성북구 보문로 140',
            PRODUCT, '1', '', '', '문 앞에 놓아주세요']
    sh = src.read('xl/worksheets/sheet1.xml').decode()
    m = re.search(r'<row r="2"[^>]*>.*?</row>', sh, re.S)
    tag = re.match(r'<row[^>]*>', m.group(0)).group(0)
    cells = ''.join('<c r="%s2" t="inlineStr"><is><t>%s</t></is></c>' % (c, escape(v)) for c, v in zip('ABCDEFGHIJK', vals) if v)
    sh = sh.replace(m.group(0), tag + cells + '</row>')
    out = zipfile.ZipFile(SAMPLE, 'w', zipfile.ZIP_DEFLATED)
    for n in src.namelist():
        out.writestr(n, sh if n == 'xl/worksheets/sheet1.xml' else src.read(n))
    out.close()

# ---------------------------------------------------------------- browser helpers
c = CDP(9333, "farmfood.adminplus.co.kr")
c.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
OVERLAY = open(os.path.join(HERE, "overlay.js"), encoding="utf-8").read()

def js(code, timeout=60):
    return c.js(code, timeout=timeout)

def ensure_overlay():
    js(OVERLAY)

def S(t): time.sleep(t)

def cap(chip, text): js("G.cap(%s,%s)" % (json.dumps(chip), json.dumps(text)))

def find_expr(text, nth=0): return "G.find(%s,%d)" % (json.dumps(text), nth)

def box_text(text, label=None, pad=6, nth=0):
    return js("G.box(G.rect(%s,%d),%s)" % (find_expr(text, nth), pad, json.dumps(label)))

def box_sel(sel, label=None, pad=6, nth=0):
    return js("G.box(G.rect(G.q(%s,%d),%d),%s)" % (json.dumps(sel), nth, pad, json.dumps(label)))

def box_xywh(x, y, w, h, label=None):
    return js("G.box({x:%d,y:%d,w:%d,h:%d},%s)" % (x, y, w, h, json.dumps(label)))

def point_text(text, nth=0, wait=0.9):
    ok = js("G.moveTo(%s)" % find_expr(text, nth)); S(wait); return ok

def point_sel(sel, nth=0, wait=0.9):
    ok = js("G.moveTo(G.q(%s,%d))" % (json.dumps(sel), nth)); S(wait); return ok

def click_text(text, nth=0, after=1.2):
    """포인터를 옮긴 뒤 클릭. (주문/결제 버튼에는 쓰지 않음)"""
    assert text not in ("주문서 생성하기", "결제하기", "선택건 결제하기"), "never click " + text
    point_text(text, nth)
    js("G.pulse()"); S(0.25)
    r = js("(()=>{const e=%s; if(!e) return 'NOT FOUND'; e.click(); return 'ok'})()" % find_expr(text, nth))
    if r != "ok":
        raise RuntimeError("click failed: " + text)
    S(after)

def clear(): js("G.clear()")

def type_into(sel, text, nth=0, per=0.09):
    js("(()=>{const e=G.q(%s,%d); e.focus(); if(e.select) e.select(); return 1})()" % (json.dumps(sel), nth))
    for ch in text:
        c.call("Input.insertText", text=ch); S(per)

def img_data(name):
    return "data:image/jpeg;base64," + base64.b64encode(open(os.path.join(PDF_IMG, name), "rb").read()).decode()

def slide(name, chip, text, boxes=(), tag="실제 화면 예시", hold=5.5, img_w=1900):
    """PDF 캡처 화면을 보여주는 장면. boxes: (x,y,w,h,label) in image pixels."""
    k = 1920 / img_w
    js("G.ptrShow(false)"); clear()
    js("G.slide(%s,1,%s)" % (json.dumps(img_data(name)), json.dumps(tag)))
    cap(chip, text); S(1.0)
    for (x, y, w, h, label) in boxes:
        box_xywh(x * k, y * k, w * k, h * k, label); S(0.9)
    S(hold)
    clear(); js("G.slideOff()"); js("G.ptrShow(true)"); S(0.5)

def go_menu(parent, child):
    """왼쪽 메뉴: 부모 펼치고 자식 클릭."""
    if not js("!!%s" % find_expr(child)):
        click_text(parent, after=0.8)
    click_text(child, after=1.8)
    ensure_overlay()

# ---------------------------------------------------------------- scenes
def scenes():
    js("(()=>{const a=document.getElementById('g-root'); a&&a.remove(); const b=document.getElementById('g-style'); b&&b.remove(); window.G=null; return 1})()")
    ensure_overlay()
    js("G.capOff();G.clear();G.slideOff();G.cardOff();G.move(1300,700)")
    # 첫 화면: 상품리스트
    js("location.hash='#/product'"); S(2)
    js("[...document.querySelectorAll('button,a,span')].filter(b=>b.offsetParent&&b.textContent.trim()==='닫기').forEach(b=>b.click())"); S(0.6)
    ensure_overlay()
    js("window.scrollTo(0,0)")

    # 0. 제목
    js("G.ptrShow(false)")
    js("G.card(%s)" % json.dumps('<div class="logo"><span>🌱</span>팜코치 B2B</div><h1>발주 방법 가이드</h1>\n      <h2>엑셀 대량발주부터 예치금 충전 · 결제까지 한 번에!</h2>\n      <ol><li>엑셀 업로드</li><li>내용 확인 → 제품 매칭 → 주문서 생성</li><li>예치금 충전 (충전하기 → 입금)</li><li>결제 대기에서 결제하기</li><li>주문리스트에서 \'주문접수\' 확인</li></ol>'))
    S(7)
    js("G.cardOff()"); S(0.8)

    # 1. 로그인 (PDF)
    slide("p01_obj4.jpg", "시작", "팜코치 발주 사이트에서 <em>협력업체 회원가입</em> 후 <em>로그인</em>해요",
          boxes=[(769, 483, 380, 50, "로그인"), (850, 548, 96, 22, "회원가입")], tag="로그인 화면", hold=3.5, img_w=1918)

    # 2. 상품리스트 + 상단 잔액
    cap("상품 보기", "로그인하면 <em>상품리스트</em>가 나와요. 카테고리별로 상품과 공급가를 볼 수 있어요")
    js("G.move(700,180)"); S(1)
    box_text("전체보기", None, 6); box_text("가공식품", None, 6); S(0.2)
    point_text("농산물", 1, 1.0); S(2.5); clear()
    cap("꼭 확인", "오른쪽 위에서 <em>예치금 · 적립금 · 결제대기</em>를 확인해요. 예치금이 없으면 결제가 안 돼요!")
    box_sel("div[class*=balance], .ox-top-bal, header + div div", None, 6)  # may not exist -> fallback below
    r = js("(()=>{const e=G.find('결제대기 : 0 건')||[...document.querySelectorAll('*')].find(x=>x.offsetParent&&/^예치금 : .*예치금미입금/.test(x.textContent.trim().replace(/\\s+/g,' '))&&x.children.length<12); if(!e) return null; let p=e; while(p.parentElement && p.parentElement.getBoundingClientRect().width<700) p=p.parentElement; return G.rect(p,6)})()")
    clear()
    if r: js("G.box(%s,null)" % json.dumps(r)); js("G.move(%d,%d)" % (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2 + 10))
    S(4.5); clear()

    # 3. 대량 주문입력(엑셀)
    cap("1단계", "왼쪽 메뉴에서 <em>주문입력 → 대량 주문입력(엑셀)</em>을 눌러요")
    go_menu("주문입력", "대량 주문입력(엑셀)")
    S(0.5)
    cap("1단계", "주문이 1~2건이면 위의 <em>단건 주문입력</em>으로 해도 돼요")
    box_text("단건 주문입력", None, 4); point_text("단건 주문입력", 0, 1.0); S(2.2); clear()
    cap("1단계", "처음이라면 <em>양식다운로드</em>로 엑셀 양식을 받아서 주문 정보를 적어요")
    box_text("양식다운로드", None, 6); point_text("양식다운로드"); S(3); clear()
    cap("1단계", "다 적은 엑셀 파일을 <em>업로드 파일 선택</em>으로 올려요 (끌어다 놓아도 돼요)")
    box_text("업로드 파일 선택", None, 6); point_text("업로드 파일 선택"); js("G.pulse()"); S(0.6)
    doc = c.call("DOM.getDocument", depth=-1, pierce=True)
    nid = c.call("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="input[type=file]")["nodeId"]
    c.call("DOM.setFileInputFiles", files=[SAMPLE], nodeId=nid)
    S(1.2); clear(); ensure_overlay()
    box_text("팜코치_발주서.xlsx", "올린 파일", 8); S(2.5); clear()
    cap("1단계", "<em>다음: 엑셀 내용 확인</em>을 눌러요")
    click_text("다음: 엑셀 내용 확인", after=2.5); ensure_overlay()

    # 4. 내용 확인
    cap("2단계", "올린 주문의 <em>건수와 내용</em>(주문자 · 받는 분 · 주소 · 상품 · 수량)이 맞는지 꼭 확인해요")
    r = js("G.rect(G.q('table'),8)")
    if r: js("G.box(%s,'미리보기')" % json.dumps(r)); js("G.move(%d,%d)" % (r["x"] + 400, r["y"] + r["h"] - 20))
    S(4.5); clear()
    cap("2단계", "문제가 없으면 <em>주문제품 매칭하기</em>를 눌러요")
    click_text("주문제품 매칭하기", after=3); ensure_overlay()

    # 5. 제품 매칭
    cap("3단계", "엑셀에 적은 상품명을 <em>실제 판매 상품</em>과 연결해요")
    box_text(PRODUCT, "엑셀 상품명", 8); S(3); clear()
    cap("3단계", "오른쪽 칸에 상품명을 검색하고, 목록에서 <em>맞는 상품</em>을 골라요")
    point_sel("input[placeholder*='제품명 또는 코드']"); js("G.pulse()")
    type_into("input[placeholder*='제품명 또는 코드']", SEARCH, per=0.12); S(1.8)
    pick = js("(()=>{const b=[...document.querySelectorAll('li button')].filter(e=>e.offsetParent).find(e=>e.textContent.trim().startsWith(%s)" % json.dumps(PRODUCT) + "); if(!b) return null; return G.rect(b,4)})()")
    if pick:
        js("G.box(%s,null)" % json.dumps(pick)); js("G.move(%d,%d)" % (pick["x"] + 200, pick["y"] + pick["h"] / 2)); S(1.4)
        js("G.pulse()"); S(0.2)
        js("[...document.querySelectorAll('li button')].filter(e=>e.offsetParent).find(e=>e.textContent.trim().startsWith(%s)" % json.dumps(PRODUCT) + ").click()")
        S(1.6); clear()
    ensure_overlay()
    cap("3단계", "연결된 상품과 <em>수량</em>을 확인해요. (엑셀 수량 × 여기 수량만큼 주문돼요)")
    r = js("(()=>{const i=[...document.querySelectorAll('input')].filter(e=>e.offsetParent&&e.type==='text'&&/^\\d+$/.test(e.value)).pop(); return i?G.rect(i,6):null})()")
    if r: js("G.box(%s,'수량')" % json.dumps(r)); js("G.move(%d,%d)" % (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2))
    S(3.5); clear()
    cap("3단계", "안내를 읽고 <em>위 내용을 확인하였습니다</em>에 체크해요")
    point_text("위 내용을 확인하였습니다"); js("G.pulse()")
    js("(()=>{const cb=[...document.querySelectorAll('input[type=checkbox]')].filter(e=>e.offsetParent).pop(); if(cb && !cb.checked) cb.click(); return 1})()")
    S(2)
    cap("3단계", "마지막으로 <em>주문서 생성하기</em>를 누르면 주문이 들어가요<small>※ 영상에서는 누르지 않았어요</small>")
    box_text("주문서 생성하기", "누르기", 8); point_text("주문서 생성하기"); S(4.5); clear()

    # 6. 결제대기 (PDF)
    slide("p06_obj30.jpg", "4단계", "주문서를 만들면 <em>결제 대기</em>에 주문이 생겨요. 아직 결제 전이라 <em>출고되지 않아요!</em>",
          boxes=[(1468, 68, 405, 36, "결제대기 1건"), (247, 444, 1626, 50, "방금 올린 주문")], tag="주문 후 화면 예시", hold=4.5, img_w=1900)

    # 7. 예치금 충전
    cap("5단계", "결제하려면 먼저 예치금을 넣어요. <em>예치금 → 예치금 충전</em>")
    go_menu("예치금", "예치금 충전"); S(0.5)
    cap("5단계", "<em>예치금 충전하기</em>를 눌러요")
    click_text("예치금 충전하기", after=1.6); ensure_overlay()
    cap("5단계", "충전할 <em>금액</em>을 적어요")
    point_sel("input[name=payamount]"); type_into("input[name=payamount]", "100000", per=0.12)
    js("(()=>{const e=G.q('input[name=payamount]'); e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true})); return 1})()")
    S(1.5)
    cap("5단계", "<em>입금할 계좌</em>를 골라요")
    point_sel("select[name=accountnumber]"); js("G.pulse()")
    js("(()=>{const s=G.q('select[name=accountnumber]'); const o=[...s.options].find(o=>o.value); if(o){s.value=o.value; s.dispatchEvent(new Event('change',{bubbles:true}));} if(window.jQuery) jQuery(s).trigger('change'); return 1})()")
    S(2)
    cap("5단계", "<em>입금자명</em>을 적어요. 띄어쓰기 포함 <em>9자리까지만</em> 인식돼요!")
    point_sel("input[name=accountname]"); type_into("input[name=accountname]", "팜코치상회", per=0.15)
    box_sel("input[name=accountname]", "9자리까지", 6); S(3.5); clear()
    cap("5단계", "<em>결제하기</em>를 누른 뒤 안내된 계좌로 입금해요. 꼭 <em>충전하기 → 입금</em> 순서로!<small>※ 영상에서는 누르지 않았어요</small>")
    box_text("결제하기", "누르기", 8); point_text("결제하기"); S(5); clear()
    click_text("창닫기", after=1.2); ensure_overlay()

    # 8. 입금 확인 (PDF)
    slide("p09_obj39.jpg", "6단계", "입금이 확인되면 <em>예치금 현황</em>과 오른쪽 위에 금액이 들어와요",
          boxes=[(1460, 68, 430, 36, "예치금"), (248, 378, 1642, 46, "충전 내역")], tag="입금 후 화면 예시", hold=4, img_w=1918)

    # 9. 결제
    cap("7단계", "이제 결제해요. <em>결제 → 결제 대기</em>")
    go_menu("결제", "결제 대기"); S(1.2)
    slide("p10_obj43.jpg", "7단계", "결제할 주문에 <em>체크</em>하고 <em>선택건 결제하기</em>를 눌러요",
          boxes=[(268, 452, 34, 36, "체크"), (1745, 356, 131, 34, "선택건 결제하기")], tag="결제 화면 예시", hold=4, img_w=1902)
    slide("p11_obj47.jpg", "8단계", "금액을 확인하고 <em>결제하기</em>! 적립금이 있으면 같이 쓸 수 있어요",
          boxes=[(813, 307, 214, 37, "예치금 사용"), (1185, 681, 112, 37, "결제하기")], tag="결제 화면 예시", hold=4, img_w=1917)

    # 10. 주문리스트
    cap("9단계", "<em>주문리스트 → 전체주문</em>에서 내 주문을 확인해요")
    go_menu("주문리스트", "전체주문"); S(1.5)
    slide("p12_obj51.jpg", "9단계", "결제까지 끝나면 주문상태가 <em>'주문접수'</em>로 바뀌어요. 이제 출고 준비 시작!",
          boxes=[(1647, 355, 84, 50, "주문접수")], tag="결제 후 화면 예시", hold=4, img_w=1916)

    # 11. 마무리
    js("G.capOff();G.ptrShow(false)")
    js("G.card(%s)" % json.dumps('<div class="logo"><span>🌱</span>팜코치 B2B</div><h1 style="font-size:66px">꼭 기억하세요!</h1>\n      <ul><li>예치금은 <b>충전하기 → 입금</b> 순서로 (입금자명 <b>9자리까지</b>)</li>\n      <li>주문서를 만든 뒤 <b>결제까지 해야</b> 출고돼요</li>\n      <li>품절 · 공지는 <b>팜코치 오픈톡방</b>에서 안내해요</li>\n      <li>궁금한 점은 <b>팜코치 B2B CS 채널톡</b>으로 문의해 주세요</li></ul>\n      <div class="g-foot">CS 채널톡 pf.kakao.com/_AxhRWn · 오픈톡방 open.kakao.com/o/gA5kL9Rg</div>'))
    S(8)

# ---------------------------------------------------------------- capture + encode
frames = []; result = {}

class Srv(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.path = self.path.split("?")[0]
        if self.path == "/enc.html": body, ct = open(os.path.join(HERE, "enc2.html"), "rb").read(), "text/html"
        elif self.path == "/frames.json": body, ct = json.dumps(frames).encode(), "application/json"
        elif self.path.startswith("/f/"): body, ct = open(os.path.join(FR, self.path[3:]), "rb").read(), "image/jpeg"
        else: self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        n = int(self.headers["Content-Length"]); open(os.path.join(OUT, "order-guide.mp4"), "wb").write(self.rfile.read(n))
        result["size"] = n; self.send_response(200); self.end_headers()


def encode():
    srv = ThreadingHTTPServer(("127.0.0.1", 9446), Srv)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:9333/json/new?http://127.0.0.1:9446/enc.html?r=%d" % time.time(), method="PUT")).read()
    S(1.5)
    e = CDP(9333, "9446/enc.html")
    e.call("Network.enable"); e.call("Network.setCacheDisabled", cacheDisabled=True)
    e.call("Page.bringToFront")
    print("encode:", e.js("run()", timeout=900))
    for _ in range(120):
        if result: break
        S(0.5)
    secs = fixmp4.fix(os.path.join(OUT, "order-guide.mp4"))
    import remux  # 앞뒤로 넘기기(탐색)가 잘 되는 일반 MP4로 변환 → 이 파일을 docs/media/order-guide.mp4 로 복사
    remux.remux(os.path.join(OUT, "order-guide.mp4"), os.path.join(OUT, "order-guide-final.mp4"))
    print("완성:", os.path.join(OUT, "order-guide-final.mp4"))
    print("video:", result, "seconds:", secs)
    e.call("Page.close"); srv.shutdown()


def main():
    if "--encode-only" in sys.argv:
        frames.extend(json.load(open(os.path.join(OUT, "frames2.json")))); encode(); return
    make_sample()
    if DRY:
        scenes(); print("dry run done"); return
    shutil.rmtree(FR, ignore_errors=True); os.makedirs(FR)
    t0 = [None]
    def on_frame(p):
        c.ws.send(json.dumps({"id": 0, "method": "Page.screencastFrameAck", "params": {"sessionId": p["sessionId"]}}))
        ts = p["metadata"]["timestamp"]
        if t0[0] is None: t0[0] = ts
        fn = "%05d.jpg" % len(frames)
        open(os.path.join(FR, fn), "wb").write(base64.b64decode(p["data"]))
        frames.append([round(ts - t0[0], 3), fn])
    c.handlers["Page.screencastFrame"] = on_frame
    c.call("Page.bringToFront")
    c.call("Page.startScreencast", format="jpeg", quality=88, maxWidth=W, maxHeight=H)
    try:
        scenes()
    finally:
        S(0.5); c.call("Page.stopScreencast"); S(0.5)
    print("frames:", len(frames), "seconds:", frames[-1][0]); json.dump(frames, open(os.path.join(OUT,"frames2.json"),"w"))
    encode()
    c.call("Page.bringToFront")

if __name__ == "__main__":
    main()
