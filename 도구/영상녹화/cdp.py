"""Tiny Chrome DevTools Protocol client using only the Python standard library."""
import base64, json, os, socket, struct, threading, urllib.request, queue


class WS:
    def __init__(self, url):
        assert url.startswith("ws://")
        hostport, path = url[5:].split("/", 1)
        host, port = hostport.split(":")
        self.s = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (path, hostport, key)).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        self.rest = buf.split(b"\r\n\r\n", 1)[1]
        self.lock = threading.Lock()

    def _recv(self, n):
        while len(self.rest) < n:
            chunk = self.s.recv(1 << 20)
            if not chunk:
                raise ConnectionError("closed")
            self.rest += chunk
        out, self.rest = self.rest[:n], self.rest[n:]
        return out

    def send(self, text):
        data = text.encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126); hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127); hdr += struct.pack(">Q", n)
        mask = os.urandom(4)
        hdr += mask
        with self.lock:
            self.s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        msg = b""
        while True:
            b1, b2 = self._recv(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv(8))[0]
            payload = self._recv(n)
            op = b1 & 0x0F
            if op == 9:  # ping
                continue
            msg += payload
            if b1 & 0x80:
                return msg.decode("utf-8", "replace")


class CDP:
    def __init__(self, port, target_url_contains=None):
        tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % port))
        page = [t for t in tabs if t["type"] == "page" and (not target_url_contains or target_url_contains in t["url"])][0]
        self.ws = WS(page["webSocketDebuggerUrl"])
        self.id = 0
        self.pending = {}
        self.events = queue.Queue()
        self.handlers = {}
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                m = json.loads(self.ws.recv())
            except Exception:
                return
            if "id" in m and m["id"] in self.pending:
                self.pending.pop(m["id"]).put(m)
            elif "method" in m:
                h = self.handlers.get(m["method"])
                if h:
                    h(m["params"])

    def call(self, method, timeout=60, **params):
        self.id += 1
        q = queue.Queue()
        self.pending[self.id] = q
        self.ws.send(json.dumps({"id": self.id, "method": method, "params": params}))
        r = q.get(timeout=timeout)
        if "error" in r:
            raise RuntimeError(r["error"])
        return r.get("result", {})

    def js(self, expr, timeout=60):
        r = self.call("Runtime.evaluate", timeout=timeout, expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError("JS error: %s | %s" % (d.get("exception", {}).get("description", d.get("text")), expr[:200]))
        return r.get("result", {}).get("value")
