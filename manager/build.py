"""불러온 원본(raw) + 내가 프로그램에서 고친 내용(edits)을 합쳐서
셀러 사이트가 읽는 docs/data.json 을 만듭니다."""
import json
import os
import re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(ROOT, "manager", "cache", "raw.json")
EDITS_PATH = os.path.join(ROOT, "manager", "data", "edits.json")
OUT_PATH = os.path.join(ROOT, "docs", "data.json")

DEFAULT_NOTICE = """■ 공지사항 필독 부탁드립니다! ■

1. 입점사이트 안내
ㄴ https://zrr.kr/KBvjLs


2. 발주가이드 안내
ㄴ https://zrr.kr/PbQTJU


3. 문의링크 안내
▶ 발주 / 정산 / CS문의 채널톡
ㄴ http://pf.kakao.com/_AxhRWn

▶ 상품 / MD문의 채널톡
ㄴ http://pf.kakao.com/_UympG"""

GROUP_FIELDS = ["name", "cat", "img", "big", "ship", "jeju", "island", "link", "note"]
OPTION_FIELDS = ["name", "price"]


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def default_edits():
    return {
        "notice": DEFAULT_NOTICE,
        "md": [],              # [{"g": 그룹코드, "o": [옵션코드...], "text": 문구}]
        "hideFarmPrefix": True,  # 옵션명 앞 "(팜)" 숨기기
        "groups": {},          # 그룹코드: {고친 항목}
        "options": {},         # 옵션코드: {고친 항목}
        # 공지사항 아래 바로가기 버튼
        "links": [
            {"label": "입점사이트 안내", "url": "https://zrr.kr/KBvjLs", "color": "blue"},
            {"label": "발주가이드 안내", "url": "https://zrr.kr/PbQTJU", "color": "green"},
            {"label": "발주·정산·CS 문의 채널톡", "url": "http://pf.kakao.com/_AxhRWn", "color": "yellow"},
            {"label": "상품·MD 문의 채널톡", "url": "http://pf.kakao.com/_UympG", "color": "yellow"},
        ],
        # 셀러 사이트에서 바로 틀 수 있는 영상 (파일은 docs/media/ 에 있음)
        "videos": [
            {"title": "발주 방법 가이드 영상", "file": "media/order-guide.mp4"},
        ],
    }


def load_edits():
    e = default_edits()
    e.update(load_json(EDITS_PATH, {}))
    return e


def clean_option_name(name, hide_prefix):
    if hide_prefix:
        name = re.sub(r"^\s*\(팜\)\s*", "", name)
    return re.sub(r"\s+", " ", name).strip()


def merged_group(g, raw_opts, edits):
    """원본 그룹 + 고친 내용 → 최종 그룹 (사이트에 나갈 모양)."""
    ge = edits["groups"].get(g["id"], {})
    out = {"id": g["id"], "date": g["date"]}
    for k in GROUP_FIELDS:
        out[k] = ge[k] if k in ge else g.get(k, "")

    # 사이트에 보이기: 자동이면 '특정 거래처 전용' 그룹은 숨김
    vis = ge.get("visible", "auto")
    out["hidden"] = (vis == "hide") or (vis == "auto" and g.get("restricted"))

    # 품절: 자동이면 관리자 사이트 상태를 따름
    st = ge.get("status", "auto")
    group_soldout = g.get("soldout") if st == "auto" else (st == "soldout")

    opts = []
    for oid in g.get("options", []):
        o = raw_opts.get(oid)
        if not o:
            continue
        oe = edits["options"].get(oid, {})
        if oe.get("hidden"):
            continue
        ost = oe.get("status", "auto")
        o_soldout = o["soldout"] if ost == "auto" else (ost == "soldout")
        if group_soldout:
            o_soldout = True
        opts.append({
            "id": oid,
            "name": clean_option_name(oe.get("name", o["name"]), edits.get("hideFarmPrefix", True)),
            "price": oe.get("price", o["price"]),
            "soldout": o_soldout,
            "tax": o.get("tax", "면세"),
        })
    out["soldout"] = group_soldout or (bool(opts) and all(o["soldout"] for o in opts))
    # 품절 옵션은 셀러에게 보여주지 않음
    out["options"] = [o for o in opts if not o["soldout"]]
    for o in out["options"]:
        o.pop("soldout", None)
    taxes = {o["tax"] for o in out["options"]}
    out["tax"] = taxes.pop() if len(taxes) == 1 else ("혼합" if taxes else "")
    # 원산지 / 제조국: 비고 안의 '원산지 : ...' 줄에서 꺼냄 (직접 고친 값이 있으면 그 값)
    if ge.get("origin"):
        out["origin"] = ge["origin"]
    else:
        m = re.search(r"(?:원산지|제조국|원재료\s*원산지)\s*[:：]\s*([^\n/]+)", out.get("note") or "")
        out["origin"] = m.group(1).strip() if m else ""
    return out


def build(raw=None, edits=None):
    raw = raw if raw is not None else load_json(RAW_PATH, None)
    edits = edits if edits is not None else load_edits()
    if not raw:
        return None
    groups = [merged_group(g, raw["options"], edits) for g in raw["groups"]]
    # 숨김 · 품절 그룹은 셀러 사이트에 아예 안 나감
    visible = [g for g in groups if not g.pop("hidden") and not g.pop("soldout") and g["options"]]
    visible.sort(key=lambda g: g["date"], reverse=True)  # 최신 상품이 맨 위

    by_id = {g["id"]: g for g in visible}
    md = []
    for pick in edits.get("md", []):
        g = by_id.get(pick.get("g"))
        if not g:
            continue
        md.append({"g": g["id"], "o": [o for o in pick.get("o", []) if any(x["id"] == o for x in g["options"])],
                   "text": pick.get("text", "")})

    # 그룹 안 옵션들의 과세여부가 모두 같으면 옵션마다 적지 않음 (파일 가볍게)
    for g in visible:
        if g["tax"] != "혼합":
            for o in g["options"]:
                o.pop("tax", None)

    data = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "synced": raw.get("synced", ""),
        "notice": edits.get("notice", ""),
        "noticeHtml": edits.get("noticeHtml"),  # 서식 있는 공지 (없으면 위 글자를 그대로 씀)
        "links": [l for l in edits.get("links", []) if l.get("label") and l.get("url")],
        "videos": [v for v in edits.get("videos", []) if v.get("file")],
        "categories": raw.get("categories", []),
        "md": md,
        "groups": visible,
    }
    save_json(OUT_PATH, data, compact=True)
    stamp_versions()
    return data


def stamp_versions():
    """index.html 이 app.js 등을 부를 때 '?v=내용지문'을 붙임.
    파일 내용이 바뀌면 지문도 바뀌어서, 셀러 브라우저가 옛날 파일을 쓰지 않고 바로 새 파일을 받음."""
    import hashlib
    site = os.path.dirname(OUT_PATH)
    page = os.path.join(site, "index.html")
    try:
        html = open(page, encoding="utf-8").read()
    except FileNotFoundError:
        return
    new = html
    for name in ("app.css", "app.js", "notice.js"):
        try:
            h = hashlib.md5(open(os.path.join(site, name), "rb").read()).hexdigest()[:8]
        except FileNotFoundError:
            continue
        new = re.sub(r'(["\'])' + re.escape(name) + r'(\?v=[0-9a-f]+)?(["\'])', r"\g<1>%s?v=%s\g<3>" % (name, h), new)
    if new != html:
        with open(page, "w", encoding="utf-8", newline="") as f:
            f.write(new)
