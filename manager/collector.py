"""팜코치B2B(adminplus) 관리자 사이트에서 상품 정보를 읽어오는 부분.

읽기만 합니다. 관리자 사이트의 내용은 절대 바꾸지 않습니다.
원가(pcost)는 가져오지 않습니다.
"""
import html
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

BASE = "https://farmfood.adminplus.co.kr"

CATEGORIES = [
    {"code": "001", "name": "농산물"},
    {"code": "002", "name": "축산물"},
    {"code": "003", "name": "수산물"},
    {"code": "004", "name": "김치/반찬"},
    {"code": "005", "name": "가공식품"},
]
CATE_BY_NAME = {"농산물": "001", "축산물": "002", "수산물": "003", "김치/반찬류": "004", "가공식품": "005"}


class LoginError(Exception):
    pass


class Session:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.opener.addheaders = [("User-Agent", "Mozilla/5.0 (farmcoach-manager)")]

    def get(self, path, params=None):
        url = BASE + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        with self.opener.open(url, timeout=60) as r:
            return r.read().decode("utf-8", "replace")

    def post(self, path, data):
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(BASE + path, data=body, headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        with self.opener.open(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace").strip()

    def login(self, user_id, password):
        self.get("/admin-app/")  # 쿠키 받기
        res = self.post("/admin-app/login.chk.php", {"admid": user_id, "admpwd": password})
        if res == "ok":
            return
        if res == "show_captcha":
            raise LoginError("로그인 보안문자가 떴어요. 팜코치 관리자 사이트에 한 번 직접 로그인한 뒤 다시 눌러 주세요.")
        if res == "expired":
            raise LoginError("관리자 사이트 사용기간이 만료됐다고 나와요.")
        raise LoginError("로그인 실패: " + (res[:200] or "아이디/비밀번호를 확인해 주세요."))

    def api_json(self, actpage, params):
        q = {"mod": "product/api", "actpage": actpage, "proc": "json"}
        q.update(params)
        text = self.get("/admin/", q)
        if text.strip() == "logoff":
            raise LoginError("로그인이 풀렸어요. 다시 불러오기를 눌러 주세요.")
        return json.loads(text)


# ---------- 글자 정리 도우미 ----------

class _Text(HTMLParser):
    """HTML을 사람이 읽는 글자로 바꿉니다 (줄바꿈 유지)."""
    BREAK = {"br", "p", "div", "tr", "li", "table", "h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BREAK:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append("  ")

    def handle_data(self, data):
        self.out.append(data)


def html_to_text(s):
    p = _Text()
    p.feed((s or "").replace("\r", ""))
    p.close()
    t = "".join(p.out).replace("\xa0", " ")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"[ \t]{3,}", "  ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def clean_spaces(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ---------- 상품 설명 나누기 ----------

URL_RE = re.compile(r"https?://[^\s<>\"']+")


def parse_description(pcontent, ldesc):
    """상품 설명에서 배송비 / 제주 / 도서산간 / 상세페이지 링크 / 비고를 나눕니다."""
    text = html_to_text(pcontent)
    ship = jeju = island = link = ""

    m = re.search(r"<기본\s*배송비>\s*(.*?)\s*(?=<도서산간|제주도?\s*:|$)", text, re.S)
    if m:
        ship = clean_spaces(m.group(1).replace("\n", " / ")).strip(" /")
        text = text.replace(m.group(0), "\n")
    text = re.sub(r"<도서산간\s*추가\s*배송비>", "\n", text)

    m = re.search(r"제주(?:도)?\s*[:：]\s*([^\n]*?)(?=도서산간\s*[:：]|\n|$)", text)
    if m:
        jeju = m.group(1).strip()
        text = text.replace(m.group(0), "\n", 1)
    m = re.search(r"도서산간\s*[:：]\s*([^\n]*)", text)
    if m:
        island = m.group(1).strip()
        text = text.replace(m.group(0), "\n", 1)

    # "상세페이지 링크 :", "상세페이지다운 :", "상세페이지 다운 :", "상세링크 :" 등 여러 모양
    m = re.search(r"상세\s*(?:페이지)?\s*(?:링크|다운로드|다운|주소)?\s*[:：]?\s*(https?://\S+)", text)
    if m:
        link = m.group(1).strip()
        text = text.replace(m.group(0), "\n", 1)

    rest = re.sub(r"\n{3,}", "\n\n", text).strip()
    note_parts = [p for p in [(ldesc or "").strip(), rest] if p]
    note = "\n\n".join(note_parts)
    return {"ship": ship, "jeju": jeju, "island": island, "link": link, "note": note}


# ---------- 상품그룹 상세 화면 읽기 ----------

class _Form(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = []  # (name, value, type, checked)
        self._select = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("name"):
            self.fields.append((a["name"], a.get("value", ""), (a.get("type") or "text").lower(), "checked" in a))
        elif tag == "select":
            self._select = a.get("name")
        elif tag == "option" and self._select and "selected" in a:
            self.fields.append((self._select, a.get("value", ""), "select", True))

    def handle_endtag(self, tag):
        if tag == "select":
            self._select = None


def parse_group_form(page):
    f = _Form()
    f.feed(page)
    f.close()
    pstate = None
    adpcodes, pcate, pname, ldesc = [], [], "", ""
    smode, partners = "show", 0
    for name, value, typ, checked in f.fields:
        if name == "pstate" and typ == "radio" and checked:
            pstate = value
        elif name == "supplies_biz_smode":
            smode = value
        elif name == "supplies_bzidx[]":
            partners += 1
        elif name == "adpcode[]":
            adpcodes.append(value)
        elif name == "pcate[]":
            pcate.append(value)
        elif name == "pname" and not pname:
            pname = value
        elif name == "ldesc":
            ldesc = value

    def textarea(name):
        # 상품 설명 칸은 HTML이 그대로 들어있고 <기본 배송비> 같은 글자만 &lt; 로 바뀌어 있음
        m = re.search(r'<textarea[^>]*name=["\']' + re.escape(name) + r'["\'][^>]*>(.*?)</textarea>', page, re.S)
        return m.group(1) if m else ""

    if not ldesc:
        ldesc = html_to_text(textarea("ldesc"))
    return {
        "pstate": pstate,
        # 특정 거래처에게만 보이게 설정된 그룹
        "restricted": smode == "show" and partners > 0,
        "options": adpcodes,
        "cate": pcate[0][:3] if pcate else "",
        "name": pname,
        "ldesc": ldesc,
        "pcontent": textarea("pcontent"),
    }


# ---------- 배송비설정 읽기 ----------

def _won(v):
    try:
        return int(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0


def describe_policy(fields):
    """배송비 조건 화면의 값으로 '3,000원 (50,000원 이상 무료)' 같은 글을 만듭니다."""
    one, many = {}, {}
    for name, value, typ, checked in fields:
        if typ in ("radio", "checkbox"):
            if checked:
                one[name] = value
        elif name.endswith("[]"):
            many.setdefault(name, []).append(value)
        else:
            one.setdefault(name, value)
    kind = one.get("dlvsgrp", "")
    unit = {"price": "원", "qty": "개", "weight": one.get("display_unit") or "kg"}.get(kind, "")
    mins, amts = many.get("ordamtmin[]", []), many.get("orddlvamt[]", [])
    ship = ""
    if kind == "free":
        ship = "무료"
    elif kind == "fix":
        fee = _won(one.get("dlvsfixcharge"))
        ship = "무료" if fee == 0 else "{:,}원".format(fee)
    elif kind in ("price", "qty", "weight") and amts:
        first = _won(amts[0])
        ship = "무료" if first == 0 else "{:,}원".format(first)
        if one.get("ordamtmax_loop") == "1" and len(mins) > 1 and _won(mins[1]):
            ship += " ({:,}{}마다 {:,}원씩)".format(_won(mins[1]), unit, first)
        elif len(amts) > 1 and _won(amts[-1]) == 0 and len(mins) > 1 and _won(mins[-1]):
            ship += " ({:,}{} 이상 무료)".format(_won(mins[-1]), unit)
    extra = one.get("dlvsgrpusearea") == "1"
    jeju = "{:,}원".format(_won(one.get("dlvaddjeju"))) if extra and _won(one.get("dlvaddjeju")) else ""
    island = "{:,}원".format(_won(one.get("dlvadddsangan"))) if extra and _won(one.get("dlvadddsangan")) else ""
    return {"ship": ship, "jeju": jeju, "island": island}


def collect_policies(s, needed):
    """배송비설정 목록(한 쪽에 20개씩)을 끝까지 넘겨 보고, 상품에 쓰인 정책만 자세히 읽습니다."""
    by_name, page = {}, 1
    while page <= 100:
        text = s.get("/admin/", {"mod": "config/proc", "actpage": "dlv.grp.list.new.list.proc", "page": page})
        rows = re.findall(r'class="ox-dlv-code">(\d+)</td>.*?class="ox-dlv-subject-text">([^<]*)</span>', text, re.S)
        new = [(i, n) for i, n in rows if html.unescape(n).strip() not in by_name]
        if not new:  # 마지막 쪽을 넘기면 같은 내용이 반복됨
            break
        for idx, name in new:
            by_name[html.unescape(name).strip()] = idx
        page += 1

    def one(name):
        f = _Form()
        f.feed(s.get("/admin/config/dlv_shipgrp.form.html.php", {"idx": by_name[name]}))
        return name, describe_policy(f.fields)

    names = [n for n in needed if n in by_name]
    with ThreadPoolExecutor(max_workers=5) as ex:
        return dict(ex.map(one, names))


# ---------- 목록 읽기 ----------

def _all_rows(s, actpage, extra=None, rows=1000):
    out, page = [], 1
    while True:
        params = {"page": page, "rows": rows, "sidx": "regdate", "sord": "desc"}
        if extra:
            params.update(extra)
        data = s.api_json(actpage, params)
        got = data.get("rows") or []
        out.extend(got)
        if len(got) < rows:
            return out
        page += 1


def _option_name(pname_html):
    m = re.search(r"<div style='margin-left:0px'>(.*)</div>", pname_html or "", re.S)
    inner = m.group(1) if m else (pname_html or "")
    remote = "제주/도서산간 불가" in inner
    inner = re.sub(r"<span class='icon[^']*'[^>]*>.*?</span>", " ", inner, flags=re.S)
    return clean_spaces(strip_tags(inner)), remote


def _group_list_info(pname_html):
    thumb = big = ""
    m = re.search(r"<img src='([^']+)'", pname_html or "")
    if m:
        thumb = m.group(1)
    m = re.search(r'preViewLayer\(this,\s*"([^"]+)"', pname_html or "")
    if m:
        big = m.group(1).replace("\\/", "/")
    if "noimage" in thumb:
        thumb = big = ""
    return clean_spaces(strip_tags(pname_html)), thumb, big


def collect(user_id, password, progress=lambda msg, done=None, total=None: None):
    s = Session()
    progress("팜코치 관리자 사이트에 로그인하는 중…")
    s.login(user_id, password)

    progress("상품(옵션) 목록 읽는 중…")
    prows = _all_rows(s, "prt.list.list.api")
    onsale = {r["pcode"] for r in _all_rows(s, "prt.list.list.api", {"pstate": "1"})}
    taxable = {r["pcode"] for r in _all_rows(s, "prt.list.list.api", {"taxation": "1"})}
    options = {}
    for r in prows:
        name, remote = _option_name(r.get("pname"))
        try:
            price = int(float(r.get("price") or 0))
        except ValueError:
            price = 0
        options[r["pcode"]] = {
            "id": r["pcode"],
            "name": name,
            "price": price,
            "soldout": r["pcode"] not in onsale,
            "tax": "과세" if r["pcode"] in taxable else "면세",
            "remote_no": remote,
            "ship_grp": strip_tags(r.get("dlv_shipping_grp")),
        }

    progress("배송비설정 읽는 중…")
    try:
        policies = collect_policies(s, {o["ship_grp"] for o in options.values() if o["ship_grp"]})
    except Exception:  # 배송비설정을 못 읽어도 나머지는 계속
        policies = {}

    progress("상품그룹 목록 읽는 중…")
    grows = _all_rows(s, "prt.grp.list.list.api")

    def detail(row):
        page = s.get("/admin/", {"mod": "product", "actpage": "prt.grp.form", "pcode": row["pcode"], "embed": "1"})
        return row, parse_group_form(page)

    groups = []
    total = len(grows)
    done = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        for row, form in ex.map(detail, grows):
            done += 1
            progress("상품그룹 상세 읽는 중… (%d/%d)" % (done, total), done, total)
            list_name, thumb, big = _group_list_info(row.get("pname"))
            cate = form["cate"] or CATE_BY_NAME.get(strip_tags(row.get("cate")), "")
            desc = parse_description(form["pcontent"], form["ldesc"])
            # 설명에 배송비가 없으면 배송비설정(옵션에 연결된 정책)에서 채움
            opts = [options[o] for o in form["options"] if o in options]
            pols = {o["ship_grp"] for o in opts}
            pol = policies.get(pols.pop()) if len(pols) == 1 else None
            if pol:
                for k in ("ship", "jeju", "island"):
                    if not desc[k]:
                        desc[k] = pol[k]
            if opts and all(o["remote_no"] for o in opts):
                desc["jeju"] = desc["jeju"] or "불가"
                desc["island"] = desc["island"] or "불가"
            groups.append({
                "id": row["pcode"],
                "name": form["name"] or list_name,
                "cat": cate,
                "date": (row.get("regdate") or "")[:16],
                "img": thumb,
                "big": big,
                "soldout": form["pstate"] == "0",
                "restricted": form["restricted"],
                "options": [o for o in form["options"] if o in options],
                **desc,
            })

    used = {o for g in groups for o in g["options"]}
    return {
        "groups": groups,
        "options": {k: v for k, v in options.items() if k in used},
        "categories": CATEGORIES,
    }
