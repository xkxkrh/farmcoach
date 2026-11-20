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
    out["options"] = opts
    out["soldout"] = group_soldout or (bool(opts) and all(o["soldout"] for o in opts))
    taxes = {o["tax"] for o in opts}
    out["tax"] = taxes.pop() if len(taxes) == 1 else ("혼합" if taxes else "")
    return out


def build(raw=None, edits=None):
    raw = raw if raw is not None else load_json(RAW_PATH, None)
    edits = edits if edits is not None else load_edits()
    if not raw:
        return None
    groups = [merged_group(g, raw["options"], edits) for g in raw["groups"]]
    visible = [g for g in groups if not g.pop("hidden") and g["options"]]
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
        "categories": raw.get("categories", []),
        "md": md,
        "groups": visible,
    }
    save_json(OUT_PATH, data, compact=True)
    return data
