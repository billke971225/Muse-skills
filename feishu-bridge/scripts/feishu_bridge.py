#!/usr/bin/env python3
"""Feishu (Lark) DM bridge: WebSocket long connection <-> local inbox/outbox.

Single file, stdlib + lark-oapi. Run with ~/workspace/.venvs/pw/bin/python.

CRITICAL PATCH (do not remove): this VM's outbound traffic must go through the
environment proxy, but the SDK's WS client defaults to proxy=None. We
monkey-patch _ws_connect_kwargs so websockets.connect() picks up the proxy
from the environment (proxy=True => use env vars). Without this, WS connect
fails.

Security iron rules:
- App ID / App Secret live ONLY in state/feishu.json (mode 600).
- Never print secret values: `status` prints present/absent only.
- Never log secrets.

Commands:
    serve            # foreground daemon: WS receive -> inbox ; outbox loop sends
    send --text "x"  # send a test message (uses chat_id from latest inbox msg)
    status           # credentials/owner/process/inbox-outbox counts (no secrets)
"""
import argparse
import json
import logging
import os
import sys
import tempfile
import threading
import time

# --- proxy patch: must run before any WS connect happens ---
import lark_oapi.ws.client as _wsc

_wsc._ws_connect_kwargs = lambda: {"proxy": True}  # noqa: E731

import lark_oapi as lark
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler

BASE = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(BASE, "inbox")
PENDING = os.path.join(BASE, "outbox", "pending")
SENT = os.path.join(BASE, "outbox", "sent")
LOGS = os.path.join(BASE, "logs")
STATE = os.path.join(BASE, "state")
CRED_FILE = os.path.join(STATE, "feishu.json")
OWNER_FILE = os.path.join(STATE, "owner_open_id")
PID_FILE = os.path.join(STATE, "serve.pid")

ACK_TEXT = "收到，正在回复…"

os.makedirs(LOGS, exist_ok=True)  # logging config runs at import time
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS, "serve.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("feishu_bridge")


def ensure_dirs():
    for d in (INBOX, PENDING, SENT, LOGS, STATE):
        os.makedirs(d, exist_ok=True)


def load_creds():
    """Return (app_id, app_secret). Raise if missing."""
    with open(CRED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["app_id"], data["app_secret"]


def build_client(app_id, app_secret):
    return (
        lark.Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(lark.LogLevel.ERROR)
        .build()
    )


def api_send_text(app_id, app_secret, chat_id, text):
    """Send a text message to a p2p chat. Returns True on success."""
    client = build_client(app_id, app_secret)
    req = (
        lark.im.v1.model.CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            lark.im.v1.model.CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": text}, ensure_ascii=False))
            .build()
        )
        .build()
    )
    try:
        resp = client.im.v1.message.create(req)
        if resp.success():
            return True
        log.warning("send failed: code=%s msg=%s", resp.code, resp.msg)
        return False
    except Exception as e:  # noqa: BLE001 - network/SDK errors must not kill serve
        log.warning("send exception: %s", type(e).__name__)
        return False


def atomic_write_json(path, obj):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_owner():
    try:
        with open(OWNER_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def set_owner(open_id):
    fd, tmp = tempfile.mkstemp(dir=STATE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(open_id)
        os.chmod(tmp, 0o600)
        os.replace(tmp, OWNER_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def on_message_receive(data: lark.im.v1.model.P2ImMessageReceiveV1):
    """WS event handler. Real payload lives under data.event (not data.message)."""
    try:
        event = data.event
        msg = event.message
        # 1. only p2p DMs
        if msg.chat_type != "p2p":
            return
        # 2. only text
        if msg.message_type != "text":
            return
        sender_open_id = event.sender.sender_id.open_id
        # 3. owner lock: first DM sender becomes the owner
        owner = get_owner()
        if owner is None:
            set_owner(sender_open_id)
            owner = sender_open_id
            log.info("owner locked")
        if sender_open_id != owner:
            return
        # 4. dedup by inbox file
        message_id = msg.message_id
        inbox_path = os.path.join(INBOX, message_id + ".json")
        if os.path.exists(inbox_path):
            return
        try:
            text = json.loads(msg.content).get("text", "")
        except (ValueError, AttributeError):
            text = ""
        # 5. atomic inbox write (600)
        atomic_write_json(
            inbox_path,
            {
                "message_id": message_id,
                "text": text,
                "from_open_id": sender_open_id,
                "chat_id": msg.chat_id,
                "ts": int(time.time()),
            },
        )
        log.info("inbox: new message stored")
        # 6. instant ack (liveness signal); failure only logged
        try:
            app_id, app_secret = load_creds()
            api_send_text(app_id, app_secret, msg.chat_id, ACK_TEXT)
        except Exception as e:  # noqa: BLE001
            log.warning("ack failed: %s", type(e).__name__)
    except Exception as e:  # noqa: BLE001 - handler must never crash the WS loop
        log.warning("handler exception: %s", type(e).__name__)


def outbox_loop(app_id, app_secret):
    """Every 2s: send pending outbox files, archive to sent/."""
    while True:
        try:
            for name in sorted(os.listdir(PENDING)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(PENDING, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        item = json.load(f)
                    chat_id, text = item["chat_id"], item["text"]
                except (OSError, ValueError, KeyError):
                    continue
                if api_send_text(app_id, app_secret, chat_id, text):
                    atomic_write_json(os.path.join(SENT, name), item)
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    log.info("outbox: sent 1 message")
                time.sleep(1)
        except Exception as e:  # noqa: BLE001
            log.warning("outbox loop exception: %s", type(e).__name__)
        time.sleep(2)


def cmd_serve():
    ensure_dirs()
    app_id, app_secret = load_creds()
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    os.chmod(PID_FILE, 0o600)

    t = threading.Thread(target=outbox_loop, args=(app_id, app_secret), daemon=True)
    t.start()

    handler = (
        EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message_receive)
        .build()
    )
    ws = _wsc.Client(
        app_id, app_secret, event_handler=handler, auto_reconnect=True,
        log_level=lark.LogLevel.ERROR,
    )
    log.info("connecting to feishu WS ...")
    ws.start()  # blocking; auto_reconnect handles drops


def latest_chat_id():
    names = sorted(
        (n for n in os.listdir(INBOX) if n.endswith(".json")),
        key=lambda n: os.path.getmtime(os.path.join(INBOX, n)),
    )
    if not names:
        return None
    with open(os.path.join(INBOX, names[-1]), "r", encoding="utf-8") as f:
        return json.load(f).get("chat_id")


def cmd_send(text):
    ensure_dirs()
    chat_id = latest_chat_id()
    if not chat_id:
        print("ERROR: no inbox message yet; the user must DM the bot first "
              "(bot cannot initiate a conversation).")
        sys.exit(1)
    app_id, app_secret = load_creds()
    ok = api_send_text(app_id, app_secret, chat_id, text)
    print("sent" if ok else "FAILED (see logs/serve.log)")
    sys.exit(0 if ok else 1)


def cmd_status():
    ensure_dirs()
    cred_ok = os.path.exists(CRED_FILE)
    try:
        if cred_ok:
            load_creds()
    except Exception:  # noqa: BLE001
        cred_ok = False
    print("credentials:", "present" if cred_ok else "MISSING")
    owner = get_owner()
    print("owner:", "locked" if owner else "not set")
    alive = False
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        alive = True
    except (OSError, ValueError):
        alive = False
    print("serve:", "running" if alive else "not running")
    print("inbox:", len([n for n in os.listdir(INBOX) if n.endswith(".json")]))
    print("outbox pending:", len([n for n in os.listdir(PENDING) if n.endswith(".json")]))
    print("outbox sent:", len([n for n in os.listdir(SENT) if n.endswith(".json")]))


def main():
    ap = argparse.ArgumentParser(prog="feishu_bridge.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    p_send = sub.add_parser("send")
    p_send.add_argument("--text", required=True)
    sub.add_parser("status")
    args = ap.parse_args()
    if args.cmd == "serve":
        cmd_serve()
    elif args.cmd == "send":
        cmd_send(args.text)
    elif args.cmd == "status":
        cmd_status()


if __name__ == "__main__":
    main()
