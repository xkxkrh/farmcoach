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


def load_config():
    return build.load_json(CONFIG_PATH, {})


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def run_sync(user_id, password):
    def progress(msg, done=None, total=None):
        state.update(msg=msg, done=done or 0, total=total or 0)

    try:
        raw = collector.collect(user_id, password, progress)
        raw["synced"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        build.save_json(build.RAW_PATH, raw)
        data = build.build(raw)
        n_sale = sum(1 for g in data["groups"] if not g["soldout"])
        state.update(msg="불러오기 완료! 그룹 %d개 (판매중 %d개)" % (len(data["groups"]), n_sale), error="",
                     last=raw["synced"])
    except collector.LoginError as e:
        state.update(error=str(e), msg="")
    except Exception as e:  # 네트워크 오류 등
        traceback.print_exc()
        state.update(error="불러오기 실패: %s" % e, msg="")
    finally:
        state["busy"] = False


def publish():
    if not os.path.exists(build.OUT_PATH):
        return False, "아직 불러온 상품이 없어요. 먼저 '팜코치에서 불러오기'를 눌러 주세요."
    git("add", "docs", "manager/data")
    code, out = git("diff", "--cached", "--quiet")
    if code == 0:
        return True, "바뀐 내용이 없어서 올릴 게 없어요. (사이트는 이미 최신이에요)"
    msg = "상품 정보 업데이트 " + datetime.now().strftime("%Y-%m-%d %H:%M")
    code, out = git("commit", "-m", msg)
    if code != 0:
        return False, "저장(커밋) 실패:\n" + out
    code, out = git("push")
    if code != 0:
        return False, "깃허브에 올리기 실패 (인터넷 연결이나 깃허브 로그인을 확인해 주세요):\n" + out
    return True, "올리기 완료! 1~2분 뒤 셀러 사이트에 반영돼요."


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
            raw = build.load_json(build.RAW_PATH, None)
            cfg = load_config()
            return self.send(200, {
                "raw": raw,
                "edits": build.load_edits(),
                "savedId": cfg.get("id", ""),
                "version": read_version(),
                "hasPassword": bool(cfg.get("pw")),
            })
        if p == "/api/progress":
            return self.send(200, state)
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
            ok, msg = publish()
            return self.send(200, {"ok": ok, "msg": msg})

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
