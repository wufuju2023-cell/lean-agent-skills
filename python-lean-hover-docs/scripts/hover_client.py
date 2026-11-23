#!/usr/bin/env python3
"""hover_client.py — 直接向 basedpyright-langserver 要 hover 文本。

用途：在命令行复现 nvim 里「按 K」看到的内容（K 背后就是同一个 LSP 请求），
便于脚本化验证/回归。输出即悬停浮窗里的 Markdown。

用法：
  python3 hover_client.py <server> <file> <line0> <char0> [root]
例：
  python3 hover_client.py basedpyright-langserver lmc/session.py 76 25 .
说明：line0/char0 均从 0 开始；root 是工作区根目录（决定读取哪个 pyrightconfig.json）。
"""
import json
import os
import selectors
import subprocess
import sys
import time


def main() -> int:
    server = sys.argv[1]
    file = os.path.abspath(sys.argv[2])
    line = int(sys.argv[3])
    char = int(sys.argv[4])
    root = os.path.abspath(sys.argv[5]) if len(sys.argv) > 5 else os.path.dirname(file)

    proc = subprocess.Popen(
        [server, "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=root,
    )
    assert proc.stdin and proc.stdout
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    buf = bytearray()
    deadline = time.time() + 180.0

    def send(msg: dict) -> None:
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        proc.stdin.flush()

    def read_msg(timeout: float):
        end = time.time() + timeout
        while True:
            he = buf.find(b"\r\n\r\n")
            if he != -1:
                length = None
                for h in bytes(buf[:he]).split(b"\r\n"):
                    if h.lower().startswith(b"content-length:"):
                        length = int(h.split(b":", 1)[1].strip())
                if length is not None and len(buf) - (he + 4) >= length:
                    body = bytes(buf[he + 4 : he + 4 + length])
                    del buf[: he + 4 + length]
                    return json.loads(body.decode("utf-8"))
            remaining = min(end, deadline) - time.time()
            if remaining <= 0:
                raise TimeoutError("等待 LSP 消息超时")
            for _key, _ev in sel.select(remaining):
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    raise EOFError("服务端提前关闭了 stdout")
                buf.extend(chunk)

    def wait_response(rid: int, timeout: float = 180.0):
        end = time.time() + timeout
        while True:
            msg = read_msg(max(0.1, end - time.time()))
            if "id" in msg and "method" in msg:  # 服务端发起的请求：一律 null 应答
                send({"jsonrpc": "2.0", "id": msg["id"], "result": None})
                continue
            if msg.get("id") == rid:
                return msg

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "processId": None,
            "clientInfo": {"name": "hover-client", "version": "0.1"},
            "rootUri": "file://" + root,
            "workspaceFolders": [{"uri": "file://" + root, "name": os.path.basename(root)}],
            "capabilities": {},
        }})
        wait_response(1)
        send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

        with open(file, encoding="utf-8") as fh:
            text = fh.read()
        uri = "file://" + file
        send({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": uri, "languageId": "python", "version": 1, "text": text}}})

        result = None
        for attempt in range(10):
            rid = 100 + attempt
            send({"jsonrpc": "2.0", "id": rid, "method": "textDocument/hover", "params": {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": char}}})
            result = wait_response(rid).get("result")
            if result:
                break
            time.sleep(1.5)

        contents = (result or {}).get("contents")
        if isinstance(contents, dict) and "value" in contents:
            print(contents["value"])
        else:
            print("（没有悬停结果）", json.dumps(result, ensure_ascii=False))

        send({"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": None})
        try:
            wait_response(3, timeout=10)
        except Exception:
            pass
        send({"jsonrpc": "2.0", "method": "exit", "params": None})
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        return 0
    finally:
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
