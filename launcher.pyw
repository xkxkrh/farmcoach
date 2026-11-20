"""팜코치 런처 — 관리 프로그램 다운로드/업데이트/실행.

- 이 파일이 farmcoach 폴더 안에 있으면 그 폴더를 씀.
- 이 파일만 따로 있으면 옆에 'farmcoach' 폴더를 만들어 깃허브에서 내려받음.
- 업데이트는 깃허브(xkxkrh/farmcoach)의 최신 내용을 받아옴. 내 컴퓨터에서 고친 내용은 지켜짐.
파이썬 기본 기능(tkinter)만 사용합니다.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import ttk, messagebox

LAUNCHER_VERSION = "1.1.0"
REPO_URL = "https://github.com/xkxkrh/farmcoach.git"
PORT = 8765
APP_URL = "http://127.0.0.1:%d" % PORT

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = HERE if os.path.isfile(os.path.join(HERE, "manager", "app.py")) else os.path.join(HERE, "farmcoach")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# 색 (ZEF 런처 느낌)
BG = "#f3f3f3"; BOX = "#ffffff"; LINE = "#c9c9c9"; GREEN = "#1e7b4f"; ORANGE = "#c2410c"; RED = "#b91c1c"; BLUE = "#2563eb"
FONT = ("Malgun Gothic", 10)


def git(*args, cwd=None, timeout=300):
    r = subprocess.run(["git", *args], cwd=cwd or APP_DIR, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    return r.returncode, (r.stdout + r.stderr).strip()


def has_git():
    try:
        return git("--version", cwd=HERE)[0] == 0
    except (OSError, subprocess.SubprocessError):
        return False


def installed():
    return os.path.isdir(os.path.join(APP_DIR, ".git")) and os.path.isfile(os.path.join(APP_DIR, "manager", "app.py"))


def read(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


def running():
    s = socket.socket()
    s.settimeout(0.4)
    try:
        return s.connect_ex(("127.0.0.1", PORT)) == 0
    finally:
        s.close()


def python_exe():
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.isfile(cand):
            return cand
    return exe


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("팜코치 런처 v" + LAUNCHER_VERSION)
        self.geometry("460x430")
        self.minsize(430, 380)
        self.configure(bg=BG)
        self.busy = False
        self.state_info = {}

        top = tk.Frame(self, bg=BG); top.pack(fill="x", padx=16, pady=(14, 8))
        self.who = tk.Label(top, text="", bg=BG, font=FONT, fg="#333"); self.who.pack(side="left")
        self.btn_check = ttk.Button(top, text="다시 확인", command=self.check); self.btn_check.pack(side="right")

        box = tk.Frame(self, bg=BOX, highlightbackground=LINE, highlightthickness=1); box.pack(fill="x", padx=16)
        tk.Label(box, text="팜코치 관리 프로그램", bg=BOX, font=("Malgun Gothic", 12, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 0))
        self.status = tk.Label(box, text="확인 중…", bg=BOX, font=FONT, fg="#555", anchor="w"); self.status.pack(fill="x", padx=14, pady=(2, 10))
        row = tk.Frame(box, bg=BOX); row.pack(fill="x", padx=14, pady=(0, 14))
        self.btn_update = tk.Button(row, text="업데이트", font=("Malgun Gothic", 11, "bold"), relief="flat", bg="#d6dbe4", fg="#555",
                                    activebackground="#c3cad6", width=12, height=1, command=self.update_app, state="disabled")
        self.btn_update.pack(side="left", padx=(0, 10), ipady=4)
        self.btn_run = tk.Button(row, text="실행", font=("Malgun Gothic", 11), relief="solid", bd=1, bg="#ffffff", fg="#111",
                                 highlightbackground=BLUE, activebackground="#eef3ff", width=12, height=1, command=self.run_app, state="disabled")
        self.btn_run.pack(side="left", ipady=4)
        self.btn_stop = tk.Label(row, text="프로그램 끄기", bg=BOX, fg="#888", font=("Malgun Gothic", 9, "underline"), cursor="hand2")
        self.btn_stop.bind("<Button-1>", lambda e: self.stop_app())

        self.bar = ttk.Progressbar(self, mode="determinate", maximum=100); self.bar.pack(fill="x", padx=16, pady=(14, 8))

        wrap = tk.Frame(self, bg=BOX, highlightbackground=LINE, highlightthickness=1); wrap.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.log_box = tk.Text(wrap, height=10, font=("Consolas", 9), bg=BOX, relief="flat", wrap="word", state="disabled")
        sb = ttk.Scrollbar(wrap, command=self.log_box.yview); self.log_box.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.log_box.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        self.log("팜코치 런처 v%s" % LAUNCHER_VERSION)
        self.log("설치 폴더: %s" % APP_DIR)
        self.after(200, self.check)

    # ---------- 화면 도우미 ----------
    def log(self, msg):
        def put():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, put)

    def set_status(self, text, color="#555"):
        self.after(0, lambda: self.status.configure(text=text, fg=color))

    def set_bar(self, v):
        self.after(0, lambda: self.bar.configure(value=v))

    def set_buttons(self):
        def apply():
            st = self.state_info
            can_update = (not self.busy) and (st.get("behind", 0) > 0 or not st.get("installed") or st.get("need_restart"))
            self.btn_update.configure(state="normal" if can_update else "disabled",
                                      text="설치하기" if not st.get("installed") else "업데이트",
                                      bg=GREEN if can_update else "#d6dbe4", fg="#fff" if can_update else "#555")
            self.btn_run.configure(state="normal" if (st.get("installed") and not self.busy) else "disabled",
                                   text="열기" if st.get("running") else "실행")
            self.btn_check.configure(state="disabled" if self.busy else "normal")
            if st.get("running") and not self.busy:
                self.btn_stop.pack(side="right")
            else:
                self.btn_stop.pack_forget()
        self.after(0, apply)

    def work(self, fn):
        if self.busy:
            return
        self.busy = True
        self.set_buttons()

        def go():
            try:
                fn()
            except Exception as e:  # 예상 못 한 오류도 화면에 보여줌
                self.log("오류: %s" % e)
                self.set_status("문제가 생겼어요. 아래 내용을 확인해 주세요.", RED)
            finally:
                self.busy = False
                self.set_buttons()
        threading.Thread(target=go, daemon=True).start()

    # ---------- 확인 ----------
    def check(self):
        self.work(self._check)

    def _check(self):
        self.set_bar(10)
        cfg = {}
        try:
            cfg = json.loads(read(os.path.join(APP_DIR, "manager", "config.json"), "{}") or "{}")
        except ValueError:
            pass
        uid = cfg.get("id")
        self.after(0, lambda: self.who.configure(text=("관리자 %s 님" % uid) if uid else "관리자 로그인 정보 없음 (프로그램에서 처음 불러올 때 입력)"))
        info = {"installed": installed(), "running": running(), "behind": 0}
        self.log("")
        self.log("--- 최신 버전 확인 중 ---")
        if not has_git():
            info["installed"] = False
            self.state_info = info
            self.set_status("Git 프로그램이 필요해요 (git-scm.com 에서 설치)", RED)
            self.log("Git 이 설치되어 있지 않아요. https://git-scm.com/download/win 에서 설치 후 '다시 확인'을 눌러 주세요.")
            self.set_bar(0)
            return
        if not info["installed"]:
            self.state_info = info
            self.set_status("아직 설치되지 않았어요 → '설치하기'를 눌러 주세요", ORANGE)
            self.log("프로그램이 아직 없어요. 설치하기를 누르면 깃허브에서 내려받아요.")
            self.set_bar(0)
            return
        local_v = read(os.path.join(APP_DIR, "VERSION"), "?")
        self.set_bar(30)
        code, out = git("fetch", "--quiet", "origin", "main", timeout=120)
        if code != 0:
            self.state_info = info
            self.set_status("최신 버전을 확인하지 못했어요 (인터넷 연결 확인) · 현재 %s" % local_v, ORANGE)
            self.log("확인 실패: " + out[:300])
            self.set_bar(0)
            return
        self.set_bar(70)
        rc, rv = git("show", "origin/main:VERSION")
        remote_v = rv.strip() if rc == 0 and rv.strip() else local_v
        behind = git("rev-list", "--count", "HEAD..origin/main")[1].strip()
        info["behind"] = int(behind) if behind.isdigit() else 0
        dirty = git("status", "--porcelain")[1].strip()
        info["local_v"], info["remote_v"] = local_v, remote_v
        info["prog_v"] = self.running_version() if info["running"] else ""
        # 파일은 새 버전인데 켜져 있는 프로그램은 옛 버전 → 다시 켜야 새 기능이 적용됨
        info["need_restart"] = bool(info["running"] and info["prog_v"] != local_v)
        self.state_info = info
        self.log("내 버전: %s / 최신 버전: %s" % (local_v, remote_v))
        if remote_v != local_v:
            self.set_status("새 버전이 있어요 (%s → %s) · 업데이트를 눌러 주세요" % (local_v, remote_v), ORANGE)
            self.log("새 버전이 있어요. 업데이트를 누르면 받아요.")
        elif info["need_restart"]:
            self.set_status("새 버전(%s)을 적용할 수 있어요 · 업데이트를 눌러 주세요" % local_v, ORANGE)
            self.log("켜져 있는 프로그램은 %s 버전이에요. 업데이트를 누르면 %s 버전으로 다시 켜져요." % (info["prog_v"] or "예전", local_v))
        elif info["behind"]:
            self.set_status("최신입니다 (%s) · 다른 곳에서 올린 내용 %d건 받기 가능" % (local_v, info["behind"]), GREEN)
            self.log("프로그램은 최신이에요. 다른 컴퓨터에서 올린 상품/공지 내용 %d건이 있어요." % info["behind"])
        else:
            self.set_status("최신입니다 (%s)" % local_v, GREEN)
            self.log("최신입니다.")
        if dirty:
            self.log("※ 아직 '사이트에 올리기' 하지 않은 내 변경이 있어요. 업데이트해도 지워지지 않아요.")
        self.log("프로그램 상태: %s" % ("켜져 있어요" if info["running"] else "꺼져 있어요"))
        self.set_bar(100)

    # ---------- 설치 / 업데이트 ----------
    def update_app(self):
        self.work(self._update)

    def _update(self):
        self.set_bar(5)
        if not installed():
            self.log("")
            self.log("--- 설치 중 (깃허브에서 내려받기) ---")
            self.set_status("설치 중… 잠시만 기다려 주세요", BLUE)
            if os.path.exists(APP_DIR) and os.listdir(APP_DIR):
                self.log("설치할 폴더에 이미 다른 파일이 있어요: " + APP_DIR)
                self.set_status("설치 폴더가 비어 있지 않아요", RED)
                return
            code, out = git("clone", REPO_URL, APP_DIR, cwd=HERE, timeout=900)
            self.log(out[-800:] or "완료")
            if code != 0:
                self.set_status("설치에 실패했어요", RED)
                return
            self.set_bar(100)
            self.log("설치 완료!")
            self._check()
            return

        was_running = running()
        self.log("")
        self.log("--- 업데이트 중 ---")
        if was_running and self.running_version() and self.running_version() != read(os.path.join(APP_DIR, "VERSION"), ""):
            self.log("켜져 있는 프로그램을 새 버전으로 바꿔요.")
        self.set_status("업데이트 중… 잠시만 기다려 주세요", BLUE)
        if was_running:
            self.log("업데이트를 위해 프로그램을 잠깐 꺼요.")
            self._shutdown()
            if running():
                self.set_status("프로그램을 끄지 못했어요", RED)
                self.log("※ 프로그램이 꺼지지 않아요. 컴퓨터를 다시 켠 뒤 업데이트를 눌러 주세요.")
                return
        self.set_bar(30)
        code, out = git("pull", "--rebase", "--autostash", "origin", "main", timeout=600)
        self.log(out[-1200:] or "완료")
        if code != 0:
            git("rebase", "--abort")
            self.set_status("업데이트 중 문제가 생겼어요 (내 변경과 겹침)", RED)
            self.log("※ 내 컴퓨터에서 고친 내용과 새 내용이 겹쳐요. 관리 프로그램에서 '사이트에 올리기'를 먼저 한 뒤 다시 시도해 주세요.")
            return
        self.set_bar(80)
        self.log("업데이트 완료! (버전 %s)" % read(os.path.join(APP_DIR, "VERSION"), "?"))
        if was_running:
            self.log("프로그램을 다시 켜요. 열려 있던 프로그램 화면은 15초 안에 자동으로 새 화면으로 바뀌어요.")
            self._start(open_browser=False)
        self._check()

    def running_version(self):
        try:
            return json.load(urllib.request.urlopen(APP_URL + "/api/progress", timeout=3)).get("version") or ""
        except Exception:
            return ""

    # ---------- 실행 / 끄기 ----------
    def run_app(self):
        if running():
            webbrowser.open(APP_URL)
            self.log("프로그램 화면을 열었어요.")
            return
        self.work(lambda: self._start(open_browser=True))

    def _start(self, open_browser=True):
        log_path = os.path.join(APP_DIR, "manager", "cache", "app.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        args = [python_exe(), os.path.join(APP_DIR, "manager", "app.py")] + ([] if open_browser else ["--no-browser"])
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        with open(log_path, "a", encoding="utf-8") as lf:
            subprocess.Popen(args, cwd=APP_DIR, stdout=lf, stderr=lf, env=env, creationflags=NO_WINDOW)
        for _ in range(40):
            if running():
                break
            time.sleep(0.25)
        if running():
            self.log("관리 프로그램을 켰어요 → " + APP_URL)
            self.state_info["running"] = True
        else:
            self.log("프로그램을 켜지 못했어요. 기록: " + log_path)
            self.set_status("실행에 실패했어요", RED)

    def _shutdown(self):
        try:
            req = urllib.request.Request(APP_URL + "/api/shutdown", data=b"{}", headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass
        for _ in range(40):
            if not running():
                break
            time.sleep(0.25)
        self.state_info["running"] = running()

    def stop_app(self):
        if not messagebox.askyesno("프로그램 끄기", "관리 프로그램을 끌까요?\n(저장된 내용은 그대로 남아요)"):
            return

        def go():
            self._shutdown()
            self.log("관리 프로그램을 껐어요.")
        self.work(go)


if __name__ == "__main__":
    Launcher().mainloop()
