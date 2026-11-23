"""팜코치 관리 프로그램.

실행하면 내 컴퓨터에서만 열리는 관리 화면(http://127.0.0.1:8765)이 뜹니다.
- 팜코치에서 불러오기 : 관리자 사이트에서 상품 정보를 읽어옴 (읽기만 함)
- 편집 : 이름/비고/품절/공지사항/MD추천 등을 고침
- 사이트에 올리기 : 깃허브에 올려서 셀러 사이트에 반영
추가 설치가 필요 없도록 파이썬 기본 기능만 사용합니다.
"""
import json
import mimetypes
import os
import re
import urllib.parse
import subprocess
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402
import collector  # noqa: E402

ROOT = build.ROOT
HERE = os.path.join(ROOT, "manager")
UI_DIR = os.path.join(HERE, "ui")
SITE_DIR = os.path.join(ROOT, "docs")
CONFIG_PATH = os.path.join(HERE, "config.json")
MEDIA_DIR = os.path.join(SITE_DIR, "media")
MAX_VIDEO = 90 * 1000 * 1000
PORT = 8765

state = {"busy": False, "msg": "", "done": 0, "total": 0, "error": "", "last": ""}
lock = threading.Lock()


def read_version():
    try:
        with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


# 프로그램을 켤 때의 버전을 기억 (파일이 새 버전으로 바뀌어도, 다시 켜기 전까지는 옛 버전으로 동작 중이라는 뜻)
RUNNING_VERSION = read_version()


def load_config():
    return build.load_json(CONFIG_PATH, {})


GIT_ENV = dict(os.environ, GIT_EDITOR="true", GIT_MERGE_AUTOEDIT="no")


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=GIT_ENV)
    return r.returncode, (r.stdout + r.stderr).strip()


def run_sync(user_id, password):
    def progress(msg, done=None, total=None):
        state.update(msg=msg, done=done or 0, total=total or 0)

    try:
        raw = collector.collect(user_id, password, progress)
        raw["synced"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        build.save_json(build.RAW_PATH, raw)
        data = build.build(raw)
        # data["groups"] 는 셀러 사이트에 나가는(판매중) 그룹만 들어 있음
        n_sale = len(data["groups"]) if data else 0
        state.update(msg="불러오기 완료! 그룹 %d개 (사이트에 보이는 판매중 %d개)" % (len(raw["groups"]), n_sale), error="",
                     last=raw["synced"])
    except collector.LoginError as e:
        state.update(error=str(e), msg="")
    except Exception as e:  # 네트워크 오류 등
        traceback.print_exc()
        state.update(error="불러오기 실패: %s" % e, msg="")
    finally:
        state["busy"] = False


# ---------------------------------------------------------------------------
# 올리기 전 자동 받기: 다른 사람이 먼저 올린 내용을 받아 내 내용과 합친 뒤 올림
# ---------------------------------------------------------------------------
EDITS_REL = "manager/data/edits.json"
RAW_REL = "manager/data/raw.json"                    # 나눠 쓰는 상품 원본 → 겹치면 더 최근에 불러온 쪽을 씀
REGEN_REL = ("docs/data.json", "docs/index.html")   # 프로그램이 만들어 내는 파일 → 합친 뒤 다시 만듦
_MISSING = object()


def _merge3(base, theirs, mine, path, conflicts, resolve):
    """세 갈래 합치기. theirs = 다른 사람이 올린 것, mine = 내 것, base = 갈라지기 전."""
    if theirs == mine:
        return theirs
    if theirs == base:
        return mine
    if mine == base:
        return theirs
    if isinstance(theirs, dict) and isinstance(mine, dict) and (base is _MISSING or isinstance(base, dict)):
        b = base if isinstance(base, dict) else {}
        out = {}
        for k in list(theirs.keys()) + [k for k in mine.keys() if k not in theirs] + [k for k in b if k not in theirs and k not in mine]:
            v = _merge3(b.get(k, _MISSING), theirs.get(k, _MISSING), mine.get(k, _MISSING), path + [k], conflicts, resolve)
            if v is not _MISSING:
                out[k] = v
        return out
    conflicts.append(path)                       # 같은 칸을 둘 다 다르게 고침
    return mine if resolve == "mine" else theirs


def _conflict_label(path, raw):
    names = {}
    if raw:
        names.update({g["id"]: g["name"] for g in raw.get("groups", [])})
        names.update({k: o["name"] for k, o in raw.get("options", {}).items()})
    fields = {"name": "이름", "cat": "카테고리", "ship": "배송비", "jeju": "제주", "island": "도서산간", "link": "상세링크",
              "img": "사진", "note": "비고", "origin": "원산지", "visible": "보이기", "status": "판매 상태", "price": "가격",
              "hidden": "숨김"}
    top = path[0] if path else ""
    if top in ("groups", "options") and len(path) >= 2:
        what = "상품" if top == "groups" else "옵션"
        f = fields.get(path[2], path[2]) if len(path) > 2 else "전체"
        return "%s '%s'의 %s" % (what, names.get(path[1], path[1]), f)
    return {"notice": "공지사항", "noticeHtml": "공지사항", "md": "MD추천", "links": "바로가기 버튼",
            "videos": "영상 목록", "hideFarmPrefix": "설정 '(팜) 숨기기'"}.get(top, top)


def _rebase_onto_remote(resolve):
    """내 커밋들을 원격 최신 위로 옮김. 반환: (ok, conflicts[labels], msg)"""
    def raw_at(rev):
        c, t = git("show", "%s:%s" % (rev, RAW_REL))
        try:
            return json.loads(t) if c == 0 else {}
        except ValueError:
            return {}
    mine, theirs = raw_at("HEAD"), raw_at("origin/main")
    latest = mine if mine.get("synced", "") > theirs.get("synced", "") else theirs
    code, out = git("rebase", "--autostash", "origin/main")
    regen = False
    for _ in range(50):
        if code == 0:
            break
        unmerged = [f for f in git("diff", "--name-only", "--diff-filter=U")[1].splitlines() if f.strip()]
        if not unmerged:  # 충돌 없이 멈춤(빈 커밋 등)
            code, out = git("rebase", "--skip") if "nothing to commit" in out or "empty" in out else git("rebase", "--continue")
            continue
        conflicts = []
        for f in unmerged:
            if f == EDITS_REL:
                def stage(n):
                    c, t = git("show", ":%d:%s" % (n, f))
                    try:
                        return json.loads(t) if c == 0 else {}
                    except ValueError:
                        return {}
                # rebase 중: 2번 = 원격(다른 사람), 3번 = 내 커밋
                merged = _merge3(stage(1), stage(2), stage(3), [], conflicts, resolve)
                build.save_json(build.EDITS_PATH, merged)
                git("add", f)
            elif f == RAW_REL:
                def stage_raw(n):
                    c, t = git("show", ":%d:%s" % (n, f))
                    try:
                        return json.loads(t) if c == 0 else {}
                    except ValueError:
                        return {}
                theirs, mine = stage_raw(2), stage_raw(3)
                newer = mine if mine.get("synced", "") > theirs.get("synced", "") else theirs
                build.save_json(build.SHARED_RAW_PATH, newer)
                git("add", f)
                regen = True
            elif f in REGEN_REL:
                git("checkout", "--ours", "--", f)   # 일단 원격 것으로 두고, 끝난 뒤 다시 만듦
                git("add", f)
                regen = True
            else:
                git("rebase", "--abort")
                return False, [], "다른 사람이 올린 파일과 겹쳐서 자동으로 합치지 못했어요: %s\n런처에서 [업데이트]를 먼저 누른 뒤 다시 올려 주세요." % f
        if conflicts and not resolve:
            git("rebase", "--abort")
            raw = build.load_raw()
            labels = []
            for p in conflicts:
                lb = _conflict_label(p, raw)
                if lb not in labels:
                    labels.append(lb)
            return False, labels, "같은 곳을 다른 사람도 고쳤어요."
        code, out = git("rebase", "--continue")
    if code != 0:
        git("rebase", "--abort")
        return False, [], "자동으로 합치지 못했어요:\n" + out[-500:]
    if "autostash" in out.lower() and "conflict" in out.lower():
        return False, [], "받은 내용과 이 PC에서 고치던 프로그램 파일이 겹쳤어요. 개발 담당자에게 알려 주세요."
    # 상품 원본은 줄 단위로 섞지 않고, 더 최근에 불러온 것 하나만 통째로 남김 (예전 상품이 섞여 남지 않게)
    if latest and build.load_json(build.SHARED_RAW_PATH, {}) != latest:
        build.save_json(build.SHARED_RAW_PATH, latest)
        regen = True
    if regen:
        build.build()                               # 합쳐진 내용으로 사이트 데이터 다시 만들기
        git("add", "docs", "manager/data")
        if git("diff", "--cached", "--quiet")[0] != 0:
            git("commit", "-m", "합친 내용으로 사이트 데이터 다시 만들기")
    return True, [], ""


def publish(resolve=None):
    r = _publish(resolve)
    if r.get("ok"):
        build.purge_old_raw()
    return r


def _publish(resolve=None):
    """resolve: None(겹치면 멈추고 물어봄) | 'mine'(겹친 칸은 내 것) | 'theirs'(겹친 칸은 다른 사람 것)"""
    if not os.path.exists(build.OUT_PATH):
        return {"ok": False, "msg": "아직 불러온 상품이 없어요. 먼저 '팜코치에서 불러오기'를 눌러 주세요."}
    git("add", "docs", "manager/data")
    if git("diff", "--cached", "--quiet")[0] != 0:
        code, out = git("commit", "-m", "상품 정보 업데이트 " + datetime.now().strftime("%Y-%m-%d %H:%M"))
        if code != 0:
            return {"ok": False, "msg": "저장(커밋) 실패:\n" + out}
    received = False
    for attempt in range(3):
        code, out = git("fetch", "origin", "main")
        if code != 0:
            return {"ok": False, "msg": "깃허브에 연결하지 못했어요 (인터넷 연결을 확인해 주세요):\n" + out[-400:]}
        behind = git("rev-list", "--count", "HEAD..origin/main")[1].strip()
        ahead = git("rev-list", "--count", "origin/main..HEAD")[1].strip()
        if behind not in ("", "0"):                 # 다른 사람이 먼저 올린 게 있음 → 받아서 합치기
            ok, conflicts, msg = _rebase_onto_remote(resolve)
            if not ok:
                return {"ok": False, "conflict": conflicts, "msg": msg}
            received = True
            ahead = git("rev-list", "--count", "origin/main..HEAD")[1].strip()
        if ahead in ("", "0"):
            return {"ok": True, "received": received,
                    "msg": "다른 사람이 올린 내용을 받아 왔어요. 내 쪽에는 새로 올릴 게 없어요." if received
                    else "바뀐 내용이 없어서 올릴 게 없어요. (사이트는 이미 최신이에요)"}
        code, out = git("push", "origin", "HEAD:main")
        if code == 0:
            return {"ok": True, "received": received,
                    "msg": ("다른 사람이 올린 내용과 합쳐서 " if received else "") + "올리기 완료! 1~2분 뒤 셀러 사이트에 반영돼요."}
        if "rejected" not in out and "fetch first" not in out and "non-fast-forward" not in out:
            return {"ok": False, "msg": "깃허브에 올리기 실패 (인터넷 연결이나 깃허브 로그인을 확인해 주세요):\n" + out[-400:]}
        # 그 사이 누가 또 올림 → 다시 받아서 합치기
    return {"ok": False, "msg": "다른 사람이 계속 올리고 있어서 잠시 뒤 다시 눌러 주세요."}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def serve_file(self, base, rel):
        rel = rel.lstrip("/") or "index.html"
        path = os.path.normpath(os.path.join(base, rel))
        if not path.startswith(os.path.normpath(base)) or not os.path.isfile(path):
            return self.send(404, "not found", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):  # 영상 앞뒤로 넘기기용 (부분 전송)
            size = os.path.getsize(path)
            a, _, b = rng[6:].partition("-")
            start = int(a or 0); end = min(int(b) if b else size - 1, size - 1)
            with open(path, "rb") as f:
                f.seek(start); data = f.read(end - start + 1)
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        with open(path, "rb") as f:
            self.send(200, f.read(), ctype)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/state":
            raw = build.load_raw()
            cfg = load_config()
            return self.send(200, {
                "raw": raw,
                "edits": build.load_edits(),
                "savedId": cfg.get("id", ""),
                "version": RUNNING_VERSION,
                "hasPassword": bool(cfg.get("pw")),
            })
        if p == "/api/progress":
            return self.send(200, dict(state, version=RUNNING_VERSION))
        if p == "/site" or p.startswith("/site/"):
            return self.serve_file(SITE_DIR, p[len("/site"):])
        return self.serve_file(UI_DIR, p)

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/video":
            return self.upload_video()
        try:
            body = self.read_body()
        except json.JSONDecodeError:
            return self.send(400, {"ok": False, "msg": "잘못된 요청"})

        if p == "/api/edits":
            edits = build.default_edits()
            edits.update(body)
            build.save_json(build.EDITS_PATH, edits)
            build.build(edits=edits)
            return self.send(200, {"ok": True})

        if p == "/api/sync":
            cfg = load_config()
            uid = body.get("id") or cfg.get("id")
            pw = body.get("pw") or cfg.get("pw")
            if not uid or not pw:
                return self.send(200, {"ok": False, "needLogin": True})
            if body.get("remember"):
                build.save_json(CONFIG_PATH, {"id": uid, "pw": pw})
            with lock:
                if state["busy"]:
                    return self.send(200, {"ok": True})
                state.update(busy=True, error="", msg="시작하는 중…", done=0, total=0)
            threading.Thread(target=run_sync, args=(uid, pw), daemon=True).start()
            return self.send(200, {"ok": True})

        if p == "/api/forget":
            if os.path.exists(CONFIG_PATH):
                os.remove(CONFIG_PATH)
            return self.send(200, {"ok": True})

        if p == "/api/shutdown":  # 런처가 업데이트 전에 프로그램을 끌 때 사용
            self.send(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        if p == "/api/video-delete":
            rel = body.get("file", "")
            path = os.path.normpath(os.path.join(SITE_DIR, rel))
            if rel.startswith("media/") and path.startswith(MEDIA_DIR) and os.path.isfile(path):
                os.remove(path)
            return self.send(200, {"ok": True})

        if p == "/api/publish":
            resolve = body.get("resolve") if body.get("resolve") in ("mine", "theirs") else None
            with lock:
                return self.send(200, publish(resolve))

        return self.send(404, {"ok": False})

    def upload_video(self):
        """영상 파일 받기 → docs/media/ 에 저장. 깃허브는 한 파일 100MB까지라 90MB로 제한."""
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_VIDEO:
            self.rfile.read(n)
            return self.send(200, {"ok": False, "msg": "영상이 너무 커요 (%.0fMB). 90MB 이하로 줄여서 올려 주세요." % (n / 1e6)})
        name = urllib.parse.unquote(self.headers.get("X-Filename") or "video.mp4")
        base, ext = os.path.splitext(os.path.basename(name))
        if ext.lower() not in (".mp4", ".webm", ".mov", ".m4v"):
            self.rfile.read(n)
            return self.send(200, {"ok": False, "msg": "mp4 영상 파일만 올릴 수 있어요."})
        safe = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", base).strip("-") or "video"
        os.makedirs(MEDIA_DIR, exist_ok=True)
        fn = "%s-%s%s" % (safe[:40], datetime.now().strftime("%m%d%H%M%S"), ext.lower())
        with open(os.path.join(MEDIA_DIR, fn), "wb") as f:
            left = n
            while left:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                f.write(chunk); left -= len(chunk)
        return self.send(200, {"ok": True, "file": "media/" + fn, "size": n})


def main():
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print("이미 켜져 있어요. 브라우저에서 http://127.0.0.1:%d 을 열어 주세요." % PORT)
        webbrowser.open("http://127.0.0.1:%d" % PORT)
        return
    url = "http://127.0.0.1:%d" % PORT
    print("팜코치 관리 프로그램이 켜졌어요:", url)
    print("이 검은 창을 닫으면 프로그램이 꺼져요.")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    server.serve_forever()
    server.server_close()


if __name__ == "__main__":
    main()
